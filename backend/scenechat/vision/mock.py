"""Deterministic offline scene-analysis provider."""

from scenechat.models import ObjectDescription, SceneAnalysis
from scenechat.vision.base import AVAILABLE_STATUS, ProviderStatus


class MockVisionProvider:
    name = "mock"

    async def health(self) -> ProviderStatus:
        return AVAILABLE_STATUS

    async def analyse_scene(self, image: bytes, question: str) -> SceneAnalysis:
        summaries = {
            "What objects can you see?": (
                "The prepared scene shows a display, a laptop, a microphone and two people."
            ),
            "Describe the scene.": (
                "This appears to be a university demonstration booth. Two people are near "
                "a display, with a laptop and microphone on the table."
            ),
            "What is happening here?": (
                "Two people appear to be taking part in a demonstration near a display and table."
            ),
            "Which objects are closest to the camera?": (
                "The table and microphone appear closest, followed by the open laptop."
            ),
            "Describe this scene for someone who cannot see it.": (
                "A bright demonstration area contains a large display behind a table. Two people "
                "stand nearby, and an open laptop and microphone are visible in front."
            ),
            "What might this equipment be used for?": (
                "The display, laptop and microphone might be used for a public technology demonstration."
            ),
            "What details might the system be uncertain about?": (
                "The purpose of the equipment and the activity are interpretations; small background "
                "objects are also unclear."
            ),
        }
        return SceneAnalysis(
            summary=summaries.get(question, summaries["Describe the scene."]),
            objects=[
                ObjectDescription(
                    label="laptop",
                    description="An open laptop is visible on the table.",
                    approximate_location="centre foreground",
                ),
                ObjectDescription(
                    label="display",
                    description="A large display is visible behind the table.",
                    approximate_location="centre background",
                ),
            ],
            relationships=["Two people are standing near the demonstration table."],
            uncertainties=["The exact purpose of small background items is unclear."],
            provider=self.name,
        )
