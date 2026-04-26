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

    print("---")
    print(f"failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
