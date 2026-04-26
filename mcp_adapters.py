from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from typing import Any


@dataclass(frozen=True)
class MockEHRAdapter:
    adapter_name: str = "mock_ehr"

    def get_patient_summary(self, patient_id: str) -> dict[str, Any]:
        pid = (patient_id or "").strip()
        if not pid:
            raise ValueError("patient_id is required")

        if pid == "demo_patient_001":
            return {
                "patient_id": pid,
                "age": 42,
                "sex": "F",
                "allergies": ["penicillin"],
                "chronic_conditions": ["hypertension"],
                "recent_visits": [
                    {"date": "2026-02-11", "reason": "annual physical", "notes": "BP borderline; advised lifestyle changes."},
                    {"date": "2025-12-03", "reason": "cough", "notes": "viral URI suspected; supportive care."},
                ],
            }

        return {
            "patient_id": pid,
            "age": 35,
            "sex": "U",
            "allergies": [],
            "chronic_conditions": [],
            "recent_visits": [],
            "note": "Mock patient record (unknown patient_id).",
        }


@dataclass(frozen=True)
class MockAppointmentAdapter:
    adapter_name: str = "mock_appointments"

    def list_available_slots(self, department: str) -> dict[str, Any]:
        dept = (department or "").strip()
        if not dept:
            raise ValueError("department is required")

        today = Date.today().isoformat()
        return {
            "department": dept,
            "date": today,
            "slots": [
                {"time": "09:00", "available": True},
                {"time": "10:30", "available": True},
                {"time": "14:00", "available": True},
            ],
        }

    def book_appointment(self, department: str, date: str, time: str) -> dict[str, Any]:
        dept = (department or "").strip()
        d = (date or "").strip()
        t = (time or "").strip()
        if not dept:
            raise ValueError("department is required")
        if not d:
            raise ValueError("date is required (YYYY-MM-DD)")
        if not t:
            raise ValueError("time is required (HH:MM)")

        # Very lightweight validation (demo only).
        if len(d) != 10 or d[4] != "-" or d[7] != "-":
            raise ValueError("date must be in YYYY-MM-DD format")
        if len(t) != 5 or t[2] != ":":
            raise ValueError("time must be in HH:MM format")

        return {
            "appointment_id": f"apt_{dept.lower().replace(' ', '_')}_{d}_{t.replace(':', '')}",
            "department": dept,
            "date": d,
            "time": t,
            "status": "booked",
            "instructions": "Arrive 10 minutes early; bring a photo ID and insurance card (if available).",
        }


@dataclass(frozen=True)
class MockPharmacyAdapter:
    adapter_name: str = "mock_pharmacy"

    def check_drug_availability(self, drug_name: str) -> dict[str, Any]:
        name = (drug_name or "").strip()
        if not name:
            raise ValueError("drug_name is required")

        key = name.lower()
        inventory = {
            "ibuprofen": {"in_stock": True, "quantity": 120, "notes": ["Take with food if stomach upset occurs."]},
            "acetaminophen": {"in_stock": True, "quantity": 85, "notes": ["Do not exceed labeled daily maximum dose."]},
            "amoxicillin": {"in_stock": False, "quantity": 0, "notes": ["Prescription required; stock varies by location."]},
        }
        if key in inventory:
            return {"drug_name": name, **inventory[key]}

        return {
            "drug_name": name,
            "in_stock": True,
            "quantity": 20,
            "notes": ["Mock result for unknown drug name; confirm with pharmacy."],
        }

