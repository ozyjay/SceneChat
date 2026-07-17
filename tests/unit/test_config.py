import pytest
from pydantic import ValidationError

from scenechat.config import Settings


def test_safe_defaults_do_not_store_frames():
    settings = Settings(_env_file=None)
    assert settings.store_frames is False
    assert settings.store_video is False
    assert settings.scenechat_host == "127.0.0.1"
    assert settings.scenechat_port == 3700
    assert settings.model_provider == "fallback"
    assert settings.model_fallback_mode == "replay"
    assert settings.vision_max_tokens == 350


@pytest.mark.parametrize("field", ["store_frames", "store_video"])
def test_storage_is_rejected(field):
    with pytest.raises(ValidationError, match="storage are not supported"):
        Settings(**{field: True})


@pytest.mark.parametrize("port", [3600, 8000, 8610, 8650, 8699, 11434])
def test_modeldeck_management_legacy_and_worker_ports_are_rejected(port):
    with pytest.raises(ValidationError, match="gateway on port 8600"):
        Settings(modeldeck_url=f"http://127.0.0.1:{port}")


@pytest.mark.parametrize(
    "url",
    [
        "http://0.0.0.0:8600",
        "https://example.invalid:8600",
        "http://127.0.0.1:8600/v1",
    ],
)
def test_modeldeck_non_loopback_and_non_gateway_urls_are_rejected(url):
    with pytest.raises(ValidationError, match="loopback ModelDeck gateway"):
        Settings(modeldeck_url=url)


def test_modeldeck_gateway_is_allowed():
    settings = Settings(
        model_provider="modeldeck", modeldeck_url="http://127.0.0.1:8600"
    )
    assert settings.modeldeck_model == "scenechat-vision"


def test_modeldeck_model_must_use_scenechat_vision_alias():
    with pytest.raises(ValidationError, match="scenechat-vision gateway alias"):
        Settings(modeldeck_model="text-diffusion")


@pytest.mark.parametrize("value", [0, 127, 513])
def test_vision_output_limit_has_safe_bounds(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, vision_max_tokens=value)


def test_detector_model_options_are_an_explicit_allowlist():
    settings = Settings(
        _env_file=None,
        detector_backend="auto",
        detector_model="/models/yolov8s-worldv2.pt",
        detector_text_encoder="/models/mobileclip2_b.ts",
        detector_yoloworld_clip="/models/ViT-B-32.pt",
        detector_model_options={
            "yoloworld-s": "/models/yolov8s-worldv2.pt",
            "yoloe-26s": "/models/yoloe-26s-seg.pt",
        },
    )

    assert settings.available_detector_models() == {
        "yoloworld-s": "/models/yolov8s-worldv2.pt",
        "yoloe-26s": "/models/yoloe-26s-seg.pt",
    }
    assert settings.detector_model_id() == "yoloworld-s"


def test_detector_model_must_be_in_configured_options():
    with pytest.raises(ValidationError, match="present in DETECTOR_MODEL_OPTIONS"):
        Settings(
            _env_file=None,
            detector_backend="yoloworld",
            detector_model="/models/unlisted.pt",
            detector_yoloworld_clip="/models/ViT-B-32.pt",
            detector_model_options={"yoloworld-s": "/models/yolov8s-worldv2.pt"},
        )


@pytest.mark.parametrize("backend", ["none", "replay"])
def test_offline_detector_modes_ignore_stale_live_model_selection(backend):
    settings = Settings(
        _env_file=None,
        detector_backend=backend,
        detector_model="/models/stale.pt",
        detector_model_options={"yoloe-26s": "/models/yoloe-26s-seg.pt"},
    )

    assert settings.detector_backend == backend


def test_yoloe_requires_an_explicit_local_text_encoder():
    with pytest.raises(ValidationError, match="DETECTOR_TEXT_ENCODER is required"):
        Settings(_env_file=None, detector_backend="yoloe")

    with pytest.raises(ValidationError, match="DETECTOR_TEXT_ENCODER is required"):
        Settings(
            _env_file=None,
            detector_backend="auto",
            detector_model="/models/yoloe-26s-seg.pt",
        )


def test_yoloworld_requires_explicit_local_clip_weights():
    with pytest.raises(ValidationError, match="DETECTOR_YOLOWORLD_CLIP is required"):
        Settings(
            _env_file=None,
            detector_backend="yoloworld",
            detector_model="/models/yolov8s-worldv2.pt",
        )


def test_standard_yolo_backend_and_checkpoints_are_rejected():
    with pytest.raises(ValidationError, match="must be auto, none, replay"):
        Settings(_env_file=None, detector_backend="yolo")

    with pytest.raises(ValidationError, match="must be YOLOE or YOLO-World"):
        Settings(
            _env_file=None,
            detector_backend="auto",
            detector_model="/models/yolo11s.pt",
        )


@pytest.mark.parametrize("value", [0, 0.49, 30.1])
def test_detector_rate_limit_has_safe_bounds(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, detector_max_fps=value)


def test_detector_prompts_must_be_in_approved_vocabulary():
    with pytest.raises(ValidationError, match="DETECTOR_PROMPTS must be present"):
        Settings(
            _env_file=None,
            detector_prompts=["person", "visitor identity"],
            detector_prompt_allowlist=["person"],
        )


@pytest.mark.parametrize("port", [3600, 8000, 8600, 8610, 8699])
def test_scenechat_must_own_only_port_3700(port):
    with pytest.raises(ValidationError, match="SCENECHAT_PORT must be 3700"):
        Settings(scenechat_port=port)
