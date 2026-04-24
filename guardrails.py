from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailResult:
    triggered: bool
    reason: str | None = None
    safe_reply: str | None = None


class Guardrails:
    """
    Very small, interview-friendly guardrail layer.

    This is intentionally rule-based (no ML): easy to reason about, easy to test.
    """

    EMERGENCY_PHRASES: tuple[str, ...] = (
        "chest pain",
        "pressure in chest",
        "shortness of breath",
        "can't breathe",
        "difficulty breathing",
        "severe bleeding",
        "passed out",
        "fainted",
        "seizure",
        "face drooping",
        "slurred speech",
        "one-sided weakness",
        "suicidal",
        "overdose",
    )

    def check(self, message: str) -> GuardrailResult:
        text = message.lower()
        for phrase in self.EMERGENCY_PHRASES:
            if phrase in text:
                return GuardrailResult(
                    triggered=True,
                    reason=f"Matched emergency phrase: '{phrase}'",
                    safe_reply=(
                        "I’m concerned your symptoms could be an emergency. "
                        "Please call your local emergency number (or go to the nearest ER) now. "
                        "If you can, ask someone to stay with you. "
                        "I can’t safely triage this via chat."
                    ),
                )

        return GuardrailResult(triggered=False)

