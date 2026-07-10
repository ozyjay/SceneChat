"""Detector selection kept independent from camera capture."""

from scenechat.config import Settings
from scenechat.detection.base import Detector, NoopDetector


def create_detector(settings: Settings) -> Detector:
    backend = settings.detector_backend
    if backend in {"none", "replay"}:
        return NoopDetector()
    if backend == "auto" and not settings.detector_model:
        return NoopDetector()
    if backend in {"auto", "yolo"}:
        from scenechat.detection.yolo import YoloDetector

        return YoloDetector(settings.detector_model, settings.detector_confidence)
    raise ValueError(f"unsupported detector backend: {backend}")

