"""Object detector interface."""

from typing import Any, Protocol

from scenechat.models import Detection


class Detector(Protocol):
    name: str

    def detect(self, frame: Any) -> list[Detection]:
        """Run one detection pass on an OpenCV BGR frame."""


class NoopDetector:
    name = "none"

    def detect(self, frame: Any) -> list[Detection]:
        return []

