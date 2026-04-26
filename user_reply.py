"""
User-facing reply templates (no raw RAG chunks, no source paths in text).
"""

from __future__ import annotations

from typing import Any

from guardrails import GuardrailResult

_DISCLAIMER = (
    "This is general information only—not a diagnosis or personal medical advice. "
    "If you are unsure or feel worse, contact a qualified clinician or local emergency services."
)


def _greet(intake: dict[str, Any]) -> str:
    n = intake.get("name")
    if n:
        return f"{n}, "
    return ""


def _hint_category(retrieval_hint: str, intake: dict[str, Any]) -> str:
    h = (retrieval_hint or "").lower()
    sy = " ".join(intake.get("symptoms") or []).lower()
    bp = (intake.get("body_part") or "").lower()
    if "ankle" in h or bp == "ankle" or "ankle injury" in sy:
        return "ankle"
    if "chest" in h or "chest pain" in sy:
        return "chest"
    if "shortness" in h or "shortness of breath" in sy:
        return "sob"
    if "fever" in h or "fever" in sy:
        return "fever"
    if "cough" in h or "cough" in sy:
        return "cough"
    if "skin_rash" in h or "hives" in h or "allergic" in h or "rash" in sy:
        return "rash"
    if "anxiety" in h or "insomnia" in h or "anxiety" in sy or "insomnia" in sy:
        return "mh"
    return "generic"


def _ankle_followup_incomplete(intake: dict[str, Any]) -> list[str]:
    need: list[str] = []
    if intake.get("can_bear_weight") is None:
        need.append("walking")
    if intake.get("swelling") is None and intake.get("bruising") is None:
        need.append("swelling_or_bruising")
    if intake.get("pain_score") is None:
        need.append("pain_score")
    return need


def _ankle_should_escalate(intake: dict[str, Any]) -> bool:
    r = (intake.get("risk_level_hint") or "").lower()
    if r in ("urgent", "emergency"):
        return True
    s = (intake.get("swelling") or "").lower()
    b = (intake.get("bruising") or "").lower()
    if s == "severe" or b == "significant":
        return True
    if intake.get("worsening_pain") is True:
        return True
    ps, wp = intake.get("pain_score"), intake.get("walking_painful")
    if ps is not None and int(ps) >= 6 and wp is True:
        return True
    return False


def _ankle_urgent_prose(intake: dict[str, Any]) -> str:
    g = _greet(intake)
    bits: list[str] = []
    if (intake.get("swelling") or "").lower() == "severe" or (intake.get("bruising") or "").lower() == "significant":
        bits.append("significant visible swelling or bruising")
    if intake.get("worsening_pain") is True:
        bits.append("worsening pain since the injury")
    if intake.get("walking_painful") is True and intake.get("can_bear_weight") is True:
        bits.append("pain with walking or weight bearing")
    ps = intake.get("pain_score")
    if ps is not None and int(ps) >= 6:
        bits.append(f"moderate-to-higher self-rated pain (around {int(ps)}/10)")

    why = (
        (", and ".join(bits) if bits else "the combination of pain, swelling, and function you described")
    )

    return (
        f"{g}thanks for the details. Because your ankle is {why}, it would be safer to get it checked the same day "
        "by a clinician or urgent care—partly to consider whether imaging may be needed, such as to **rule out a fracture** "
        "or a more serious **ligament injury** (I can’t tell from chat).\n\n"
        "Until you’re seen, avoid “pushing through” sharp pain. Rest the ankle, keep it **elevated** when you can, "
        "and use **ice** wrapped in a cloth for 15–20 minutes at a time, with breaks. You can use a light **compression** "
        "wrap as long as it does **not** increase pain, tingling, numbness, or color change in the toes.\n\n"
        "**Go to emergency care now** if you **cannot bear weight** or the ankle looks **deformed**, the toes are **numb, "
        "very cold, or blue**, or the pain and swelling are **escalating quickly**.\n\n"
        "If you have access, a visit for **orthopaedics/urgent care** can be a reasonable same-day next step. "
        "Would you like help with finding **urgent care** or **orthopaedics** options in your area (demo: not booked here)?\n\n"
        f"{_DISCLAIMER}"
    )


