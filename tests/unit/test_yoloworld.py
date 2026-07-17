import sys
import os
from types import ModuleType, SimpleNamespace

import pytest

from scenechat.config import Settings
from scenechat.detection.factory import create_detector
from scenechat.detection.yoloworld import YoloWorldDetector


class FakeCoordinates:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class FakeYoloWorldModel:
    def __init__(self):
        self.class_calls = []
        self.cache_calls = []
        self.results = []
        self.fail_class_update = False

    def set_classes(self, prompts):
        if self.fail_class_update:
            raise RuntimeError("prompt encoding failed")
        self.class_calls.append(list(prompts))
        self.cache_calls.append(os.environ.get("CLIP_CACHE_DIR"))

    def predict(self, frame, **kwargs):
        assert kwargs == {"conf": 0.45, "verbose": False}
        return self.results


def build_detector(monkeypatch, tmp_path):
    model_path = tmp_path / "yolov8s-worldv2.pt"
    clip_path = tmp_path / "ViT-B-32.pt"
    model_path.touch()
    clip_path.touch()
    model = FakeYoloWorldModel()
    ultralytics = ModuleType("ultralytics")
    ultralytics.YOLOWorld = lambda path: model
    monkeypatch.setitem(sys.modules, "ultralytics", ultralytics)
    detector = YoloWorldDetector(
        str(model_path), str(clip_path), 0.45, ["person", "camera"]
    )
    return detector, model, model_path, clip_path


def test_yoloworld_applies_prompts_and_skips_unchanged_updates(monkeypatch, tmp_path):
    monkeypatch.delenv("CLIP_CACHE_DIR", raising=False)
    detector, model, _, _ = build_detector(monkeypatch, tmp_path)

    assert detector.prompts == ["person", "camera"]
    assert model.class_calls == [["person", "camera"]]
    assert model.cache_calls == [str(tmp_path)]
    assert "CLIP_CACHE_DIR" not in os.environ

    detector.set_prompts(["person", "camera"])

    assert model.class_calls == [["person", "camera"]]


def test_yoloworld_prompt_update_preserves_public_state_on_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("CLIP_CACHE_DIR", "original-cache")
    detector, model, _, _ = build_detector(monkeypatch, tmp_path)
    model.fail_class_update = True

    with pytest.raises(RuntimeError, match="prompt encoding failed"):
        detector.set_prompts(["book"])

    assert detector.prompts == ["person", "camera"]
    assert os.environ["CLIP_CACHE_DIR"] == "original-cache"


def test_yoloworld_returns_normalised_detections(monkeypatch, tmp_path):
    detector, model, _, _ = build_detector(monkeypatch, tmp_path)
    box = SimpleNamespace(
        xyxy=[FakeCoordinates([10, 20, 70, 80])], cls=[0], conf=[0.9]
    )
    model.results = [SimpleNamespace(boxes=[box], names={0: "person"})]

    detections = detector.detect(SimpleNamespace(shape=(100, 100, 3)))

    assert detections[0].model_dump() == {
        "label": "person",
        "confidence": 0.9,
        "x": 0.1,
        "y": 0.2,
        "width": 0.6,
        "height": 0.6000000000000001,
        "tracking_id": None,
    }


def test_factory_builds_yoloworld_with_validated_settings(monkeypatch, tmp_path):
    detector, _, model_path, clip_path = build_detector(monkeypatch, tmp_path)
    constructor_calls = []
    monkeypatch.setattr(
        "scenechat.detection.yoloworld.YoloWorldDetector",
        lambda *args: constructor_calls.append(args) or detector,
    )
    settings = Settings(
        _env_file=None,
        detector_backend="yoloworld",
        detector_model=str(model_path),
        detector_yoloworld_clip=str(clip_path),
        detector_confidence=0.6,
        detector_prompts=["person"],
        detector_prompt_allowlist=["person"],
    )

    selected = create_detector(settings)

    assert selected is detector
    assert constructor_calls == [
        (str(model_path), str(clip_path), 0.6, ["person"])
    ]
