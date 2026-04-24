# Medical Agent (version-1: MVP)

Minimal FastAPI backend that demonstrates a clean, explainable "medical agent" architecture with fine-tuned LLM and user-friendly frontend.

## What this is

- FastAPI service with:
  - `GET /health`
  - `POST /chat`
- In-memory session state
- A simple orchestrator agent that calls mock tools
- A safety guardrail layer that short-circuits emergency symptoms
- A model client abstraction (defaults to deterministic mock; optional OpenAI integration)


**Next steps (practical order)**

- Swap `MockModelClient` for a real **LLM client** with evals and red-team prompts; keep the same `ModelClient` contract.
- Back **session store** with **Redis** (TTL) or a small DB; add idempotent session creation if needed.
- Implement real **knowledge_retrieval** (RAG) with source citations; wire **medication_safety** to a vetted knowledge base or API, not free-form LLM.
- Add **observability** (structured logs, trace ids, tool latency) and **basic security** (auth, PII redaction, rate limits).
- Expand **test suite** and a small **eval set** of emergency vs benign utterances for guardrails.

## Run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/health`.

## Optional: enable a real LLM (OpenAI)

By default, the app uses `MockModelClient` (deterministic, interview-friendly).

To enable OpenAI:

```bash
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`, then start the server as usual. If `OPENAI_API_KEY` is missing, the app automatically falls back to `MockModelClient`.

Optional:

- `OPENAI_MODEL` in `.env.example` is a placeholder for model selection; the current implementation uses its internal default unless you wire that env var in.

## Minimal RAG (LangChain + Chroma)

This repo includes a tiny local RAG pipeline over markdown files in `docs/medical_knowledge/`.

- Vectors are persisted locally in `chroma_db/`.
- Embeddings use OpenAI `text-embedding-3-small` when `OPENAI_API_KEY` is set.
- If embeddings fail or the key is missing, it falls back to simple keyword retrieval.

## Observability and eval

- **`tool_trace`** on `POST /chat`: ordered steps, each with `tool`, `status`, `summary`, and optional **`provider`** (for example RAG `retrieval_provider`, or `mock` / `openai` on the final model step).
- **Eval harness** (no HTTP): `eval_cases.json` + `run_eval.py` calls the orchestrator directly and checks `guardrail_triggered`, `triage_level`, and an expected RAG source filename substring.

```bash
python run_eval.py
```

## Tool schema

Each pipeline step is documented as a **`ToolSpec`** (`tool_specs.py`): `name`, `description`, `input_fields`, `output_fields`. The registry **`TOOL_SPECS`** maps tool name → spec (including **guardrails** as the pre-step, plus all `ToolResult.name` values from `tools.py`).

```python
from tool_specs import TOOL_SPECS

for name, spec in TOOL_SPECS.items():
    print(name, "—", spec.description)
```

## Example request

```bash
curl -X POST http://127.0.0.1:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\": null, \"message\": \"I have a fever and cough for 2 days\"}"
```

## Example response (non-emergency)

Example response body shape (truncated for readability):

```json
{
  "session_id": "2b4a...9f1c",
  "guardrail_triggered": false,
  "triage_level": "self_care",
  "retrieval_provider": "keyword_fallback",
  "tool_trace": [
    { "tool": "guardrails", "status": "ok", "summary": "no emergency phrases matched" },
    { "tool": "symptom_extraction", "status": "ok", "summary": "symptoms=[...], duration_days=..." },
    { "tool": "knowledge_rag", "status": "ok", "summary": "top_k=..., sources=[...]", "provider": "keyword_fallback" },
    { "tool": "model", "status": "ok", "summary": "reply_chars=...", "provider": "mock" }
  ],
  "reply": "…",
  "tool_outputs": {
    "symptom_extraction": { "symptoms": ["fever", "cough"], "duration_days": 2 },
    "triage_suggestion": { "triage_level": "self_care" },
    "medication_safety": { "status": "placeholder", "note": "No medication safety logic implemented (mock tool)." },
    "knowledge_rag": { "retrieved_context": "...", "sources": ["fever.md"], "top_k": 4, "retrieval_provider": "keyword_fallback" },
    "human_handoff": { "recommended": false, "reason": "triage" },
    "guardrails": { "triggered": false }
  }
}
```

## Multi-turn session memory

The client keeps a **single** `session_id` across turns. The server ties that id to one conversation: each `/chat` call updates the same session (e.g. message history and a few fields you would pass into a real model). **No database** — state lives only in the running server.

**Limitation:** if the **server restarts**, in-memory sessions are **gone**; the client’s old `session_id` will not recover prior turns unless you add persistent storage later.

**Turn 1** — new conversation (`session_id: null`); **save** the `session_id` from the JSON response.

```bash
curl -X POST http://127.0.0.1:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\": null, \"message\": \"I have fever and cough for two days\"}"
```

**What to expect (Turn 1) — highlights**

- A new `session_id` in the body (use it for Turn 2).
- `guardrail_triggered: false` for a typical minor-illness message.
- `triage_level` set by the mock triage step (e.g. `self_care` here).
- `tool_outputs.symptom_extraction` includes symptoms such as `fever`, `cough` and `duration_days: 2` when phrased that way.
- A `reply` that reflects extracted symptoms and mock triage.

**Turn 2** — same conversation: **replace the UUID** below with the `session_id` you received from Turn 1.

```bash
curl -X POST http://127.0.0.1:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\": \"8f0e2c1a-3b4d-4e5f-9a0b-1c2d3e4f5a6b\", \"message\": \"Now I also feel tired\"}"
```

**What to expect (Turn 2) — highlights**

- The **same** `session_id` echoed back (confirms you stayed on one thread).
- `guardrail_triggered: false` unless the new text hits an emergency pattern.
- `tool_outputs` computed for **this** message (the mock extractors are keyword-based, so a short follow-up may yield fewer or no new symptoms than Turn 1).
- A fresh `reply` for the new text; the server-side session has now recorded both user turns for a future “real” model or richer orchestration.

## Safety disclaimer

This is a demo framework. It is not medical advice and is not intended for real clinical use.

