"""
Optional LangGraph orchestration experiment (does not replace stable orchestrator.py).

Build with compile_medical_graph(model) or quick-test with run_graph_demo(message).
"""

from __future__ import annotations

from typing import Any, Literal

from typing_extensions import TypedDict

from guardrails import Guardrails
from model import ModelClient, get_default_model_client
from tools import (
    human_handoff_placeholder,
    knowledge_rag_tool,
    symptom_extraction,
    triage_suggestion,
)


class MedicalAgentState(TypedDict, total=False):
    """Shared graph state; nodes return partial updates."""

    message: str
    guardrail_triggered: bool
    guardrail_reason: str | None
    safe_reply: str | None
    triage_level: str | None
    symptoms: list[str]
    duration_days: int | None
    handoff_recommended: bool
    handoff_reason: str
    retrieved_context: str
    rag_sources: list[str]
    retrieval_provider: str | None
    reply: str


def guardrails_node(state: MedicalAgentState) -> dict[str, Any]:
    result = Guardrails().check(state["message"])
    out: dict[str, Any] = {
        "guardrail_triggered": result.triggered,
        "guardrail_reason": result.reason,
        "safe_reply": result.safe_reply,
    }
    if result.triggered and result.severity == "emergency":
        out["triage_level"] = "emergency"
    elif result.triggered and result.severity == "urgent":
        out["triage_level"] = "urgent"
    return out


def symptom_extraction_node(state: MedicalAgentState) -> dict[str, Any]:
    ex = symptom_extraction(state["message"])
    return {
        "symptoms": ex.output["symptoms"],
        "duration_days": ex.output["duration_days"],
    }


def triage_node(state: MedicalAgentState) -> dict[str, Any]:
    tr = triage_suggestion(
        symptoms=state.get("symptoms") or [],
        duration_days=state.get("duration_days"),
        message=state["message"],
    )
    return {"triage_level": tr.output["triage_level"]}


def human_handoff_node(state: MedicalAgentState) -> dict[str, Any]:
    h = human_handoff_placeholder(
        triage_level=state.get("triage_level"),
        guardrail_triggered=bool(state.get("guardrail_triggered")),
    )
    return {
        "handoff_recommended": h.output["recommended"],
        "handoff_reason": h.output["reason"],
    }


def rag_retrieval_node(state: MedicalAgentState) -> dict[str, Any]:
    k = knowledge_rag_tool(state["message"], top_k=4)
    return {
        "retrieved_context": k.output.get("retrieved_context", ""),
        "rag_sources": list(k.output.get("sources") or []),
        "retrieval_provider": k.output.get("retrieval_provider"),
    }


def _route_after_guardrails(state: MedicalAgentState) -> Literal["handoff_branch", "extract_branch"]:
    if state.get("guardrail_triggered") and state.get("triage_level") == "emergency":
        return "handoff_branch"
    return "extract_branch"


def _route_after_triage(state: MedicalAgentState) -> Literal["urgent_branch", "normal_branch"]:
    level = state.get("triage_level")
    if level in ("urgent", "emergency"):
        return "urgent_branch"
    return "normal_branch"


def _make_final_response_node(model: ModelClient):
    def final_response_node(state: MedicalAgentState) -> dict[str, Any]:
        if state.get("guardrail_triggered"):
            return {"reply": state.get("safe_reply") or "Emergency safety message."}

        h_rec = state.get("handoff_recommended")
        if h_rec is None:
            h = human_handoff_placeholder(
                triage_level=state.get("triage_level"),
                guardrail_triggered=False,
            )
            h_rec = h.output["recommended"]

        context = {
            "symptoms": state.get("symptoms") or [],
            "triage_level": state.get("triage_level"),
            "retrieved_context": state.get("retrieved_context", ""),
            "sources": state.get("rag_sources") or [],
            "handoff_recommended": h_rec,
        }
        reply = model.generate(user_message=state["message"], context=context)
        return {"reply": reply}

    return final_response_node


def compile_medical_graph(model: ModelClient):
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(MedicalAgentState)
    g.add_node("guardrails", guardrails_node)
    g.add_node("symptom_extraction", symptom_extraction_node)
    g.add_node("triage", triage_node)
    g.add_node("human_handoff", human_handoff_node)
    g.add_node("rag_retrieval", rag_retrieval_node)
    g.add_node("final_response", _make_final_response_node(model))

    g.add_edge(START, "guardrails")
    g.add_conditional_edges(
        "guardrails",
        _route_after_guardrails,
        {
            "handoff_branch": "human_handoff",
            "extract_branch": "symptom_extraction",
        },
    )
    g.add_edge("symptom_extraction", "triage")
    g.add_conditional_edges(
        "triage",
        _route_after_triage,
        {
            "urgent_branch": "human_handoff",
            "normal_branch": "rag_retrieval",
        },
    )
    g.add_edge("human_handoff", "final_response")
    g.add_edge("rag_retrieval", "final_response")
    g.add_edge("final_response", END)
    return g.compile()


def run_graph_demo(message: str) -> MedicalAgentState:
    """Local smoke test using the same model selection as the FastAPI app."""
    app = compile_medical_graph(get_default_model_client())
    return app.invoke({"message": message})
