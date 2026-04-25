from __future__ import annotations

from dataclasses import dataclass

from safety_policy import RED_FLAG_RULES


@dataclass(frozen=True)
class GuardrailResult:
    triggered: bool
    severity: str | None = None  # "emergency" | "urgent"
    matched_rule_ids: list[str] | None = None
    matched_phrases: list[str] | None = None
    reason: str | None = None
    safe_reply: str | None = None


class Guardrails:
    def check(self, message: str) -> GuardrailResult:
        text = message.lower()
        matched_rule_ids: list[str] = []
        matched_phrases: list[str] = []
        severities: list[str] = []
        reasons: list[str] = []

        for rule in RED_FLAG_RULES:
            hits = [p for p in rule.patterns if p in text]
            if hits:
                matched_rule_ids.append(rule.id)
                matched_phrases.extend(hits[:3])
                severities.append(rule.severity)
                reasons.append(rule.reason)

        if not matched_rule_ids:
            return GuardrailResult(triggered=False, severity=None, matched_rule_ids=[], matched_phrases=[])

        severity = "emergency" if "emergency" in severities else "urgent"
        reason = "; ".join(dict.fromkeys(reasons))[:240]

        if severity == "emergency":
            safe_reply = (
                "I’m concerned your symptoms could be an emergency. "
                "Please call your local emergency number (or go to the nearest ER) now. "
                "If you can, ask someone to stay with you. "
                "I can’t safely triage this via chat."
            )
        else:
            safe_reply = (
                "Some symptoms you mentioned can be serious. "
                "I recommend getting urgent medical evaluation (urgent care or contacting a clinician) soon. "
                "If symptoms rapidly worsen or you have trouble breathing, seek emergency care."
            )

        return GuardrailResult(
            triggered=True,
            severity=severity,
            matched_rule_ids=matched_rule_ids,
            matched_phrases=list(dict.fromkeys(matched_phrases))[:8],
            reason=reason,
            safe_reply=safe_reply,
        )