def _ankle_missing_questions(need: list[str]) -> str:
    kmap = {
        "walking": "1) Can you take a few steps on it (even if it hurts)?",
        "swelling_or_bruising": "2) How much swelling and bruising do you see? (Even a little counts.)",
        "pain_score": "3) Roughly how strong is the pain from 1 to 10?",
    }
    lines: list[str] = []
    for key in need:
        if key in kmap and kmap[key] not in lines:
            lines.append(kmap[key])
    return "\n".join(lines) if lines else "Could you share a bit more about weight-bearing, visible swelling/bruising, and pain level?"


def _ankle_first_visit_template(intake: dict[str, Any], loc: str) -> str:
    g = _greet(intake)
    need = _ankle_followup_incomplete(intake)
    dur = intake.get("duration") or "the past couple of days"
    return (
        f"{g}a twisted {loc or 'ankle'} for {dur} often fits a sprain-type injury. "
        "I can’t tell you for certain what happened without an exam.\n\n"
        "Many people are advised to try relative rest, ice, comfortable compression, and elevation early on, "
        "and to increase gentle movement as pain allows.\n\n"
        "Please seek urgent care now if you cannot bear weight, notice major deformity, numb/cold toes, "
        "severe swelling, or pain that is rapidly worsening.\n\n"
        "To guide next steps, could you share:\n"
        f"{_ankle_missing_questions(need)}\n\n"
        f"{_DISCLAIMER}"
    )


def _ankle_followup_ask_template(intake: dict[str, Any], loc: str) -> str:
    g = _greet(intake)
    need = _ankle_followup_incomplete(intake)
    return (
        f"{g}thanks for the update. To help fine-tune what to do next, could you share:\n\n"
        f"{_ankle_missing_questions(need)}\n\n"
        f"{_DISCLAIMER}"
    )


def _ankle_has_multiturn_clinical_context(intake: dict[str, Any]) -> bool:
    """True once the user has added information beyond a first-visit chief complaint (follow-up turns)."""
    if intake.get("answered_followups"):
        return True
    if intake.get("worsening_pain") is True:
        return True
    s = (intake.get("swelling") or "").lower()
    b = (intake.get("bruising") or "").lower()
    if s in ("mild", "moderate", "severe") or b in ("mild", "moderate", "significant"):
        return True
    if intake.get("can_bear_weight") is not None or intake.get("walking_painful") is not None:
        return True
    if intake.get("pain_score") is not None:
        return True
    return False


