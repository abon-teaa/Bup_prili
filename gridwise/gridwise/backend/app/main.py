import time
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.models import OptimizeRequest, OptimizeResponse, HealthResponse
from app.llm_interpreter import interpret_notes
from app.guardrails import apply_guardrails
from app.optimizer import solve_microgrid_optimization
from app.recalculator import audit_and_summarize_plan

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("gridwise.main")

app = FastAPI(
    title="GridWise API Backend",
    description="LLM-Assisted Microgrid Energy Optimization System",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Look for frontend folder in parent directory
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"

@app.get("/health", response_model=HealthResponse, tags=["Readiness"])
async def health_check():
    """
    Readiness monitoring endpoint for judging harness and continuous monitoring.
    Must respond with HTTP 200 OK within 60 seconds of container startup.
    """
    return HealthResponse(status="ok")

@app.post("/optimize-energy", response_model=OptimizeResponse, tags=["Optimization"])
async def optimize_energy(request: OptimizeRequest):
    """
    Core endpoint executing LLM note interpretation, guardrailing, and 24-hour microgrid schedule generation.
    """
    start_time = time.time()
    try:
        raw_interpretations = await interpret_notes(
            request.operator_notes,
            request.battery.capacity_kwh
        )

        directives = apply_guardrails(
            raw_interpretations,
            request.battery,
            len(request.operator_notes)
        )

        hourly_plan = solve_microgrid_optimization(
            request.hours,
            request.battery,
            directives
        )

        total_grid, total_cost, peak_grid, summary = audit_and_summarize_plan(
            request.hours,
            request.battery,
            directives,
            hourly_plan
        )

        elapsed = time.time() - start_time
        logger.info(f"Optimization completed for scenario {request.scenario_id} in {elapsed:.3f}s")

        return OptimizeResponse(
            scenario_id=request.scenario_id,
            directive_interpretation=directives,
            hourly_plan=hourly_plan,
            total_grid_kwh=total_grid,
            total_cost_bdt=total_cost,
            peak_grid_kwh=peak_grid,
            plan_summary=summary
        )

    except Exception as e:
        logger.error(f"Error processing scenario {request.scenario_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization failed: {str(e)}"
        )

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend_root")
