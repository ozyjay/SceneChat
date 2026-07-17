"""Pydantic schemas shared by services and API routes."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Detection(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    confidence: float = Field(ge=0, le=1)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    tracking_id: int | None = Field(default=None, ge=0)

    @field_validator("width")
    @classmethod
    def width_within_frame(cls, value: float, info):
        x = info.data.get("x", 0)
        if x + value > 1.000001:
            raise ValueError("box extends beyond frame width")
        return value

    @field_validator("height")
    @classmethod
    def height_within_frame(cls, value: float, info):
        y = info.data.get("y", 0)
        if y + value > 1.000001:
            raise ValueError("box extends beyond frame height")
        return value


class ObjectDescription(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=300)
    approximate_location: str = Field(min_length=1, max_length=80)


class SceneAnalysis(BaseModel):
    summary: str = Field(min_length=1, max_length=800)
    objects: list[ObjectDescription] = Field(default_factory=list, max_length=30)
    relationships: list[str] = Field(default_factory=list, max_length=20)
    uncertainties: list[str] = Field(default_factory=list, max_length=20)
    safety_notes: list[str] = Field(default_factory=list, max_length=10)
    generated_at: datetime = Field(default_factory=utc_now)
    provider: str = Field(default="unknown", max_length=40)
    latency_ms: float | None = Field(default=None, ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    completion_token_limit: int | None = Field(default=None, ge=1)


class AppState(BaseModel):
    revision: int = 0
    generation: int = 0
    mode: str = "Prepared demonstration"
    internal_mode: str = "development"
    provider: str = "mock"
    provider_available: bool = True
    privacy_screen: bool = False
    camera_running: bool = False
    camera_device: int = 0
    detector_backend: str = "replay"
    detector_model: str | None = None
    detector_prompts: list[str] = Field(default_factory=list)
    detector_prompt_auto_update: bool = False
    replay_scenario: str = "demo_booth"
    detections: list[Detection] = Field(default_factory=list)
    scene_analysis: SceneAnalysis | None = None
    selected_question: str = "Describe the scene."
    detector_fps: float = 0
    last_model_latency_ms: float | None = None
    analysis_in_progress: bool = False
    auto_analyse: bool = False
    auto_analyse_interval_seconds: float = 5
    staff_error: str | None = None


class HealthStatus(BaseModel):
    status: str
    mode: str
    provider: str
    provider_available: bool
    camera_running: bool
    privacy_screen: bool
    version: str
