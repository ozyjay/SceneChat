import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scenechat.config import Settings
from scenechat.detection import NoopDetector
from scenechat.models import AppState, Detection
from scenechat.services.camera import CameraService, discover_camera_devices
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
