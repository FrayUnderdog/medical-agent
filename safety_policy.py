from __future__ import annotations

from dataclasses import dataclass


Severity = str  # "emergency" | "urgent"


@dataclass(frozen=True)
class RedFlagRule:
    id: str
    category: str
    severity: Severity  # "emergency" | "urgent"
    patterns: tuple[str, ...]
    reason: str
    recommended_action: str


# Simple, deterministic substring patterns. Keep phrases lower-case.
RED_FLAG_RULES: tuple[RedFlagRule, ...] = (
    # Respiratory emergency
    RedFlagRule(
        id="resp_cannot_breathe",
        category="respiratory_emergency",
        severity="emergency",
        patterns=(
            "can't breathe",
            "cannot breathe",
            "trouble breathing",
            "difficulty breathing",
            "can't catch my breath",
            "cannot catch my breath",
            "gasping",
            "blue lips",
            "cannot speak full sentences",
            "can't speak full sentences",
        ),
        reason="Possible severe breathing problem.",
        recommended_action="Seek emergency care now.",
    ),
    # Chest pain / cardiovascular red flags
    RedFlagRule(
        id="cv_chest_pain",
        category="chest_pain_cardiovascular",
        severity="emergency",
        patterns=("chest pain", "pressure in chest"),
        reason="Chest pain can be an emergency.",
        recommended_action="Seek emergency care now.",
    ),
    # Neurological red flags
    RedFlagRule(
        id="neuro_stroke_like",
        category="neurological_red_flags",
        severity="emergency",
        patterns=("slurred speech", "one-sided weakness", "face drooping", "seizure"),
        reason="Possible neurologic emergency symptoms.",
        recommended_action="Seek emergency care now.",
    ),
    # Severe bleeding / blood symptoms
    RedFlagRule(
        id="bleed_severe",
        category="severe_bleeding_blood_symptoms",
        severity="emergency",
        patterns=("severe bleeding", "coughing up large amounts of blood"),
        reason="Severe bleeding can be life-threatening.",
        recommended_action="Seek emergency care now.",
    ),
    RedFlagRule(
        id="bleed_coughing_blood",
        category="severe_bleeding_blood_symptoms",
        severity="urgent",
        patterns=("coughing blood", "cough up blood", "blood in phlegm", "hemoptysis"),
        reason="Coughing blood can be serious and needs prompt evaluation.",
        recommended_action="Seek urgent medical evaluation soon.",
    ),
    # Infection red flags
    RedFlagRule(
        id="infect_fever_stiff_neck",
        category="infection_red_flags",
        severity="emergency",
        patterns=("fever and stiff neck", "fever with stiff neck", "stiff neck and fever"),
        reason="Fever with stiff neck can be an emergency.",
        recommended_action="Seek emergency care now.",
    ),
    RedFlagRule(
        id="infect_fever_confusion",
        category="infection_red_flags",
        severity="emergency",
        patterns=("fever and confusion", "fever with confusion", "confused with fever"),
        reason="Fever with confusion can be an emergency.",
        recommended_action="Seek emergency care now.",
    ),
    # Self-harm / mental health crisis
    RedFlagRule(
        id="mh_self_harm",
        category="self_harm_mental_health_crisis",
        severity="emergency",
        patterns=("suicidal", "kill myself", "end my life", "overdose", "self harm", "hurt myself"),
        reason="Self-harm crisis requires immediate help.",
        recommended_action="Contact emergency services or a crisis line now.",
    ),
)

