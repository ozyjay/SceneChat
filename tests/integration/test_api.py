import httpx
import pytest

from scenechat.config import Settings
from scenechat.main import create_app


def _settings():
    return Settings(
        scenechat_mode="replay",
        vision_provider="replay",
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
        assert (await client.get("/")).status_code == 200
        assert (await client.get("/staff")).status_code == 200
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
        disabled = await client.post("/api/privacy", json={"enabled": False})
        assert disabled.json()["privacy_screen"] is False
        assert (await client.get("/api/frame")).status_code == 200


@pytest.mark.anyio
async def test_detector_only_disables_analysis():
    async with AppClient() as client:
        assert (await client.post("/api/mode", json={"mode": "detector-only"})).status_code == 200
        response = await client.post("/api/analyse", json={"question": "Describe the scene."})
        assert response.status_code == 409
