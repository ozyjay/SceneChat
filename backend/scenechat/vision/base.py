"""Provider interface and safe model-output parsing."""

import json
import re
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from scenechat.config import ROOT
from scenechat.models import SceneAnalysis


class VisionProviderError(RuntimeError):
    """A safe, staff-visible vision provider failure."""


class VisionLanguageProvider(Protocol):
    name: str

    async def analyse_scene(self, image: bytes, question: str) -> SceneAnalysis:
        """Analyse one image in response to one approved question."""

    async def health(self) -> bool:
        """Return whether the provider is currently available."""


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
        payload["provider"] = provider
        return SceneAnalysis.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise VisionProviderError("The model returned an invalid structured response.") from exc

