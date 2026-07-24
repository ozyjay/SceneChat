import json

import pytest

from scenechat.detection.prompt_learning import sanitise_scene_analysis
from scenechat.vision.base import VisionProviderError, parse_scene_analysis


def valid_payload():
    return {
        "summary": "A laptop is visible.",
        "objects": [
            {
                "label": "laptop",
                "description": "An open laptop.",
                "approximate_location": "centre",
            }
        ],
        "relationships": [],
        "uncertainties": ["The brand is unclear."],
        "safety_notes": [],
    }


def test_parses_json_and_sets_adapter_provider():
    result = parse_scene_analysis(json.dumps(valid_payload()), "modeldeck")
    assert result.provider == "modeldeck"
    assert result.summary == "A laptop is visible."


def test_parses_one_markdown_fence():
    result = parse_scene_analysis(
        f"```json\n{json.dumps(valid_payload())}\n```", "modeldeck"
    )
    assert result.objects[0].label == "laptop"


@pytest.mark.parametrize("raw", ["not json", "[]", '{"summary": ""}'])
def test_invalid_output_has_safe_error(raw):
    with pytest.raises(VisionProviderError, match="invalid structured response"):
        parse_scene_analysis(raw, "modeldeck")


def test_rejects_extra_operational_fields_and_unbounded_list_text():
    extra = valid_payload() | {"latency_ms": 1}
    with pytest.raises(VisionProviderError, match="invalid structured response"):
        parse_scene_analysis(json.dumps(extra), "modeldeck")

    too_long = valid_payload() | {"relationships": ["x" * 181]}
    with pytest.raises(VisionProviderError, match="invalid structured response"):
        parse_scene_analysis(json.dumps(too_long), "modeldeck")


def test_non_displayed_safety_note_is_replaced_before_shared_state():
    payload = valid_payload() | {
        "safety_notes": [
            "No ethnicity, religion, health, or other sensitive attribute was inferred."
        ]
    }

    parsed = parse_scene_analysis(json.dumps(payload), "modeldeck")
    sanitised = sanitise_scene_analysis(parsed)

    assert sanitised.objects == []
    assert sanitised.safety_notes == [
        "Some structured objects were withheld by the safety policy."
    ]
    assert "ethnicity" not in sanitised.model_dump_json()
    assert "religion" not in sanitised.model_dump_json()


@pytest.mark.parametrize(
    "change",
    [
        {"summary": "word " * 45},
        {
            "objects": [
                {
                    "label": "object",
                    "description": "word " * 16,
                    "approximate_location": "centre",
                }
            ]
        },
        {"relationships": ["First sentence. Second sentence."]},
        {"uncertainties": ["uncertain"] * 4},
        {"safety_notes": ["note", "another note"]},
    ],
)
def test_rejects_output_outside_modeldeck_contract_bounds(change):
    with pytest.raises(VisionProviderError, match="invalid structured response"):
        parse_scene_analysis(json.dumps(valid_payload() | change), "modeldeck")


@pytest.mark.parametrize(
    "summary",
    [
        "Her name is Alice.",
        "A 14-year-old person is visible.",
        "The person's religion is apparent.",
    ],
)
def test_rejects_prohibited_identification_and_sensitive_claims(summary):
    payload = valid_payload() | {"summary": summary}
    with pytest.raises(VisionProviderError, match="unsafe to display"):
        parse_scene_analysis(json.dumps(payload), "modeldeck")
