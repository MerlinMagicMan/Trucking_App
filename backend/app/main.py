"""
FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routes
from app.api.routes import router

# Database initialization
from app.db.connection import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler
    Creates database tables on startup
    """
    # Create tables
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup if needed


# Create FastAPI app
app = FastAPI(
    title="Single-Truck Optimization API",
    description="Decision-support engine for reefer owner-operators",
    version="1.0.0",
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


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Single-Truck Optimization API",
        "version": "1.0.0",
        "docs": "/docs"
    }
