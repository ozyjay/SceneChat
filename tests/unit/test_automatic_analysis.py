import asyncio
from types import SimpleNamespace

import pytest

import scenechat.main as main_module
from scenechat.config import Settings
from scenechat.models import AppState, SceneAnalysis
from scenechat.services.analysis import AnalysisService
from scenechat.services.state import StateStore
from scenechat.vision.base import ProviderStatus


def test_automatic_question_is_curated_and_avoids_immediate_repeat(monkeypatch):
    questions = ["Describe the scene.", "What objects can you see?"]
    offered = []

    def choose(candidates):
        offered.extend(candidates)
        return candidates[0]

    monkeypatch.setattr(main_module.random, "choice", choose)

    selected = main_module._select_automatic_question(
        questions, "Describe the scene."
    )

    assert selected == "What objects can you see?"
    assert offered == ["What objects can you see?"]


def test_automatic_question_supports_a_single_curated_choice(monkeypatch):
    monkeypatch.setattr(main_module.random, "choice", lambda candidates: candidates[0])

    assert (
        main_module._select_automatic_question(
            ["Describe the scene."], "Describe the scene."
        )
        == "Describe the scene."
    )


def test_automatic_question_rejects_an_empty_curated_list():
    with pytest.raises(ValueError, match="At least one curated question"):
        main_module._select_automatic_question([], "Describe the scene.")


@pytest.mark.anyio
async def test_automatic_cooldown_starts_after_analysis_completes():
    fake_time = 0.0
    started_at = []
    second_started = asyncio.Event()
    original_sleep = asyncio.sleep

    async def advance_time(seconds):
        nonlocal fake_time
        fake_time += seconds
        await original_sleep(0)

    class SlowProvider:
        async def analyse_scene(self, image, question):
            nonlocal fake_time
            started_at.append(fake_time)
            fake_time += 7
            if len(started_at) == 2:
                second_started.set()
            return SceneAnalysis(summary="A stable prepared result.", provider="mock")

    store = StateStore(
        AppState(
            provider="mock",
            internal_mode="live",
            desired_mode="live",
            camera_running=True,
            auto_analyse=True,
            auto_analyse_interval_seconds=20,
        )
    )
    service = AnalysisService(
        store,
        {"mock": SlowProvider()},
        {"Describe the scene."},
        timeout=60,
    )
    app = SimpleNamespace(
        state=SimpleNamespace(
            state_store=store,
            camera=SimpleNamespace(latest_jpeg=lambda: b"image"),
            analysis=service,
            settings=Settings(
                _env_file=None,
                detector_backend="replay",
            ),
        )
    )

    scheduler = asyncio.create_task(
        main_module._automatic_analysis(
            app,
            monotonic=lambda: fake_time,
            sleep=advance_time,
        )
    )
    try:
        await asyncio.wait_for(second_started.wait(), timeout=1)
    finally:
        scheduler.cancel()
        with pytest.raises(asyncio.CancelledError):
            await scheduler

    assert started_at == [20.5, 47.5]


@pytest.mark.anyio
async def test_provider_recovery_restores_desired_mode():
    sleep_calls = 0

    async def stop_after_one_check(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise RuntimeError("stop test loop")

    class RecoveredProvider:
        async def health(self):
            return ProviderStatus(True, "available", "ModelDeck is ready.")

    store = StateStore(
        AppState(
            provider="modeldeck",
            provider_available=False,
            internal_mode="detector-only",
            desired_mode="live",
            mode="Detector only",
        )
    )
    app = SimpleNamespace(
        state=SimpleNamespace(
            state_store=store,
            providers={"modeldeck": RecoveredProvider()},
            settings=Settings(_env_file=None, detector_backend="replay"),
        )
    )

    with pytest.raises(RuntimeError, match="stop test loop"):
        await main_module._provider_recovery(
            app,
            sleep=stop_after_one_check,
            check_seconds=30,
        )

    state = await store.snapshot()
    assert state.provider_available is True
    assert state.internal_mode == "live"
    assert state.desired_mode == "live"
    assert state.mode == "Combined"