def format_user_facing_answer(
    *,
    user_message: str,
    intake: dict[str, Any],
    triage_level: str | None,
    guardrail: GuardrailResult,
    retrieval_hint: str,
    handoff_recommended: bool,
) -> str:
    """
    Build a short, product-style reply. Does not include retrieved chunk text or file paths.
    """
    g = _greet(intake)
    cat = _hint_category(retrieval_hint, intake)
    loc = " ".join(
        p for p in (intake.get("side_or_location"), intake.get("body_part")) if p
    ).strip()

    is_ankle = cat == "ankle" or (intake.get("body_part") == "ankle" and intake.get("mechanism") == "twisting injury")

    if guardrail.triggered and guardrail.severity == "urgent":
        return (
            f"{g}some of what you described can be serious. "
            "Please arrange urgent medical assessment today (urgent care or a clinician phone line), "
            "and seek emergency care if symptoms worsen quickly.\n\n"
            f"{_DISCLAIMER}"
        )

    if is_ankle:
        if _ankle_should_escalate(intake):
            return _ankle_urgent_prose(intake)
        need = _ankle_followup_incomplete(intake)
        if need:
            if _ankle_has_multiturn_clinical_context(intake):
                return _ankle_followup_ask_template(intake, loc)
            return _ankle_first_visit_template(intake, loc)
        return (
            f"{g}thanks — I’ve noted you can bear weight, what you see with swelling/bruising, and your pain level. "
            "Keep an eye on red-flag symptoms from earlier; if new numbness, severe pain, or rapid swelling develops, seek care.\n\n"
            f"{_DISCLAIMER}"
        )

    if (
        cat in {"fever", "cough"}
        or "fever" in (intake.get("symptoms") or [])
        or "cough" in (intake.get("symptoms") or [])
    ):
        return (
            f"{g}fever and/or cough are often seen with common viral illnesses, but timing and warning signs matter.\n\n"
            "Rest, fluids, and monitoring temperature can be reasonable for mild cases in otherwise healthy adults, "
            "while watching for breathing difficulty, chest pain, confusion, or dehydration.\n\n"
            "Could you share whether you have shortness of breath, chest pain, stiff neck, or trouble keeping fluids down?\n\n"
            f"{_DISCLAIMER}"
        )

    if cat in {"chest", "sob"} or (
        "chest pain" in (intake.get("symptoms") or [])
        and "shortness of breath" in (intake.get("symptoms") or [])
    ):
        return (
            f"{g}chest discomfort with breathing symptoms needs a cautious approach.\n\n"
            "If symptoms are severe, sudden, or worsening, call your local emergency number now.\n\n"
            "If symptoms are mild and stable, still arrange prompt medical assessment the same day when both are new for you.\n\n"
            f"{_DISCLAIMER}"
        )

    if cat == "rash" or "rash" in (intake.get("symptoms") or []):
        trig = intake.get("food_trigger")
        extra = f" after {trig}" if trig else ""
        return (
            f"{g}a new rash{extra} can have several causes, including irritation or allergy. "
            "I can’t identify the exact cause here.\n\n"
            "Watch for lip or tongue swelling, throat tightness, wheeze, faintness, or spreading hives—those need emergency care.\n\n"
            "If the rash is mild and you feel otherwise well, a clinician can help decide whether antihistamines or other care fit your situation.\n\n"
            "Did you take any new medicines, or have fever or breathing symptoms alongside the rash?\n\n"
            f"{_DISCLAIMER}"
        )

    if cat == "mh" or "anxiety" in (intake.get("symptoms") or []) or "insomnia" in (intake.get("symptoms") or []):
        return (
            f"{g}feeling anxious and sleeping poorly is common, and it can feed on itself.\n\n"
            "Gentle routines—fixed wake time, daylight exposure, limiting late caffeine, and a wind‑down hour—help some people.\n\n"
            "If you have thoughts of harming yourself, seek immediate help from local crisis services.\n\n"
            "What tends to spike the anxiety most (work, health worries, caffeine), and how many nights has sleep been short?\n\n"
            f"{_DISCLAIMER}"
        )

    sy = intake.get("symptoms") or []
    sy_text = ", ".join(sy) if sy else "what you described"
    hand = "\n\nIf you are worried or symptoms worsen, consider speaking with a clinician soon." if handoff_recommended else ""
    return (
        f"{g}thanks for sharing that — I’ve noted {sy_text}.\n\n"
        "If you can add timing, severity, and any red-flag symptoms (chest pain, trouble breathing, confusion, severe pain), "
        "that helps decide how quickly to seek care."
        f"{hand}\n\n"
        f"{_DISCLAIMER}"
    )


def retrieval_hint_from_sources(sources: list[str]) -> str:
    if not sources:
        return ""
    first = sources[0].lower().replace("\\", "/")
    base = first.split("/")[-1]
    return base.replace(".md", "")


def intake_brief_for_model(intake: dict[str, Any]) -> str:
    parts: list[str] = []
    if intake.get("name"):
        parts.append(f"name={intake['name']}")
    if intake.get("chief_complaint"):
        parts.append(f"chief_complaint={intake['chief_complaint']}")
    sy = intake.get("symptoms") or []
    if sy:
        parts.append("symptoms=" + ", ".join(str(s) for s in sy[:10]))
    if intake.get("duration"):
        parts.append(f"duration={intake['duration']}")
    loc = " ".join(p for p in (intake.get("side_or_location"), intake.get("body_part")) if p).strip()
    if loc:
        parts.append(f"location={loc}")
    for k in ("swelling", "bruising", "pain_score", "can_bear_weight", "walking_painful", "worsening_pain"):
        if k in intake and intake[k] is not None:
            parts.append(f"{k}={intake[k]}")
    rf = intake.get("red_flags") or []
    if rf:
        parts.append("red_flags=" + ", ".join(str(r) for r in rf[:8]))
    return "; ".join(parts) if parts else "intake=minimal"
