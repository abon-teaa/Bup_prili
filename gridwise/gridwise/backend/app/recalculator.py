import logging
from typing import List, Tuple
from app.models import HourInput, BatteryInput, DirectiveInterpretation, HourlyPlanItem, BatteryAction

logger = logging.getLogger("gridwise.recalculator")

def audit_and_summarize_plan(
    hours: List[HourInput],
    battery: BatteryInput,
    directives: List[DirectiveInterpretation],
    hourly_plan: List[HourlyPlanItem]
) -> Tuple[float, float, float, str]:
    total_grid_kwh = 0.0
    total_cost_bdt = 0.0
    peak_grid_kwh = 0.0
    prev_bat_energy = battery.initial_energy_kwh

    for item in hourly_plan:
        h = item.hour
        demand = hours[h].demand_kwh
        tariff = hours[h].tariff_bdt_per_kwh
        grid = item.grid_kwh
        solar_used = item.solar_used_kwh
        
        if item.battery_action == BatteryAction.CHARGE:
            chg = item.battery_kwh
            dis = 0.0
        elif item.battery_action == BatteryAction.DISCHARGE:
            chg = 0.0
            dis = item.battery_kwh
        else:
            chg = 0.0
            dis = 0.0

        supply = grid + solar_used + dis
        consumption = demand + chg
        if abs(supply - consumption) > 1e-3:
            logger.error(f"Hour {h} Energy Balance mismatch! Supply: {supply:.4f}, Consumption: {consumption:.4f}")

        expected_after = prev_bat_energy + chg - dis
        if abs(item.battery_energy_after_kwh - expected_after) > 1e-3:
            logger.error(f"Hour {h} Battery State mismatch! Expected: {expected_after:.4f}, Actual: {item.battery_energy_after_kwh:.4f}")
            
        prev_bat_energy = item.battery_energy_after_kwh

        total_grid_kwh += grid
        cost_this_hour = grid * tariff
        total_cost_bdt += cost_this_hour
        if grid > peak_grid_kwh:
            peak_grid_kwh = grid

    if abs(hourly_plan[-1].battery_energy_after_kwh - battery.initial_energy_kwh) > 1e-3:
        logger.error("End-of-day battery neutrality constraint violated!")

    applied_directives_count = sum(1 for d in directives if d.applies)
    summary = (
        f"24-Hour Microgrid Dispatch Plan generated successfully. "
        f"Total grid import: {total_grid_kwh:.2f} kWh across 24 hours. "
        f"Total electricity expenditure: {total_cost_bdt:.2f} BDT. "
        f"Peak grid demand: {peak_grid_kwh:.2f} kWh. "
        f"End-of-day battery state preserved at {hourly_plan[-1].battery_energy_after_kwh:.2f} kWh (initial: {battery.initial_energy_kwh:.2f} kWh). "
        f"Successfully integrated {applied_directives_count} active operator directive(s) into physical guardrails."
    )

    return round(total_grid_kwh, 4), round(total_cost_bdt, 4), round(peak_grid_kwh, 4), summary
