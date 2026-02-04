"""
FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Import routes
from app.api.routes import router
from app.api.org_routes import org_router
from app.api.ingestion_routes import ingestion_router
from app.api.intel_routes import intel_router
from app.api.copilot_routes import copilot_router
from app.api.outcome_routes import outcome_router
from app.api.decision_routes import decision_router
from app.api.calibration_routes import calibration_router
from app.api.trust_routes import trust_router

# Database initialization
from app.db.connection import engine, Base, SessionLocal

# Import all models so create_all picks them up
import app.models.events  # noqa: F401
import app.models.tenant  # noqa: F401
import app.models.snapshot  # noqa: F401
import app.models.analytics  # noqa: F401
import app.models.copilot_evaluation  # noqa: F401
import app.models.plan_outcome  # noqa: F401
import app.models.decision_context  # noqa: F401  Stratum 5D: Learning Loop
from app.models.tenant import Organization, Truck
from app.ingestion.scheduler import start_scheduler, stop_scheduler


def _seed_demo_data():
    """Create Demo Fleet org and Truck 001 if they don't exist."""
    db = SessionLocal()
    try:
        demo = db.query(Organization).filter_by(name="Demo Fleet").first()
        if not demo:
            demo = Organization(name="Demo Fleet")
            db.add(demo)
            db.flush()
            truck = Truck(
                org_id=demo.id,
                name="Truck 001 (Reefer)",
                equipment_type="reefer",
                home_base_city="Dallas",
                home_base_state="TX",
            )
            db.add(truck)
            db.commit()
            logger.info("Seeded Demo Fleet org and Truck 001")
        else:
            db.rollback()
    except Exception as e:
        db.rollback()
        logger.warning(f"Seed data failed: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler
    Creates database tables on startup, seeds demo data
    """
    try:
        Base.metadata.create_all(bind=engine)
        _seed_demo_data()
        start_scheduler()
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}. DB-dependent features will return 503.")
    yield
    stop_scheduler()


# Create FastAPI app
app = FastAPI(
    title="Single-Truck Optimization API",
    description="Decision-support engine for reefer owner-operators",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")
app.include_router(org_router, prefix="/api")
app.include_router(ingestion_router, prefix="/api")
app.include_router(intel_router, prefix="/api")
app.include_router(copilot_router, prefix="/api")
app.include_router(outcome_router, prefix="/api")
app.include_router(decision_router, prefix="/api")
app.include_router(calibration_router, prefix="/api")
app.include_router(trust_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Single-Truck Optimization API",
        "version": "2.0.0",
        "docs": "/docs"
    }
