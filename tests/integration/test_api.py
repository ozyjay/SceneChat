import asyncio

import httpx
import pytest

import scenechat.main as main_module
from scenechat.config import Settings
from scenechat.detection import NoopDetector
from scenechat.main import create_app
from scenechat.models import ObjectDescription, SceneAnalysis
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
        assert '<button id="operatorToast"' in public.text
        assert public.text.index(
            'class="control-panel camera-panel"'
        ) < public.text.index('class="control-panel emergency-panel"')
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
        assert '/assets/styles.css?v=16' in public.text
        assert '/assets/public.js?v=21' in public.text
        assert 'id="activePromptChips"' in public.text
        assert 'id="learnedPromptChips"' in public.text
        assert 'id="clearLearnedPrompts"' in public.text
        assert 'id="promptLearningStatus"' in public.text
        assert 'id="detectorPromptSelect"' not in public.text
        assert 'id="analysisStatus"' in public.text
        assert 'id="analysisStatusTitle"' in public.text
        assert 'id="analysisStatusDetail"' in public.text
        assert 'id="detectorLegend"' in public.text
        assert "teal strong · gold possible · red uncertain" in public.text
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
        script = await client.get("/assets/public.js?v=21")
        assert "Automatic scene analysis enabled" in script.text
        assert "Automatic analysis paused" in script.text
        assert "Automatic scene analysis is paused until the camera starts again" in script.text
        assert "Object detection updated" in script.text
        assert "Privacy screen activated" in script.text
        assert "dismissNotifications" in script.text
        assert "{minimum: 0.75, key: 'strong', label: 'strong match'}" in script.text
        assert "{minimum: 0.55, key: 'possible', label: 'possible match'}" in script.text
        assert "label: 'uncertain match'" in script.text
        assert "This score is not a probability." in script.text


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
async def test_analysis_ignores_buffered_camera_frame_after_camera_stops(monkeypatch):
    class CapturingProvider:
        def __init__(self):
            self.image = None

        async def analyse_scene(self, image, question):
            self.image = image
            return SceneAnalysis(summary="Prepared replay scene.", provider="replay")

    async with AppClient() as client:
        provider = CapturingProvider()
        app = client._transport.app
        app.state.providers["replay"] = provider
        app.state.analysis.providers["replay"] = provider
        monkeypatch.setattr(app.state.camera, "latest_jpeg", lambda: b"stale-camera-frame")

        response = await client.post(
            "/api/analyse", json={"question": "Describe the scene."}
        )

        assert response.status_code == 200
        prepared_image = app.state.registry.image_path("demo_booth").read_bytes()
        assert provider.image == prepared_image


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
async def test_automatic_analysis_interval_accepts_twenty_to_three_hundred_seconds():
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

        upper_bound = await client.post(
            "/api/auto-analyse",
            json={"enabled": True, "interval_seconds": 300},
        )
        assert upper_bound.status_code == 200

        too_slow = await client.post(
            "/api/auto-analyse",
            json={"enabled": True, "interval_seconds": 300.1},
        )
        assert too_slow.status_code == 422

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
async def test_provider_recheck_restores_the_requested_live_mode():
    async with AppClient() as client:
        app = client._transport.app

        async def available():
            return ProviderStatus(
                True,
                "available",
                "ModelDeck scenechat-vision is ready.",
            )

        app.state.providers["modeldeck"].health = available
        await app.state.state_store.mutate(
            lambda state: (
                setattr(state, "provider", "modeldeck"),
                setattr(state, "provider_available", False),
                setattr(state, "internal_mode", "detector-only"),
                setattr(state, "desired_mode", "live"),
                setattr(state, "mode", "Detector only"),
            )
        )

        checked = await client.post("/api/provider/check")

        assert checked.status_code == 200
        assert checked.json()["provider_available"] is True
        assert checked.json()["internal_mode"] == "live"
        assert checked.json()["desired_mode"] == "live"
        assert checked.json()["mode"] == "Combined"


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
    created_with_prompts = []

    def create_detector(settings):
        created_with_prompts.append(list(settings.detector_prompts))
        return NoopDetector()

    monkeypatch.setattr(main_module, "create_detector", create_detector)
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
                setattr(state, "detector_prompt_baseline", ["person"]),
                setattr(state, "detector_learned_prompts", ["tripod"]),
                setattr(state, "detector_prompts", ["person", "tripod"]),
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
        assert switched.json()["detector_prompt_baseline"] == ["person"]
        assert switched.json()["detector_learned_prompts"] == ["tripod"]
        assert switched.json()["detector_prompts"] == ["person", "tripod"]
        assert created_with_prompts[-1] == ["person", "tripod"]
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
        assert accepted.json()["detector_prompt_baseline"] == ["person", "camera"]
        assert accepted.json()["detector_learned_prompts"] == []
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


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("backend", "model", "extra"),
    [
        (
            "yoloe",
            "/models/yoloe-26s-seg.pt",
            {"detector_text_encoder": "/models/mobileclip2_b.ts"},
        ),
        (
            "yoloworld",
            "/models/yolov8s-worldv2.pt",
            {"detector_yoloworld_clip": "/models/ViT-B-32.pt"},
        ),
    ],
)
async def test_scene_analysis_learns_safe_objects_for_both_promptable_detectors(
    monkeypatch, backend, model, extra
):
    monkeypatch.setattr(main_module, "create_detector", lambda settings: NoopDetector())
    settings = Settings(
        _env_file=None,
        scenechat_mode="live",
        model_provider="mock",
        detector_backend=backend,
        detector_model=model,
        detector_prompts=["person"],
        detector_prompt_allowlist=["person", "camera"],
        detector_prompt_auto_update=True,
        **extra,
    )
    app = create_app(settings)
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )

    class LearningProvider:
        name = "mock"

        async def health(self):
            return ProviderStatus(True, "available", "Provider is available.")

        async def analyse_scene(self, image, question):
            return SceneAnalysis(
                summary="A tripod and wheelchair are visible.",
                objects=[
                    ObjectDescription(
                        label="tripod",
                        description="A tripod is visible.",
                        approximate_location="centre",
                    ),
                    ObjectDescription(
                        label="wheelchair",
                        description="A wheelchair is visible.",
                        approximate_location="left",
                    ),
                ],
                relationships=["The wheelchair is beside the tripod."],
                provider=self.name,
            )

    provider = LearningProvider()
    app.state.providers["mock"] = provider
    app.state.analysis.providers["mock"] = provider
    applied = []
    monkeypatch.setattr(
        app.state.camera,
        "set_detector_prompts",
        lambda prompts: applied.append(list(prompts)),
    )
    try:
        response = await client.post(
            "/api/analyse", json={"question": "Describe the scene."}
        )
        assert response.status_code == 200
        learning = response.json()["prompt_learning"]
        assert learning["added"] == ["tripod"]
        assert learning["rejected_count"] == 1
        assert learning["rejection_reasons"] == {"medical_or_assistive": 1}
        assert "wheelchair" not in response.text
        assert response.json()["analysis"]["summary"] == (
            "A tripod and [withheld] are visible."
        )
        assert response.json()["analysis"]["relationships"] == [
            "The [withheld] is beside the tripod."
        ]

        state = (await client.get("/api/state")).json()
        assert state["detector_prompt_baseline"] == ["person"]
        assert state["detector_learned_prompts"] == ["tripod"]
        assert state["detector_prompts"] == ["person", "tripod"]
        assert state["detector_prompt_safety_rejections"] == 1
        assert "wheelchair" not in str(state)
        assert applied == [["person", "tripod"]]

        manually_applied = await client.post(
            "/api/detector/prompts",
            json={"prompts": ["person", "camera"], "auto_update": True},
        )
        assert manually_applied.status_code == 200
        assert manually_applied.json()["detector_prompt_baseline"] == [
            "person",
            "camera",
        ]
        assert manually_applied.json()["detector_learned_prompts"] == []

        await client.post(
            "/api/analyse", json={"question": "Describe the scene."}
        )
        cleared = await client.post("/api/detector/learned/clear")
        assert cleared.status_code == 200
        assert cleared.json()["scene_analysis"] is not None
        assert cleared.json()["detector_prompts"] == ["person", "camera"]
        assert cleared.json()["detector_learned_prompts"] == []
        assert applied[-1] == ["person", "camera"]

        await client.post(
            "/api/analyse", json={"question": "Describe the scene."}
        )
        reset = await client.post("/api/reset")
        assert reset.status_code == 200
        assert reset.json()["scene_analysis"] is None
        assert reset.json()["detector_prompts"] == ["person", "camera"]
        assert reset.json()["detector_learned_prompts"] == []
        assert reset.json()["detector_prompt_safety_rejections"] == 0
        assert reset.json()["detector_prompt_rejection_reasons"] == {}
        assert applied[-1] == ["person", "camera"]
    finally:
        await client.aclose()
        await lifespan.__aexit__(None, None, None)


