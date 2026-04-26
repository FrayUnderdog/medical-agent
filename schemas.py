from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = Field(
        default=None, description="If omitted, the server will create one."
    )
    message: str = Field(..., min_length=1, description="User message.")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    guardrail_triggered: bool
    triage_level: str | None = None
    retrieval_provider: str | None = None
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)
    tool_outputs: dict = Field(default_factory=dict)
    patient_summary: dict[str, Any] | None = Field(
        default=None,
        description="Structured summary for UI; not a diagnosis.",
    )

