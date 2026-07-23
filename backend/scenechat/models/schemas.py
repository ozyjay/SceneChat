"""Pydantic schemas shared by services and API routes."""

import re
from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


_WORD = re.compile(r"\b[\w'-]+\b", re.UNICODE)
_SENTENCE_END = re.compile(r"[.!?]+(?:\s|$)")


def _word_count(value: str) -> int:
    return len(_WORD.findall(value))


def _sentence_count(value: str) -> int:
    endings = len(_SENTENCE_END.findall(value))
    return max(1, endings) if value.strip() else 0


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
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=48)
    description: str = Field(min_length=1, max_length=150)
    approximate_location: str = Field(min_length=1, max_length=48)

    @field_validator("description")
    @classmethod
    def bounded_description_words(cls, value: str) -> str:
        if _word_count(value) > 15:
            raise ValueError("object descriptions must contain no more than 15 words")
        return value


PublicListItem = Annotated[str, Field(min_length=1, max_length=180)]


class SceneAnalysisPayload(BaseModel):
    """Strict model-generated fields accepted before trusted metadata is added."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=360)
    objects: list[ObjectDescription] = Field(default_factory=list, max_length=8)
    relationships: list[PublicListItem] = Field(default_factory=list, max_length=3)
    uncertainties: list[PublicListItem] = Field(default_factory=list, max_length=3)
    safety_notes: list[PublicListItem] = Field(default_factory=list, max_length=1)

    @field_validator("summary")
    @classmethod
    def bounded_summary_words(cls, value: str) -> str:
        if _word_count(value) >= 45:
            raise ValueError("summary must contain fewer than 45 words")
        return value

    @field_validator("relationships", "uncertainties", "safety_notes")
    @classmethod
    def bounded_list_items(cls, value: list[str]) -> list[str]:
        if any(_word_count(item) > 24 for item in value):
            raise ValueError("list entries must contain no more than 24 words")
        if any(_sentence_count(item) > 1 for item in value):
            raise ValueError("list entries must contain at most one sentence")
        return value


class SceneAnalysis(SceneAnalysisPayload):
    generated_at: datetime = Field(default_factory=utc_now)
    provider: str = Field(default="unknown", max_length=40)
    latency_ms: float | None = Field(default=None, ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    completion_token_limit: int | None = Field(default=None, ge=1)
    prompt_rejection_reasons: dict[str, int] = Field(
        default_factory=dict, exclude=True, repr=False
    )


class PromptLearningOutcome(BaseModel):
    added: list[str] = Field(default_factory=list)
    evicted: list[str] = Field(default_factory=list)
    rejected_count: int = Field(default=0, ge=0)
    rejection_reasons: dict[str, int] = Field(default_factory=dict)
    capacity_skipped_count: int = Field(default=0, ge=0)


class AppState(BaseModel):
    revision: int = 0
    generation: int = 0
    mode: str = "Prepared demonstration"
    internal_mode: str = "development"
    provider: str = "mock"
    provider_available: bool = True
    provider_status_code: str = "available"
    provider_status_message: str = "Provider is available."
    privacy_screen: bool = False
    camera_running: bool = False
    camera_device: int = 0
    detector_backend: str = "replay"
    detector_model: str | None = None
    detector_prompts: list[str] = Field(default_factory=list)
    detector_prompt_baseline: list[str] = Field(default_factory=list)
    detector_learned_prompts: list[str] = Field(default_factory=list)
    detector_prompt_auto_update: bool = False
    detector_prompt_safety_rejections: int = 0
    detector_prompt_rejection_reasons: dict[str, int] = Field(default_factory=dict)
    detector_prompt_capacity_skips: int = 0
    replay_scenario: str = "demo_booth"
    detections: list[Detection] = Field(default_factory=list)
    scene_analysis: SceneAnalysis | None = None
    selected_question: str = "Describe the scene."
    detector_fps: float = 0
    last_model_latency_ms: float | None = None
    analysis_in_progress: bool = False
    auto_analyse: bool = False
    auto_analyse_interval_seconds: float = 20
    auto_analyse_questions: list[str] = Field(
        default_factory=lambda: ["Describe the scene."]
    )
    staff_error: str | None = None


class HealthStatus(BaseModel):
    status: str
    mode: str
    provider: str
    provider_available: bool
    camera_running: bool
    privacy_screen: bool
    version: str
