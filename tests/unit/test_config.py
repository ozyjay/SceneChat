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


@pytest.mark.parametrize("port", [3600, 8000, 8600, 8610, 8699])
def test_scenechat_must_own_only_port_3700(port):
    with pytest.raises(ValidationError, match="SCENECHAT_PORT must be 3700"):
        Settings(scenechat_port=port)
