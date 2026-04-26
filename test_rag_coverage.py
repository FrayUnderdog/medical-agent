"""
RAG coverage smoke tests (retrieval + trace). Safe without NHS_API_KEY.

Usage:
  python test_rag_coverage.py
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from guardrails import Guardrails
from rag_service import retrieve_medical_context
from tools import knowledge_rag_tool, symptom_extraction, triage_suggestion


def _print_trace(label: str, out: dict) -> None:
    rt = out.get("retrieval_trace") or {}
    print(f"\n=== {label} ===")
    for k in (
        "offline_retrieved_count",
        "offline_top_score",
        "offline_avg_top5_score",
        "fallback_triggered",
        "fallback_reason",
        "fallback_skipped",
        "nhs_enabled",
        "nhs_results_count",
        "selected_sources",
        "latency_ms",
    ):
        if k in rt:
            print(f"  {k}: {rt[k]}")
    print(f"  sources: {out.get('sources')}")
    print(f"  retrieval_provider: {out.get('retrieval_provider')}")


def _sources_blob(out: dict) -> str:
    return " ".join(out.get("sources") or []).lower()


def _ctx(out: dict) -> str:
    return (out.get("retrieved_context") or "").lower()


def _rag_dict_from_result(res: object) -> dict:
    return {
        "retrieval_trace": getattr(res, "retrieval_trace", {}),
        "sources": getattr(res, "sources", []),
        "retrieved_context": getattr(res, "retrieved_context", ""),
        "retrieval_provider": getattr(res, "retrieval_provider", ""),
    }


def main() -> int:
    load_dotenv()
    failed = 0

    # 1) Ankle
    tr = knowledge_rag_tool("I twisted my left ankle two days ago", top_k=4)
    out = tr.output
    _print_trace("ankle twist", out)
    blob = _sources_blob(out)
    if "ankle_sprain" not in blob and "ankle" not in blob:
        print("FAIL case1: expected ankle-related source path")
        failed += 1
    else:
        print("PASS case1: ankle-related source present")

    # 2) Chest + breath — guardrail; RAG checked separately (orchestrator skips RAG on emergency)
    msg = "I have chest pain and shortness of breath"
    g = Guardrails().check(msg)
    if not (g.triggered and g.severity == "emergency"):
        print(f"FAIL case2: expected emergency guardrail, got triggered={g.triggered} sev={g.severity}")
        failed += 1
    else:
        print("PASS case2: emergency guardrail")

    r2 = retrieve_medical_context(msg, top_k=4)
    r2d = _rag_dict_from_result(r2)
    _print_trace("chest sob (offline retrieval)", r2d)
    b2 = _sources_blob(r2d)
    if "chest_pain" not in b2 or "shortness" not in b2:
        print("FAIL case2b: expected chest_pain and shortness_of_breath in sources")
        failed += 1
    else:
        print("PASS case2b: chest / SOB sources in offline retrieval")

    # 3) Peanut rash
    tr3 = knowledge_rag_tool("I have a skin rash after eating peanuts", top_k=4)
    out3 = tr3.output
    _print_trace("peanut rash", out3)
    b3 = _sources_blob(out3)
    if not any(x in b3 for x in ("allergic_reaction", "hives", "skin_rash")):
        print("FAIL case3: expected allergy / rash sources")
        failed += 1
    else:
        print("PASS case3: allergy or rash sources")
    ctx3 = _ctx(out3)
    if "severe allergic reaction" not in ctx3 and "severe_allergic_reaction" not in b3:
        print("WARN case3: severe allergy red-flag snippet not in top context (may still be acceptable)")

    # 4) GI
    tr4 = knowledge_rag_tool("I have diarrhea and vomiting", top_k=4)
    out4 = tr4.output
    _print_trace("diarrhea vomiting", out4)
    b4 = _sources_blob(out4)
    if "diarrhea" not in b4 or "vomit" not in b4:
        print("FAIL case4: expected diarrhea and vomiting sources")
        failed += 1
    else:
        print("PASS case4: GI sources")

    # 5) Anxiety + sleep
    tr5 = knowledge_rag_tool("I feel anxious and cannot sleep", top_k=4)
    out5 = tr5.output
    _print_trace("anxiety insomnia", out5)
    b5 = _sources_blob(out5)
    c5 = _ctx(out5)
    has_anx = "anxiety" in b5 or "anxiety" in c5
    has_sleep = "insomnia" in b5 or "insomnia" in c5 or "sleep" in c5
    if not (has_anx and has_sleep):
        print("FAIL case5: expected anxiety + sleep/insomnia coverage in sources or context")
        failed += 1
    else:
        print("PASS case5: anxiety / sleep coverage")

    rt5 = out5.get("retrieval_trace") or {}
    if rt5.get("fallback_triggered") and not rt5.get("nhs_enabled"):
        if rt5.get("fallback_skipped") != "missing_api_key":
            print(
                "INFO: fallback triggered without NHS key — "
                f"fallback_skipped={rt5.get('fallback_skipped')!r} "
                "(expected missing_api_key when gate fires on keyword/Chroma path)"
            )

    sx = symptom_extraction(msg)
    trg = triage_suggestion(sx.output["symptoms"], sx.output["duration_days"], message=msg)
    print(f"\nTriage for chest case: {trg.output!r}")

    print("\n--- summary ---")
    print(f"failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
