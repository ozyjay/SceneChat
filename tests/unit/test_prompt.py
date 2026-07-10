from scenechat.vision.base import build_prompt


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

