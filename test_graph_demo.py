"""
Run three fixed messages through the LangGraph medical demo (MockModelClient for stable output).

Usage:
  python test_graph_demo.py
"""

from __future__ import annotations

from graph_orchestrator import compile_medical_graph
from model import MockModelClient


CASES = [
    "I have chest pain and trouble breathing",
    "I have a fever for two days",
    "I have productive cough with blood for about a week",
]


def main() -> None:
    app = compile_medical_graph(MockModelClient())
    for msg in CASES:
        out = app.invoke({"message": msg})
        print("---")
        print("message:", msg)
        print("guardrail_triggered:", out.get("guardrail_triggered"))
        print("triage_level:", out.get("triage_level"))
        print("retrieval_provider:", out.get("retrieval_provider"))
        print("reply (first 200 chars):", (out.get("reply") or "")[:200])


if __name__ == "__main__":
    main()