@pytest.mark.anyio
@pytest.mark.parametrize("invalidation", ["privacy", "reset"])
async def test_invalidated_analysis_cannot_change_detector_prompts(
    monkeypatch, invalidation
):
    monkeypatch.setattr(main_module, "create_detector", lambda settings: NoopDetector())
    settings = Settings(
        _env_file=None,
        scenechat_mode="live",
        model_provider="mock",
        detector_backend="yoloe",
        detector_model="/models/yoloe-26s-seg.pt",
        detector_text_encoder="/models/mobileclip2_b.ts",
        detector_prompts=["person"],
        detector_prompt_allowlist=["person"],
        detector_prompt_auto_update=True,
    )
    app = create_app(settings)
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    concurrent_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )

    class Provider:
        async def analyse_scene(self, image, question):
            return SceneAnalysis(
                summary="A tripod and wheelchair are visible.",
                objects=[
                    ObjectDescription(
                        label="tripod",
                        description="A tripod is visible.",
                        approximate_location="centre",
                    ),
                    ObjectDescription(
                        label="wheelchair",
                        description="A wheelchair is visible.",
                        approximate_location="left",
                    ),
                ],
                provider="mock",
            )

    app.state.providers["mock"] = Provider()
    app.state.analysis.providers["mock"] = app.state.providers["mock"]
    prompt_update_started = asyncio.Event()
    release_prompt_update = asyncio.Event()
    applied = []

    async def block_first_prompt_update(app, prompts):
        applied.append(list(prompts))
        if prompts == ["person", "tripod"]:
            prompt_update_started.set()
            await release_prompt_update.wait()

    monkeypatch.setattr(
        main_module, "_set_detector_prompts", block_first_prompt_update
    )
    try:
        analysis_task = asyncio.create_task(
            client.post("/api/analyse", json={"question": "Describe the scene."})
        )
        await asyncio.wait_for(prompt_update_started.wait(), 2)
        assert "wheelchair" not in str(
            (await app.state.state_store.snapshot()).model_dump()
        )

        if invalidation == "privacy":
            invalidation_task = asyncio.create_task(
                concurrent_client.post("/api/privacy", json={"enabled": True})
            )
            invalidated = await invalidation_task
            assert invalidated.status_code == 200
        else:
            invalidation_task = asyncio.create_task(
                concurrent_client.post("/api/reset")
            )
            for _ in range(100):
                if (await app.state.state_store.snapshot()).scene_analysis is None:
                    break
                await asyncio.sleep(0.01)
            assert (await app.state.state_store.snapshot()).scene_analysis is None

        release_prompt_update.set()
        response = await analysis_task
        if invalidation == "reset":
            assert (await invalidation_task).status_code == 200

        assert response.status_code == 200
        assert response.json()["prompt_learning"]["added"] == []
        state = (await client.get("/api/state")).json()
        assert state["detector_prompts"] == ["person"]
        assert state["detector_learned_prompts"] == []
        assert applied[0] == ["person", "tripod"]
        assert applied[-1] == ["person"]
    finally:
        release_prompt_update.set()
        await concurrent_client.aclose()
        await client.aclose()
        await lifespan.__aexit__(None, None, None)


