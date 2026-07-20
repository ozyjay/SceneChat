"""Scene-analysis orchestration, timeout isolation, and stale-result rejection."""

import asyncio

from scenechat.services.state import StateStore
from scenechat.vision.base import VisionLanguageProvider, VisionProviderError


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
            provider_name = snapshot.provider
            provider = self.providers[provider_name]
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
                message = "Scene analysis is temporarily unavailable."

                current = await self.state.snapshot()
                if current.generation != generation or current.provider != provider_name:
                    raise RuntimeError(message) from exc

                if isinstance(exc, VisionProviderError):
                    status_code = exc.code
                    staff_message = exc.staff_message
                elif isinstance(exc, TimeoutError):
                    status_code = "timeout"
                    staff_message = "The scene-analysis request timed out."
                else:
                    status_code = "provider_error"
                    staff_message = message

                def degrade(state):
                    state.analysis_in_progress = False
                    state.provider_available = False
                    state.provider_status_code = status_code
                    state.provider_status_message = staff_message
                    state.staff_error = staff_message
                    if state.provider == "modeldeck":
                        state.internal_mode = "detector-only"
                        state.mode = (
                            "Live camera only"
                            if state.mode == "Live scene description"
                            else "Detector only"
                        )

                await self.state.mutate(degrade)
                raise RuntimeError(message) from exc
