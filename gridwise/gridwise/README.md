# GridWise — Smart Campus Energy Optimization System

BUP CSE FEST 2026 | Preliminary Round Submission[cite: 11]

GridWise is an HTTP service that receives a 24-hour campus energy scenario along with natural-language operator notes[cite: 11]. It uses an LLM to parse unstructured directives, validates them through deterministic guardrails, and solves a 24-hour constrained optimization problem to minimize total grid electricity cost (BDT) while maintaining microgrid rules[cite: 11].

---

## Architecture & Flow

* **LLM Directive Parser:** Uses a language model (e.g., OpenAI GPT-4o-mini) to translate unstructured `operator_notes` into structured `directive_interpretation` entries[cite: 11].
* **Deterministic Guardrails:** Validates directive types, hour bounds (`0..23` in ascending order), numeric ranges, and applies flags before passing constraints to the optimizer[cite: 11].
* **Mathematical Optimizer:** Uses linear programming (PuLP) to solve the 24-hour dispatch schedule, minimizing grid electricity cost in BDT while respecting battery transitions and grid caps[cite: 11].

```
Energy Data + Operator Notes
         │
         ▼
   LLM Interpreter      ── Parses notes into structured directive types
         │
         ▼
 Guardrail Validator    ── Validates bounds, hours, and applies flags
         │
         ▼
    Math Optimizer      ── Solves 24-hour dispatch LP (minimizes cost in BDT)
         │
         ▼
   Final Validator      ── Replays plan to verify constraints and neutrality
         │
         ▼
    API Response        ── Returns directive_interpretation + hourly_plan
```

---

## Supported Directives

* `solar_reduction`: Multiplies available solar power by `factor` during specified hours[cite: 11].
* `minimum_battery_reserve`: Sets `minimum_energy_kwh` floor for battery state of charge during specified hours[cite: 11].
* `no_charge_window`: Enforces battery charging to 0 kWh during specified hours[cite: 11].
* `no_discharge_window`: Enforces battery discharging to 0 kWh during specified hours[cite: 11].
* `max_grid_window`: Caps grid power imports to `max_grid_kwh` during specified hours[cite: 11].
* `no_op`: Handles irrelevant or non-operational notes (`applies: false`, `structured_adjustment: null`)[cite: 11].

---

## Endpoints

| Endpoint | Method | Description | Response Code |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | Health check endpoint returning `{"status": "ok"}`[cite: 11] | `200 OK`[cite: 11] |
| `/optimize-energy` | `POST` | Accepts 24h energy profile & notes; returns interpretations & optimal schedule[cite: 11] | `200 OK` / `400 Bad Request`[cite: 11] |

---

## Environment Variables

Configure these variables in your environment or a `.env` file (do not commit secrets to the repository)[cite: 11]:

```env
PORT=8000
LLM_PROVIDER=openai
LLM_API_KEY=your_api_key_here
LLM_MODEL=gpt-4o-mini
```

---

## Project Structure

```
gridwise/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI application & route definitions
│   │   ├── guardrails.py         # Response validation & directive checks
│   │   ├── optimizer.py          # Linear programming dispatch solver
│   │   └── config.py             # Settings & environment variables
│   ├── tests/                    # Pytest unit and integration test suite
│   └── requirements.txt          # Python dependencies
├── frontend/
│   ├── index.html                # Control panel dashboard interface
│   ├── styles.css                # Interface styles
│   └── app.js                    # Chart.js visualization & API calls
├── docker-compose.yml
└── README.md
```

---

## Local Setup & Quickstart

### Prerequisites
* Python 3.10+
* Docker & Docker Compose (optional for containerized execution)[cite: 11]

### 1. Run Python Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

* **API Documentation:** http://localhost:8000/docs
* **Health Check Endpoint:** http://localhost:8000/health[cite: 11]

### 2. Run Test Suite

```bash
cd backend
python -m pytest -v
```

---

## Docker Deployment & Fallback

Build and launch the complete stack via Docker Compose:

```bash
docker compose up --build
```

Or build and run the backend container individually[cite: 11]:

```bash
cd backend
docker build -t gridwise-backend:latest .
docker run -p 8000:8000 --env-file .env gridwise-backend:latest
```

---

## Sample Request & Verification

### 1. Health Verification (`GET /health`)[cite: 11]

```bash
curl -X GET http://localhost:8000/health
```

**Expected Output:**
```json
{"status": "ok"}
```

### 2. Energy Optimization (`POST /optimize-energy`)[cite: 11]

```bash
curl -X POST http://localhost:8000/optimize-energy \
  -H "Content-Type: application/json" \
  -
