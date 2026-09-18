import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_post_optimize_energy():
    hours = []
    for h in range(24):
        hours.append({
            "hour": h,
            "demand_kwh": 30.0,
            "solar_kwh": 50.0 if 8 <= h <= 16 else 0.0,
            "tariff_bdt_per_kwh": 8.0
        })

    payload = {
        "scenario_id": "test_api_scenario",
        "operator_notes": [
            "Cloud cover will reduce solar generation by 30% from 12 PM to 2 PM.",
            "Water the plants at the substation."
        ],
        "hours": hours,
        "battery": {
            "capacity_kwh": 200.0,
            "initial_energy_kwh": 50.0,
            "minimum_energy_kwh": 20.0,
            "max_charge_kwh_per_hour": 40.0,
            "max_discharge_kwh_per_hour": 40.0
        }
    }

    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["scenario_id"] == "test_api_scenario"
    assert len(data["directive_interpretation"]) == 2
    assert len(data["hourly_plan"]) == 24
    assert data["total_grid_kwh"] >= 0
    assert data["total_cost_bdt"] >= 0
    assert data["peak_grid_kwh"] >= 0
    assert "24-Hour Microgrid Dispatch Plan" in data["plan_summary"]
