import asyncio

import pytest

from scenechat.models import AppState, Detection, SceneAnalysis
from scenechat.services.analysis import AnalysisService
from scenechat.services.state import StateStore


class ControlledProvider:
    name = "mock"

    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def health(self):
        return True

    async def analyse_scene(self, image, question):
        self.started.set()
        await self.release.wait()
        return SceneAnalysis(summary="A result that became stale.", provider=self.name)


@pytest.mark.anyio
async def test_reset_clears_generated_text_and_increments_generation():
    store = StateStore(AppState(scene_analysis=SceneAnalysis(summary="Old result")))
    before = await store.snapshot()
    result = await store.reset([])
    assert result.scene_analysis is None
    assert result.generation == before.generation + 1
    assert result.selected_question == "Describe the scene."


@pytest.mark.anyio
async def test_result_started_before_reset_is_rejected():
    provider = ControlledProvider()
    store = StateStore(AppState(provider="mock"))
    service = AnalysisService(store, {"mock": provider}, {"Describe the scene."}, timeout=2)
    task = asyncio.create_task(service.analyse(b"image", "Describe the scene."))
    await provider.started.wait()
    await store.reset([])
    provider.release.set()
    _, applied = await task
    assert applied is False
    assert (await store.snapshot()).scene_analysis is None


@pytest.mark.anyio
async def test_provider_failure_degrades_vllm_to_detector_only():
    class FailingProvider:
        async def analyse_scene(self, image, question):
            raise RuntimeError("raw internal detail")

    store = StateStore(AppState(provider="vllm", internal_mode="live", mode="Combined"))
    service = AnalysisService(store, {"vllm": FailingProvider()}, {"Describe the scene."}, 1)
    with pytest.raises(RuntimeError, match="detector-only operation"):
        await service.analyse(b"image", "Describe the scene.")
    state = await store.snapshot()
    assert state.internal_mode == "detector-only"
    assert state.mode == "Detector only"
    assert "raw internal detail" not in state.staff_error


@pytest.mark.anyio
async def test_provider_timeout_does_not_leave_analysis_running():
    class SlowProvider:
        async def analyse_scene(self, image, question):
            await asyncio.sleep(1)

    store = StateStore(AppState(provider="vllm", internal_mode="live", mode="Combined"))
    service = AnalysisService(store, {"vllm": SlowProvider()}, {"Describe the scene."}, 0.01)
    with pytest.raises(RuntimeError, match="detector-only operation"):
        await service.analyse(b"image", "Describe the scene.")
    state = await store.snapshot()
    assert state.analysis_in_progress is False
    assert state.provider_available is False
