"""Provider interface and safe model-output parsing."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from scenechat.config import ROOT
from scenechat.models import SceneAnalysis, SceneAnalysisPayload


class VisionProviderError(RuntimeError):
    """A safe, staff-visible vision provider failure."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        staff_message: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.staff_message = staff_message or message


@dataclass(frozen=True)
class ProviderStatus:
    available: bool
    code: str
    message: str


AVAILABLE_STATUS = ProviderStatus(True, "available", "Provider is available.")


class VisionLanguageProvider(Protocol):
    name: str

    async def analyse_scene(self, image: bytes, question: str) -> SceneAnalysis:
        """Analyse one image in response to one approved question."""

    async def health(self) -> ProviderStatus:
        """Return a safe, operator-facing provider readiness status."""


def load_system_prompt(path: Path | None = None) -> str:
    return (path or ROOT / "prompts" / "scene_analysis_system.txt").read_text(
        encoding="utf-8"
    ).strip()


def build_prompt(question: str) -> str:
    """Build a prompt only for a caller-validated curated question."""
    return f"{load_system_prompt()}\n\nSelected curated question:\n{question}"


def parse_scene_analysis(raw: str, provider: str) -> SceneAnalysis:
    """Validate JSON model output, accepting a single optional Markdown fence."""
    cleaned = raw.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(1)
    try:
        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise ValueError("model output was not a JSON object")
        parsed = SceneAnalysisPayload.model_validate(payload)
        _validate_public_output(parsed)
        return SceneAnalysis(**parsed.model_dump(), provider=provider)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise VisionProviderError("The model returned an invalid structured response.") from exc


_PROHIBITED_OUTPUT_PATTERNS = (
    r"\b(?:facial|face) recognition\b",
    r"\b(?:his|her|their) name is\b",
    r"\bnamed [A-Z][A-Za-z'-]+\b",
    r"\b\d{1,3}[ -]years?[ -]old\b",
    r"\b(?:ethnicity|religion|sexuality|criminality|political views?)\b",
    r"\b(?:disabled|autistic|depressed|anxious) person\b",
)


def _validate_public_output(payload: SceneAnalysisPayload) -> None:
    """Reject high-confidence prohibited claims before public display."""
    text = "\n".join(
        [
            payload.summary,
            *(item.label for item in payload.objects),
            *(item.description for item in payload.objects),
            *(item.approximate_location for item in payload.objects),
            *payload.relationships,
            *payload.uncertainties,
            *payload.safety_notes,
        ]
    )
    if any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in _PROHIBITED_OUTPUT_PATTERNS
    ):
        raise VisionProviderError("The model returned output that is unsafe to display.")
