from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolResult:
    name: str
    output: dict


SYMPTOM_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fever": ("fever", "temperature"),
    "cough": ("cough", "coughing"),
    "hemoptysis": (
        "hemoptysis",
        "coughing blood",
        "cough up blood",
        "blood in phlegm",
        "blood in sputum",
        "bloody phlegm",
        "bloody sputum",
        "cough with blood",
        "blood with cough",
        "productive cough and blood",
        "blood when i cough",
        "bloody cough",
    ),
    "shortness_of_breath": (
        "shortness of breath",
        "short of breath",
        "trouble breathing",
        "difficulty breathing",
        "breathless",
        "winded",
    ),
    "chest_pain": ("chest pain", "pressure in chest"),
    "stiff_neck": ("stiff neck", "neck stiffness"),
    "confusion": ("confusion", "confused", "disoriented", "altered mental"),
    "sore_throat": ("sore throat", "throat pain"),
    "headache": ("headache", "migraine"),
    "nausea": ("nausea", "queasy"),
    "vomiting": ("vomit", "vomiting", "threw up"),
    "diarrhea": ("diarrhea", "loose stool"),
    "abdominal_pain": ("stomach pain", "abdominal pain", "belly pain"),
    "rash": ("rash", "hives"),
    "dizziness": ("dizzy", "dizziness", "lightheaded"),
}


def symptom_extraction(message: str) -> ToolResult:
    text = message.lower()
    symptoms: list[str] = []
    for canonical, keywords in SYMPTOM_KEYWORDS.items():
        if any(k in text for k in keywords):
            symptoms.append(canonical)

    duration_days: int | None = None
    m = re.search(r"\b(\d{1,2})\s*(day|days)\b", text)
    if m:
        duration_days = int(m.group(1))
    else:
        word_to_days: dict[str, int] = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
        }
        m2 = re.search(r"\b(one|two|three|four|five)\s*(day|days)\b", text)
        if m2:
            duration_days = word_to_days[m2.group(1)]
        elif re.search(r"\ba\s+week\b|\bone\s+week\b", text):
            duration_days = 7

    return ToolResult(
        name="symptom_extraction",
        output={"symptoms": symptoms, "duration_days": duration_days},
    )


def triage_suggestion(symptoms: list[str], duration_days: int | None, message: str = "") -> ToolResult:
    # Minimal deterministic triage logic: not medical advice.
    text = message.lower()
    s = set(symptoms)

    severe_sob = any(
        p in text
        for p in (
            "can't breathe",
            "cannot breathe",
            "can't catch my breath",
            "cannot catch my breath",
            "gasping",
            "blue lips",
            "severe shortness",
            "very short of breath",
        )
    )

    # 3. Chest pain + trouble breathing => emergency
    if "chest_pain" in s and (
        "shortness_of_breath" in s or "trouble breathing" in text or "difficulty breathing" in text
    ):
        return ToolResult(name="triage_suggestion", output={"triage_level": "emergency"})

    # 4. Fever + stiff neck / confusion => emergency
    if "fever" in s and ("stiff_neck" in s or "confusion" in s):
        return ToolResult(name="triage_suggestion", output={"triage_level": "emergency"})

    # 2. Cough + shortness of breath => urgent or emergency by severity
    if "cough" in s and "shortness_of_breath" in s:
        return ToolResult(
            name="triage_suggestion",
            output={"triage_level": "emergency" if severe_sob else "urgent"},
        )

    # 1. Cough + blood / hemoptysis => urgent
    if "cough" in s and "hemoptysis" in s:
        return ToolResult(name="triage_suggestion", output={"triage_level": "urgent"})

    # 5. Prolonged (>=7d) cough or fever => routine vs urgent by red flags
    if duration_days is not None and duration_days >= 7 and ("cough" in s or "fever" in s):
        red = "hemoptysis" in s or "chest_pain" in s or "shortness_of_breath" in s
        return ToolResult(
            name="triage_suggestion",
            output={"triage_level": "urgent" if red else "routine"},
        )

    level = "routine"
    if "fever" in symptoms and duration_days is not None and duration_days >= 3:
        level = "urgent"
    elif "vomiting" in symptoms or "diarrhea" in symptoms:
        level = "routine"
    elif len(symptoms) == 0:
        level = "routine"
    else:
        level = "self_care"

    return ToolResult(name="triage_suggestion", output={"triage_level": level})


def medication_safety_placeholder(message: str) -> ToolResult:
    return ToolResult(
        name="medication_safety",
        output={
            "status": "placeholder",
            "note": "No medication safety logic implemented (mock tool).",
        },
    )


def knowledge_retrieval_placeholder(symptoms: list[str]) -> ToolResult:
    facts: list[str] = []
    if "fever" in symptoms:
        facts.append("Fever can be caused by many infections; hydration and rest often help.")
    if "cough" in symptoms:
        facts.append("A cough may be viral; seek care if worsening or breathing issues occur.")
    if not facts:
        facts.append("No specific knowledge retrieved for these symptoms (placeholder).")

    return ToolResult(
        name="knowledge_retrieval",
        output={"status": "placeholder", "facts": facts},
    )


def knowledge_rag_tool(query: str, *, top_k: int = 4) -> ToolResult:
    from rag_service import retrieve_medical_context

    res = retrieve_medical_context(query, top_k=top_k)
    output: dict = {
        "recall_top_k": res.recall_top_k,
        "rerank_top_n": res.rerank_top_n,
        "reranker_provider": res.reranker_provider,
        "reranker_used": res.reranker_used,
        "retrieved_context": res.retrieved_context,
        "sources": res.sources,
        "top_k": res.top_k,
        "retrieval_provider": res.retrieval_provider,
        "retrieval_trace": res.retrieval_trace,
    }
    if res.retrieval_provider == "keyword_fallback":
        output["retrieval_error"] = res.retrieval_error
    return ToolResult(
        name="knowledge_rag",
        output=output,
    )


def human_handoff_placeholder(triage_level: str | None, guardrail_triggered: bool) -> ToolResult:
    recommended = guardrail_triggered or triage_level in {"urgent", "emergency"}
    return ToolResult(
        name="human_handoff",
        output={
            "recommended": recommended,
            "reason": "guardrail" if guardrail_triggered else "triage",
        },
    )

