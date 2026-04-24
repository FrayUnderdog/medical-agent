from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class Session:
    session_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    history: list[dict] = field(default_factory=list)

    last_triage_level: str | None = None
    last_extracted_symptoms: list[str] = field(default_factory=list)


class SessionStore:
    """
    Minimal in-memory session state.

    Trade-off: no persistence; resets on restart.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str | None) -> Session:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]

        new_id = session_id or str(uuid4())
        session = Session(session_id=new_id)
        self._sessions[new_id] = session
        return session

    def touch(self, session: Session) -> None:
        session.updated_at = datetime.now(timezone.utc)

