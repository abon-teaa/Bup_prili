import pytest
from app.models import HourInput, BatteryInput, DirectiveInterpretation, DirectiveType
from app.optimizer import solve_microgrid_optimization
from app.recalculator import audit_and_summarize_plan

def test_optimization_and_recalculation():
    hours = []
    for h in range(24):
        tariff = 18.0 if 17 <= h <= 20 else 5.0
        demand = 80.0 if 17 <= h <= 20 else 30.0
        solar = 100.0 if 8 <= h <= 15 else 0.0
        hours.append(HourInput(hour=h, demand_kwh=demand, solar_kwh=solar, tariff_bdt_per_kwh=tariff))

    battery = BatteryInput(
        capacity_kwh=200.0,
        initial_energy_kwh=50.0,
        minimum_energy_kwh=20.0,
        max_charge_kwh_per_hour=40.0,
        max_discharge_kwh_per_hour=40.0
    )

    directives = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.SOLAR_REDUCTION,
            structured_adjustment={"hours": [12, 13], "factor": 0.7},
            explanation="Cloud cover solar reduction"
        )
    ]

    plan = solve_microgrid_optimization(hours, battery, directives)
    assert len(plan) == 24

    total_grid, total_cost, peak_grid, summary = audit_and_summarize_plan(hours, battery, directives, plan)
    
    assert total_grid >= 0
    assert total_cost >= 0
    assert peak_grid >= 0
    assert abs(plan[23].battery_energy_after_kwh - 50.0) < 1e-3

    for item in plan:
        h = item.hour
        chg = item.battery_kwh if item.battery_action == "charge" else 0.0
        dis = item.battery_kwh if item.battery_action == "discharge" else 0.0
        supply = item.grid_kwh + item.solar_used_kwh + dis
        consumption = hours[h].demand_kwh + chg
        assert abs(supply - consumption) < 1e-3
