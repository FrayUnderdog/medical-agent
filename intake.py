"""
Rule-based structured intake extraction (no LLM).

Merges new utterances into existing session intake: new values fill empty
fields; non-empty existing scalars are preserved. Lists are unioned.
"""

from __future__ import annotations

import re
from typing import Any


_NAME_STOP = frozenset(
    {
        "here",
        "not",
        "fine",
        "good",
        "sick",
        "able",
        "having",
        "still",
        "very",
        "okay",
        "ok",
        "sorry",
        "worried",
        "experiencing",
        "feeling",
        "doing",
        "seeing",
        "trying",
    }
)

_WORD_NUM = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _norm_str(s: str | None) -> str:
    if s is None:
        return ""
    return " ".join(str(s).split()).strip()


def _uniq_ci(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for x in items:
        t = _norm_str(x)
        if not t:
            continue
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def _merge_scalar(old: Any, new: Any) -> Any:
    if old not in (None, "", []):
        return old
    return new if new not in (None, "", []) else old


def _merge_list(old: list[str] | None, new: list[str] | None) -> list[str]:
    return _uniq_ci(list(old or []) + list(new or []))


def _parse_name(text: str) -> str | None:
    t = text.strip()
    m = re.search(r"\bmy\s+name\s+is\s+([A-Za-z][A-Za-z'\-]{0,39})\b", t, re.I)
    if m:
        return m.group(1).strip("'\"").title()
    m = re.search(r"\b(?:call\s+me|i\s*'?m\s+called)\s+([A-Za-z][A-Za-z'\-]{0,39})\b", t, re.I)
    if m:
        return m.group(1).strip("'\"").title()
    m = re.search(r"\bi\s*'?m\s+([A-Za-z][a-z]{1,29})\b", t, re.I)
    if m:
        w = m.group(1)
        if w.lower() in _NAME_STOP:
            return None
        return w[0].upper() + w[1:]
    m = re.search(r"\bi\s+am\s+([A-Za-z][a-z]{1,29})\b", t, re.I)
    if m:
        w = m.group(1)
        if w.lower() in _NAME_STOP:
            return None
        return w[0].upper() + w[1:]
    return None


def _parse_age(text: str) -> str | None:
    m = re.search(r"\b(\d{1,3})\s*years?\s*old\b", text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"\bage\s*[:is]?\s*(\d{1,3})\b", text, re.I)
    if m:
        return m.group(1)
    m = re.search(r"\bi\s*'?m\s+(\d{1,3})(?:\s*years?\s*old)?\b", text, re.I)
    if m:
        return m.group(1)
    return None


def _parse_duration(text: str) -> str | None:
    low = text.lower()
    if re.search(r"\bsince\s+yesterday\b", low):
        return "1 day"
    if re.search(r"\bsince\s+last\s+week\b", low):
        return "1 week"
    m = re.search(
        r"\b(?:for|about|over)\s+((?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2}))\s+"
        r"(day|days|week|weeks|month|months|hour|hours)\b",
        low,
    )
    if m:
        q = m.group(1)
        unit = m.group(2)
        n = int(q) if q.isdigit() else _WORD_NUM.get(q, 1)
        return f"{n} {unit}"
    m = re.search(
        r"\b(two|three|four|five|six|seven|eight|nine|ten|\d{1,2})\s+(day|days|week|weeks)\s+ago\b",
        low,
    )
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else _WORD_NUM.get(m.group(1), 1)
        return f"{n} {m.group(2)}"
    return None


def _parse_side(text: str) -> str | None:
    low = text.lower()
    if re.search(r"\bleft\b", low) and not re.search(r"\bleft\s+over\b", low):
        return "left"
    if re.search(r"\bright\b", low):
        return "right"
    if re.search(r"\bbilateral\b|\bboth\s+(?:sides|legs|arms)\b", low):
        return "bilateral"
    return None


def _parse_body_part(text: str) -> str | None:
    low = text.lower()
    pairs = [
        ("ankle", "ankle"),
        ("wrist", "wrist"),
        ("knee", "knee"),
        ("elbow", "elbow"),
        ("shoulder", "shoulder"),
        ("neck", "neck"),
        ("back", "back"),
        ("chest", "chest"),
        ("abdomen", "abdomen"),
        ("stomach", "abdomen"),
        ("belly", "abdomen"),
        ("throat", "throat"),
        ("head", "head"),
        ("skin", "skin"),
    ]
    for pat, label in pairs:
        if pat in low:
            return label
    return None


def _parse_mechanism(text: str) -> str | None:
    low = text.lower()
    if re.search(r"\btwist(?:ed|ing)?\b", low):
        return "twisting injury"
    if re.search(r"\bfell|fall\b", low):
        return "fall"
    if re.search(r"\bhit|struck|banged\b", low):
        return "direct blow"
    return None


def _parse_severity(text: str) -> str | None:
    low = text.lower()
    m = re.search(r"\b(?:pain|severity)\s*(?:of|:)?\s*(\d{1,2})\s*/\s*10\b", low)
    if m:
        return f"{m.group(1)}/10"
    m = re.search(r"\b(\d{1,2})\s*/\s*10\b", low)
    if m and "pain" in low:
        return f"{m.group(1)}/10"
    if re.search(r"\bsevere\b", low):
        return "severe"
    if re.search(r"\bmild\b", low):
        return "mild"
    return None


def _parse_allergies_line(text: str) -> list[str]:
    out: list[str] = []
    m = re.search(r"\ballergic\s+to\s+([A-Za-z0-9][A-Za-z0-9\s\-]{1,48})\b", text, re.I)
    if m:
        out.append(_norm_str(m.group(1)).rstrip(".,;"))
    return out


def _parse_chronic(text: str) -> list[str]:
    low = text.lower()
    out: list[str] = []
    if "diabetes" in low or "diabetic" in low:
        out.append("diabetes")
    if "hypertension" in low or "high blood pressure" in low:
        out.append("hypertension")
    if "asthma" in low:
        out.append("asthma")
    return out


def _parse_meds(text: str) -> list[str]:
    # Minimal placeholder — avoid dosing
    if re.search(r"\btaking\s+(\w+(?:\s+\w+){0,3})\b", text, re.I):
        m = re.search(r"\btaking\s+([A-Za-z][A-Za-z\s\-]{2,40})\b", text, re.I)
        if m and "birth" not in m.group(1).lower():
            return [_norm_str(m.group(1)).rstrip(".,;")[:60]]
    return []


def _detect_red_flags(text: str) -> list[str]:
    low = text.lower()
    flags: list[str] = []
    if "chest pain" in low:
        flags.append("chest pain")
    if re.search(r"\b(shortness\s+of\s+breath|trouble\s+breathing|difficulty\s+breathing|can'?t\s+breathe)\b", low):
        flags.append("breathing difficulty")
    if "chest pain" in low and re.search(
        r"\b(shortness\s+of\s+breath|trouble\s+breathing|difficulty\s+breathing)\b", low
    ):
        flags.append("possible cardiac or pulmonary emergency pattern")
    if re.search(r"\b(slurred\s+speech|face\s+drooping|one[- ]sided\s+weakness)\b", low):
        flags.append("possible stroke warning signs")
    if "worst headache" in low or "thunderclap" in low:
        flags.append("sudden severe headache")
    if re.search(r"\b(stiff\s+neck|fever)\b", low) and "confusion" in low:
        flags.append("fever with confusion or neck stiffness")
    return _uniq_ci(flags)


def _detect_symptoms(text: str) -> list[str]:
    low = text.lower()
    found: list[str] = []
    rules: list[tuple[str, str]] = [
        ("fever", r"\bfever\b|\bfebrile\b"),
        ("cough", r"\bcough(?:ing)?\b"),
        ("chest pain", r"\bchest\s+pain\b"),
        ("shortness of breath", r"\b(shortness\s+of\s+breath|trouble\s+breathing|difficulty\s+breathing)\b"),
        ("headache", r"\bheadache\b|\bmigraine\b"),
        ("rash", r"\brush\b|\bhives\b"),
        ("nausea", r"\bnausea\b|\bnauseous\b"),
        ("vomiting", r"\bvomit(?:ing)?\b|\bthrew\s+up\b"),
        ("diarrhea", r"\bdiarrhea\b|\bloose\s+stool\b"),
        ("dizziness", r"\bdizz(?:y|iness)\b|\blightheaded\b"),
        ("sore throat", r"\bsore\s+throat\b"),
        ("abdominal pain", r"\b(stomach|abdominal|belly)\s+pain\b"),
        ("anxiety", r"\banxious\b|\banxiety\b"),
        ("insomnia", r"\b(can'?t|cannot)\s+sleep\b|\binsomnia\b|\btrouble\s+sleeping\b"),
        (
            "ankle injury",
            r"\bankle\b.*\b(twist|sprain|injur)|\b(twist|sprain|twisted).*\bankle\b|\bankle\b.*\btwisted\b",
        ),
    ]
    for label, pat in rules:
        if re.search(pat, low):
            found.append(label)
    if "peanut" in low and "rash" in low:
        if "possible allergic reaction" not in [x.lower() for x in found]:
            found.append("possible allergic reaction")
    return _uniq_ci(found)


def _chief_complaint_from(text: str, body: str | None, side: str | None, symptoms: list[str]) -> str | None:
    low = text.lower()
    if "rash" in low and "peanut" in low:
        return "rash after eating peanuts"
    if body == "ankle" and ("twist" in low or "sprain" in low or "ankle" in low):
        loc = f"{(side + ' ') if side else ''}{body} injury".strip()
        return loc
    if symptoms:
        return ", ".join(symptoms[:4])
    return None


def _likely_department(symptoms: list[str], body: str | None, text: str) -> str | None:
    low = text.lower()
    sl = " ".join(symptoms).lower()
    if body == "ankle" or "ankle injury" in sl:
        return "Orthopedics"
    if "chest pain" in sl or "shortness of breath" in sl:
        return "Emergency / Cardiology"
    if "rash" in sl or "hives" in low or "peanut" in low:
        return "Dermatology / Allergy"
    if "anxiety" in sl or "insomnia" in sl:
        return "Mental Health / Primary Care"
    if "fever" in sl or "cough" in sl:
        return "Internal Medicine"
    if "headache" in sl:
        return "Neurology / Primary Care"
    return "Primary Care"


def _risk_level_hint(text: str, red: list[str], symptoms: list[str]) -> str:
    low = text.lower()
    if red and ("possible cardiac or pulmonary emergency pattern" in red or (
        "chest pain" in low and re.search(r"\b(shortness\s+of\s+breath|trouble\s+breathing)\b", low)
    )):
        return "emergency"
    if red and any("stroke" in r for r in red):
        return "emergency"
    if "chest pain" in low and "shortness of breath" in " ".join(symptoms).lower():
        return "emergency"
    if "severe" in low and ("bleeding" in low or "can't breathe" in low or "cannot breathe" in low):
        return "emergency"
    if "peanut" in low and "rash" in low and re.search(r"\b(swelling|wheeze|throat|can'?t\s+breathe)\b", low):
        return "emergency"
    if "ankle injury" in " ".join(symptoms).lower() or ("ankle" in low and "twist" in low):
        return "routine"
    return "routine"


def _confidence(merged: dict[str, Any]) -> float:
    keys = [
        "name",
        "age",
        "chief_complaint",
        "symptoms",
        "body_part",
        "duration",
        "side_or_location",
    ]
    score = 0.0
    for k in keys:
        v = merged.get(k)
        if v is None or v == "" or v == []:
            continue
        score += 1.0 / len(keys)
    return round(min(1.0, score + 0.15), 2)


def _empty_intake() -> dict[str, Any]:
    return {
        "name": None,
        "age": None,
        "sex_or_gender": None,
        "chief_complaint": None,
        "symptoms": [],
        "body_part": None,
        "side_or_location": None,
        "duration": None,
        "mechanism": None,
        "severity": None,
        "allergies": [],
        "chronic_conditions": [],
        "medications": [],
        "red_flags": [],
        "likely_department": None,
        "risk_level_hint": "routine",
        "food_trigger": None,
        "confidence": 0.0,
    }


def _parse_message_only(message: str) -> dict[str, Any]:
    text = _norm_str(message)
    low = text.lower()
    symptoms = _detect_symptoms(text)
    body = _parse_body_part(text)
    side = _parse_side(text)
    duration = _parse_duration(text)
    mechanism = _parse_mechanism(text)
    red = _detect_red_flags(text)
    food_trigger = None
    if re.search(r"\b(?:after\s+eating|from)\s+peanuts\b", low) or ("peanut" in low and "rash" in low):
        food_trigger = "peanuts"
    chief = _chief_complaint_from(text, body, side, symptoms)
    dept = _likely_department(symptoms, body, text)
    risk = _risk_level_hint(text, red, symptoms)
    if food_trigger and "possible allergic reaction" not in [s.lower() for s in symptoms]:
        symptoms = _uniq_ci(symptoms + ["possible allergic reaction"])

    return {
        "name": _parse_name(text),
        "age": _parse_age(text),
        "sex_or_gender": None,
        "chief_complaint": chief,
        "symptoms": symptoms,
        "body_part": body,
        "side_or_location": side,
        "duration": duration,
        "mechanism": mechanism,
        "severity": _parse_severity(text),
        "allergies": _parse_allergies_line(text),
        "chronic_conditions": _parse_chronic(text),
        "medications": _parse_meds(text),
        "red_flags": red,
        "likely_department": dept,
        "risk_level_hint": risk,
        "food_trigger": food_trigger,
    }


def _merge_intake(existing: dict[str, Any] | None, parsed: dict[str, Any]) -> dict[str, Any]:
    base = _empty_intake()
    if existing:
        for k, v in existing.items():
            if k in base:
                base[k] = v
    # scalars
    for key in (
        "name",
        "age",
        "sex_or_gender",
        "chief_complaint",
        "body_part",
        "side_or_location",
        "duration",
        "mechanism",
        "severity",
        "likely_department",
        "risk_level_hint",
        "food_trigger",
    ):
        base[key] = _merge_scalar(base.get(key), parsed.get(key))
    # lists
    base["symptoms"] = _merge_list(base.get("symptoms"), parsed.get("symptoms"))
    base["allergies"] = _merge_list(base.get("allergies"), parsed.get("allergies"))
    base["chronic_conditions"] = _merge_list(base.get("chronic_conditions"), parsed.get("chronic_conditions"))
    base["medications"] = _merge_list(base.get("medications"), parsed.get("medications"))
    base["red_flags"] = _merge_list(base.get("red_flags"), parsed.get("red_flags"))
    pr = (parsed.get("risk_level_hint") or "routine").lower()
    br = (base.get("risk_level_hint") or "routine").lower()
    rank = {"routine": 1, "self_care": 1, "urgent": 2, "emergency": 3, "unknown": 0}
    if rank.get(pr, 1) > rank.get(br, 1):
        base["risk_level_hint"] = parsed.get("risk_level_hint")
    elif not base.get("risk_level_hint"):
        base["risk_level_hint"] = parsed.get("risk_level_hint") or "routine"
    base["confidence"] = _confidence(base)
    return base


def extract_patient_intake(message: str, existing_state: dict | None = None) -> dict[str, Any]:
    """
    Extract and merge structured intake from natural language.

    Returns a stable dict (unknowns as None or []).
    """
    parsed = _parse_message_only(message)
    merged = _merge_intake(existing_state, parsed)
    merged["confidence"] = _confidence(merged)
    return merged


def build_patient_summary_for_response(
    intake: dict[str, Any],
    *,
    guardrail_triggered: bool,
    guardrail_severity: str | None,
    triage_level: str | None,
) -> dict[str, Any]:
    """Shape for /chat `patient_summary` (UI + clients)."""
    risk = "unknown"
    if guardrail_triggered and guardrail_severity == "emergency":
        risk = "emergency"
    elif guardrail_triggered and guardrail_severity == "urgent":
        risk = "urgent"
    elif (intake.get("risk_level_hint") or "").lower() == "emergency":
        risk = "emergency"
    elif triage_level == "emergency":
        risk = "emergency"
    elif triage_level == "urgent":
        risk = "urgent"
    elif triage_level in {"routine", "self_care"}:
        risk = str(triage_level)
    elif intake.get("risk_level_hint"):
        risk = str(intake.get("risk_level_hint"))

    loc_parts = [p for p in (intake.get("side_or_location"), intake.get("body_part")) if p]
    body_loc = " ".join(loc_parts) if loc_parts else None

    return {
        "name": intake.get("name"),
        "age": intake.get("age"),
        "chief_complaint": intake.get("chief_complaint"),
        "symptoms": intake.get("symptoms") or [],
        "duration": intake.get("duration"),
        "body_part": intake.get("body_part"),
        "side_or_location": intake.get("side_or_location"),
        "mechanism": intake.get("mechanism"),
        "allergies": intake.get("allergies") or [],
        "chronic_conditions": intake.get("chronic_conditions") or [],
        "likely_department": intake.get("likely_department"),
        "risk_level": risk,
        "body_location_label": body_loc,
    }
