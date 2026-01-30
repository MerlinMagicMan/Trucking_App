# Trucking Operating System

**Plan-based decision intelligence for reefer owner-operators.**

This is **not** a load board—it's a decision engine that generates complete **multi-day, multi-load plans** with full cost transparency, timeline modeling, and risk assessment.

**Phase 0 Status:** ✅ Complete - [See Validation Report](PHASE_0_VALIDATION_REPORT.md)

## Features

### Single-Load Optimization (MVP)
- **HOS-Aware**: Only recommends loads you can legally complete
- **Reload Intelligence**: Favors deliveries to reefer hubs (Dallas, Houston, KC, Phoenix, Atlanta)
- **Conservative Recommendations**: Deterministic, explainable results for stressed humans
- **Audit Logging**: Every optimization request logged to PostgreSQL

### Multi-Load Plan Generation (Phase 0) 🆕
- **Multi-Day Planning**: 2-3 chained loads over 7-14 day horizons
- **Full Cost Modeling**: Fuel, tolls, waiting, maintenance, opportunity cost
- **Complete Timelines**: Every minute accounted for (drive, wait, rest, loading)
- **Risk Assessment**: HOS tightness, market weakness, delivery windows, deadhead
- **Profit Per Day**: Key metric for plan comparison (not just reload_score)
- **Deterministic**: Same input → same plans, every time
- **Desktop-First UI**: Plan inspection and comparison interface

## Tech Stack

- **Backend**: Python 3.11 + FastAPI
- **Frontend**: Vite + React + TypeScript
- **Database**: PostgreSQL
- **Architecture**: Monorepo

## Prerequisites

