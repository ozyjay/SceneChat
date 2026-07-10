import json

import pytest

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
    result = parse_scene_analysis(json.dumps(valid_payload()), "vllm")
    assert result.provider == "vllm"
    assert result.summary == "A laptop is visible."


def test_parses_one_markdown_fence():
    result = parse_scene_analysis(f"```json\n{json.dumps(valid_payload())}\n```", "vllm")
    assert result.objects[0].label == "laptop"


@pytest.mark.parametrize("raw", ["not json", "[]", '{"summary": ""}'])
def test_invalid_output_has_safe_error(raw):
    with pytest.raises(VisionProviderError, match="invalid structured response"):
        parse_scene_analysis(raw, "vllm")

