import pytest

from scenechat.config import Settings
from scenechat.detection import NoopDetector, create_detector
from scenechat.vision.mock import MockVisionProvider


def test_replay_detector_configuration_needs_no_optional_dependency():
    detector = create_detector(Settings(detector_backend="replay"))
    assert isinstance(detector, NoopDetector)


@pytest.mark.anyio
async def test_mock_provider_is_deterministic_and_question_aware():
    provider = MockVisionProvider()
    description = await provider.analyse_scene(b"unused", "Describe the scene.")
    objects = await provider.analyse_scene(b"unused", "What objects can you see?")
    assert description.summary != objects.summary
    assert description.provider == "mock"
