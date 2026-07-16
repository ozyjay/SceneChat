"""Validated application configuration."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[2]
SCENECHAT_PORT = 3700
MODELDECK_GATEWAY_PORT = 8600


class Settings(BaseSettings):
    """SceneChat settings loaded from environment variables and an optional `.env`."""

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    scenechat_mode: str = "development"
    scenechat_host: str = "127.0.0.1"
    scenechat_port: int = Field(default=SCENECHAT_PORT, ge=1024, le=65535)

    camera_device: int = Field(default=0, ge=0)
    camera_width: int = Field(default=1280, ge=320, le=7680)
    camera_height: int = Field(default=720, ge=240, le=4320)
    camera_fps: int = Field(default=30, ge=1, le=120)

    detector_backend: str = "replay"
    detector_model: str = ""
    detector_confidence: float = Field(default=0.40, ge=0, le=1)

    model_provider: str = "fallback"
    modeldeck_url: str = "http://127.0.0.1:8600"
    modeldeck_api_key: str = ""
    modeldeck_model: str = "scenechat-vision"
    model_fallback_mode: str = "replay"
    vision_request_timeout_seconds: float = Field(default=20, gt=0, le=120)
    auto_analyse: bool = False
    auto_analyse_interval_seconds: float = Field(default=5, ge=3, le=60)

    store_frames: bool = False
    store_video: bool = False
    replay_scenario: str = "demo_booth"

    @field_validator("scenechat_mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        allowed = {"development", "live", "detector-only", "mock", "replay"}
        if value not in allowed:
            raise ValueError(f"must be one of {sorted(allowed)}")
        return value

    @field_validator("model_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        if value not in {"modeldeck", "replay", "fallback", "mock"}:
            raise ValueError("must be modeldeck, replay, fallback, or mock")
        return value

    @field_validator("model_fallback_mode")
    @classmethod
    def validate_fallback_mode(cls, value: str) -> str:
        if value != "replay":
            raise ValueError("must be replay")
        return value

    @field_validator("detector_backend")
    @classmethod
    def validate_detector(cls, value: str) -> str:
        if value not in {"auto", "none", "replay", "yolo"}:
            raise ValueError("must be auto, none, replay, or yolo")
        return value

    @model_validator(mode="after")
    def apply_safety_rules(self) -> "Settings":
        if self.store_frames or self.store_video:
            raise ValueError("visitor frame and video storage are not supported")
        if self.scenechat_port != SCENECHAT_PORT:
            raise ValueError(f"SCENECHAT_PORT must be {SCENECHAT_PORT}")

        parsed = urlparse(self.modeldeck_url)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.port != MODELDECK_GATEWAY_PORT
            or parsed.path not in {"", "/"}
            or parsed.params
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError(
                "MODELDECK_URL must be the loopback ModelDeck gateway on port "
                f"{MODELDECK_GATEWAY_PORT}"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
