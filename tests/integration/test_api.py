import httpx
import pytest

from scenechat.config import Settings
from scenechat.main import create_app


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
        assert 'id="operator-controls"' in public.text
        assert 'id="cameraChoices"' in public.text
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
async def test_detector_only_disables_analysis():
    async with AppClient() as client:
        assert (await client.post("/api/mode", json={"mode": "detector-only"})).status_code == 200
        response = await client.post("/api/analyse", json={"question": "Describe the scene."})
        assert response.status_code == 409


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
