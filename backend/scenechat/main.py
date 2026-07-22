"""SceneChat FastAPI application."""

import asyncio
import json
import mimetypes
import random
import resource
from collections import Counter
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Annotated

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from scenechat import __version__
from scenechat.config import (
    MODELDECK_PROTOCOL_CONTRACT,
    MODELDECK_REQUIRED_CAPABILITIES,
    ROOT,
    Settings,
    get_settings,
)
from scenechat.detection import create_detector
from scenechat.detection.prompt_learning import plan_prompt_learning
from scenechat.models import (
    AppState,
    Detection,
    HealthStatus,
    PromptLearningOutcome,
    SceneAnalysis,
)
from scenechat.replay import ReplayRegistry
from scenechat.services.analysis import AnalysisBusy, AnalysisService
from scenechat.services.camera import CameraService, CameraUnavailable, discover_camera_devices
from scenechat.services.runtime import shutdown_requested
from scenechat.services.state import StateStore
from scenechat.vision import ModelDeckProvider, MockVisionProvider, ReplayVisionProvider
from scenechat.vision.base import ProviderStatus


FRONTEND = ROOT / "frontend"
PROMPTABLE_DETECTOR_BACKENDS = {"auto", "yoloe", "yoloworld"}


class AnalyseRequest(BaseModel):
    question: str


class ModeRequest(BaseModel):
    mode: str


class ProviderRequest(BaseModel):
    provider: str


class CameraRequest(BaseModel):
    device: int = Field(default=0, ge=0, le=32)


class DetectorModelRequest(BaseModel):
    model: str = Field(min_length=1, max_length=64)


class DetectorPromptRequest(BaseModel):
    prompts: list[str] = Field(min_length=1, max_length=20)
    auto_update: bool


class AutoAnalyseRequest(BaseModel):
    enabled: bool
    interval_seconds: float = Field(default=20, ge=20, le=60)
    questions: list[str] | None = Field(default=None, min_length=1, max_length=20)


class ReplayRequest(BaseModel):
    scenario: str


def _public_mode(mode: str, detector_backend: str = "replay") -> str:
    if detector_backend == "none":
        return {
            "live": "Live scene description",
            "detector-only": "Live camera only",
            "mock": "Prepared demonstration",
            "replay": "Prepared demonstration",
            "development": "Prepared demonstration",
        }[mode]
    return {
        "live": "Combined",
        "detector-only": "Detector only",
        "mock": "Prepared demonstration",
        "replay": "Prepared demonstration",
        "development": "Prepared demonstration",
    }[mode]


def _detections_for_mode(
    mode: str, detector_backend: str, prepared: list[Detection]
) -> list[Detection]:
    if detector_backend == "none" and mode in {"live", "detector-only"}:
        return []
    return list(prepared)


def _load_questions() -> list[str]:
    return json.loads((ROOT / "prompts" / "curated_questions.json").read_text("utf-8"))


def _select_automatic_question(questions: list[str], current: str) -> str:
    """Randomly choose a curated question, avoiding an immediate repeat."""
    candidates = [question for question in questions if question != current]
    if not candidates:
        candidates = list(questions)
    if not candidates:
        raise ValueError("At least one curated question is required")
    return random.choice(candidates)


async def _set_detector_prompts(app: FastAPI, prompts: list[str]) -> None:
    try:
        await run_in_threadpool(app.state.camera.set_detector_prompts, prompts)
    except (CameraUnavailable, RuntimeError, ValueError) as exc:
        await app.state.state_store.mutate(
            lambda state: setattr(state, "staff_error", "Detector prompts could not be updated.")
        )
        raise HTTPException(503, "Detector prompts could not be updated") from exc


def _empty_prompt_learning_outcome() -> PromptLearningOutcome:
    return PromptLearningOutcome()


def _same_analysis(state: AppState, analysis: SceneAnalysis) -> bool:
    return (
        _is_current_analysis(state, analysis)
        and not state.privacy_screen
    )