@pytest.mark.anyio
async def test_newer_analysis_prevents_an_older_result_learning(monkeypatch):
    monkeypatch.setattr(main_module, "create_detector", lambda settings: NoopDetector())
    settings = Settings(
        _env_file=None,
        scenechat_mode="live",
        model_provider="mock",
        detector_backend="yoloe",
        detector_model="/models/yoloe-26s-seg.pt",
        detector_text_encoder="/models/mobileclip2_b.ts",
        detector_prompts=["person"],
        detector_prompt_allowlist=["person"],
        detector_prompt_auto_update=True,
    )
    app = create_app(settings)
    lifespan = app.router.lifespan_context(app)
    await lifespan.__aenter__()
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    concurrent_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )

    class Provider:
        calls = 0

        async def analyse_scene(self, image, question):
            self.calls += 1
            label = "tripod" if self.calls == 1 else "whiteboard"
            return SceneAnalysis(
                summary="An object is visible.",
                objects=[
                    ObjectDescription(
                        label=label,
                        description=f"A {label} is visible.",
                        approximate_location="centre",
                    )
                ],
                provider="mock",
            )

    app.state.providers["mock"] = Provider()
    app.state.analysis.providers["mock"] = app.state.providers["mock"]
    first_update_started = asyncio.Event()
    release_first_update = asyncio.Event()
    applied = []

    async def block_first_prompt_update(app, prompts):
        applied.append(list(prompts))
        if prompts == ["person", "tripod"]:
            first_update_started.set()
            await release_first_update.wait()

    monkeypatch.setattr(
        main_module, "_set_detector_prompts", block_first_prompt_update
    )
    try:
        first = asyncio.create_task(
            client.post("/api/analyse", json={"question": "Describe the scene."})
        )
        await asyncio.wait_for(first_update_started.wait(), 2)
        second = asyncio.create_task(
            concurrent_client.post(
                "/api/analyse", json={"question": "Describe the scene."}
            )
        )
        for _ in range(100):
            current = await app.state.state_store.snapshot()
            if current.scene_analysis and current.scene_analysis.objects[0].label == "whiteboard":
                break
            await asyncio.sleep(0.01)
        release_first_update.set()

        first_response, second_response = await asyncio.gather(first, second)
        assert first_response.json()["prompt_learning"]["added"] == []
        assert second_response.json()["prompt_learning"]["added"] == ["whiteboard"]
        state = (await client.get("/api/state")).json()
        assert state["detector_prompts"] == ["person", "whiteboard"]
        assert state["detector_learned_prompts"] == ["whiteboard"]
        assert applied == [
            ["person", "tripod"],
            ["person"],
            ["person", "whiteboard"],
        ]
    finally:
        release_first_update.set()
        await concurrent_client.aclose()
        await client.aclose()
        await lifespan.__aexit__(None, None, None)
