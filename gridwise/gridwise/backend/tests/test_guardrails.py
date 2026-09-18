import pytest
from app.models import BatteryInput, DirectiveType
from app.guardrails import apply_guardrails

def test_guardrail_hours_sanitization():
    battery = BatteryInput(
        capacity_kwh=200,
        initial_energy_kwh=50,
        minimum_energy_kwh=20,
        max_charge_kwh_per_hour=40,
        max_discharge_kwh_per_hour=40
    )

    raw_interpretations = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "solar_reduction",
            "structured_adjustment": {"hours": [12, 13, 13, 25, -1, 14], "factor": 0.7},
            "explanation": "Test solar reduction"
        }
    ]

    validated = apply_guardrails(raw_interpretations, battery, 1)
    assert len(validated) == 1
    assert validated[0].applies is True
    assert validated[0].directive_type == DirectiveType.SOLAR_REDUCTION
    assert validated[0].structured_adjustment["hours"] == [12, 13, 14]
    assert validated[0].structured_adjustment["factor"] == 0.7

def test_guardrail_percentage_and_no_op():
    battery = BatteryInput(
        capacity_kwh=200,
        initial_energy_kwh=50,
        minimum_energy_kwh=20,
        max_charge_kwh_per_hour=40,
        max_discharge_kwh_per_hour=40
    )

    raw_interpretations = [
        {
            "note_index": 0,
            "applies": True,
            "directive_type": "minimum_battery_reserve",
            "structured_adjustment": {"hours": [18, 19, 20, 21], "minimum_energy_kwh": 100.0},
            "explanation": "50% reserve on 200kWh capacity"
        },
        {
            "note_index": 1,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "Irrelevant note"
        }
    ]

    validated = apply_guardrails(raw_interpretations, battery, 2)
    assert len(validated) == 2
    assert validated[0].directive_type == DirectiveType.MINIMUM_BATTERY_RESERVE
    assert validated[0].structured_adjustment["minimum_energy_kwh"] == 100.0
    assert validated[1].directive_type == DirectiveType.NO_OP
    assert validated[1].structured_adjustment is None
