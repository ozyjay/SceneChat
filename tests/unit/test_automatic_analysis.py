import pytest

import scenechat.main as main_module


def test_automatic_question_is_curated_and_avoids_immediate_repeat(monkeypatch):
    questions = ["Describe the scene.", "What objects can you see?"]
    offered = []

    def choose(candidates):
        offered.extend(candidates)
        return candidates[0]

    monkeypatch.setattr(main_module.random, "choice", choose)

    selected = main_module._select_automatic_question(
        questions, "Describe the scene."
    )

    assert selected == "What objects can you see?"
    assert offered == ["What objects can you see?"]


def test_automatic_question_supports_a_single_curated_choice(monkeypatch):
    monkeypatch.setattr(main_module.random, "choice", lambda candidates: candidates[0])

    assert (
        main_module._select_automatic_question(
            ["Describe the scene."], "Describe the scene."
        )
        == "Describe the scene."
    )


def test_automatic_question_rejects_an_empty_curated_list():
    with pytest.raises(ValueError, match="At least one curated question"):
        main_module._select_automatic_question([], "Describe the scene.")
