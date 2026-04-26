# Medical Agent MVP (Mock, Interview-Ready)

Minimal FastAPI backend that demonstrates a clean, explainable "medical agent" architecture without any real LLM, database, or frontend.

## What this is

- FastAPI service with:
  - `GET /health`
  - `POST /chat`
- In-memory session state (no DB)
- A simple orchestrator agent that calls mock tools
- A safety guardrail layer that short-circuits emergency symptoms
- A model client abstraction (defaults to deterministic mock; optional OpenAI integration)

## Interview package

### 1. 90-second project introduction

This is a small **FastAPI** service with `/health` and `/chat` that demonstrates how I’d structure a **medical-style agent** without a database. Each chat request loads an **in-memory session** (keyed by `session_id`), runs **guardrails** first to catch obvious emergency phrasing, then an **orchestrator** calls **mock tools** (symptom extraction, triage, plus placeholders for medication safety, knowledge, and handoff). A **`ModelClient`** turns structured tool output into a user-facing reply. By default it uses a deterministic **`MockModelClient`**, but you can optionally enable a real LLM via **OpenAI** by setting `OPENAI_API_KEY`. The point for interviews is the **separation of concerns**: safety is not buried in the “model,” tools return structured data, and the text generator is a replaceable interface—so a real LLM or real services can slot in without rewriting the whole app.

### 2. Architecture (five bullets)

- **HTTP API** — exposes `/health` and `/chat`; maps JSON to a session + message, returns reply and optional debug-shaped `tool_outputs`.
- **Session memory** — in-process only: each `session_id` maps to one conversation (history and a few last-known fields). Not durable across restarts.
- **Guardrails** — rule-based pre-check; if it fires, the pipeline **short-circuits** to a safe emergency message instead of “helpful” triage.
- **Orchestrator + tools** — deterministic pipeline: extract → triage → placeholders; tools are the place for **factual** or **policy** steps you can test in isolation.
- **Model interface** — today a mock formatter; in production you’d implement the same contract with an LLM client, prompts, and tracing—without changing the route or tool shapes.

### 3. Top 10 likely follow-up questions (short answers)

1. **Why no database?** — Keeps the demo small; sessions are a swappable concern—add Redis/Postgres if you need persistence or multi-instance.
2. **Where would a real LLM go?** — Behind the `ModelClient` interface (`generate`); pass structured `context` and enforce policies on inputs/outputs.
3. **How are guardrails implemented?** — Substring/phrase heuristics for a demo; you’d add tests, expand rules, and possibly a classifier with human review in a real product.
4. **How do you limit hallucination risk?** — Tools ground behavior; the model only narrates `context`. With an LLM, add retrieval citations, stricter system prompts, and refusal on missing data.
5. **How does triage work?** — It’s a **mock** rule: not clinically validated—suitable to show the *shape* of triage, not to ship.
6. **How would you test it?** — Unit-test tools and guardrails; integration tests on `/chat` for emergency vs non-emergency; contract tests on response shape.
7. **Multi-turn?** — Same `session_id` ties turns together; a richer system would pass history or a summary into the model step (not yet the focus of the mock).
8. **Multiple server workers?** — In-memory sessions won’t be shared; use external session store + sticky routing or a shared cache.
9. **PII/PHI?** — Demo stores messages in memory only—**no** HIPAA story; real deployment needs minimization, retention, encryption, access control, and audit.
10. **What did you actually prove?** — A clear **agent loop** and **safety-first ordering**; everything else is intentionally stubbed to stay readable in an interview.

### 4. Known limitations and next-step improvements

**Limitations**

- **No** real clinical validation; triage and extraction are **toys** for structure, not for patients.
- **In-memory** sessions: **lost on process restart**; not suitable for production reliability as-is.
- **Guardrails** are narrow; they can false-negative (miss emergencies) and false-positive (block borderline cases)—real systems need monitoring and escalation paths.
- **No** authentication, rate limits, or structured logging/metrics in this MVP.
- **Mock model** does not use full conversation context for generation (session history is stored for a future “real” model path).

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

## Two-stage RAG (optional reranking)

When Chroma + embeddings are available, retrieval is **two-stage**:

- **Embedding recall**: fetch `recall_top_k = 6` candidate chunks (fast, high-recall).
- **Reranker precision**: optionally rerank candidates with a local **BGE reranker** and keep `rerank_top_n = 3` final chunks (higher precision for the final answer).

Why these numbers for a demo:

- `6` candidates gives the reranker enough choices without slowing down much.
- `3` final chunks keeps prompts short and explainable in an interview.

