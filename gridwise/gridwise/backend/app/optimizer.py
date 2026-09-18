import logging
from typing import List
import pulp
from scipy.optimize import linprog
from app.models import HourInput, BatteryInput, DirectiveInterpretation, DirectiveType, HourlyPlanItem, BatteryAction

logger = logging.getLogger("gridwise.optimizer")

def solve_microgrid_optimization(
    hours: List[HourInput],
    battery: BatteryInput,
    directives: List[DirectiveInterpretation]
) -> List[HourlyPlanItem]:
    solar_effective = [h.solar_kwh for h in hours]
    active_reserve = [battery.minimum_energy_kwh for _ in range(24)]
    max_charge = [battery.max_charge_kwh_per_hour for _ in range(24)]
    max_discharge = [battery.max_discharge_kwh_per_hour for _ in range(24)]
    max_grid = [float('inf') for _ in range(24)]

    for interp in directives:
        if not interp.applies or not interp.structured_adjustment:
            continue
            
        adj = interp.structured_adjustment
        adj_hours = adj.get("hours", [])
        
        if interp.directive_type == DirectiveType.SOLAR_REDUCTION:
            factor = adj.get("factor", 1.0)
            for h in adj_hours:
                if 0 <= h < 24:
                    solar_effective[h] = hours[h].solar_kwh * factor

        elif interp.directive_type == DirectiveType.MINIMUM_BATTERY_RESERVE:
            min_kwh = adj.get("minimum_energy_kwh", battery.minimum_energy_kwh)
            for h in adj_hours:
                if 0 <= h < 24:
                    active_reserve[h] = max(active_reserve[h], min_kwh)

        elif interp.directive_type == DirectiveType.NO_CHARGE_WINDOW:
            for h in adj_hours:
                if 0 <= h < 24:
                    max_charge[h] = 0.0

        elif interp.directive_type == DirectiveType.NO_DISCHARGE_WINDOW:
            for h in adj_hours:
                if 0 <= h < 24:
                    max_discharge[h] = 0.0

        elif interp.directive_type == DirectiveType.MAX_GRID_WINDOW:
            cap = adj.get("max_grid_kwh", float('inf'))
            for h in adj_hours:
                if 0 <= h < 24:
                    max_grid[h] = min(max_grid[h], cap)

    # Formulate MILP Problem with PuLP
    prob = pulp.LpProblem("GridWise_Microgrid_Optimization", pulp.LpMinimize)

    E_grid = [pulp.LpVariable(f"E_grid_{h}", lowBound=0, upBound=max_grid[h] if max_grid[h] != float('inf') else None) for h in range(24)]
    E_solar_used = [pulp.LpVariable(f"E_solar_used_{h}", lowBound=0, upBound=solar_effective[h]) for h in range(24)]
    E_chg = [pulp.LpVariable(f"E_chg_{h}", lowBound=0, upBound=max_charge[h]) for h in range(24)]
    E_dis = [pulp.LpVariable(f"E_dis_{h}", lowBound=0, upBound=max_discharge[h]) for h in range(24)]
    E_bat = [pulp.LpVariable(f"E_bat_{h}", lowBound=active_reserve[h], upBound=battery.capacity_kwh) for h in range(24)]
    
    z_chg = [pulp.LpVariable(f"z_chg_{h}", cat=pulp.LpBinary) for h in range(24)]
    z_dis = [pulp.LpVariable(f"z_dis_{h}", cat=pulp.LpBinary) for h in range(24)]

    # Objective: Minimize total grid cost
    prob += pulp.lpSum([E_grid[h] * hours[h].tariff_bdt_per_kwh for h in range(24)])

    for h in range(24):
        # Energy balance
        prob += (E_grid[h] + E_solar_used[h] + E_dis[h] == hours[h].demand_kwh + E_chg[h], f"EnergyBalance_{h}")
        # Binary action lock
        prob += (E_chg[h] <= max_charge[h] * z_chg[h], f"MaxChargeBinary_{h}")
        prob += (E_dis[h] <= max_discharge[h] * z_dis[h], f"MaxDischargeBinary_{h}")
        prob += (z_chg[h] + z_dis[h] <= 1, f"SingleBatteryAction_{h}")

        # Battery dynamics
        if h == 0:
            prob += (E_bat[0] == battery.initial_energy_kwh + E_chg[0] - E_dis[0], f"BatDynamics_{h}")
        else:
            prob += (E_bat[h] == E_bat[h - 1] + E_chg[h] - E_dis[h], f"BatDynamics_{h}")

    # End of Day Neutrality
    prob += (E_bat[23] == battery.initial_energy_kwh, "EOD_Neutrality")

    solver = pulp.PULP_CBC_CMD(msg=False)
    status = prob.solve(solver)

    plan_items: List[HourlyPlanItem] = []

    if status == pulp.LpStatusOptimal:
        for h in range(24):
            grid_val = max(0.0, float(pulp.value(E_grid[h])))
            solar_val = max(0.0, float(pulp.value(E_solar_used[h])))
            chg_val = max(0.0, float(pulp.value(E_chg[h])))
            dis_val = max(0.0, float(pulp.value(E_dis[h])))
            bat_val = float(pulp.value(E_bat[h]))

            if chg_val > 1e-4:
                action = BatteryAction.CHARGE
                bat_kwh = chg_val
            elif dis_val > 1e-4:
                action = BatteryAction.DISCHARGE
                bat_kwh = dis_val
            else:
                action = BatteryAction.IDLE
                bat_kwh = 0.0

            plan_items.append(
                HourlyPlanItem(
                    hour=h,
                    grid_kwh=round(grid_val, 4),
                    solar_used_kwh=round(solar_val, 4),
                    battery_action=action,
                    battery_kwh=round(bat_kwh, 4),
                    battery_energy_after_kwh=round(bat_val, 4)
                )
            )
        return plan_items
    else:
        logger.warning("PuLP solver did not return optimal status. Falling back to SciPy solver.")
        return solve_scipy_fallback(hours, battery, solar_effective, active_reserve, max_charge, max_discharge, max_grid)

