"""
Smoke tests for ankle dialogue policy in user_reply (no RAG / orchestrator).
Usage:  python test_user_reply_ankle.py
"""

from __future__ import annotations

import sys

from guardrails import GuardrailResult
from user_reply import format_user_facing_answer


def _gr() -> GuardrailResult:
    return GuardrailResult(
        triggered=False, severity=None, reason=None, matched_rule_ids=None, matched_phrases=None
    )


def main() -> int:
    failed = 0
    # Escalation path: should recommend clinician/urgent care, not re-ask the three follow-ups
    full = {
        "name": "Ray",
        "body_part": "ankle",
        "side_or_location": "left",
        "duration": "2 days",
        "mechanism": "twisting injury",
        "swelling": "severe",
        "bruising": "significant",
        "can_bear_weight": True,
        "walking_painful": True,
        "pain_score": 6,
        "worsening_pain": True,
        "risk_level_hint": "urgent",
        "answered_followups": ["walking", "swelling_or_bruising", "pain_score"],
    }
    out = format_user_facing_answer(
        user_message="(follow-up)",
        intake=full,
        triage_level="self_care",
        guardrail=_gr(),
        retrieval_hint="ankle_sprain",
        handoff_recommended=False,
    )
    low = out.lower()
    if "can you take a few steps" in low:
        print("FAIL escalated: should not repeat walk question")
        failed += 1
    if "urgent care" not in low and "clinician" not in low:
        print("FAIL escalated: expected urgent care or clinician")
        failed += 1
    if "fracture" not in low and "ligament" not in low:
        print("FAIL escalated: expected rule-out fracture / ligament wording")
        failed += 1
    else:
        print("PASS user_reply escalated ankle")

    # Incomplete: first visit, no follow-up context yet -> long template includes all three ask lines
    first = {
        "name": "Ray",
        "body_part": "ankle",
        "side_or_location": "left",
        "duration": "2 days",
        "mechanism": "twisting injury",
        "risk_level_hint": "routine",
    }
    out2 = format_user_facing_answer(
        user_message="I twisted my ankle",
        intake=first,
        triage_level="routine",
        guardrail=_gr(),
        retrieval_hint="ankle_sprain",
        handoff_recommended=False,
    )
    if "can you take a few steps" not in out2.lower():
        print("FAIL first visit: expected walking question")
        failed += 1
    else:
        print("PASS user_reply first visit asks follow-ups")

    print(f"failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
