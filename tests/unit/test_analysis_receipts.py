import asyncio

import pytest

from scenechat.models import AppState, SceneAnalysis
from scenechat.services.analysis import AnalysisService
from scenechat.services.state import StateStore


class Provider:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def analyse_scene(self, image, question):
        self.started.set()
        await self.release.wait()
        return SceneAnalysis(summary="A desk is visible.", provider="mock")


@pytest.mark.anyio
async def test_receipt_is_content_free_and_cancelled_request_releases_state():
    provider = Provider()
    state = StateStore(AppState())
    service = AnalysisService(state, {"mock": provider}, {"Describe the scene."}, 10)
    task = asyncio.create_task(service.analyse(b"non-visitor", "Describe the scene."))
    await provider.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not (await state.snapshot()).analysis_in_progress
    provider.release.set()
    analysis, applied = await service.analyse(b"non-visitor", "Describe the scene.")
    assert applied
    assert analysis.analysis_request_id
    assert analysis.application_elapsed_ms >= 0


@pytest.mark.anyio
async def test_reset_discards_receipt_with_stale_result():
    provider = Provider()
    state = StateStore(AppState())
    service = AnalysisService(state, {"mock": provider}, {"Describe the scene."}, 10)
    task = asyncio.create_task(service.analyse(b"non-visitor", "Describe the scene."))
    await provider.started.wait()
    await state.reset([])
    provider.release.set()
    _, applied = await task
    assert not applied
    assert (await state.snapshot()).scene_analysis is None
