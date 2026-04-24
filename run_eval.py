"""
Minimal eval harness: calls Orchestrator + Guardrails directly (no HTTP).

Usage:
  python run_eval.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from guardrails import Guardrails
from model import MockModelClient
from orchestrator import Orchestrator
from sessions import SessionStore


def main() -> int:
    load_dotenv()
    root = Path(__file__).resolve().parent
    cases_path = root / "eval_cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))

    store = SessionStore()
    orchestrator = Orchestrator(store=store, model=MockModelClient())
    guardrails = Guardrails()

    passed = 0
    failed = 0

    for case in cases:
        name = case["name"]
        message = case["message"]
        exp = case["expected"]

        session = store.get_or_create(None)
        guard = guardrails.check(message)
        result = orchestrator.run(session=session, user_message=message, guardrail=guard)

        errors: list[str] = []

        if result.guardrail_triggered != exp["guardrail_triggered"]:
            errors.append(
                f"guardrail_triggered: got {result.guardrail_triggered}, "
                f"expected {exp['guardrail_triggered']}"
            )

        if "triage_level" in exp and result.triage_level != exp["triage_level"]:
            errors.append(f"triage_level: got {result.triage_level!r}, expected {exp['triage_level']!r}")

        if "rag_source_contains" in exp:
            kr = result.tool_outputs.get("knowledge_rag") or {}
            sources = kr.get("sources") or []
            needle = exp["rag_source_contains"]
            if not any(needle in s for s in sources):
                errors.append(f"RAG sources {sources!r} missing substring {needle!r}")

        if errors:
            failed += 1
            print(f"FAIL  {name}")
            for e in errors:
                print(f"        {e}")
        else:
            passed += 1
            print(f"PASS  {name}")

    print("---")
    print(f"Summary: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
