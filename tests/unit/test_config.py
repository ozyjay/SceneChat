import pytest
from pydantic import ValidationError

from scenechat.config import Settings


def test_safe_defaults_do_not_store_frames():
    settings = Settings()
    assert settings.store_frames is False
    assert settings.store_video is False
    assert settings.backend_port == 8900


@pytest.mark.parametrize("field", ["store_frames", "store_video"])
def test_storage_is_rejected(field):
    with pytest.raises(ValidationError, match="storage are not supported"):
        Settings(**{field: True})


def test_external_provider_is_blocked_by_default():
    with pytest.raises(ValidationError, match="external vision provider blocked"):
        Settings(vision_provider="vllm", vllm_base_url="https://example.invalid/v1")


def test_local_vllm_is_allowed():
    settings = Settings(vision_provider="vllm", vllm_base_url="http://127.0.0.1:8000/v1")
    assert settings.vllm_model == "google/gemma-4-E2B-it"

