"""SceneChat FastAPI application."""

import asyncio
import json
import mimetypes
import resource
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Annotated

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from scenechat import __version__
from scenechat.config import ROOT, Settings, get_settings
from scenechat.detection import create_detector
from scenechat.models import AppState, Detection, HealthStatus
from scenechat.replay import ReplayRegistry
from scenechat.services.analysis import AnalysisBusy, AnalysisService
from scenechat.services.camera import CameraService, CameraUnavailable, discover_camera_devices
from scenechat.services.runtime import shutdown_requested
from scenechat.services.state import StateStore
from scenechat.vision import ModelDeckProvider, MockVisionProvider, ReplayVisionProvider


FRONTEND = ROOT / "frontend"


class AnalyseRequest(BaseModel):
    question: str


class ModeRequest(BaseModel):
    mode: str


class ProviderRequest(BaseModel):
    provider: str


class CameraRequest(BaseModel):
    device: int = Field(default=0, ge=0, le=32)


class AutoAnalyseRequest(BaseModel):
    enabled: bool
    interval_seconds: float = Field(default=5, ge=3, le=60)


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


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        registry = ReplayRegistry()
        scenario = registry.get(configured.replay_scenario)
        initial_provider = (
            "replay" if configured.scenechat_mode == "replay" else configured.model_provider
        )
        state = StateStore(
            AppState(
                mode=_public_mode(configured.scenechat_mode, configured.detector_backend),
                internal_mode=configured.scenechat_mode,
                provider=initial_provider,
                camera_device=configured.camera_device,
                replay_scenario=scenario.id,
                detections=_detections_for_mode(
                    configured.scenechat_mode,
                    configured.detector_backend,
                    scenario.detections,
                ),
                auto_analyse=configured.auto_analyse,
                auto_analyse_interval_seconds=configured.auto_analyse_interval_seconds,
            )
        )
        modeldeck = ModelDeckProvider(
            configured.modeldeck_url,
            configured.modeldeck_api_key,
            configured.modeldeck_model,
            configured.vision_request_timeout_seconds,
        )
        providers = {
            "modeldeck": modeldeck,
            "mock": MockVisionProvider(),
            "replay": ReplayVisionProvider(scenario.responses),
            "fallback": ReplayVisionProvider(scenario.responses, name="fallback"),
        }
        detector = create_detector(configured)
        camera = CameraService(configured, detector, state)
        analysis = AnalysisService(
            state,
            providers,
            set(_load_questions()),
            configured.vision_request_timeout_seconds,
        )
        app.state.settings = configured
        app.state.registry = registry
        app.state.providers = providers
        app.state.state_store = state
        app.state.camera = camera
        app.state.analysis = analysis
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
        return FileResponse(FRONTEND / "public" / "staff.html")

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
        camera_devices = discover_camera_devices()
        if not any(
            camera["device"] == configured.camera_device for camera in camera_devices
        ):
            camera_devices.append(
                {
                    "device": configured.camera_device,
                    "name": f"Camera {configured.camera_device}",
                    "label": f"Camera {configured.camera_device}",
                }
            )
        return {
            "questions": _load_questions(),
            "modes": ["development", "live", "detector-only", "mock", "replay"],
            "providers": ["modeldeck", "replay", "fallback", "mock"],
            "detector_enabled": configured.detector_backend != "none",
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
            return {"analysis": analysis_result, "applied": applied}
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
        return await request.app.state.state_store.reset(detections)

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
        return await request.app.state.state_store.mutate(
            lambda state: setattr(state, "privacy_screen", enabled)
        )

    @app.post("/api/mode", response_model=AppState)
    async def mode(payload: ModeRequest, request: Request):
        if payload.mode not in {"development", "live", "detector-only", "mock", "replay"}:
            raise HTTPException(400, "Unsupported mode")
        current = await request.app.state.state_store.snapshot()
        scenario = request.app.state.registry.get(current.replay_scenario)

        def change(state):
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
            elif payload.mode == "replay":
                state.provider = "replay"

        return await request.app.state.state_store.mutate(change)

    @app.post("/api/provider", response_model=AppState)
    async def provider(payload: ProviderRequest, request: Request):
        if payload.provider not in request.app.state.providers:
            raise HTTPException(400, "Unsupported provider")
        available = await request.app.state.providers[payload.provider].health()
        return await request.app.state.state_store.mutate(
            lambda state: (
                setattr(state, "provider", payload.provider),
                setattr(state, "provider_available", available),
                setattr(state, "staff_error", None if available else "Provider is unavailable."),
            )
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

    @app.post("/api/auto-analyse", response_model=AppState)
    async def auto_analyse(payload: AutoAnalyseRequest, request: Request):
        return await request.app.state.state_store.mutate(
            lambda state: (
                setattr(state, "auto_analyse", payload.enabled),
                setattr(state, "auto_analyse_interval_seconds", payload.interval_seconds),
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


async def _automatic_analysis(app: FastAPI) -> None:
    loop = asyncio.get_running_loop()
    last_started = loop.time()
    while True:
        await asyncio.sleep(0.5)
        state = await app.state.state_store.snapshot()
        if not state.auto_analyse or state.internal_mode == "detector-only":
            last_started = loop.time()
            continue
        if loop.time() - last_started < state.auto_analyse_interval_seconds:
            continue
        last_started = loop.time()
        image = app.state.camera.latest_jpeg()
        if not image:
            image = app.state.registry.image_path(state.replay_scenario).read_bytes()
        try:
            await app.state.analysis.analyse(image, state.selected_question)
        except (RuntimeError, ValueError, AnalysisBusy):
            pass


app = create_app()
