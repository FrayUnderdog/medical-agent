from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app


def _pp(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)


def main() -> None:
    client = TestClient(app)

    # 1) tool discovery
    r = client.get("/mcp/tools")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "tools" in body and isinstance(body["tools"], list) and len(body["tools"]) >= 4, _pp(body)
    tool_names = {t.get("name") for t in body["tools"]}
    for expected in {"ehr_lookup", "appointment_lookup", "book_appointment", "pharmacy_lookup"}:
        assert expected in tool_names, f"Missing tool: {expected}. got={tool_names}"

    # 2) ehr_lookup
    r = client.post("/mcp/execute", json={"tool_name": "ehr_lookup", "arguments": {"patient_id": "demo_patient_001"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True, _pp(body)
    assert body["tool_name"] == "ehr_lookup", _pp(body)
    assert body["result"]["patient_id"] == "demo_patient_001", _pp(body)

    # 3) appointment_lookup
    r = client.post(
        "/mcp/execute",
        json={"tool_name": "appointment_lookup", "arguments": {"department": "primary_care"}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True, _pp(body)
    assert body["tool_name"] == "appointment_lookup", _pp(body)
    assert "slots" in (body["result"] or {}), _pp(body)

    # 4) book_appointment
    r = client.post(
        "/mcp/execute",
        json={"tool_name": "book_appointment", "arguments": {"department": "primary_care", "date": "2026-05-01", "time": "09:00"}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True, _pp(body)
    assert body["tool_name"] == "book_appointment", _pp(body)
    assert body["result"]["status"] == "booked", _pp(body)

    # 5) pharmacy_lookup
    r = client.post("/mcp/execute", json={"tool_name": "pharmacy_lookup", "arguments": {"drug_name": "ibuprofen"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True, _pp(body)
    assert body["tool_name"] == "pharmacy_lookup", _pp(body)
    assert "in_stock" in (body["result"] or {}), _pp(body)

    # 6) unknown tool
    r = client.post("/mcp/execute", json={"tool_name": "does_not_exist", "arguments": {"x": 1}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False, _pp(body)
    assert body["error"] and "Unknown tool_name" in body["error"], _pp(body)

    print("OK: MCP-style tools discovery + execute tests passed.")


if __name__ == "__main__":
    main()

