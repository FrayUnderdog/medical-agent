"""
Lightweight tool metadata for interviews and docs.

Runtime tools are unchanged; this module only describes their contract.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_fields: dict[str, str]
    output_fields: dict[str, str]


# Specs align with `ToolResult.name` values (and the guardrails pre-step used by the orchestrator).
TOOL_SPECS: dict[str, ToolSpec] = {
    "guardrails": ToolSpec(
        name="guardrails",
        description="Structured safety-policy pre-check on the raw user message; emergency short-circuits, urgent escalates.",
        input_fields={
            "message": "str — user utterance before tools or model.",
        },
        output_fields={
            "triggered": "bool — whether any red-flag rule matched.",
            "severity": "str | null — emergency | urgent when triggered.",
            "matched_rule_ids": "list[str] — ids of matched rules.",
            "matched_phrases": "list[str] — matched substrings.",
            "reason": "str | null — short explanation.",
            "safe_reply": "str | null — safety message (emergency or urgent guidance).",
        },
    ),
    "symptom_extraction": ToolSpec(
        name="symptom_extraction",
        description="Deterministic keyword extraction of canonical symptoms and simple duration hints.",
        input_fields={
            "message": "str — user utterance.",
        },
        output_fields={
            "symptoms": "list[str] — canonical symptom ids (e.g. fever, cough).",
            "duration_days": "int | null — days if parsed from text.",
        },
    ),
    "triage_suggestion": ToolSpec(
        name="triage_suggestion",
        description="Deterministic triage bucket (demo only; not clinically validated).",
        input_fields={
            "symptoms": "list[str] — from symptom_extraction.",
            "duration_days": "int | null — from symptom_extraction.",
            "message": "str — original user text for a few phrase-based rules.",
        },
        output_fields={
            "triage_level": "str — e.g. self_care, routine, urgent, emergency.",
        },
    ),
    "medication_safety": ToolSpec(
        name="medication_safety",
        description="Placeholder hook for future medication interaction checks.",
        input_fields={
            "message": "str — user utterance.",
        },
        output_fields={
            "status": "str — e.g. placeholder.",
            "note": "str — human-readable stub explanation.",
        },
    ),
    "knowledge_retrieval": ToolSpec(
        name="knowledge_retrieval",
        description="Legacy placeholder facts from symptoms (not used by the live orchestrator path).",
        input_fields={
            "symptoms": "list[str] — from symptom_extraction.",
        },
        output_fields={
            "status": "str — e.g. placeholder.",
            "facts": "list[str] — static demo strings.",
        },
    ),
    "knowledge_rag": ToolSpec(
        name="knowledge_rag",
        description="Retrieve grounded snippets from local markdown via Chroma + OpenAI embeddings, with keyword fallback.",
        input_fields={
            "query": "str — typically the user message.",
            "top_k": "int — max chunks to retrieve (default 4).",
        },
        output_fields={
            "retrieved_context": "str — joined chunk text for the model.",
            "sources": "list[str] — source filenames (e.g. fever.md).",
            "top_k": "int — effective top_k used.",
            "retrieval_provider": "str — chroma_openai_embeddings | keyword_fallback.",
            "retrieval_error": "str | omitted — short error when in keyword_fallback.",
        },
    ),
    "human_handoff": ToolSpec(
        name="human_handoff",
        description="Placeholder recommendation for escalating to a human based on triage or guardrails.",
        input_fields={
            "triage_level": "str | null — from triage_suggestion.",
            "guardrail_triggered": "bool — whether guardrails fired.",
        },
        output_fields={
            "recommended": "bool — whether handoff is suggested.",
            "reason": "str — guardrail | triage.",
        },
    ),
}
