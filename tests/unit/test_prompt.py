import hashlib

from scenechat.vision.base import build_prompt
from scenechat.config import ROOT


MODELDECK_0_2_2_PROMPT_SHA256 = (
    "44ee1d4244932d348c2b58dd9ed3ad25d8cb113d9acd0ef6b82583f70967efa0"
)


def test_prompt_contains_public_safety_rules():
    prompt = build_prompt("Describe the scene.").lower()
    for required in (
        "visible evidence",
        "never identify",
        "ethnicity",
        "religion",
        "health",
        "disability",
        "sexuality",
        "emotion",
        "criminality",
        "uncertainty",
        "json object",
    ):
        assert required in prompt


def test_prompt_contains_selected_question():
    assert build_prompt("What objects can you see?").endswith("What objects can you see?")


def test_prompt_matches_modeldeck_runtime_package_0_2_2_contract():
    prompt = (ROOT / "prompts" / "scene_analysis_system.txt").read_bytes()

    assert hashlib.sha256(prompt).hexdigest() == MODELDECK_0_2_2_PROMPT_SHA256