Fallback behavior (stability-first):

- If the reranker model/deps aren’t available or local inference fails, the system falls back to **embedding-only** ordering.
- If embeddings fail or `OPENAI_API_KEY` is missing, it falls back to **keyword retrieval**.

## Observability and eval

- **`tool_trace`** on `POST /chat`: ordered steps, each with `tool`, `status`, `summary`, and optional **`provider`** (for example RAG `retrieval_provider`, or `mock` / `openai` on the final model step).
- **Eval harness** (no HTTP): `eval_cases.json` + `run_eval.py` calls the orchestrator directly and checks `guardrail_triggered`, `triage_level`, and an expected RAG source filename substring.

```bash
python run_eval.py
```

## Frontend demo flow

Open the app root page and walk through the views:

- **Home / Symptom Intake**: lightweight intake form (optional age/sex + symptom text) that seeds the consultation message.
- **Chat Consultation**: sends messages to `POST /chat` and shows the assistant reply.
- **Emergency View**: automatically shown when `guardrail_triggered=true` or `triage_level=emergency` (includes a clearly-labeled mock “call” button).
- **Triage Result**: patient-facing summary (symptoms, duration, triage, next step).
- **Department Recommendation**: simple routing suggestion derived from `triage_level` (mocked).
- **Clinical Note Summary**: concise handoff summary + an expanded note (demo format).
- **Developer panel (collapsible)**: shows `retrieval_provider`, `reranker_used`, retrieved sources, `tool_trace`, and raw `tool_outputs`.

## Tool schema (interview)

Each pipeline step is documented as a **`ToolSpec`** (`tool_specs.py`): `name`, `description`, `input_fields`, `output_fields`. The registry **`TOOL_SPECS`** maps tool name → spec (including **guardrails** as the pre-step, plus all `ToolResult.name` values from `tools.py`).

```python
from tool_specs import TOOL_SPECS

for name, spec in TOOL_SPECS.items():
    print(name, "—", spec.description)
```

## LangGraph next-version design

This repo keeps **`orchestrator.py`** and **`POST /chat`** as the stable MVP. An **optional** LangGraph experiment lives in **`graph_orchestrator.py`**: same building blocks (`guardrails.py`, `tools.py`, `rag_service.py`, `model.py`) wired as an explicit graph for teaching and iteration.

### State

**`MedicalAgentState`** (`TypedDict`) holds the working slice of data: user `message`, guardrail flags, extracted `symptoms` / `duration_days`, `triage_level`, optional RAG fields (`retrieved_context`, `rag_sources`, `retrieval_provider`), handoff recommendation, and final `reply`. Nodes return **partial updates**; LangGraph merges them into state.

### Nodes

| Node | Role |
|------|------|
| `guardrails_node` | Runs `Guardrails().check(message)`; may set `triage_level` to `emergency` when triggered. |
| `symptom_extraction_node` | Wraps `symptom_extraction`. |
| `triage_node` | Wraps `triage_suggestion` (passes original message for phrase rules). |
| `rag_retrieval_node` | Wraps `knowledge_rag_tool` (Chroma + embeddings or keyword fallback). |
| `human_handoff_node` | Wraps `human_handoff_placeholder` when escalation is on-path. |
| `final_response_node` | Guardrail short-circuit returns `safe_reply`; otherwise calls `ModelClient.generate` with the same style of `context` as the stable orchestrator. |

### Edges

- After **guardrails**: if **`guardrail_triggered`** → **`human_handoff`** → **`final_response`**; else → **`symptom_extraction`** → **`triage`**.
- After **triage**: if **`triage_level`** is **`urgent`** or **`emergency`** → **`human_handoff`** → **`final_response`** (RAG skipped on this path); else → **`rag_retrieval`** → **`final_response`**.

### Why LangGraph helps (interview soundbite)

Linear code is fine for a demo, but real clinical workflows branch on **risk**, **missing data**, and **tool failures** (retrieval, policy APIs, human-in-the-loop). A **graph** makes branches, merges, and retries **first-class**: reviewers see the control flow, you can attach telemetry per node, and you can later swap nodes for async tools or checkpoints—**without** rewriting the HTTP contract or deleting the stable orchestrator.

### Try it locally

```bash
pip install -r requirements.txt
python test_graph_demo.py
```

Quick one-off from Python: `from graph_orchestrator import run_graph_demo` then `run_graph_demo("your message")` (uses the same model selection as the app via `get_default_model_client()`).

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