def _is_current_analysis(state: AppState, analysis: SceneAnalysis) -> bool:
    return (
        state.scene_analysis is not None
        and state.scene_analysis.generated_at == analysis.generated_at
    )


async def _learn_detector_prompts_from_analysis(
    app: FastAPI, configured: Settings, analysis: SceneAnalysis
) -> PromptLearningOutcome:
    if configured.detector_backend not in PROMPTABLE_DETECTOR_BACKENDS:
        return _empty_prompt_learning_outcome()

    async with app.state.detector_prompt_lock:
        state = await app.state.state_store.snapshot()
        plan = plan_prompt_learning(
            state.detector_prompt_baseline,
            state.detector_learned_prompts,
            analysis.objects,
            has_safety_notes=False,
        )
        rejection_reasons = Counter(analysis.prompt_rejection_reasons)
        rejection_reasons.update(plan.outcome.rejection_reasons)
        outcome = plan.outcome.model_copy(
            update={
                "rejected_count": sum(rejection_reasons.values()),
                "rejection_reasons": dict(rejection_reasons),
            }
        )

        def sanitise_current(app_state: AppState) -> None:
            if _is_current_analysis(app_state, analysis):
                app_state.scene_analysis.objects = plan.safe_objects

        await app.state.state_store.mutate(sanitise_current)
        state = await app.state.state_store.snapshot()
        if not state.detector_prompt_auto_update or not _same_analysis(state, analysis):
            return _empty_prompt_learning_outcome()

        prompts_changed = plan.prompts != state.detector_prompts
        if prompts_changed:
            try:
                await _set_detector_prompts(app, plan.prompts)
            except HTTPException:
                return _empty_prompt_learning_outcome()

        learning_applied = False

        def apply_learning(app_state: AppState) -> None:
            nonlocal learning_applied
            if not _same_analysis(app_state, analysis):
                return
            reasons = Counter(app_state.detector_prompt_rejection_reasons)
            reasons.update(outcome.rejection_reasons)
            app_state.detector_prompts = plan.prompts
            app_state.detector_learned_prompts = plan.learned_prompts
            app_state.detector_prompt_safety_rejections += (
                outcome.rejected_count
            )
            app_state.detector_prompt_rejection_reasons = dict(reasons)
            app_state.detector_prompt_capacity_skips += (
                plan.outcome.capacity_skipped_count
            )
            if app_state.scene_analysis is not None:
                app_state.scene_analysis.objects = plan.safe_objects
            app_state.staff_error = None
            learning_applied = True

        await app.state.state_store.mutate(apply_learning)
        if not learning_applied:
            current = await app.state.state_store.snapshot()
            if prompts_changed:
                with suppress(HTTPException):
                    await _set_detector_prompts(app, current.detector_prompts)
            return _empty_prompt_learning_outcome()
        return outcome


def _degrade_modeldeck_state(state: AppState, detector_backend: str) -> None:
    state.internal_mode = "detector-only"
    state.mode = "Live camera only" if detector_backend == "none" else "Detector only"


