import asyncio

import httpx
import pytest

import scenechat.main as main_module
from scenechat.config import Settings
from scenechat.detection import NoopDetector
from scenechat.main import create_app
from scenechat.models import SceneAnalysis
from scenechat.vision.base import ProviderStatus


def _settings():
    return Settings(
        scenechat_mode="replay",
        model_provider="replay",
        detector_backend="replay",
    )


class AppClient:
    def __init__(self):
        self.app = create_app(_settings())
        self.client = None

    async def __aenter__(self):
        self.lifespan = self.app.router.lifespan_context(self.app)
        await self.lifespan.__aenter__()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        )
        return self.client

    async def __aexit__(self, *args):
        await self.client.aclose()
        await self.lifespan.__aexit__(*args)


@pytest.mark.anyio
async def test_health_public_state_and_pages():
    async with AppClient() as client:
        public = await client.get("/")
        assert public.status_code == 200
        assert '<dialog id="operator-controls"' in public.text
        assert 'id="closeOperatorControls"' in public.text
        assert 'id="operatorToast"' in public.text
        assert 'class="operator-shell"' not in public.text
        assert 'id="cameraChoices"' in public.text
        assert 'id="detectorModelSelect"' in public.text
        assert 'id="detectorPromptChoices"' in public.text
        assert 'id="detectorPromptSelectionCount"' in public.text
        assert 'id="selectAllDetectorPrompts"' in public.text
        assert 'id="clearAllDetectorPrompts"' in public.text
        assert 'id="autoQuestionChoices"' in public.text
        assert 'id="autoScheduleStatus"' in public.text
        assert 'id="headerPrivacy"' in public.text
        assert '/assets/styles.css?v=13' in public.text
        assert '/assets/public.js?v=15' in public.text
        assert 'id="activePromptChips"' in public.text
        assert 'id="detectorPromptSelect"' not in public.text
        assert 'id="analysisStatus"' in public.text
        assert 'id="analysisStatusTitle"' in public.text
        assert 'id="analysisStatusDetail"' in public.text
        assert 'id="detectorLegend"' in public.text
        assert 'id="analysisObjects"' in public.text
        assert 'Scene model mentioned' in public.text
        assert 'Fast object detector' in public.text
        assert 'id="checkProvider"' in public.text
        assert 'id="providerGuidance"' in public.text
        assert 'id="cameraDevice"' not in public.text
        staff = await client.get("/staff")
        assert staff.status_code == 307
        assert staff.headers["location"] == "/#operator-controls"
        health = await client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert (await client.get("/api/diagnostics")).status_code == 200
        assert (await client.get("/api/frame")).status_code == 200


@pytest.mark.anyio
async def test_replay_analysis_and_reset_flow():
    async with AppClient() as client:
        response = await client.post("/api/analyse", json={"question": "Describe the scene."})
        assert response.status_code == 200
        assert response.json()["analysis"]["provider"] == "replay"
        assert (await client.get("/api/state")).json()["scene_analysis"] is not None
        reset = await client.post("/api/reset")
        assert reset.status_code == 200
        assert reset.json()["scene_analysis"] is None


@pytest.mark.anyio
async def test_clear_description_invalidates_in_flight_generation():
    async with AppClient() as client:
        before = (await client.get("/api/state")).json()["generation"]
        cleared = await client.post("/api/analysis/clear")
        assert cleared.status_code == 200
        assert cleared.json()["generation"] == before + 1
        assert cleared.json()["scene_analysis"] is None


@pytest.mark.anyio
async def test_non_curated_question_is_rejected():
    async with AppClient() as client:
        response = await client.post("/api/analyse", json={"question": "Who is this person?"})
        assert response.status_code == 400


@pytest.mark.anyio
async def test_privacy_screen_blocks_frame_and_can_be_restored():
    async with AppClient() as client:
        enabled = await client.post("/api/privacy", json={"enabled": True})
        assert enabled.status_code == 200
        assert enabled.json()["privacy_screen"] is True
        assert (await client.get("/api/frame")).status_code == 423
        blocked_analysis = await client.post(
            "/api/analyse", json={"question": "Describe the scene."}
        )
        assert blocked_analysis.status_code == 423
        disabled = await client.post("/api/privacy", json={"enabled": False})
        assert disabled.json()["privacy_screen"] is False
        assert (await client.get("/api/frame")).status_code == 200


