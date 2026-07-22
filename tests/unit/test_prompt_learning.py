import pytest

from scenechat.detection.prompt_learning import plan_prompt_learning
from scenechat.models import ObjectDescription


def candidate(label: str, description: str | None = None) -> ObjectDescription:
    return ObjectDescription(
        label=label,
        description=description or f"A {label} is visible.",
        approximate_location="centre",
    )


def test_safe_non_allowlisted_objects_are_learned_and_duplicates_are_ignored():
    plan = plan_prompt_learning(
        ["person"],
        [],
        [candidate("tripod"), candidate("projector"), candidate("tripod")],
        has_safety_notes=False,
    )

    assert plan.prompts == ["person", "tripod", "projector"]
    assert plan.learned_prompts == ["tripod", "projector"]
    assert plan.outcome.added == ["tripod", "projector"]
    assert plan.outcome.rejected_count == 0


@pytest.mark.parametrize(
    ("label", "description", "reason"),
    [
        ("Tripod", "A tripod is visible.", "invalid_shape"),
        ("this is a very long object label", "Visible object.", "invalid_shape"),
        ("young woman", "A person is visible.", "sensitive_trait"),
        ("person", "A woman is visible.", "human_or_identity"),
        ("person", "An Australian person is visible.", "sensitive_trait"),
        ("lanyard", "A happy employee is wearing it.", "sensitive_trait"),
        ("visitor", "A visitor is visible.", "human_or_identity"),
        ("tripod", "The tripod is beside a student.", "human_or_identity"),
        ("wheelchair", "A wheelchair is visible.", "medical_or_assistive"),
        ("inhaler", "An inhaler is visible.", "medical_or_assistive"),
        ("bible", "A bible is visible.", "religious_or_political"),
        ("campaign badge", "A campaign badge is visible.", "religious_or_political"),
        ("underwear", "Underwear is visible.", "intimate"),
        ("knife", "A knife is visible.", "weapon_or_drug"),
        ("wine glass", "A wine glass is visible.", "weapon_or_drug"),
        ("john", "A person is visible.", "human_or_identity"),
    ],
)
def test_conservative_filter_rejects_unsafe_or_malformed_candidates(
    label, description, reason
):
    plan = plan_prompt_learning(
        [],
        [],
        [candidate(label, description)],
        has_safety_notes=False,
    )

    assert plan.prompts == []
    assert plan.outcome.added == []
    assert plan.outcome.rejection_reasons == {reason: 1}


def test_generic_person_is_allowed_without_sensitive_wording():
    plan = plan_prompt_learning(
        [],
        [],
        [candidate("person", "A person is visible near a table.")],
        has_safety_notes=False,
    )

    assert plan.learned_prompts == ["person"]


def test_safety_notes_block_all_candidates_without_exposing_labels():
    plan = plan_prompt_learning(
        [],
        [],
        [candidate("whiteboard"), candidate("projector")],
        has_safety_notes=True,
    )

    assert plan.outcome.rejected_count == 2
    assert plan.outcome.rejection_reasons == {"model_safety_note": 2}
    assert plan.outcome.added == []


def test_oldest_learned_prompts_are_replaced_but_baseline_is_preserved():
    baseline = [f"base-{index}" for index in range(5)]
    learned = [f"learned-{index}" for index in range(15)]
    plan = plan_prompt_learning(
        baseline,
        learned,
        [candidate("tripod"), candidate("projector")],
        has_safety_notes=False,
    )

    assert plan.prompts[:5] == baseline
    assert plan.outcome.evicted == ["learned-0", "learned-1"]
    assert plan.learned_prompts[-2:] == ["tripod", "projector"]
    assert len(plan.prompts) == 20


def test_full_baseline_skips_new_candidates_without_eviction():
    baseline = [f"base-{index}" for index in range(20)]
    plan = plan_prompt_learning(
        baseline,
        [],
        [candidate("whiteboard")],
        has_safety_notes=False,
    )

    assert plan.prompts == baseline
    assert plan.outcome.capacity_skipped_count == 1
    assert plan.outcome.evicted == []
