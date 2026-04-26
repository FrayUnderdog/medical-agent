"""
Unit tests for rule-based patient intake extraction.

Usage:
  python test_intake.py
"""

from __future__ import annotations

import sys

from intake import extract_patient_intake


def main() -> int:
    failed = 0

    out1 = extract_patient_intake("I'm Ray, I twisted my left ankle two days ago.", None)
    if out1.get("name") != "Ray":
        print(f"FAIL ray name: {out1.get('name')!r}")
        failed += 1
    if out1.get("body_part") != "ankle":
        print(f"FAIL ray body_part: {out1.get('body_part')!r}")
        failed += 1
    if out1.get("side_or_location") != "left":
        print(f"FAIL ray side: {out1.get('side_or_location')!r}")
        failed += 1
    dur = (out1.get("duration") or "").lower()
    if "2" not in dur or "day" not in dur:
        print(f"FAIL ray duration: {out1.get('duration')!r}")
        failed += 1
    if out1.get("likely_department") != "Orthopedics":
        print(f"FAIL ray dept: {out1.get('likely_department')!r}")
        failed += 1
    else:
        print("PASS ray ankle")

    out2 = extract_patient_intake("My name is Amy, I have fever and cough since yesterday.", None)
    if out2.get("name") != "Amy":
        print(f"FAIL amy name: {out2.get('name')!r}")
        failed += 1
    sy2 = [s.lower() for s in (out2.get("symptoms") or [])]
    if "fever" not in sy2 or "cough" not in sy2:
        print(f"FAIL amy symptoms: {out2.get('symptoms')!r}")
        failed += 1
    else:
        print("PASS amy fever cough")

    out3 = extract_patient_intake("I have chest pain and shortness of breath.", None)
    if (out3.get("risk_level_hint") or "").lower() != "emergency":
        print(f"FAIL chest risk: {out3.get('risk_level_hint')!r}")
        failed += 1
    if not (out3.get("red_flags") or []):
        print(f"FAIL chest red_flags: {out3.get('red_flags')!r}")
        failed += 1
    else:
        print("PASS chest emergency")

    out4 = extract_patient_intake("I got a rash after eating peanuts.", None)
    sy4 = " ".join(out4.get("symptoms") or []).lower()
    if "rash" not in sy4 and "allergic" not in sy4:
        print(f"FAIL peanut symptoms: {out4.get('symptoms')!r}")
        failed += 1
    else:
        print("PASS peanut rash")

    out5 = extract_patient_intake("I feel anxious and cannot sleep.", None)
    sy5 = [s.lower() for s in (out5.get("symptoms") or [])]
    if "anxiety" not in sy5 or "insomnia" not in sy5:
        print(f"FAIL mh symptoms: {out5.get('symptoms')!r}")
        failed += 1
    else:
        print("PASS anxiety insomnia")

    # —— Multi-turn Ray ankle: CN + EN follow-ups ——
    session_state: dict = {}
    m1 = "I'm Ray, I twisted my left ankle two days ago."
    m2 = "现在脚踝肿胀的很严重，比受伤时更疼了。"
    m3 = (
        "1) Can you take a few steps on it? Yeah, but it's painful. "
        "2) How much swelling or bruising do you see? I can see a lot bruise around my ankle "
        "3) Roughly how strong is the pain from 1–10? 6"
    )
    out1 = extract_patient_intake(m1, session_state)
    # single-turn follow-up answers (do not require swelling to be present)
    out_follow = extract_patient_intake(m3, out1)
    if (out_follow.get("bruising") or "").lower() != "significant":
        print(f"FAIL ray followup bruising: {out_follow.get('bruising')!r}")
        failed += 1
    out2 = extract_patient_intake(m2, out1)
    out3 = extract_patient_intake(m3, out2)
    if out3.get("name") != "Ray":
        print(f"FAIL ray3 name: {out3.get('name')!r}")
        failed += 1
    if out3.get("body_part") != "ankle":
        print(f"FAIL ray3 body_part: {out3.get('body_part')!r}")
        failed += 1
    if out3.get("side_or_location") != "left":
        print(f"FAIL ray3 side: {out3.get('side_or_location')!r}")
        failed += 1
    dur3 = (out3.get("duration") or "").lower()
    if "2" not in dur3 or "day" not in dur3:
        print(f"FAIL ray3 duration: {out3.get('duration')!r}")
        failed += 1
    if (out3.get("swelling") or "").lower() != "severe":
        print(f"FAIL ray3 swelling: {out3.get('swelling')!r}")
        failed += 1
    if (out3.get("bruising") or "").lower() != "significant":
        print(f"FAIL ray3 bruising: {out3.get('bruising')!r}")
        failed += 1
    if out3.get("walking_painful") is not True:
        print(f"FAIL ray3 walking_painful: {out3.get('walking_painful')!r}")
        failed += 1
    if out3.get("can_bear_weight") is not True:
        print(f"FAIL ray3 can_bear_weight: {out3.get('can_bear_weight')!r}")
        failed += 1
    if out3.get("pain_score") != 6:
        print(f"FAIL ray3 pain_score: {out3.get('pain_score')!r}")
        failed += 1
    if out3.get("worsening_pain") is not True:
        print(f"FAIL ray3 worsening: {out3.get('worsening_pain')!r}")
        failed += 1
    if (out3.get("risk_level_hint") or "").lower() != "urgent":
        print(f"FAIL ray3 risk: {out3.get('risk_level_hint')!r}")
        failed += 1
    af_raw = out3.get("answered_followups") or []
    for key in ("walking", "swelling_or_bruising", "pain_score"):
        if not any((str(x) or "").lower() == key for x in af_raw):
            print(f"FAIL ray3 answered_followups missing {key!r}: {out3.get('answered_followups')!r}")
            failed += 1
    if out3.get("likely_department") != "Orthopedics / Urgent Care":
        print(f"FAIL ray3 dept: {out3.get('likely_department')!r}")
        failed += 1
    else:
        print("PASS ray multirun ankle")

    print("---")
    print(f"failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
