import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scenechat.config import Settings
from scenechat.detection import NoopDetector
from scenechat.main import _camera_monitor
from scenechat.models import AppState, Detection
from scenechat.services.camera import (
    MAX_CONSECUTIVE_READ_FAILURES,
    CameraService,
    discover_camera_devices,
)
from scenechat.services.state import StateStore


def add_video_node(
    root: Path, index: int, name: str, physical_device: Path, stream_index: int
) -> None:
    node = root / f"video{index}"
    node.mkdir()
    (node / "name").write_text(name, encoding="utf-8")
    (node / "index").write_text(str(stream_index), encoding="utf-8")
    (node / "device").symlink_to(physical_device, target_is_directory=True)


def test_camera_discovery_lists_names_and_groups_physical_device_nodes(tmp_path):
    sysfs = tmp_path / "video4linux"
    sysfs.mkdir()
    logi = tmp_path / "usb-logi"
    c920 = tmp_path / "usb-c920"
    logi.mkdir()
    c920.mkdir()
    add_video_node(sysfs, 0, "Logi 4K Stream Edition", logi, 0)
    add_video_node(sysfs, 1, "Logi 4K Stream Edition", logi, 1)
    add_video_node(sysfs, 2, "Logi 4K Stream Edition", logi, 0)
    add_video_node(sysfs, 4, "HD Pro Webcam C920", c920, 0)

    assert discover_camera_devices(sysfs) == [
        {
            "device": 0,
            "name": "Logi 4K Stream Edition",
            "label": "Logi 4K Stream Edition (video0)",
        },
        {
            "device": 4,
            "name": "HD Pro Webcam C920",
            "label": "HD Pro Webcam C920 (video4)",
        },
    ]
    assert discover_camera_devices(sysfs, selected_device=2)[0] == {
        "device": 2,
        "name": "Logi 4K Stream Edition",
        "label": "Logi 4K Stream Edition (video2)",
    }


@pytest.mark.anyio
async def test_start_switches_from_an_active_camera(monkeypatch):
    class RunningThread:
        def is_alive(self):
            return True

        def join(self, timeout=None):
            return None

    store = StateStore(AppState(camera_running=True, camera_device=0))
    service = CameraService(
        Settings(_env_file=None),
        NoopDetector(),
        store,
    )
    service._thread = RunningThread()
    monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace())
    monkeypatch.setattr(service, "_capture_loop", lambda device: service._ready.set())

    await service.start(4)

    state = await store.snapshot()
    assert state.camera_running is True
    assert state.camera_device == 4
    await service.stop()


@pytest.mark.anyio
async def test_start_clears_prepared_detections_from_live_camera(monkeypatch):
    prepared = Detection(
        label="prepared display",
        confidence=0.9,
        x=0.1,
        y=0.1,
        width=0.2,
        height=0.2,
    )
    store = StateStore(AppState(detections=[prepared]))
    service = CameraService(
        Settings(_env_file=None),
        NoopDetector(),
        store,
    )
    monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace())
    monkeypatch.setattr(service, "_capture_loop", lambda device: service._ready.set())

    await service.start(4)

    state = await store.snapshot()
    assert state.camera_running is True
    assert state.detections == []
    await service.stop()


def test_capture_stops_after_repeated_read_failures_and_clears_buffers(monkeypatch):
    class FailedCapture:
        def __init__(self):
            self.read_count = 0

        def isOpened(self):
            return True

        def set(self, property_id, value):
            return True

        def read(self):
            self.read_count += 1
            return False, None

        def release(self):
            return None

    capture = FailedCapture()
    cv2 = SimpleNamespace(
        VideoCapture=lambda device: capture,
        CAP_PROP_FRAME_WIDTH=1,
        CAP_PROP_FRAME_HEIGHT=2,
        CAP_PROP_FPS=3,
    )
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    monkeypatch.setattr("scenechat.services.camera.time.sleep", lambda seconds: None)
    service = CameraService(Settings(_env_file=None), NoopDetector(), StateStore(AppState()))
    service._latest_jpeg = b"stale frame"
    service._latest_detections = [
        Detection(label="person", confidence=0.9, x=0, y=0, width=0.5, height=0.5)
    ]

    service._capture_loop(0)

    assert service._start_error == (
        "Camera stopped returning frames; reconnect it before restarting."
    )
    assert service.latest_jpeg() is None
    assert service.latest_detections() == []
    assert service._fps == 0.0
    assert capture.read_count == MAX_CONSECUTIVE_READ_FAILURES


