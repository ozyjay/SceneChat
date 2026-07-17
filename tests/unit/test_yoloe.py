import sys
from contextlib import nullcontext
from types import ModuleType, SimpleNamespace

import pytest

from scenechat.config import Settings
from scenechat.detection.factory import create_detector
from scenechat.detection.yoloe import YoloEDetector


class FakeFeatures:
    def __init__(self):
        self.reshape_args = None

    def reshape(self, *shape):
        self.reshape_args = shape
        return self


class FakeEncoder:
    instances = []

    def __init__(self, device, path):
        self.device = device
        self.path = path
        self.features = FakeFeatures()
        self.tokens = None
        self.__class__.instances.append(self)

    def tokenize(self, prompts):
        self.tokens = list(prompts)
        return "tokens"

    def encode_text(self, tokens):
        assert tokens == "tokens"
        return self.features


class FakeHead:
    def get_tpe(self, features):
        return ("embeddings", features)


class FakeInnerModel:
    def __init__(self):
        self.model = [FakeHead()]

    def parameters(self):
        return iter([SimpleNamespace(device="test-device")])


class FakeYoloEModel:
    def __init__(self):
        self.model = FakeInnerModel()
        self.class_calls = []
        self.results = []
        self.fail_class_update = False

    def set_classes(self, prompts, embeddings):
        if self.fail_class_update:
            raise RuntimeError("encoding failed")
        self.class_calls.append((list(prompts), embeddings))

    def predict(self, frame, **kwargs):
        assert kwargs == {"conf": 0.4, "verbose": False}
        return self.results


class FakeCoordinates:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


def install_fake_yoloe_dependencies(monkeypatch, model):
    ultralytics = ModuleType("ultralytics")
    ultralytics.YOLOE = lambda path: model
    text_model = ModuleType("ultralytics.nn.text_model")
    text_model.MobileCLIPTS = FakeEncoder
    torch = ModuleType("torch")
    torch.inference_mode = nullcontext
    monkeypatch.setitem(sys.modules, "ultralytics", ultralytics)
    monkeypatch.setitem(sys.modules, "ultralytics.nn.text_model", text_model)
    monkeypatch.setitem(sys.modules, "torch", torch)


def build_detector(monkeypatch, tmp_path):
    model_path = tmp_path / "yoloe-26s-seg.pt"
    encoder_path = tmp_path / "mobileclip2_b.ts"
    model_path.touch()
    encoder_path.touch()
    model = FakeYoloEModel()
    install_fake_yoloe_dependencies(monkeypatch, model)
    detector = YoloEDetector(
        str(model_path), str(encoder_path), 0.4, ["person", "camera"]
    )
    return detector, model, model_path, encoder_path


def test_yoloe_encodes_prompts_locally_and_skips_unchanged_updates(
    monkeypatch, tmp_path
):
    FakeEncoder.instances.clear()
    detector, model, _, encoder_path = build_detector(monkeypatch, tmp_path)

    assert detector.prompts == ["person", "camera"]
    assert len(model.class_calls) == 1
    encoder = FakeEncoder.instances[0]
    assert encoder.device == "test-device"
    assert encoder.path == str(encoder_path)
    assert encoder.tokens == ["person", "camera"]
    assert encoder.features.reshape_args == (1, 2, -1)

    detector.set_prompts(["person", "camera"])

    assert len(model.class_calls) == 1
    assert len(FakeEncoder.instances) == 1


def test_yoloe_prompt_update_is_atomic_when_encoding_application_fails(
    monkeypatch, tmp_path
):
    detector, model, _, _ = build_detector(monkeypatch, tmp_path)
    model.fail_class_update = True

    with pytest.raises(RuntimeError, match="encoding failed"):
        detector.set_prompts(["book"])

    assert detector.prompts == ["person", "camera"]


def test_yoloe_clamps_boxes_and_rejects_boxes_outside_the_frame(monkeypatch, tmp_path):
    detector, model, _, _ = build_detector(monkeypatch, tmp_path)
    valid_box = SimpleNamespace(
        xyxy=[FakeCoordinates([-10, -5, 50, 40])], cls=[0], conf=[0.85]
    )
    outside_box = SimpleNamespace(
        xyxy=[FakeCoordinates([120, 10, 140, 30])], cls=[0], conf=[0.75]
    )
    model.results = [SimpleNamespace(boxes=[valid_box, outside_box], names={0: "person"})]
    frame = SimpleNamespace(shape=(100, 100, 3))

    detections = detector.detect(frame)

    assert len(detections) == 1
    assert detections[0].model_dump() == {
        "label": "person",
        "confidence": 0.85,
        "x": 0.0,
        "y": 0.0,
        "width": 0.5,
        "height": 0.4,
        "tracking_id": None,
    }


def test_factory_builds_yoloe_with_validated_settings(monkeypatch, tmp_path):
    detector, _, model_path, encoder_path = build_detector(monkeypatch, tmp_path)
    constructor_calls = []
    monkeypatch.setattr(
        "scenechat.detection.yoloe.YoloEDetector",
        lambda *args: constructor_calls.append(args) or detector,
    )
    settings = Settings(
        _env_file=None,
        detector_backend="yoloe",
        detector_model=str(model_path),
        detector_text_encoder=str(encoder_path),
        detector_confidence=0.55,
        detector_prompts=["person"],
        detector_prompt_allowlist=["person"],
    )

    selected = create_detector(settings)

    assert selected is detector
    assert constructor_calls == [
        (str(model_path), str(encoder_path), 0.55, ["person"])
    ]