- **Docker** (for PostgreSQL)
- **Python 3.11+**
- **Node.js 18+** and npm
- **Git**

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd Trucking_App
```

### 2. Start PostgreSQL

```bash
docker-compose up -d
```

Wait for PostgreSQL to be healthy:

```bash
docker-compose ps
```

### 3. Backend Setup

```bash
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI server (from backend directory)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at [http://localhost:8000](http://localhost:8000)

API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Frontend Setup

Open a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```

Frontend will be available at [http://localhost:5173](http://localhost:5173)

### 5. Alternative: Use Root Scripts

From the project root:

```bash
# Install all dependencies (backend + frontend)
npm run install:all

# Start both backend and frontend concurrently
npm run dev
```

## Usage

### Single-Load Mode (MVP)
1. **Open** [http://localhost:5173](http://localhost:5173)
2. **Enter** your truck's current location (default: Oklahoma City)
3. **Set** your remaining HOS (drive time, on-duty, cycle)
4. **Click** "Find Best Loads"
5. **Review** the top 3 recommendations with reload scores and explanations
6. **View** the 24-48 hour forward-look timeline

### Multi-Load Plans (Phase 0) 🆕
1. **Navigate to** [http://localhost:5173/plans](http://localhost:5173/plans)
2. **Enter** your truck snapshot (location + HOS)
3. **Set** planning parameters:
   - Planning horizon: 7-14 days
   - Max plans: 1-3
   - Search radius: miles
4. **Click** "Generate Plans"
5. **Review** 0-3 plans ranked by **profit per day**
6. **Expand** sections to inspect:
   - Complete timeline (drive/wait/rest/loading)
   - Financial breakdown (revenue, all costs, net profit)
   - Risk signals (HOS, market, timing)
   - Explanations (≥3 reasons per plan)
7. **Compare** up to 2 plans side-by-side

## Running Tests

```bash
cd backend
pytest tests/ -v
```

**Test Results:** ✅ 64 passed, 5 skipped (stub environment)

Key test coverage:
- ✅ **Determinism**: Same input → same output (MVP + Phase 0)
- ✅ **Financial Integrity**: All costs sum correctly, profit_per_day accurate
- ✅ **Timeline Validity**: Chronological, gap-free time blocks
- ✅ **Risk Assessment**: HOS, market, timing, deadhead risks
- ✅ **Plan Quality**: 2-3 loads, ≥3 explanations, sorted by profit/day
- ✅ **Backward Compatibility**: MVP `/api/optimize` unchanged
- ✅ **HOS-infeasible loads** never appear in recommendations
- ✅ **Reload scores** always 0-100
- ✅ **API validation**: Parameter bounds, error handling

See [Phase 0 Validation Report](PHASE_0_VALIDATION_REPORT.md) for full details.

## API Endpoints

### POST /api/optimize (MVP)

Submit truck snapshot for single-load optimization.

**Request:**
```json
{
  "current_lat": 35.4676,
  "current_lng": -97.5164,
  "hos": {
    "drive_remaining_min": 660,
    "on_duty_remaining_min": 840,
    "cycle_remaining_min": 4200
  }
}
```

**Response:**
```json
{
  "snapshot_id": "uuid",
  "recommendations": [
    {
      "load_id": "truckstop_TS001",
      "rank": 1,
      "reload_score": 85,
      "confidence": "high",
      "explanations": [
        "Short 45-mile deadhead to pickup",
        "Delivers into Dallas reefer hub at 8am",
        "Comfortable 2-hour buffer before pickup window"
      ],
      ...
    }
  ],
  "forward_look": { ... },
  "warnings": [],
  "loads_analyzed": 25,
  "loads_feasible": 18
}
```

### POST /api/plans/generate (Phase 0) 🆕

Generate multi-load plans (2-3 loads over 7-14 days).

**Request:**
```json
{
  "current_lat": 35.4676,
  "current_lng": -97.5164,
  "hos": {
    "drive_remaining_min": 660,
    "on_duty_remaining_min": 840,
    "cycle_remaining_min": 4200
  }
}
```

**Query Parameters:**
- `planning_horizon_days`: 7-14 (default: 7)
- `max_plans`: 1-3 (default: 3)
- `radius_miles`: 50-1000 (default: 250)

**Response:**
```json
{
  "snapshot_id": "uuid",
  "plans": [
    {
      "plan_id": "uuid",
      "profit_per_day_usd": 307.50,
      "net_profit_usd": 2152.50,
      "total_revenue_usd": 4800.00,
      "total_costs_usd": 2647.50,
      "loads": [/* 2-3 LoadInPlan objects */],
      "time_blocks": [/* Complete timeline */],
      "financial_events": [/* All revenue + costs */],
      "risk_signals": [/* HOS, market, timing risks */],
      "explanations": [
        "Excellent financial outcome: $2,153 net profit over 7 days ($307/day).",
        "Ends in Dallas reefer hub - excellent position for next load.",
        "Chains 2 loads through Dallas (445 total loaded miles)."
      ],
      "confidence": "high",
      "plan_score": 85,
      ...
    }
  ],
  "warnings": [],
  "metadata": {
    "planning_horizon_days": 7,
    "radius_miles": 250,
    "plans_requested": 3,
    "plans_generated": 2
  }
}
```

### GET /api/health

Check API health.

### GET /api/connectors/health

Check all load board connectors.

## Project Structure

```
/workspaces/Trucking_App/
├── backend/
│   ├── app/
│   │   ├── api/routes.py          # API endpoints
│   │   ├── models/canonical.py    # Pydantic models
│   │   ├── connectors/            # Truckstop, DAT
│   │   ├── engine/                # Optimization logic
│   │   ├── db/                    # Database connection
│   │   └── data/mock_loads_ok_tx.json
│   ├── tests/                     # Pytest tests
│   ├── alembic/                   # DB migrations
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── pages/                 # 3 screens
│   │   ├── components/            # Reusable components
│   │   ├── services/api.ts        # API client
│   │   └── types/models.ts        # TypeScript types
│   └── package.json
│
├── docker-compose.yml
└── package.json                   # Root scripts
```

## Environment Variables

Copy `.env.example` to create a `.env` file:

```bash
cp .env.example .env
```

Key variables:
- `DATABASE_URL`: PostgreSQL connection string
- `CORS_ORIGINS`: Allowed frontend origins
- `API_PORT`: Backend port (default: 8000)

## Development Notes

### Mock Data

The MVP uses mock load data from `backend/app/data/mock_loads_ok_tx.json`. This file contains ~25 realistic reefer loads across OK/TX/KS/AR.

To integrate with real Truckstop API:
1. Update `TruckstopConnector` in `backend/app/connectors/truckstop.py`
2. Add API credentials to `.env`
3. Implement live API calls in `search_loads()`

### Database Migrations

Create new migration:
```bash
cd backend
alembic revision --autogenerate -m "description"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback:
```bash
alembic downgrade -1
```

### Adding New Connectors

1. Create `backend/app/connectors/yourconnector.py`
2. Extend `BaseConnector`
3. Implement `search_loads()`, `normalize()`, `health_check()`
4. Add to `OptimizationEngine` in `backend/app/api/routes.py`

## Troubleshooting

### Backend won't start

- Check PostgreSQL: `docker-compose ps`
- Verify migrations: `alembic current`
- Check logs: `docker-compose logs postgres`

### Frontend shows CORS errors

- Verify `CORS_ORIGINS` in `.env`
- Restart backend after changing `.env`

### Tests failing

- Ensure PostgreSQL is running
- Run migrations: `alembic upgrade head`
- Check mock data exists: `ls backend/app/data/mock_loads_ok_tx.json`

## Production Deployment

**Database**:
- Use managed PostgreSQL (AWS RDS, Google Cloud SQL, etc.)
- Update `DATABASE_URL` in production `.env`

**Backend**:
- Deploy FastAPI with Gunicorn/Uvicorn
- Use environment-based config
- Enable logging and monitoring

**Frontend**:
- Build: `cd frontend && npm run build`
- Serve `dist/` folder with nginx or CDN
- Update `VITE_API_URL` for production backend

## Contributing

This is an MVP. Focus areas for contribution:
- Real Truckstop API integration
- ML-based reload scoring
- Weather integration for reefer routes
- Multi-stop route optimization

## License

[Your License Here]

## Support

For issues, see:
- API docs: http://localhost:8000/docs
- Architecture: See [ARCHITECTURE.md](ARCHITECTURE.md)
- Tests: `pytest backend/tests -v`

---

**Reminder**: You are building decision intelligence for stressed humans, not CRUD software. Speed, clarity, and conservative recommendations matter more than features.
