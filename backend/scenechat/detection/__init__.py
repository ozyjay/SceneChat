"""Object detector adapters."""

from .base import Detector, NoopDetector
from .factory import create_detector

__all__ = ["Detector", "NoopDetector", "create_detector"]

