"""Safe replay-manifest parsing."""

import json
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from scenechat.config import ROOT
from scenechat.models import Detection, SceneAnalysis


class ReplayScenario(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=100)
    image: str
    detections: list[Detection]
    responses: dict[str, SceneAnalysis]

    @field_validator("image")
    @classmethod
    def safe_relative_image(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("replay image must be a safe relative path")
        return value


class ReplayManifest(BaseModel):
    version: int = 1
    scenarios: list[ReplayScenario]


class ReplayRegistry:
    def __init__(self, manifest_path: Path | None = None):
        self.manifest_path = manifest_path or ROOT / "replay_assets" / "manifest.json"
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        manifest = ReplayManifest.model_validate(payload)
        self._scenarios = {scenario.id: scenario for scenario in manifest.scenarios}
        for scenario in manifest.scenarios:
            if not self.image_path(scenario.id).is_file():
                raise ValueError(f"missing replay image: {scenario.image}")

    def get(self, scenario_id: str) -> ReplayScenario:
        try:
            return self._scenarios[scenario_id]
        except KeyError as exc:
            raise KeyError(f"unknown replay scenario: {scenario_id}") from exc

    def all(self) -> list[ReplayScenario]:
        return list(self._scenarios.values())

    def image_path(self, scenario_id: str) -> Path:
        scenario = self._scenarios[scenario_id]
        return self.manifest_path.parent / scenario.image
