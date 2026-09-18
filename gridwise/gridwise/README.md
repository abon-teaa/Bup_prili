# GridWise — LLM-Assisted Microgrid Energy Optimization System

**BUP CSE FEST 2026 Hackathon Submission**

GridWise is an AI-assisted microgrid energy management and optimization system. It interprets unstructured natural-language operator notes using Large Language Models (LLM), applies deterministic operational guardrails, and solves a 24-hour constrained microgrid dispatch optimization problem to minimize total grid electricity cost (in BDT) while strictly adhering to physical battery, solar, grid, and operator constraints.

---

## 📁 Repository Structure

```
gridwise/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI REST Endpoints (/health, /optimize-energy)
│   │   ├── config.py           # Configuration & Environment Settings
│   │   ├── models.py           # Pydantic Schemas (Request & Response)
│   │   ├── llm_interpreter.py  # LLM Note Interpreter & Rule Fallback Engine
│   │   ├── guardrails.py       # Deterministic Guardrails & Sanitizer
│   │   ├── optimizer.py        # 24-Hour MILP Energy Optimization Solver (PuLP/SciPy)
│   │   └── recalculator.py     # Plan Replayer & Metric Recalculator
│   ├── tests/                  # Pytest Unit & Integration Suite
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── index.html              # Glassmorphic Web Dashboard HTML
│   ├── styles.css              # Custom Dark Glassmorphism CSS Design System
│   └── app.js                  # Interactive Chart.js & API Integration Logic
│
├── docker-compose.yml
└── README.md
```

---

## 🚀 Quick Start & Local Execution

### 1. Run Backend Server
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
- OpenAPI Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Visual Web Dashboard: [http://localhost:8000](http://localhost:8000)

### 2. Run Test Suite
```bash
cd backend
python -m pytest -v
```

---

## 🐳 Containerized Deployment (Docker)

```bash
docker compose up --build
```
Or build backend directly:
```bash
cd backend
docker build -t gridwise-backend:latest .
docker run -p 8000:8000 gridwise-backend:latest
```
