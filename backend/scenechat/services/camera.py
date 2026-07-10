"""Bounded latest-frame camera service with no frame persistence."""

import asyncio
import threading
import time
from typing import Any

from scenechat.config import Settings
from scenechat.detection import Detector
from scenechat.models import Detection
from scenechat.services.state import StateStore


class CameraUnavailable(RuntimeError):
    pass


class CameraService:
    def __init__(self, settings: Settings, detector: Detector, state: StateStore):
        self.settings = settings
        self.detector = detector
        self.state = state
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._frame_lock = threading.Lock()
        self._latest_jpeg: bytes | None = None
        self._latest_detections: list[Detection] = []
        self._fps = 0.0
        self._ready = threading.Event()
        self._start_error: str | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def latest_jpeg(self) -> bytes | None:
        with self._frame_lock:
            return self._latest_jpeg

    def latest_detections(self) -> list[Detection]:
        with self._frame_lock:
            return list(self._latest_detections)

    async def start(self, device: int | None = None) -> None:
        if self.running:
            return
        try:
            import cv2  # noqa: F401
        except ImportError as exc:
            raise CameraUnavailable(
                "Camera support is not installed; use mock or replay mode."
            ) from exc
        self._stop.clear()
        self._ready.clear()
        self._start_error = None
        selected = self.settings.camera_device if device is None else device
        self._thread = threading.Thread(
            target=self._capture_loop, args=(selected,), daemon=True, name="scenechat-camera"
        )
        self._thread.start()
        opened = await asyncio.to_thread(self._ready.wait, 3)
        if not opened or self._start_error:
            self._stop.set()
            if self._thread:
                await asyncio.to_thread(self._thread.join, 1)
            self._thread = None
            raise CameraUnavailable(
                self._start_error or f"Camera device {selected} did not become ready."
            )
        await self.state.mutate(
            lambda state: (
                setattr(state, "camera_running", True),
                setattr(state, "camera_device", selected),
                setattr(state, "privacy_screen", False),
            )
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._thread = None
        with self._frame_lock:
            self._latest_jpeg = None
            self._latest_detections = []
        await self.state.mutate(
            lambda state: (
                setattr(state, "camera_running", False),
                setattr(state, "detector_fps", 0.0),
            )
        )

    def _capture_loop(self, device: int) -> None:
        import cv2

        capture = cv2.VideoCapture(device)
        if not capture.isOpened():
            self._start_error = f"Camera device {device} could not be opened."
            self._ready.set()
            capture.release()
            return
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.camera_width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.camera_height)
        capture.set(cv2.CAP_PROP_FPS, self.settings.camera_fps)
        frames = 0
        window_started = time.perf_counter()
        self._ready.set()
        try:
            while not self._stop.is_set() and capture.isOpened():
                ok, frame = capture.read()
                if not ok:
                    time.sleep(0.1)
                    continue
                detections = self.detector.detect(frame)
                encoded_ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if not encoded_ok:
                    continue
                frames += 1
                elapsed = time.perf_counter() - window_started
                if elapsed >= 1:
                    self._fps = frames / elapsed
                    frames = 0
                    window_started = time.perf_counter()
                with self._frame_lock:
                    # One latest frame only: older frames are dropped rather than queued.
                    self._latest_jpeg = encoded.tobytes()
                    self._latest_detections = detections
        except Exception:
            self._start_error = "Camera capture stopped after an internal camera or detector error."
        finally:
            self._ready.set()
            capture.release()
