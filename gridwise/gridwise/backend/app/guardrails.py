import logging
from typing import List, Dict, Any, Optional
from app.models import DirectiveInterpretation, DirectiveType, BatteryInput

logger = logging.getLogger("gridwise.guardrails")

def apply_guardrails(
    raw_interpretations: List[Dict[str, Any]],
    battery: BatteryInput,
    expected_note_count: int
) -> List[DirectiveInterpretation]:
    validated: List[DirectiveInterpretation] = []

    for idx in range(expected_note_count):
        item = None
        for raw in raw_interpretations:
            if raw.get("note_index") == idx:
                item = raw
                break
                
        if not item and idx < len(raw_interpretations):
            item = raw_interpretations[idx]

        if not item:
            item = {
                "note_index": idx,
                "applies": False,
                "directive_type": "no_op",
                "structured_adjustment": None,
                "explanation": "No directive extracted from note."
            }

        directive_str = item.get("directive_type", "no_op")
        try:
            directive_type = DirectiveType(directive_str)
        except ValueError:
            directive_type = DirectiveType.NO_OP

        adj = item.get("structured_adjustment")
        explanation = str(item.get("explanation", ""))
        validated_adj: Optional[Dict[str, Any]] = None

        if directive_type == DirectiveType.NO_OP or not isinstance(adj, dict):
            applies = False
            directive_type = DirectiveType.NO_OP
            validated_adj = None
            if not explanation:
                explanation = "Non-actionable operator note or no-op."
        else:
            raw_hours = adj.get("hours", [])
            valid_hours = []
            if isinstance(raw_hours, list):
                for h in raw_hours:
                    if isinstance(h, (int, float)):
                        h_int = int(h)
                        if 0 <= h_int <= 23:
                            valid_hours.append(h_int)
            valid_hours = sorted(list(set(valid_hours)))

            if not valid_hours:
                applies = False
                directive_type = DirectiveType.NO_OP
                validated_adj = None
                explanation += " (Invalid or empty hours specified; guardrails changed directive to no_op)"
            else:
                applies = True
                if directive_type == DirectiveType.SOLAR_REDUCTION:
                    factor = adj.get("factor", 1.0)
                    if isinstance(factor, (int, float)):
                        factor = max(0.0, min(1.0, float(factor)))
                    else:
                        factor = 1.0
                    validated_adj = {"hours": valid_hours, "factor": round(factor, 4)}

                elif directive_type == DirectiveType.MINIMUM_BATTERY_RESERVE:
                    min_kwh = adj.get("minimum_energy_kwh", battery.minimum_energy_kwh)
                    if isinstance(min_kwh, (int, float)):
                        min_kwh = max(0.0, min(battery.capacity_kwh, float(min_kwh)))
                    else:
                        min_kwh = battery.minimum_energy_kwh
                    validated_adj = {"hours": valid_hours, "minimum_energy_kwh": round(min_kwh, 2)}

                elif directive_type in (DirectiveType.NO_CHARGE_WINDOW, DirectiveType.NO_DISCHARGE_WINDOW):
                    validated_adj = {"hours": valid_hours}

                elif directive_type == DirectiveType.MAX_GRID_WINDOW:
                    max_grid = adj.get("max_grid_kwh", 1000.0)
                    if isinstance(max_grid, (int, float)):
                        max_grid = max(0.0, float(max_grid))
                    else:
                        max_grid = 1000.0
                    validated_adj = {"hours": valid_hours, "max_grid_kwh": round(max_grid, 2)}
                else:
                    applies = False
                    directive_type = DirectiveType.NO_OP
                    validated_adj = None

        validated.append(
            DirectiveInterpretation(
                note_index=idx,
                applies=applies,
                directive_type=directive_type,
                structured_adjustment=validated_adj,
                explanation=explanation or "Directive processed and validated."
            )
        )

    return validated
