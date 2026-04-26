from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from guardrails import GuardrailResult
from model import MockModelClient, ModelClient, OpenAIModelClient
from sessions import Session, SessionStore
from tools import (
    human_handoff_placeholder,
    knowledge_rag_tool,
    medication_safety_placeholder,
    symptom_extraction,
    triage_suggestion,
)


@dataclass
class OrchestratorResult:
    reply: str
    guardrail_triggered: bool
    triage_level: str | None
    retrieval_provider: str | None
    tool_trace: list[dict[str, Any]]
    tool_outputs: dict


def _model_provider(model: ModelClient) -> str:
    if isinstance(model, OpenAIModelClient):
        return "openai"
    if isinstance(model, MockModelClient):
        return "mock"
    return type(model).__name__


def _trace(
    tool: str,
    *,
    status: str,
    summary: str,
    provider: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {"tool": tool, "status": status, "summary": summary}
    if provider:
        row["provider"] = provider
    return row


class Orchestrator:
    def __init__(self, *, store: SessionStore, model: ModelClient) -> None:
        self._store = store
        self._model = model

    def run(self, *, session: Session, user_message: str, guardrail: GuardrailResult) -> OrchestratorResult:
        # Always store user message.
        session.history.append({"role": "user", "content": user_message})

        if guardrail.triggered and guardrail.severity == "emergency":
            session.history.append({"role": "assistant", "content": guardrail.safe_reply})
            self._store.touch(session)
            reason = (guardrail.reason or "emergency pattern")[:200]
            trace = [_trace("guardrails", status="triggered", summary=reason)]
            return OrchestratorResult(
                reply=guardrail.safe_reply or "Emergency safety message.",
                guardrail_triggered=True,
                triage_level="emergency",
                retrieval_provider=None,
                tool_trace=trace,
                tool_outputs={
                    "guardrails": {
                        "triggered": True,
                        "severity": guardrail.severity,
                        "matched_rule_ids": guardrail.matched_rule_ids,
                        "matched_phrases": guardrail.matched_phrases,
                        "reason": guardrail.reason,
                    }
                },
            )

        trace: list[dict[str, Any]] = [
            _trace(
                "guardrails",
                status="flagged" if guardrail.triggered else "ok",
                summary=(guardrail.reason or "no red flags matched")[:200],
                provider=guardrail.severity,
            ),
        ]
        urgent_policy = bool(guardrail.triggered and guardrail.severity == "urgent")

        extracted = symptom_extraction(user_message)
        symptoms = extracted.output["symptoms"]
        duration_days = extracted.output["duration_days"]
        trace.append(
            _trace(
                extracted.name,
                status="ok",
                summary=f"symptoms={symptoms}, duration_days={duration_days}",
            )
        )

        triage = triage_suggestion(symptoms=symptoms, duration_days=duration_days, message=user_message)
        triage_level = triage.output["triage_level"]
        if urgent_policy and triage_level in {"routine", "self_care"}:
            triage_level = "urgent"
        trace.append(
            _trace(
                triage.name,
                status="ok",
                summary=f"triage_level={triage_level}",
            )
        )

        med_safety = medication_safety_placeholder(user_message)
        trace.append(
            _trace(
                med_safety.name,
                status="ok",
                summary=med_safety.output.get("status", "ok"),
            )
        )

        knowledge = knowledge_rag_tool(user_message, top_k=4)
        kprov = knowledge.output.get("retrieval_provider")
        krerank = knowledge.output.get("reranker_used")
        ksrc = knowledge.output.get("sources") or []
        krt = knowledge.output.get("retrieval_trace") or {}
        ksum = (
            f"top_k={knowledge.output.get('top_k')}, rerank={bool(krerank)}, "
            f"fb={krt.get('fallback_triggered')}, sources={ksrc[:3]}"
        )
        trace.append(
            _trace(
                knowledge.name,
                status="ok",
                summary=ksum[:240],
                provider=kprov,
            )
        )

        handoff = human_handoff_placeholder(triage_level=triage_level, guardrail_triggered=urgent_policy)
        trace.append(
            _trace(
                handoff.name,
                status="ok",
                summary=f"recommended={handoff.output.get('recommended')}",
            )
        )

        # Update session state.
        session.last_extracted_symptoms = list(symptoms)
        session.last_triage_level = triage_level

        context = {
            "symptoms": symptoms,
            "triage_level": triage_level,
            "retrieved_context": knowledge.output.get("retrieved_context", ""),
            "sources": knowledge.output.get("sources", []),
            "handoff_recommended": handoff.output.get("recommended", False),
        }
        reply = self._model.generate(user_message=user_message, context=context)
        trace.append(
            _trace(
                "model",
                status="ok",
                summary=f"reply_chars={len(reply)}",
                provider=_model_provider(self._model),
            )
        )

        session.history.append({"role": "assistant", "content": reply})
        self._store.touch(session)

        tool_outputs = {
            extracted.name: extracted.output,
            triage.name: {"triage_level": triage_level},
            med_safety.name: med_safety.output,
            knowledge.name: knowledge.output,
            handoff.name: handoff.output,
            "guardrails": {
                "triggered": bool(guardrail.triggered),
                "severity": guardrail.severity,
                "matched_rule_ids": guardrail.matched_rule_ids,
                "matched_phrases": guardrail.matched_phrases,
                "reason": guardrail.reason,
            },
        }

        # Output consistency validation (minimal, deterministic).
        reply_l = reply.lower()
        implies_emergency = any(
            p in reply_l
            for p in (
                "call your local emergency number",
                "nearest er",
                "emergency room",
                "call 911",
            )
        )
        if implies_emergency and triage_level in {"routine", "self_care"}:
            triage_level = "emergency"
            tool_outputs[triage.name] = {"triage_level": triage_level}

        if triage_level in {"urgent", "emergency"} and not handoff.output.get("recommended"):
            tool_outputs[handoff.name]["recommended"] = True
            tool_outputs[handoff.name]["reason"] = "triage"

        return OrchestratorResult(
            reply=reply,
            guardrail_triggered=bool(guardrail.triggered),
            triage_level=triage_level,
            retrieval_provider=knowledge.output.get("retrieval_provider"),
            tool_trace=trace,
            tool_outputs=tool_outputs,
        )

