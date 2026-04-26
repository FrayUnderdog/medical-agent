from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from guardrails import Guardrails
from model import get_default_model_client
from orchestrator import Orchestrator
from schemas import ChatRequest, ChatResponse
from sessions import SessionStore
from mcp_server import router as mcp_router

load_dotenv()

app = FastAPI(title="Medical Agent MVP", version="0.1.0")


store = SessionStore()
guardrails = Guardrails()
orchestrator = Orchestrator(store=store, model=get_default_model_client())

_STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html", media_type="text/html; charset=utf-8")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    session = store.get_or_create(req.session_id)
    guardrail = guardrails.check(req.message)

    result = orchestrator.run(session=session, user_message=req.message, guardrail=guardrail)

    return ChatResponse(
        session_id=session.session_id,
        reply=result.reply,
        guardrail_triggered=result.guardrail_triggered,
        triage_level=result.triage_level,
        retrieval_provider=result.retrieval_provider,
        tool_trace=result.tool_trace,
        tool_outputs=result.tool_outputs,
    )

app.include_router(mcp_router)


app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

