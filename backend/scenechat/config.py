"""Validated application configuration."""

import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[2]
SCENECHAT_PORT = 3700
MODELDECK_GATEWAY_PORT = 8600
MODELDECK_MODEL_ALIAS = "scenechat-vision"
MODELDECK_PROTOCOL_CONTRACT = "scene-analysis-v1"
MODELDECK_REQUIRED_CAPABILITIES = ("image_input", "structured_output")
DEFAULT_DETECTOR_PROMPTS = [
    "person",
    "computer mouse",
    "keyboard",
    "laptop",
    "monitor",
]
DEFAULT_DETECTOR_PROMPT_ALLOWLIST = DEFAULT_DETECTOR_PROMPTS + [
    "mobile phone",
    "camera",
    "microphone",
    "bottle",
    "cup",
    "chair",
    "table",
    "book",
    "backpack",
    "cabinet",
    "headphones",
    "pen",
    "paper",
    "glasses",
    "potted plant",
]


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
    detector_model_options: dict[str, str] = Field(default_factory=dict)
    detector_confidence: float = Field(default=0.40, ge=0, le=1)
    detector_max_fps: float = Field(default=5, ge=0.5, le=30)
    detector_text_encoder: str = ""
    detector_yoloworld_clip: str = ""
    detector_prompts: list[str] = Field(
        default_factory=lambda: list(DEFAULT_DETECTOR_PROMPTS), min_length=1, max_length=20
    )
    detector_prompt_allowlist: list[str] = Field(
        default_factory=lambda: list(DEFAULT_DETECTOR_PROMPT_ALLOWLIST),
        min_length=1,
        max_length=40,
    )
    detector_prompt_auto_update: bool = False

    model_provider: str = "fallback"
    modeldeck_url: str = "http://127.0.0.1:8600"
    modeldeck_model: str = MODELDECK_MODEL_ALIAS
    vision_request_timeout_seconds: float = Field(default=20, gt=0, le=120)
    vision_analysis_max_edge: int = Field(default=0, ge=0, le=1280)
    vision_max_tokens: int = Field(default=1024, ge=128, le=1024)
    auto_analyse: bool = False
    auto_analyse_interval_seconds: float = Field(default=90, ge=20, le=300)

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

    @field_validator("modeldeck_model")
    @classmethod
    def validate_modeldeck_model(cls, value: str) -> str:
        if value != MODELDECK_MODEL_ALIAS:
            raise ValueError("must be the ModelDeck scenechat-vision gateway alias")
        return value

    @field_validator("vision_analysis_max_edge")
    @classmethod
    def validate_vision_analysis_max_edge(cls, value: int) -> int:
        if value != 0 and value < 256:
            raise ValueError("must be 0 (disabled) or between 256 and 1280")
        return value

    @field_validator("detector_backend")
    @classmethod
    def validate_detector(cls, value: str) -> str:
        if value not in {"auto", "none", "replay", "yoloe", "yoloworld"}:
            raise ValueError("must be auto, none, replay, yoloe, or yoloworld")
        return value

    @field_validator("detector_prompts", "detector_prompt_allowlist")
    @classmethod
    def validate_detector_prompts(cls, value: list[str]) -> list[str]:
        cleaned = [" ".join(item.strip().lower().split()) for item in value]
        if any(not item or len(item) > 50 for item in cleaned):
            raise ValueError("detector prompts must contain 1 to 50 characters")
        if any(not re.fullmatch(r"[a-z0-9][a-z0-9 ._-]*", item) for item in cleaned):
            raise ValueError("detector prompts contain unsupported characters")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("detector prompts must be unique")
        return cleaned

    @field_validator("detector_model_options")
    @classmethod
    def validate_detector_model_options(cls, value: dict[str, str]) -> dict[str, str]:
        for model_id, path in value.items():
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", model_id):
                raise ValueError(
                    "model identifiers must use only letters, numbers, '.', '_' or '-'"
                )
            if not path.strip():
                raise ValueError("model paths must not be empty")
        if len(set(value.values())) != len(value):
            raise ValueError("model paths must be unique")
        return value

    @model_validator(mode="after")
    def apply_safety_rules(self) -> "Settings":
        if self.store_frames or self.store_video:
            raise ValueError("visitor frame and video storage are not supported")
        if self.scenechat_port != SCENECHAT_PORT:
            raise ValueError(f"SCENECHAT_PORT must be {SCENECHAT_PORT}")
        if (
            self.detector_backend in {"auto", "yoloe", "yoloworld"}
            and self.detector_model_options
            and self.detector_model
            and self.detector_model not in self.detector_model_options.values()
        ):
            raise ValueError("DETECTOR_MODEL must be present in DETECTOR_MODEL_OPTIONS")
        if not set(self.detector_prompts).issubset(self.detector_prompt_allowlist):
            raise ValueError("DETECTOR_PROMPTS must be present in DETECTOR_PROMPT_ALLOWLIST")
        configured_models = [
            path
            for path in [self.detector_model, *self.detector_model_options.values()]
            if path
        ]
        if self.detector_backend == "yoloe" and any(
            not Path(path).name.startswith("yoloe-") for path in configured_models
        ):
            raise ValueError("YOLOE detector models must use yoloe-* checkpoints")
        if self.detector_backend == "yoloworld" and any(
            "world" not in Path(path).stem.lower() for path in configured_models
        ):
            raise ValueError("YOLO-World detector models must use *world* checkpoints")
        if self.detector_backend == "auto" and any(
            not Path(path).name.startswith("yoloe-")
            and "world" not in Path(path).stem.lower()
            for path in configured_models
        ):
            raise ValueError("auto detector models must be YOLOE or YOLO-World checkpoints")
        yoloe_selected = self.detector_backend == "yoloe" or (
            self.detector_backend == "auto"
            and any(Path(path).name.startswith("yoloe-") for path in configured_models)
        )
        if yoloe_selected and not self.detector_text_encoder:
            raise ValueError("DETECTOR_TEXT_ENCODER is required for the YOLOE backend")
        yoloworld_selected = self.detector_backend == "yoloworld" or (
            self.detector_backend == "auto"
            and any("world" in Path(path).stem.lower() for path in configured_models)
        )
        if yoloworld_selected and not self.detector_yoloworld_clip:
            raise ValueError(
                "DETECTOR_YOLOWORLD_CLIP is required for the YOLO-World backend"
            )

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

    def available_detector_models(self) -> dict[str, str]:
        """Return the server-configured detector allowlist keyed by public identifier."""
        if self.detector_model_options:
            return dict(self.detector_model_options)
        if self.detector_model:
            return {Path(self.detector_model).stem: self.detector_model}
        return {}

    def detector_model_id(self) -> str | None:
        for model_id, path in self.available_detector_models().items():
            if path == self.detector_model:
                return model_id
        return None

    def detector_supports_prompts(self) -> bool:
        return self.detector_backend in {"yoloe", "yoloworld"} or (
            self.detector_backend == "auto" and bool(self.available_detector_models())
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
