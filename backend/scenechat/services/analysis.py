"""Scene-analysis orchestration, timeout isolation, and stale-result rejection."""

import asyncio

from scenechat.services.state import StateStore
from scenechat.vision.base import VisionLanguageProvider


class AnalysisBusy(RuntimeError):
    pass


class AnalysisService:
    def __init__(
        self,
        state: StateStore,
        providers: dict[str, VisionLanguageProvider],
        questions: set[str],
        timeout: float,
    ):
        self.state = state
        self.providers = providers
        self.questions = questions
        self.timeout = timeout
        self._lock = asyncio.Lock()

    async def analyse(self, image: bytes, question: str):
        if question not in self.questions:
            raise ValueError("Only curated questions are accepted")
        if self._lock.locked():
            raise AnalysisBusy("A scene analysis is already running")
        async with self._lock:
            snapshot = await self.state.snapshot()
            generation = snapshot.generation
            provider = self.providers[snapshot.provider]
            await self.state.mutate(
                lambda state: (
                    setattr(state, "analysis_in_progress", True),
                    setattr(state, "selected_question", question),
                    setattr(state, "staff_error", None),
                )
            )
            try:
                analysis = await asyncio.wait_for(
                    provider.analyse_scene(image, question), timeout=self.timeout
                )
                applied = await self.state.set_analysis(analysis, generation)
                return analysis, applied
            except Exception as exc:
                message = "Scene analysis failed; detector-only operation remains available."

                def degrade(state):
                    state.analysis_in_progress = False
                    state.provider_available = False
                    state.staff_error = message
                    if state.provider == "vllm":
                        state.internal_mode = "detector-only"
                        state.mode = "Detector only"

                await self.state.mutate(degrade)
                raise RuntimeError(message) from exc
