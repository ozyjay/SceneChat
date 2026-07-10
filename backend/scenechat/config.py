"""Validated application configuration."""

from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """SceneChat settings loaded from environment variables and an optional `.env`."""

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    scenechat_mode: str = "development"
    backend_host: str = "127.0.0.1"
    backend_port: int = Field(default=8900, ge=1024, le=65535)
    public_frontend_port: int = Field(default=3900, ge=1024, le=65535)

    camera_device: int = Field(default=0, ge=0)
    camera_width: int = Field(default=1280, ge=320, le=7680)
    camera_height: int = Field(default=720, ge=240, le=4320)
    camera_fps: int = Field(default=30, ge=1, le=120)

    detector_backend: str = "replay"
    detector_model: str = ""
    detector_confidence: float = Field(default=0.40, ge=0, le=1)

    vision_provider: str = "mock"
    vllm_base_url: str = "http://127.0.0.1:8000/v1"
    vllm_api_key: str = "local"
    vllm_model: str = "google/gemma-4-E2B-it"
    vision_request_timeout_seconds: float = Field(default=20, gt=0, le=120)
    auto_analyse: bool = False
    auto_analyse_interval_seconds: float = Field(default=5, ge=3, le=60)

    store_frames: bool = False
    store_video: bool = False
    allow_external_vision_provider: bool = False
    replay_scenario: str = "demo_booth"

    @field_validator("scenechat_mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        allowed = {"development", "live", "detector-only", "mock", "replay"}
        if value not in allowed:
            raise ValueError(f"must be one of {sorted(allowed)}")
        return value

    @field_validator("vision_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        if value not in {"mock", "replay", "vllm"}:
            raise ValueError("must be mock, replay, or vllm")
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
        if self.backend_port in {3000, 5173, 8000, 8080}:
            raise ValueError("backend port must use the reserved SceneChat range")
        if self.vision_provider == "vllm":
            parsed = urlparse(self.vllm_base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("VLLM_BASE_URL must be an HTTP(S) URL")
            try:
                local = ip_address(parsed.hostname).is_loopback
            except ValueError:
                local = parsed.hostname == "localhost"
            if not local and not self.allow_external_vision_provider:
                raise ValueError(
                    "external vision provider blocked; set "
                    "ALLOW_EXTERNAL_VISION_PROVIDER=true only after approval and signage"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
