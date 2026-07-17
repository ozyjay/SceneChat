"""Object detector interface."""

from typing import Any, Protocol

from scenechat.models import Detection


def normalise_box(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    frame_width: int,
    frame_height: int,
) -> tuple[float, float, float, float] | None:
    """Clamp pixel coordinates to the frame and reject empty boxes."""
    left = min(1.0, max(0.0, x1 / frame_width))
    top = min(1.0, max(0.0, y1 / frame_height))
    right = min(1.0, max(0.0, x2 / frame_width))
    bottom = min(1.0, max(0.0, y2 / frame_height))
    if right <= left or bottom <= top:
        return None
    return left, top, right - left, bottom - top


class Detector(Protocol):
    name: str

    def detect(self, frame: Any) -> list[Detection]:
        """Run one detection pass on an OpenCV BGR frame."""


class NoopDetector:
    name = "none"

    def detect(self, frame: Any) -> list[Detection]:
        return []
