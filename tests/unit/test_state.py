import asyncio

import pytest

from scenechat.models import AppState, Detection, SceneAnalysis
from scenechat.services.analysis import AnalysisService
from scenechat.services.analysis import AnalysisBusy
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
async def test_analysis_service_allows_only_one_request_at_a_time():
    provider = ControlledProvider()
    store = StateStore(AppState(provider="mock"))
    service = AnalysisService(store, {"mock": provider}, {"Describe the scene."}, timeout=2)
    first = asyncio.create_task(service.analyse(b"image", "Describe the scene."))
    await provider.started.wait()

    with pytest.raises(AnalysisBusy):
        await service.analyse(b"newer-image", "Describe the scene.")

    provider.release.set()
    await first


@pytest.mark.anyio
async def test_provider_failure_degrades_modeldeck_without_switching_provider():
    class FailingProvider:
        async def analyse_scene(self, image, question):
            raise RuntimeError("raw internal detail")

    store = StateStore(AppState(provider="modeldeck", internal_mode="live", mode="Combined"))
    service = AnalysisService(
        store, {"modeldeck": FailingProvider()}, {"Describe the scene."}, 1
    )
    with pytest.raises(RuntimeError, match="temporarily unavailable"):
        await service.analyse(b"image", "Describe the scene.")
    state = await store.snapshot()
    assert state.internal_mode == "detector-only"
    assert state.mode == "Detector only"
    assert state.provider == "modeldeck"
    assert "raw internal detail" not in state.staff_error


@pytest.mark.anyio
async def test_provider_failure_preserves_previous_valid_result():
    class FailingProvider:
        async def analyse_scene(self, image, question):
            raise RuntimeError("raw internal detail")

    previous = SceneAnalysis(summary="Previous valid description.", provider="modeldeck")
    store = StateStore(
        AppState(
            provider="modeldeck",
            internal_mode="live",
            mode="Combined",
            scene_analysis=previous,
        )
    )
    service = AnalysisService(
        store, {"modeldeck": FailingProvider()}, {"Describe the scene."}, 1
    )

    with pytest.raises(RuntimeError, match="temporarily unavailable"):
        await service.analyse(b"image", "Describe the scene.")

    assert (await store.snapshot()).scene_analysis == previous


@pytest.mark.anyio
async def test_failure_made_stale_by_reset_does_not_degrade_recovered_state():
    class ControlledFailure:
        def __init__(self):
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def analyse_scene(self, image, question):
            self.started.set()
            await self.release.wait()
            raise RuntimeError("late failure")

    provider = ControlledFailure()
    store = StateStore(AppState(provider="modeldeck", internal_mode="live", mode="Combined"))
    service = AnalysisService(
        store, {"modeldeck": provider}, {"Describe the scene."}, 2
    )
    task = asyncio.create_task(service.analyse(b"image", "Describe the scene."))
    await provider.started.wait()
    await store.reset([])
    provider.release.set()

    with pytest.raises(RuntimeError, match="temporarily unavailable"):
        await task

    state = await store.snapshot()
    assert state.internal_mode == "live"
    assert state.provider_available is True
    assert state.staff_error is None


@pytest.mark.anyio
async def test_provider_failure_uses_camera_only_wording_without_detector():
    class FailingProvider:
        async def analyse_scene(self, image, question):
            raise RuntimeError("raw internal detail")

    store = StateStore(
        AppState(
            provider="modeldeck",
            internal_mode="live",
            mode="Live scene description",
        )
    )
    service = AnalysisService(
        store, {"modeldeck": FailingProvider()}, {"Describe the scene."}, 1
    )
    with pytest.raises(RuntimeError, match="temporarily unavailable"):
        await service.analyse(b"image", "Describe the scene.")
    state = await store.snapshot()
    assert state.internal_mode == "detector-only"
    assert state.mode == "Live camera only"


@pytest.mark.anyio
async def test_provider_timeout_does_not_leave_analysis_running():
    class SlowProvider:
        async def analyse_scene(self, image, question):
            await asyncio.sleep(1)

    store = StateStore(AppState(provider="modeldeck", internal_mode="live", mode="Combined"))
    service = AnalysisService(
        store, {"modeldeck": SlowProvider()}, {"Describe the scene."}, 0.01
    )
    with pytest.raises(RuntimeError, match="temporarily unavailable"):
        await service.analyse(b"image", "Describe the scene.")
    state = await store.snapshot()
    assert state.analysis_in_progress is False
    assert state.provider_available is False
