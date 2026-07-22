"""Concurrency-safe, resettable public application state."""

import asyncio
from collections.abc import Callable

from scenechat.models import AppState, Detection, SceneAnalysis


class StateStore:
    def __init__(self, initial: AppState):
        self._state = initial
        self._lock = asyncio.Lock()
        self.changed = asyncio.Condition()

    async def snapshot(self) -> AppState:
        async with self._lock:
            return self._state.model_copy(deep=True)

    async def mutate(self, change: Callable[[AppState], None]) -> AppState:
        async with self._lock:
            change(self._state)
            self._state.revision += 1
            result = self._state.model_copy(deep=True)
        async with self.changed:
            self.changed.notify_all()
        return result

    async def reset(self, detections: list[Detection]) -> AppState:
        def change(state: AppState) -> None:
            state.generation += 1
            state.scene_analysis = None
            state.selected_question = "Describe the scene."
            state.detections = detections
            state.analysis_in_progress = False
            state.last_model_latency_ms = None
            state.staff_error = None
            state.detector_prompts = list(state.detector_prompt_baseline)
            state.detector_learned_prompts = []
            state.detector_prompt_safety_rejections = 0
            state.detector_prompt_rejection_reasons = {}
            state.detector_prompt_capacity_skips = 0

        return await self.mutate(change)

    async def set_analysis(self, analysis: SceneAnalysis, generation: int) -> bool:
        applied = False

        def change(state: AppState) -> None:
            nonlocal applied
            if state.generation != generation:
                return
            state.scene_analysis = analysis
            state.last_model_latency_ms = analysis.latency_ms
            state.analysis_in_progress = False
            state.provider_available = True
            state.provider_status_code = "available"
            state.provider_status_message = (
                "ModelDeck scenechat-vision is ready with image_input and "
                "structured_output."
                if analysis.provider == "modeldeck"
                else "Provider is available."
            )
            state.staff_error = None
            applied = True

        await self.mutate(change)
        return applied
