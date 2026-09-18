from typing import List, Optional, Any, Dict
from enum import Enum
from pydantic import BaseModel, Field, ValidationInfo, field_validator

class DirectiveType(str, Enum):
    SOLAR_REDUCTION = "solar_reduction"
    MINIMUM_BATTERY_RESERVE = "minimum_battery_reserve"
    NO_CHARGE_WINDOW = "no_charge_window"
    NO_DISCHARGE_WINDOW = "no_discharge_window"
    MAX_GRID_WINDOW = "max_grid_window"
    NO_OP = "no_op"

class BatteryAction(str, Enum):
    CHARGE = "charge"
    DISCHARGE = "discharge"
    IDLE = "idle"

# --- Request Schemas ---

class HourInput(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0-23)")
    demand_kwh: float = Field(..., ge=0, description="Energy demand in kWh")
    solar_kwh: float = Field(..., ge=0, description="Solar energy generation forecast in kWh")
    tariff_bdt_per_kwh: float = Field(..., ge=0, description="Electricity tariff rate in BDT/kWh")

class BatteryInput(BaseModel):
    capacity_kwh: float = Field(..., gt=0, description="Total battery storage capacity in kWh")
    initial_energy_kwh: float = Field(..., ge=0, description="Initial battery energy level at start of day (kWh)")
    minimum_energy_kwh: float = Field(..., ge=0, description="Minimum reserve energy level in kWh")
    max_charge_kwh_per_hour: float = Field(..., ge=0, description="Maximum charge rate in kWh/h")
    max_discharge_kwh_per_hour: float = Field(..., ge=0, description="Maximum discharge rate in kWh/h")

    @field_validator("initial_energy_kwh", "minimum_energy_kwh")
    @classmethod
    def validate_against_capacity(cls, v: float, info: ValidationInfo) -> float:
        if "capacity_kwh" in info.data and v > info.data["capacity_kwh"]:
            pass
        return v

class OptimizeRequest(BaseModel):
    scenario_id: str = Field(..., min_length=1)
    operator_notes: List[str] = Field(..., min_length=1, max_length=3)
    hours: List[HourInput] = Field(..., min_length=24, max_length=24)
    battery: BatteryInput

    @field_validator("operator_notes")
    @classmethod
    def validate_notes(cls, v: List[str]) -> List[str]:
        for note in v:
            if not note.strip():
                raise ValueError("Operator notes cannot be empty or whitespace only")
        return v

    @field_validator("hours")
    @classmethod
    def validate_hours_sequence(cls, v: List[HourInput]) -> List[HourInput]:
        hours_seen = [h.hour for h in v]
        if sorted(hours_seen) != list(range(24)):
            raise ValueError("hours array must contain exactly 24 unique entries for hours 0 through 23")
        return sorted(v, key=lambda x: x.hour)

# --- Response Schemas ---

class DirectiveInterpretation(BaseModel):
    note_index: int = Field(..., ge=0)
    applies: bool
    directive_type: DirectiveType
    structured_adjustment: Optional[Dict[str, Any]] = None
    explanation: str

class HourlyPlanItem(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    grid_kwh: float = Field(..., ge=0)
    solar_used_kwh: float = Field(..., ge=0)
    battery_action: BatteryAction
    battery_kwh: float = Field(..., ge=0)
    battery_energy_after_kwh: float = Field(..., ge=0)

class OptimizeResponse(BaseModel):
    scenario_id: str
    directive_interpretation: List[DirectiveInterpretation]
    hourly_plan: List[HourlyPlanItem] = Field(..., min_length=24, max_length=24)
    total_grid_kwh: float = Field(..., ge=0)
    total_cost_bdt: float = Field(..., ge=0)
    peak_grid_kwh: float = Field(..., ge=0)
    plan_summary: str

class HealthResponse(BaseModel):
    status: str = "ok"