def test_capture_stops_and_clears_buffers_when_detector_fails(monkeypatch):
    class Frame:
        shape = (720, 1280, 3)

    class WorkingCapture:
        def isOpened(self):
            return True

        def set(self, property_id, value):
            return True

        def read(self):
            return True, Frame()

        def release(self):
            return None

    class FailedDetector:
        def detect(self, frame):
            raise RuntimeError("detector failed")

    cv2 = SimpleNamespace(
        VideoCapture=lambda device: WorkingCapture(),
        CAP_PROP_FRAME_WIDTH=1,
        CAP_PROP_FRAME_HEIGHT=2,
        CAP_PROP_FPS=3,
    )
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    service = CameraService(Settings(_env_file=None), FailedDetector(), StateStore(AppState()))
    service._latest_jpeg = b"stale frame"

    service._capture_loop(0)

    assert service._start_error == "Camera capture stopped after a camera or detector error."
    assert service.latest_jpeg() is None
    assert service.latest_detections() == []


def test_capture_limits_detector_runs_independently_of_camera_frames(monkeypatch):
    class Frame:
        shape = (720, 1280, 3)

    class Encoded:
        def tobytes(self):
            return b"jpeg"

    class FiniteCapture:
        def __init__(self):
            self.read_count = 0

        def isOpened(self):
            return self.read_count < 20

        def set(self, property_id, value):
            return True

        def read(self):
            self.read_count += 1
            return True, Frame()

        def release(self):
            return None

    class CountingDetector:
        def __init__(self):
            self.calls = 0

        def detect(self, frame):
            self.calls += 1
            return []

    class Clock:
        def __init__(self):
            self.value = 0.0

        def __call__(self):
            current = self.value
            self.value += 0.05
            return current

    capture = FiniteCapture()
    detector = CountingDetector()
    cv2 = SimpleNamespace(
        VideoCapture=lambda device: capture,
        CAP_PROP_FRAME_WIDTH=1,
        CAP_PROP_FRAME_HEIGHT=2,
        CAP_PROP_FPS=3,
        IMWRITE_JPEG_QUALITY=4,
        imencode=lambda extension, frame, options: (True, Encoded()),
    )
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    monkeypatch.setattr("scenechat.services.camera.time.perf_counter", Clock())
    service = CameraService(
        Settings(_env_file=None, detector_max_fps=2),
        detector,
        StateStore(AppState()),
    )

    service._capture_loop(0)

    assert capture.read_count == 20
    assert 1 < detector.calls < capture.read_count


@pytest.mark.anyio
async def test_camera_monitor_clears_public_state_after_capture_failure():
    prepared = Detection(
        label="stale person", confidence=0.9, x=0, y=0, width=0.5, height=0.5
    )
    store = StateStore(
        AppState(camera_running=True, detector_fps=24, detections=[prepared])
    )
    camera = SimpleNamespace(
        running=False,
        _start_error="Camera disconnected or became unavailable.",
    )
    monitor = asyncio.create_task(_camera_monitor(camera, store))
    await asyncio.sleep(0.3)
    monitor.cancel()
    with pytest.raises(asyncio.CancelledError):
        await monitor

    state = await store.snapshot()
    assert state.camera_running is False
    assert state.detector_fps == 0
    assert state.detections == []
    assert state.staff_error == "Camera disconnected or became unavailable."
