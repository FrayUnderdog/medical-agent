from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

from fastapi import APIRouter
from pydantic import BaseModel, Field

from mcp_adapters import MockAppointmentAdapter, MockEHRAdapter, MockPharmacyAdapter


@dataclass(frozen=True)
class MCPToolSpec:
    name: str
    description: str
    input_fields: dict[str, str]
    output_fields: dict[str, str]
    adapter: str


# Keep schema style close to `tool_specs.py` (interview-friendly, no heavy deps).
MCP_TOOLS: dict[str, MCPToolSpec] = {
    "ehr_lookup": MCPToolSpec(
        name="ehr_lookup",
        description="Mock EHR patient summary lookup by patient_id.",
        input_fields={"patient_id": "str — patient identifier."},
        output_fields={
            "patient_id": "str",
            "age": "int",
            "sex": "str",
            "allergies": "list[str]",
            "chronic_conditions": "list[str]",
            "recent_visits": "list[dict]",
        },
        adapter="mock_ehr",
    ),
    "appointment_lookup": MCPToolSpec(
        name="appointment_lookup",
        description="Mock appointment system: list available slots for a department.",
        input_fields={"department": "str — e.g. primary_care, cardiology."},
        output_fields={"department": "str", "date": "str", "slots": "list[dict{time:str, available:bool}]"},
        adapter="mock_appointments",
    ),
    "book_appointment": MCPToolSpec(
        name="book_appointment",
        description="Mock appointment system: book a slot for a department/date/time.",
        input_fields={
            "department": "str — department name.",
            "date": "str — YYYY-MM-DD.",
            "time": "str — HH:MM.",
        },
        output_fields={
            "appointment_id": "str",
            "department": "str",
            "date": "str",
            "time": "str",
            "status": "str",
        },
        adapter="mock_appointments",
    ),
    "pharmacy_lookup": MCPToolSpec(
        name="pharmacy_lookup",
        description="Mock pharmacy system: check drug availability and notes.",
        input_fields={"drug_name": "str — drug name."},
        output_fields={"drug_name": "str", "in_stock": "bool", "quantity": "int", "notes": "list[str]"},
        adapter="mock_pharmacy",
    ),
}


class ExecuteRequest(BaseModel):
    tool_name: str = Field(..., description="MCP-style tool name.")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments payload.")


class ExecuteResponse(BaseModel):
    tool_name: str
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    trace: dict[str, Any] | None = None


def _require_args(arguments: dict[str, Any], required: list[str]) -> tuple[bool, str | None]:
    missing = [k for k in required if k not in arguments or arguments.get(k) in (None, "")]
    if missing:
        return False, f"Missing required argument(s): {', '.join(missing)}"
    return True, None


router = APIRouter(tags=["mcp"])


@router.get("/mcp/tools")
def list_tools() -> dict[str, Any]:
    # Tool discovery endpoint.
    return {"tools": [asdict(spec) for spec in MCP_TOOLS.values()]}


@router.post("/mcp/execute", response_model=ExecuteResponse)
def execute_tool(req: ExecuteRequest) -> ExecuteResponse:
    t0 = time.perf_counter()
    tool_name = (req.tool_name or "").strip()
    arguments = req.arguments or {}

    spec = MCP_TOOLS.get(tool_name)
    if not spec:
        return ExecuteResponse(
            tool_name=tool_name or req.tool_name,
            ok=False,
            result=None,
            error=f"Unknown tool_name: {req.tool_name}",
            trace={"adapter": None, "latency_ms": int((time.perf_counter() - t0) * 1000)},
        )

    ehr = MockEHRAdapter()
    appt = MockAppointmentAdapter()
    pharm = MockPharmacyAdapter()

    handlers: dict[str, tuple[list[str], Callable[[dict[str, Any]], dict[str, Any]]]] = {
        "ehr_lookup": (["patient_id"], lambda a: ehr.get_patient_summary(patient_id=str(a["patient_id"]))),
        "appointment_lookup": (
            ["department"],
            lambda a: appt.list_available_slots(department=str(a["department"])),
        ),
        "book_appointment": (
            ["department", "date", "time"],
            lambda a: appt.book_appointment(
                department=str(a["department"]),
                date=str(a["date"]),
                time=str(a["time"]),
            ),
        ),
        "pharmacy_lookup": (
            ["drug_name"],
            lambda a: pharm.check_drug_availability(drug_name=str(a["drug_name"])),
        ),
    }

    required, handler = handlers[tool_name]
    ok, err = _require_args(arguments, required)
    if not ok:
        return ExecuteResponse(
            tool_name=tool_name,
            ok=False,
            result=None,
            error=err,
            trace={"adapter": spec.adapter, "latency_ms": int((time.perf_counter() - t0) * 1000)},
        )

    try:
        result = handler(arguments)
        return ExecuteResponse(
            tool_name=tool_name,
            ok=True,
            result=result,
            error=None,
            trace={"adapter": spec.adapter, "latency_ms": int((time.perf_counter() - t0) * 1000)},
        )
    except Exception as e:  # noqa: BLE001 (intentional: adapter isolation)
        return ExecuteResponse(
            tool_name=tool_name,
            ok=False,
            result=None,
            error=f"{type(e).__name__}: {e}",
            trace={"adapter": spec.adapter, "latency_ms": int((time.perf_counter() - t0) * 1000)},
        )