@pytest.mark.anyio
async def test_privacy_screen_invalidates_an_in_flight_result():
    class ControlledProvider:
        def __init__(self):
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def analyse_scene(self, image, question):
            self.started.set()
            await self.release.wait()
            return SceneAnalysis(summary="This result became private.", provider="replay")

    async with AppClient() as client:
        provider = ControlledProvider()
        app = client._transport.app
        app.state.providers["replay"] = provider
        app.state.analysis.providers["replay"] = provider
        request_task = asyncio.create_task(
            client.post("/api/analyse", json={"question": "Describe the scene."})
        )
        await provider.started.wait()
        privacy = await client.post("/api/privacy", json={"enabled": True})
        provider.release.set()
        response = await request_task

        assert privacy.json()["privacy_screen"] is True
        assert response.status_code == 200
        assert response.json()["applied"] is False
        assert (await client.get("/api/state")).json()["scene_analysis"] is None


@pytest.mark.anyio
async def test_detector_only_disables_analysis():
    async with AppClient() as client:
        assert (await client.post("/api/mode", json={"mode": "detector-only"})).status_code == 200
        response = await client.post("/api/analyse", json={"question": "Describe the scene."})
        assert response.status_code == 409


@pytest.mark.anyio
async def test_automatic_analysis_interval_requires_at_least_twenty_seconds():
    async with AppClient() as client:
        rejected = await client.post(
            "/api/auto-analyse",
            json={"enabled": True, "interval_seconds": 19.9},
        )
        assert rejected.status_code == 422

        accepted = await client.post(
            "/api/auto-analyse",
            json={
                "enabled": True,
                "interval_seconds": 20,
                "questions": ["What objects can you see?"],
            },
        )
        assert accepted.status_code == 200
        assert accepted.json()["auto_analyse"] is True
        assert accepted.json()["auto_analyse_interval_seconds"] == 20
        assert accepted.json()["auto_analyse_questions"] == [
            "What objects can you see?"
        ]

        non_curated = await client.post(
            "/api/auto-analyse",
            json={
                "enabled": True,
                "interval_seconds": 20,
                "questions": ["Identify this visitor"],
            },
        )
        assert non_curated.status_code == 400


@pytest.mark.anyio
async def test_live_mode_without_detector_uses_accurate_public_wording():
    settings = Settings(
        scenechat_mode="live",
        model_provider="mock",
        detector_backend="none",
    )
    app = create_app(settings)
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    try:
        state = (await client.get("/api/state")).json()
        assert state["mode"] == "Live scene description"
        assert state["detections"] == []
        config = (await client.get("/api/config")).json()
        assert config["detector_enabled"] is False
        assert config["providers"] == ["modeldeck", "replay", "fallback", "mock"]
        assert config["modeldeck_contract"] == {
            "model": "scenechat-vision",
            "protocol": "scene-analysis-v1",
            "required_capabilities": ["image_input", "structured_output"],
        }
        assert config["camera_devices"]
        assert all(camera["label"] for camera in config["camera_devices"])
        fallback = await client.post("/api/mode", json={"mode": "detector-only"})
        assert fallback.json()["mode"] == "Live camera only"
        assert fallback.json()["detections"] == []
        replay = await client.post("/api/mode", json={"mode": "replay"})
        assert replay.json()["detections"]
        live = await client.post("/api/mode", json={"mode": "live"})
        assert live.json()["detections"] == []
    finally:
        await client.aclose()
        await lifespan.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_fallback_provider_is_an_explicit_offline_selection():
    async with AppClient() as client:
        selected = await client.post("/api/provider", json={"provider": "fallback"})
        assert selected.status_code == 200
        assert selected.json()["provider"] == "fallback"
        response = await client.post(
            "/api/analyse", json={"question": "Describe the scene."}
        )
        assert response.status_code == 200
        assert response.json()["analysis"]["provider"] == "fallback"


@pytest.mark.anyio
async def test_provider_recheck_marks_modeldeck_unavailable_without_failover():
    async with AppClient() as client:
        app = client._transport.app

        async def unavailable():
            return ProviderStatus(
                False,
                "worker_not_ready",
                "Start the SceneChat Worker in ModelDeck and wait for ready.",
            )

        app.state.providers["modeldeck"].health = unavailable
        selected = await client.post("/api/provider", json={"provider": "modeldeck"})
        checked = await client.post("/api/provider/check")

        assert selected.status_code == 200
        assert checked.json()["provider"] == "modeldeck"
        assert checked.json()["provider_available"] is False
        assert checked.json()["provider_status_code"] == "worker_not_ready"
        assert checked.json()["internal_mode"] == "detector-only"
        assert "Start the SceneChat Worker" in checked.json()["staff_error"]