def _apply_provider_status(
    state: AppState,
    provider_name: str,
    status: ProviderStatus,
    detector_backend: str,
    *,
    invalidate: bool,
) -> None:
    if invalidate:
        state.generation += 1
        state.analysis_in_progress = False
    state.provider = provider_name
    state.provider_available = status.available
    state.provider_status_code = status.code
    state.provider_status_message = status.message
    state.staff_error = None if status.available else status.message
    if provider_name == "modeldeck" and not status.available:
        _degrade_modeldeck_state(state, detector_backend)


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        registry = ReplayRegistry()
        scenario = registry.get(configured.replay_scenario)
        curated_questions = _load_questions()
        initial_provider = {
            "mock": "mock",
            "replay": "replay",
        }.get(configured.scenechat_mode, configured.model_provider)
        modeldeck = ModelDeckProvider(
            configured.modeldeck_url,
            configured.modeldeck_model,
            configured.vision_request_timeout_seconds,
            max_tokens=configured.vision_max_tokens,
            analysis_max_edge=configured.vision_analysis_max_edge,
        )
        providers = {
            "modeldeck": modeldeck,
            "mock": MockVisionProvider(),
            "replay": ReplayVisionProvider(scenario.responses),
            "fallback": ReplayVisionProvider(scenario.responses, name="fallback"),
        }
        initial_status = await providers[initial_provider].health()
        initial_mode = configured.scenechat_mode
        initial_public_mode = _public_mode(initial_mode, configured.detector_backend)
        if initial_provider == "modeldeck" and not initial_status.available:
            initial_mode = "detector-only"
            initial_public_mode = _public_mode(initial_mode, configured.detector_backend)
        state = StateStore(
            AppState(
                mode=initial_public_mode,
                internal_mode=initial_mode,
                provider=initial_provider,
                provider_available=initial_status.available,
                provider_status_code=initial_status.code,
                provider_status_message=initial_status.message,
                staff_error=None if initial_status.available else initial_status.message,
                camera_device=configured.camera_device,
                detector_backend=configured.detector_backend,
                detector_model=configured.detector_model_id(),
                detector_prompts=(
                    configured.detector_prompts
                    if configured.detector_supports_prompts()
                    else []
                ),
                detector_prompt_baseline=(
                    configured.detector_prompts
                    if configured.detector_supports_prompts()
                    else []
                ),
                detector_prompt_auto_update=(
                    configured.detector_prompt_auto_update
                    if configured.detector_supports_prompts()
                    else False
                ),
                replay_scenario=scenario.id,
                detections=_detections_for_mode(
                    initial_mode,
                    configured.detector_backend,
                    scenario.detections,
                ),
                auto_analyse=configured.auto_analyse,
                auto_analyse_interval_seconds=configured.auto_analyse_interval_seconds,
                auto_analyse_questions=curated_questions,
            )
        )
        detector = create_detector(configured)
        camera = CameraService(configured, detector, state)
        analysis = AnalysisService(
            state,
            providers,
            set(curated_questions),
            configured.vision_request_timeout_seconds,
        )
        app.state.settings = configured
        app.state.registry = registry
        app.state.providers = providers
        app.state.state_store = state
        app.state.camera = camera
        app.state.analysis = analysis
        app.state.curated_questions = curated_questions
        app.state.detector_prompt_lock = asyncio.Lock()
        monitor = asyncio.create_task(_camera_monitor(camera, state))
        automatic = asyncio.create_task(_automatic_analysis(app))
        try:
            yield
        finally:
            monitor.cancel()
            automatic.cancel()
            with suppress(asyncio.CancelledError):
                await monitor
            with suppress(asyncio.CancelledError):
                await automatic
            await camera.stop()
            await modeldeck.close()

    app = FastAPI(
        title="SceneChat",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    @app.get("/", include_in_schema=False)
    async def public_page():
        return FileResponse(FRONTEND / "public" / "index.html")

    @app.get("/staff", include_in_schema=False)
    async def staff_page():
        return RedirectResponse("/#operator-controls")

    @app.get("/api/health", response_model=HealthStatus)
    async def health(request: Request):
        state = await request.app.state.state_store.snapshot()
        return HealthStatus(
            status="ok",
            mode=state.internal_mode,
            provider=state.provider,
            provider_available=state.provider_available,
            camera_running=state.camera_running,
            privacy_screen=state.privacy_screen,
            version=__version__,
        )

    @app.get("/api/state", response_model=AppState)
    async def current_state(request: Request):
        return await request.app.state.state_store.snapshot()

    @app.get("/api/config")
    async def public_config(request: Request):
        registry = request.app.state.registry
        state = await request.app.state.state_store.snapshot()
        camera_devices = discover_camera_devices(selected_device=state.camera_device)
        if not any(
            camera["device"] == state.camera_device for camera in camera_devices
        ):
            camera_devices.append(
                {
                    "device": state.camera_device,
                    "name": f"Camera {state.camera_device}",
                    "label": f"Camera {state.camera_device}",
                }
            )
        return {
            "questions": request.app.state.curated_questions,
            "modes": ["development", "live", "detector-only", "mock", "replay"],
            "providers": ["modeldeck", "replay", "fallback", "mock"],
            "modeldeck_contract": {
                "model": configured.modeldeck_model,
                "protocol": MODELDECK_PROTOCOL_CONTRACT,
                "required_capabilities": list(MODELDECK_REQUIRED_CAPABILITIES),
            },
            "detector_enabled": configured.detector_backend != "none",
            "detector_models": (
                [
                    {"id": model_id, "label": model_id}
                    for model_id in configured.available_detector_models()
                ]
                if configured.detector_backend in PROMPTABLE_DETECTOR_BACKENDS
                else []
            ),
            "detector_prompting": configured.detector_supports_prompts(),
            "detector_prompt_allowlist": (
                configured.detector_prompt_allowlist
                if configured.detector_supports_prompts()
                else []
            ),
            "camera_devices": camera_devices,
            "scenarios": [
                {"id": item.id, "title": item.title} for item in registry.all()
            ],
        }

    @app.get("/api/diagnostics")
    async def diagnostics():
        available_mb = None
        try:
            for line in Path("/proc/meminfo").read_text("utf-8").splitlines():
                if line.startswith("MemAvailable:"):
                    available_mb = round(int(line.split()[1]) / 1024, 1)
                    break
        except OSError:
            pass
        maximum_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {
            "process_max_rss_mb": round(maximum_rss / 1024, 1),
            "system_available_mb": available_mb,
        }

    @app.get("/api/frame")
    async def current_frame(request: Request):
        state = await request.app.state.state_store.snapshot()
        if state.privacy_screen:
            return JSONResponse({"detail": "Privacy screen active"}, status_code=423)
        jpeg = request.app.state.camera.latest_jpeg()
        if state.camera_running and jpeg:
            return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
        path = request.app.state.registry.image_path(state.replay_scenario)
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return FileResponse(path, media_type=media_type, headers={"Cache-Control": "no-store"})

    @app.get("/api/events")
    async def events(request: Request):
        async def stream():
            last_revision = -1
            try:
                while not shutdown_requested() and not await request.is_disconnected():
                    snapshot = await request.app.state.state_store.snapshot()
                    if snapshot.revision != last_revision:
                        last_revision = snapshot.revision
                        yield f"data: {snapshot.model_dump_json()}\n\n"
                    await asyncio.sleep(0.35)
            except asyncio.CancelledError:
                return

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.post("/api/analyse")
    async def analyse(payload: AnalyseRequest, request: Request):
        state = await request.app.state.state_store.snapshot()
        if state.privacy_screen:
            raise HTTPException(423, "Privacy screen active")
        if state.internal_mode == "detector-only":
            raise HTTPException(409, "Scene analysis is disabled in detector-only mode")
        image = request.app.state.camera.latest_jpeg()
        if not image:
            image = request.app.state.registry.image_path(state.replay_scenario).read_bytes()
        try:
            analysis_result, applied = await request.app.state.analysis.analyse(
                image, payload.question
            )
            prompt_learning = _empty_prompt_learning_outcome()
            if applied:
                prompt_learning = await _learn_detector_prompts_from_analysis(
                    request.app, configured, analysis_result
                )
            return {
                "analysis": analysis_result,
                "applied": applied,
                "prompt_learning": prompt_learning,
            }
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except AnalysisBusy as exc:
            raise HTTPException(409, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.post("/api/reset", response_model=AppState)
    async def reset(request: Request):
        state = await request.app.state.state_store.snapshot()
        scenario = request.app.state.registry.get(state.replay_scenario)
        detections = (
            request.app.state.camera.latest_detections()
            if state.camera_running
            else _detections_for_mode(
                state.internal_mode,
                configured.detector_backend,
                scenario.detections,
            )
        )
        await request.app.state.state_store.reset(detections)
        if configured.detector_backend in PROMPTABLE_DETECTOR_BACKENDS:
            async with request.app.state.detector_prompt_lock:
                current = await request.app.state.state_store.snapshot()
                try:
                    await _set_detector_prompts(
                        request.app, current.detector_prompt_baseline
                    )
                except HTTPException:
                    pass
                await request.app.state.state_store.mutate(
                    lambda app_state: (
                        setattr(
                            app_state,
                            "detector_prompts",
                            list(app_state.detector_prompt_baseline),
                        ),
                        setattr(app_state, "detector_learned_prompts", []),
                        setattr(app_state, "detector_prompt_safety_rejections", 0),
                        setattr(app_state, "detector_prompt_rejection_reasons", {}),
                        setattr(app_state, "detector_prompt_capacity_skips", 0),
                    )
                )
        return await request.app.state.state_store.snapshot()

    @app.post("/api/analysis/clear", response_model=AppState)
    async def clear_analysis(request: Request):
        def change(state):
            state.generation += 1
            state.scene_analysis = None
            state.analysis_in_progress = False
            state.last_model_latency_ms = None
            state.staff_error = None

        return await request.app.state.state_store.mutate(change)

    @app.post("/api/privacy", response_model=AppState)
    async def privacy(
        request: Request,
        enabled: Annotated[bool, Body(embed=True)],
    ):
        def change(state):
            if enabled and not state.privacy_screen:
                state.generation += 1
                state.analysis_in_progress = False
            state.privacy_screen = enabled

        return await request.app.state.state_store.mutate(change)

    @app.post("/api/mode", response_model=AppState)
    async def mode(payload: ModeRequest, request: Request):
        if payload.mode not in {"development", "live", "detector-only", "mock", "replay"}:
            raise HTTPException(400, "Unsupported mode")
        current = await request.app.state.state_store.snapshot()
        scenario = request.app.state.registry.get(current.replay_scenario)

        def change(state):
            state.generation += 1
            state.analysis_in_progress = False
            state.internal_mode = payload.mode
            state.mode = _public_mode(payload.mode, configured.detector_backend)
            state.detections = _detections_for_mode(
                payload.mode,
                configured.detector_backend,
                scenario.detections,
            )
            state.staff_error = None
            if payload.mode == "mock":
                state.provider = "mock"
                state.provider_available = True
                state.provider_status_code = "available"
                state.provider_status_message = "Provider is available."
            elif payload.mode == "replay":
                state.provider = "replay"
                state.provider_available = True
                state.provider_status_code = "available"
                state.provider_status_message = "Provider is available."
            elif state.provider == "modeldeck" and not state.provider_available:
                _degrade_modeldeck_state(state, configured.detector_backend)
                state.staff_error = state.provider_status_message

        return await request.app.state.state_store.mutate(change)

    @app.post("/api/provider", response_model=AppState)
    async def provider(payload: ProviderRequest, request: Request):
        if payload.provider not in request.app.state.providers:
            raise HTTPException(400, "Unsupported provider")
        status = await request.app.state.providers[payload.provider].health()
        return await request.app.state.state_store.mutate(
            lambda state: _apply_provider_status(
                state,
                payload.provider,
                status,
                configured.detector_backend,
                invalidate=True,
            )
        )

    @app.post("/api/provider/check", response_model=AppState)
    async def check_provider(request: Request):
        current = await request.app.state.state_store.snapshot()
        status = await request.app.state.providers[current.provider].health()

        def apply_if_still_selected(state):
            if state.provider != current.provider:
                return
            _apply_provider_status(
                state,
                current.provider,
                status,
                configured.detector_backend,
                invalidate=not status.available and state.analysis_in_progress,
            )

        return await request.app.state.state_store.mutate(
            apply_if_still_selected
        )

    @app.post("/api/camera/start", response_model=AppState)
    async def camera_start(payload: CameraRequest, request: Request):
        try:
            await request.app.state.camera.start(payload.device)
        except CameraUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        return await request.app.state.state_store.snapshot()

    @app.post("/api/camera/stop", response_model=AppState)
    async def camera_stop(request: Request):
        await request.app.state.camera.stop()
        state = await request.app.state.state_store.snapshot()
        scenario = request.app.state.registry.get(state.replay_scenario)
        return await request.app.state.state_store.mutate(
            lambda current: setattr(
                current,
                "detections",
                _detections_for_mode(
                    current.internal_mode,
                    configured.detector_backend,
                    scenario.detections,
                ),
            )
        )

    @app.post("/api/detector/model", response_model=AppState)
    async def select_detector_model(payload: DetectorModelRequest, request: Request):
        models = configured.available_detector_models()
        if configured.detector_backend not in PROMPTABLE_DETECTOR_BACKENDS or not models:
            raise HTTPException(409, "Live detector model switching is not enabled")
        if payload.model not in models:
            raise HTTPException(400, "Unsupported detector model")

        async with request.app.state.detector_prompt_lock:
            camera = request.app.state.camera
            state_store = request.app.state.state_store
            current = await state_store.snapshot()
            was_running = current.camera_running
            if was_running:
                await camera.stop()

            selected_settings = configured.model_copy(
                update={
                    "detector_model": models[payload.model],
                    "detector_prompts": current.detector_prompts
                    or configured.detector_prompts,
                }
            )
            try:
                detector = await run_in_threadpool(create_detector, selected_settings)
            except Exception as exc:
                if was_running:
                    with suppress(CameraUnavailable):
                        await camera.start(current.camera_device)
                raise HTTPException(
                    503,
                    "Detector model could not be loaded; the previous model remains selected",
                ) from exc

            camera.detector = detector
            await state_store.mutate(
                lambda state: (
                    setattr(state, "detector_model", payload.model),
                    setattr(state, "detections", []),
                    setattr(state, "staff_error", None),
                )
            )
            if was_running:
                try:
                    await camera.start(current.camera_device)
                except CameraUnavailable as exc:
                    raise HTTPException(503, str(exc)) from exc
            return await state_store.snapshot()

    @app.post("/api/detector/prompts", response_model=AppState)
    async def select_detector_prompts(payload: DetectorPromptRequest, request: Request):
        if configured.detector_backend not in PROMPTABLE_DETECTOR_BACKENDS:
            raise HTTPException(409, "The selected detector does not support text prompts")
        approved = {
            item.casefold(): item for item in configured.detector_prompt_allowlist
        }
        requested = [" ".join(item.strip().lower().split()) for item in payload.prompts]
        if len(set(requested)) != len(requested) or any(
            item.casefold() not in approved for item in requested
        ):
            raise HTTPException(400, "Detector prompts must use the approved vocabulary")
        prompts = [approved[item.casefold()] for item in requested]
        async with request.app.state.detector_prompt_lock:
            await _set_detector_prompts(request.app, prompts)
            return await request.app.state.state_store.mutate(
                lambda state: (
                    setattr(state, "detector_prompts", prompts),
                    setattr(state, "detector_prompt_baseline", prompts),
                    setattr(state, "detector_learned_prompts", []),
                    setattr(state, "detector_prompt_auto_update", payload.auto_update),
                    setattr(state, "staff_error", None),
                )
            )

    @app.post("/api/detector/learned/clear", response_model=AppState)
    async def clear_learned_detector_prompts(request: Request):
        if configured.detector_backend not in PROMPTABLE_DETECTOR_BACKENDS:
            raise HTTPException(409, "The selected detector does not support text prompts")
        async with request.app.state.detector_prompt_lock:
            current = await request.app.state.state_store.snapshot()
            await _set_detector_prompts(request.app, current.detector_prompt_baseline)
            return await request.app.state.state_store.mutate(
                lambda state: (
                    setattr(
                        state,
                        "detector_prompts",
                        list(state.detector_prompt_baseline),
                    ),
                    setattr(state, "detector_learned_prompts", []),
                    setattr(state, "staff_error", None),
                )
            )

    @app.post("/api/auto-analyse", response_model=AppState)
    async def auto_analyse(payload: AutoAnalyseRequest, request: Request):
        questions = payload.questions
        if questions is not None and (
            len(set(questions)) != len(questions)
            or any(question not in request.app.state.curated_questions for question in questions)
        ):
            raise HTTPException(400, "Automatic analysis must use unique curated questions")

        return await request.app.state.state_store.mutate(
            lambda state: (
                setattr(state, "auto_analyse", payload.enabled),
                setattr(state, "auto_analyse_interval_seconds", payload.interval_seconds),
                setattr(
                    state,
                    "auto_analyse_questions",
                    questions if questions is not None else state.auto_analyse_questions,
                ),
            )
        )

    @app.post("/api/replay", response_model=AppState)
    async def select_replay(payload: ReplayRequest, request: Request):
        try:
            scenario = request.app.state.registry.get(payload.scenario)
        except KeyError as exc:
            raise HTTPException(404, "Unknown replay scenario") from exc
        for provider_name in ("replay", "fallback"):
            provider = ReplayVisionProvider(scenario.responses, name=provider_name)
            request.app.state.providers[provider_name] = provider
            request.app.state.analysis.providers[provider_name] = provider

        def change(state):
            state.replay_scenario = scenario.id
            state.detections = _detections_for_mode(
                state.internal_mode,
                configured.detector_backend,
                scenario.detections,
            )
            state.scene_analysis = None
            state.generation += 1
            state.analysis_in_progress = False

        return await request.app.state.state_store.mutate(change)

    app.mount("/assets", StaticFiles(directory=FRONTEND / "src"), name="assets")
    return app


async def _camera_monitor(camera: CameraService, state: StateStore) -> None:
    previous = ([], 0.0)
    while True:
        await asyncio.sleep(0.25)
        if not camera.running:
            snapshot = await state.snapshot()
            if snapshot.camera_running:
                await state.mutate(
                    lambda app_state: (
                        setattr(app_state, "camera_running", False),
                        setattr(app_state, "detector_fps", 0.0),
                        setattr(app_state, "detections", []),
                        setattr(
                            app_state,
                            "staff_error",
                            camera._start_error or "Camera capture stopped unexpectedly.",
                        ),
                    )
                )
            continue
        current = (camera.latest_detections(), round(camera._fps, 1))
        if current != previous:
            previous = current
            await state.mutate(
                lambda app_state: (
                    setattr(app_state, "detections", current[0]),
                    setattr(app_state, "detector_fps", current[1]),
                )
                )


def _automatic_analysis_can_run(state: AppState) -> bool:
    return (
        state.auto_analyse
        and state.camera_running
        and state.internal_mode != "detector-only"
        and not state.privacy_screen
    )


async def _automatic_analysis(app: FastAPI) -> None:
    loop = asyncio.get_running_loop()
    last_started = loop.time()
    while True:
        await asyncio.sleep(0.5)
        state = await app.state.state_store.snapshot()
        if not _automatic_analysis_can_run(state):
            last_started = loop.time()
            continue
        if loop.time() - last_started < state.auto_analyse_interval_seconds:
            continue
        last_started = loop.time()
        image = app.state.camera.latest_jpeg()
        if not image:
            # Camera state can change after the scheduler snapshot. Never replace a
            # missing live frame with replay content for an automatic request.
            last_started = loop.time()
            continue
        try:
            question = _select_automatic_question(
                state.auto_analyse_questions, state.selected_question
            )
            analysis_result, applied = await app.state.analysis.analyse(
                image, question
            )
            if applied:
                await _learn_detector_prompts_from_analysis(
                    app, app.state.settings, analysis_result
                )
        except (RuntimeError, ValueError, AnalysisBusy):
            pass


app = create_app()
