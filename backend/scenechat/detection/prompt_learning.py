"""Conservative, session-scoped learning of detector text prompts."""

import re
from collections import Counter
from dataclasses import dataclass

from scenechat.models import ObjectDescription, PromptLearningOutcome, SceneAnalysis


MAX_ACTIVE_PROMPTS = 20
_LABEL_PATTERN = re.compile(r"[a-z0-9][a-z0-9 ._-]{0,49}")
_HUMAN_SUBJECT = re.compile(
    r"\b(?:person|people|human|man|men|woman|women|boy|girl|"
    r"child|children|baby|teenager|adult|visitor|student|employee)\b"
)
_NON_GENERIC_HUMAN = re.compile(
    r"\b(?:man|men|woman|women|boy|girl|child|children|baby|teenager|adult|"
    r"visitor|student|employee)\b"
)
_PROHIBITED_TERMS = {
    "human_or_identity": (
        "face", "facial", "identity", "identified", "name", "named",
        "body", "skin", "hair", "eye", "eyes", "fingerprint",
    ),
    "sensitive_trait": (
        "age", "young", "old", "elderly", "ethnicity", "ethnic", "race",
        "racial", "nationality", "gender", "sexuality", "gay", "lesbian",
        "male", "female", "nonbinary", "transgender", "disabled", "disability",
        "autistic", "autism", "asian", "african", "european", "indigenous",
        "aboriginal", "australian", "american", "british",
        "emotion", "emotional", "happy", "sad", "angry", "anxious",
        "depressed", "criminal", "criminality", "pregnant", "pregnancy",
    ),
    "medical_or_assistive": (
        "medical", "medicine", "medication", "pill", "syringe", "needle",
        "wheelchair", "crutch", "walker", "walking cane", "hearing aid",
        "prosthetic", "prosthesis", "oxygen tank", "hospital", "patient",
        "insulin", "inhaler", "defibrillator", "stethoscope", "bandage",
    ),
    "religious_or_political": (
        "religion", "religious", "christian", "muslim", "jewish", "hindu",
        "church", "mosque", "temple", "bible", "quran", "torah", "hijab",
        "cross", "crucifix", "prayer", "politics", "political", "protest",
        "campaign", "ballot", "candidate", "party badge", "national flag",
    ),
    "intimate": ("underwear", "lingerie", "bra", "condom", "intimate"),
    "weapon_or_drug": (
        "weapon", "gun", "firearm", "pistol", "rifle", "shotgun",
        "guns", "firearms", "pistols", "rifles", "shotguns", "ammunition",
        "bullet", "bullets", "knife", "knives", "sword", "machete", "bomb",
        "explosive", "grenade", "drug", "cannabis", "marijuana", "cocaine",
        "heroin", "methamphetamine", "alcohol", "beer", "wine", "spirits",
        "cigarette", "tobacco", "vape", "vaping",
    ),
}


@dataclass(frozen=True)
class PromptLearningPlan:
    prompts: list[str]
    learned_prompts: list[str]
    safe_objects: list[ObjectDescription]
    outcome: PromptLearningOutcome


def _contains_term(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def _normalise_candidate(item: ObjectDescription) -> tuple[str | None, str | None]:
    raw_label = " ".join(item.label.strip().split())
    if raw_label != raw_label.lower() or not _LABEL_PATTERN.fullmatch(raw_label):
        return None, "invalid_shape"
    if len(raw_label.split()) > 4:
        return None, "invalid_shape"

    label = raw_label
    description = " ".join(item.description.strip().lower().split())
    combined = f"{label}\n{description}"
    for reason, terms in _PROHIBITED_TERMS.items():
        if any(_contains_term(combined, term) for term in terms):
            return None, reason

    if label == "person" and _NON_GENERIC_HUMAN.search(description):
        return None, "human_or_identity"
    if label != "person" and _HUMAN_SUBJECT.search(combined):
        return None, "human_or_identity"
    return label, None


def _redact_terms(text: str, terms: set[str]) -> str:
    redacted = text
    for term in sorted(terms, key=len, reverse=True):
        if not term:
            continue
        redacted = re.sub(
            rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])",
            "[withheld]",
            redacted,
            flags=re.IGNORECASE,
        )
    return redacted


def _rejected_terms(item: ObjectDescription) -> set[str]:
    """Return only terms that must not be repeated in other public fields."""
    label = " ".join(item.label.strip().lower().split())
    description = " ".join(item.description.strip().lower().split())
    combined = f"{label}\n{description}"
    terms = {label}
    for prohibited in _PROHIBITED_TERMS.values():
        terms.update(term for term in prohibited if _contains_term(combined, term))
    terms.update(match.group(0) for match in _HUMAN_SUBJECT.finditer(combined))
    return terms


def sanitise_scene_analysis(analysis: SceneAnalysis) -> SceneAnalysis:
    """Remove unsafe candidate vocabulary before analysis reaches shared state."""
    safe_objects: list[ObjectDescription] = []
    rejection_reasons: Counter[str] = Counter()
    rejected_terms: set[str] = set()
    has_safety_notes = bool(analysis.safety_notes)
    for item in analysis.objects:
        if has_safety_notes:
            rejection_reasons["model_safety_note"] += 1
            rejected_terms.update(_rejected_terms(item))
            continue
        label, reason = _normalise_candidate(item)
        if reason:
            rejection_reasons[reason] += 1
            rejected_terms.update(_rejected_terms(item))
            continue
        assert label is not None
        safe_objects.append(item.model_copy(update={"label": label}))

    updates: dict[str, object] = {
        "objects": safe_objects,
        "prompt_rejection_reasons": dict(rejection_reasons),
    }
    if rejection_reasons:
        updates.update(
            summary=_redact_terms(analysis.summary, rejected_terms),
            relationships=[
                _redact_terms(item, rejected_terms) for item in analysis.relationships
            ],
            uncertainties=[
                _redact_terms(item, rejected_terms) for item in analysis.uncertainties
            ],
            safety_notes=(
                ["Some structured objects were withheld by the safety policy."]
                if analysis.safety_notes
                else []
            ),
        )
    return analysis.model_copy(update=updates, deep=True)


def plan_prompt_learning(
    baseline: list[str],
    learned: list[str],
    objects: list[ObjectDescription],
    *,
    has_safety_notes: bool,
) -> PromptLearningPlan:
    """Return a safe prompt update without mutating caller-owned lists."""
    next_learned = list(learned)
    active = list(baseline) + next_learned
    added: list[str] = []
    evicted: list[str] = []
    safe_objects: list[ObjectDescription] = []
    rejection_reasons: Counter[str] = Counter()
    capacity_skips = 0

    for item in objects:
        if has_safety_notes:
            rejection_reasons["model_safety_note"] += 1
            continue
        label, reason = _normalise_candidate(item)
        if reason:
            rejection_reasons[reason] += 1
            continue
        assert label is not None
        safe_objects.append(item.model_copy(update={"label": label}))
        if label in active:
            continue
        if len(active) == MAX_ACTIVE_PROMPTS:
            if not next_learned:
                capacity_skips += 1
                continue
            removed = next_learned.pop(0)
            active.remove(removed)
            evicted.append(removed)
        next_learned.append(label)
        active.append(label)
        added.append(label)

    outcome = PromptLearningOutcome(
        added=added,
        evicted=evicted,
        rejected_count=sum(rejection_reasons.values()),
        rejection_reasons=dict(rejection_reasons),
        capacity_skipped_count=capacity_skips,
    )
    return PromptLearningPlan(active, next_learned, safe_objects, outcome)
