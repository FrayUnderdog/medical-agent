from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from guardrails import GuardrailResult
from intake import build_patient_summary_for_response, extract_patient_intake
from model import MockModelClient, ModelClient, OpenAIModelClient
from sessions import Session, SessionStore
from tools import (
    human_handoff_placeholder,
    knowledge_rag_tool,
    medication_safety_placeholder,
    symptom_extraction,
    triage_suggestion,
)
from user_reply import format_user_facing_answer, intake_brief_for_model, retrieval_hint_from_sources


@dataclass
class OrchestratorResult:
    reply: str
    guardrail_triggered: bool
    triage_level: str | None
    retrieval_provider: str | None
    tool_trace: list[dict[str, Any]]
    tool_outputs: dict
    patient_summary: dict[str, Any]


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
        merged_intake = extract_patient_intake(user_message, session.patient_intake or None)
        session.patient_intake = merged_intake

        session.history.append({"role": "user", "content": user_message})

        if guardrail.triggered and guardrail.severity == "emergency":
            session.history.append({"role": "assistant", "content": guardrail.safe_reply})
            self._store.touch(session)
            reason = (guardrail.reason or "emergency pattern")[:200]
            trace = [
                _trace(
                    "patient_intake",
                    status="ok",
                    summary=f"name={merged_intake.get('name')}, cc={merged_intake.get('chief_complaint')}"[:220],
                ),
                _trace("guardrails", status="triggered", summary=reason),
            ]
            ps = build_patient_summary_for_response(
                merged_intake,
                guardrail_triggered=True,
                guardrail_severity=guardrail.severity,
                triage_level="emergency",
            )
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
                    },
                    "patient_intake": merged_intake,
                },
                patient_summary=ps,
            )

        trace: list[dict[str, Any]] = [
            _trace(
                "patient_intake",
                status="ok",
                summary=f"name={merged_intake.get('name')}, cc={merged_intake.get('chief_complaint')}"[:220],
            ),
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

        session.last_extracted_symptoms = list(symptoms)
        session.last_triage_level = triage_level

        retrieval_hint = retrieval_hint_from_sources(ksrc)

        context = {
            "symptoms": symptoms,
            "triage_level": triage_level,
            "retrieved_context": "",
            "sources": [],
            "handoff_recommended": handoff.output.get("recommended", False),
            "intake_brief": intake_brief_for_model(session.patient_intake),
        }
        _ = self._model.generate(user_message=user_message, context=context)

        reply = format_user_facing_answer(
            user_message=user_message,
            intake=session.patient_intake,
            triage_level=triage_level,
            guardrail=guardrail,
            retrieval_hint=retrieval_hint,
            handoff_recommended=bool(handoff.output.get("recommended", False)),
        )
        trace.append(
            _trace(
                "model",
                status="ok",
                summary=f"reply_chars={len(reply)} (user-facing template)",
                provider=_model_provider(self._model),
            )
        )

        session.history.append({"role": "assistant", "content": reply})
        self._store.touch(session)

        patient_summary = build_patient_summary_for_response(
            session.patient_intake,
            guardrail_triggered=bool(guardrail.triggered),
            guardrail_severity=guardrail.severity,
            triage_level=triage_level,
        )

        tool_outputs = {
            "patient_intake": session.patient_intake,
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
            patient_summary = build_patient_summary_for_response(
                session.patient_intake,
                guardrail_triggered=bool(guardrail.triggered),
                guardrail_severity=guardrail.severity,
                triage_level=triage_level,
            )

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
            patient_summary=patient_summary,
        )
