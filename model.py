from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


class ModelClient(Protocol):
    def generate(self, *, user_message: str, context: dict) -> str: ...


@dataclass
class MockModelClient:
    """
    Deterministic "model" for interview demos.
    """

    def generate(self, *, user_message: str, context: dict) -> str:
        symptoms = context.get("symptoms") or []
        triage = context.get("triage_level")
        retrieved_context = context.get("retrieved_context") or ""
        sources = context.get("sources") or []
        handoff = context.get("handoff_recommended", False)

        lines: list[str] = []
        lines.append("Thanks — I can help think through this (not medical advice).")

        if symptoms:
            pretty = ", ".join(symptoms)
            lines.append(f"What I picked up from your message: {pretty}.")
        else:
            lines.append("I couldn’t confidently extract specific symptoms from your message.")

        if triage:
            lines.append(f"Suggested triage level (mock): {triage}.")

        if retrieved_context:
            lines.append("Relevant notes (retrieved):")
            snippet = retrieved_context.strip().replace("\n", " ")
            lines.append(f"- {snippet[:240]}{'...' if len(snippet) > 240 else ''}")
            if sources:
                lines.append(f"Sources: {', '.join(sources[:5])}")

        if handoff:
            lines.append("If you’re worried or symptoms worsen, consider speaking with a clinician.")

        lines.append("If you share age, key medical conditions, and any red-flag symptoms, I can refine the next steps.")
        return "\n".join(lines)


@dataclass
class OpenAIModelClient:
    api_key: str
    model: str = "gpt-4.1-mini"

    def generate(self, *, user_message: str, context: dict) -> str:
        # Imported here so the app can still boot (and use MockModelClient)
        # when OPENAI_API_KEY is missing.
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)

        system = (
            "You are a careful medical triage assistant for a demo app. "
            "You are not a doctor. Do not provide diagnoses. "
            "Use the provided structured context (symptoms/triage/facts/handoff) to write a short, "
            "helpful next-steps reply with a safety disclaimer and a few follow-up questions."
        )

        user = (
            "User message:\n"
            f"{user_message}\n\n"
            "Structured context (authoritative):\n"
            f"{context}\n"
        )

        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )

        content = (resp.choices[0].message.content or "").strip()
        return content or "Thanks — I can help think through this (not medical advice)."


def get_default_model_client() -> ModelClient:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return MockModelClient()
    try:
        return OpenAIModelClient(api_key=api_key)
    except Exception:
        # If the OpenAI client can't initialize for any reason, keep the app usable.
        return MockModelClient()

