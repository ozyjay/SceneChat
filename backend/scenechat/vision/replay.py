"""Prepared-response provider for fully offline replay operation."""

from collections.abc import Mapping

from scenechat.models import SceneAnalysis


class ReplayVisionProvider:
    name = "replay"

    def __init__(self, responses: Mapping[str, SceneAnalysis]):
        self._responses = dict(responses)

    async def health(self) -> bool:
        return bool(self._responses)

    async def analyse_scene(self, image: bytes, question: str) -> SceneAnalysis:
        response = self._responses.get(question) or self._responses.get("Describe the scene.")
        if response is None:
            raise RuntimeError("Replay scenario has no scene response")
        return response.model_copy(update={"provider": self.name})

