"""
Optional NHS Website / Content API client (transient retrieval fallback).

Endpoint may need adjustment according to the NHS Website Content API
subscription / OAS spec — keep this module as a thin, replaceable wrapper.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote, urljoin


class NHSContentClient:
    """Lightweight search client; never raises to callers of `search`."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_s: float = 5.0,
    ) -> None:
        self._api_key = (api_key if api_key is not None else os.environ.get("NHS_API_KEY", "") or "").strip()
        self._base_url = (base_url if base_url is not None else os.environ.get("NHS_API_BASE_URL", "")).strip()
        if not self._base_url:
            # Placeholder default — replace with your subscribed host + path per NHS docs.
            self._base_url = "https://api.nhs.uk/conditions/v1"
        self._timeout_s = timeout_s
        self._last_skip_reason: str | None = None
        self._last_error: str | None = None

    def is_enabled(self) -> bool:
        return bool(self._api_key)

    def last_skip_reason(self) -> str | None:
        return self._last_skip_reason

    def last_error(self) -> str | None:
        return self._last_error

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        """
        Returns a list of uniform dicts (empty on any failure or when disabled).

        Shape:
          {"title": str, "url": str, "summary": str, "source": "nhs_api"}
        """
        self._last_skip_reason = None
        self._last_error = None

        if not query or not query.strip():
            self._last_skip_reason = "empty_query"
            return []

        if not self.is_enabled():
            self._last_skip_reason = "missing_api_key"
            return []

        try:
            import requests
        except Exception as exc:  # pragma: no cover - optional import path
            self._last_error = f"requests_import:{type(exc).__name__}"
            return []

        # Minimal GET pattern — adjust path/query per your API subscription.
        q = quote(query.strip()[:200])
        root = self._base_url.rstrip("/") + "/"
        # Common pattern: collection root + /conditions?query=...
        url = urljoin(root, f"conditions?search={q}")

        try:
            resp = requests.get(
                url,
                headers={"subscription-key": self._api_key},
                timeout=self._timeout_s,
            )
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}:{exc}"
            return []

        if resp.status_code >= 400:
            self._last_error = f"http_{resp.status_code}"
            return []

        try:
            payload = resp.json()
        except Exception as exc:
            self._last_error = f"json_decode:{type(exc).__name__}"
            return []

        return _normalize_nhs_payload(payload, limit=limit)


def _normalize_nhs_payload(payload: Any, *, limit: int) -> list[dict[str, Any]]:
    """
    Best-effort mapping of unknown JSON into the unified result shape.
    Replace with strict parsing once the OAS for your subscription is fixed.
    """
    out: list[dict[str, Any]] = []
    items: list[Any] = []

    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        for key in ("results", "conditions", "data", "items", "value"):
            v = payload.get(key)
            if isinstance(v, list):
                items = v
                break
        if not items and "name" in payload:
            items = [payload]

    for raw in items[:limit]:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("name") or raw.get("title") or raw.get("heading") or "NHS topic").strip()
        url = str(raw.get("url") or raw.get("webUrl") or raw.get("link") or "").strip()
        summary = str(
            raw.get("description")
            or raw.get("summary")
            or raw.get("synopsis")
            or raw.get("overview")
            or ""
        ).strip()
        if len(summary) > 800:
            summary = summary[:800] + "…"
        out.append(
            {
                "title": title,
                "url": url,
                "summary": summary or "No summary returned by API.",
                "source": "nhs_api",
            }
        )

    return out