@pytest.mark.anyio
async def test_modeldeck_unavailable_at_startup_keeps_offline_app_operational(monkeypatch):
    async def unavailable(_provider):
        return ProviderStatus(False, "gateway_unavailable", "ModelDeck is unavailable.")

    monkeypatch.setattr(main_module.ModelDeckProvider, "health", unavailable)
    settings = Settings(
        _env_file=None,
        scenechat_mode="live",
        model_provider="modeldeck",
        detector_backend="none",
    )
    app = create_app(settings)
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    try:
        state = (await client.get("/api/state")).json()
        assert state["provider"] == "modeldeck"
        assert state["provider_available"] is False
        assert state["internal_mode"] == "detector-only"
        assert state["mode"] == "Live camera only"
        selected = await client.post("/api/provider", json={"provider": "replay"})
        assert selected.json()["provider"] == "replay"
        assert selected.json()["provider_available"] is True
    finally:
        await client.aclose()
        await lifespan.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_operator_can_switch_only_allowlisted_detector_models(monkeypatch):
    monkeypatch.setattr(main_module, "create_detector", lambda settings: NoopDetector())
    settings = Settings(
        _env_file=None,
        scenechat_mode="live",
        model_provider="mock",
        detector_backend="auto",
        detector_model="/models/yolov8s-worldv2.pt",
        detector_text_encoder="/models/mobileclip2_b.ts",
        detector_yoloworld_clip="/models/ViT-B-32.pt",
        detector_model_options={
            "yoloworld-s": "/models/yolov8s-worldv2.pt",
            "yoloe-26s": "/models/yoloe-26s-seg.pt",
        },
    )
    app = create_app(settings)
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    try:
        lifecycle_calls = []

        async def stop_camera():
            lifecycle_calls.append("stop")
            await app.state.state_store.mutate(
                lambda state: setattr(state, "camera_running", False)
            )

        async def start_camera(device):
            lifecycle_calls.append(f"start:{device}")
            await app.state.state_store.mutate(
                lambda state: (
                    setattr(state, "camera_running", True),
                    setattr(state, "camera_device", device),
                )
            )

        monkeypatch.setattr(app.state.camera, "stop", stop_camera)
        monkeypatch.setattr(app.state.camera, "start", start_camera)
        await app.state.state_store.mutate(
            lambda state: (
                setattr(state, "camera_running", True),
                setattr(state, "camera_device", 4),
            )
        )
        config = (await client.get("/api/config")).json()
        assert config["detector_models"] == [
            {"id": "yoloworld-s", "label": "yoloworld-s"},
            {"id": "yoloe-26s", "label": "yoloe-26s"},
        ]
        switched = await client.post("/api/detector/model", json={"model": "yoloe-26s"})
        assert switched.status_code == 200
        assert switched.json()["detector_model"] == "yoloe-26s"
        assert switched.json()["camera_running"] is True
        assert lifecycle_calls == ["stop", "start:4"]
        rejected = await client.post(
            "/api/detector/model", json={"model": "../../arbitrary-model"}
        )
        assert rejected.status_code == 400
    finally:
        await client.aclose()
        await lifespan.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_yoloe_prompts_are_operator_approved(monkeypatch):
    monkeypatch.setattr(main_module, "create_detector", lambda settings: NoopDetector())
    settings = Settings(
        _env_file=None,
        scenechat_mode="live",
        model_provider="mock",
        detector_backend="yoloe",
        detector_model="/models/yoloe-26s-seg.pt",
        detector_text_encoder="/models/mobileclip2_b.ts",
        detector_prompts=["person", "computer mouse"],
        detector_prompt_allowlist=["person", "computer mouse", "camera"],
    )
    app = create_app(settings)
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    applied = []
    monkeypatch.setattr(
        app.state.camera,
        "set_detector_prompts",
        lambda prompts: applied.append(prompts),
    )
    try:
        config = (await client.get("/api/config")).json()
        assert config["detector_prompting"] is True
        assert config["detector_prompt_allowlist"] == [
            "person",
            "computer mouse",
            "camera",
        ]

        accepted = await client.post(
            "/api/detector/prompts",
            json={"prompts": ["person", "camera"], "auto_update": True},
        )
        assert accepted.status_code == 200
        assert accepted.json()["detector_prompts"] == ["person", "camera"]
        assert accepted.json()["detector_prompt_auto_update"] is True
        assert applied == [["person", "camera"]]

        rejected = await client.post(
            "/api/detector/prompts",
            json={"prompts": ["red-haired person"], "auto_update": True},
        )
        assert rejected.status_code == 400
    finally:
        await client.aclose()
        await lifespan.__aexit__(None, None, None)


def test_model_labels_extend_active_prompts_without_restoring_defaults():
    settings = Settings(
        _env_file=None,
        detector_prompts=["person", "computer mouse"],
        detector_prompt_allowlist=["person", "computer mouse", "camera"],
    )

    assert main_module._approved_detector_prompts(
        settings,
        ["computer mouse"],
        ["Camera", "red-haired person", "a black computer mouse"],
    ) == ["computer mouse", "camera"]