def solve_scipy_fallback(
    hours: List[HourInput],
    battery: BatteryInput,
    solar_effective: List[float],
    active_reserve: List[float],
    max_charge: List[float],
    max_discharge: List[float],
    max_grid: List[float]
) -> List[HourlyPlanItem]:
    c = []
    bounds = []
    
    for h in range(24):
        c.extend([hours[h].tariff_bdt_per_kwh, 0.0, 0.0, 0.0, 0.0])
        grid_b = (0, max_grid[h] if max_grid[h] != float('inf') else None)
        solar_b = (0, solar_effective[h])
        chg_b = (0, max_charge[h])
        dis_b = (0, max_discharge[h])
        bat_b = (active_reserve[h], battery.capacity_kwh)
        bounds.extend([grid_b, solar_b, chg_b, dis_b, bat_b])

    A_eq = []
    b_eq = []

    for h in range(24):
        row_bal = [0] * 120
        row_bal[h * 5 + 0] = 1.0
        row_bal[h * 5 + 1] = 1.0
        row_bal[h * 5 + 3] = 1.0
        row_bal[h * 5 + 2] = -1.0
        A_eq.append(row_bal)
        b_eq.append(hours[h].demand_kwh)

        row_bat = [0] * 120
        row_bat[h * 5 + 4] = 1.0
        row_bat[h * 5 + 2] = -1.0
        row_bat[h * 5 + 3] = 1.0
        if h == 0:
            b_eq.append(battery.initial_energy_kwh)
        else:
            row_bat[(h - 1) * 5 + 4] = -1.0
            b_eq.append(0.0)
        A_eq.append(row_bat)

    row_eod = [0] * 120
    row_eod[23 * 5 + 4] = 1.0
    A_eq.append(row_eod)
    b_eq.append(battery.initial_energy_kwh)

    res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
    
    plan_items = []
    if res.success:
        x = res.x
        for h in range(24):
            grid_val = max(0.0, float(x[h * 5 + 0]))
            solar_val = max(0.0, float(x[h * 5 + 1]))
            chg_val = max(0.0, float(x[h * 5 + 2]))
            dis_val = max(0.0, float(x[h * 5 + 3]))
            bat_val = float(x[h * 5 + 4])

            if chg_val > 1e-4:
                action = BatteryAction.CHARGE
                bat_kwh = chg_val
            elif dis_val > 1e-4:
                action = BatteryAction.DISCHARGE
                bat_kwh = dis_val
            else:
                action = BatteryAction.IDLE
                bat_kwh = 0.0

            plan_items.append(
                HourlyPlanItem(
                    hour=h,
                    grid_kwh=round(grid_val, 4),
                    solar_used_kwh=round(solar_val, 4),
                    battery_action=action,
                    battery_kwh=round(bat_kwh, 4),
                    battery_energy_after_kwh=round(bat_val, 4)
                )
            )
    return plan_items
