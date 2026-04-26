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

    if guardrail.triggered and guardrail.severity == "urgent":
        return (
            f"{g}some of what you described can be serious. "
            "Please arrange urgent medical assessment today (urgent care or a clinician phone line), "
            "and seek emergency care if symptoms worsen quickly.\n\n"
            f"{_DISCLAIMER}"
        )

    if cat == "ankle" or (intake.get("body_part") == "ankle" and intake.get("mechanism") == "twisting injury"):
        dur = intake.get("duration") or "the past couple of days"
        return (
            f"{g}a twisted {loc or 'ankle'} for {dur} often fits a sprain-type injury. "
            "I can’t tell you for certain what happened without an exam.\n\n"
            "Many people are advised to try relative rest, ice, comfortable compression, and elevation early on, "
            "and to increase gentle movement as pain allows.\n\n"
            "Please seek urgent care now if you cannot bear weight, notice major deformity, numb/cold toes, "
            "severe swelling, or pain that is rapidly worsening.\n\n"
            "To guide next steps, could you share:\n"
            "1) Can you take a few steps on it?\n"
            "2) How much swelling or bruising do you see?\n"
            "3) Roughly how strong is the pain from 1–10?\n\n"
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
        "chest pain" in (intake.get("symptoms") or []) and "shortness of breath" in (intake.get("symptoms") or [])
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
    rf = intake.get("red_flags") or []
    if rf:
        parts.append("red_flags=" + ", ".join(str(r) for r in rf[:8]))
    return "; ".join(parts) if parts else "intake=minimal"
