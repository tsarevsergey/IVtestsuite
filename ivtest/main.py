"""
IV Test Software - FastAPI Backend

Main application entry point with lifespan management.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .logging_config import setup_logging, get_logger
from .run_manager import run_manager
from .routers import status, smu, relays, protocol, data, calibration

# Initialize logging
log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
setup_logging(log_dir=log_dir)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info("IV Test Software backend starting...")
    logger.info(f"Initial state: {run_manager.state.value}")
    
    yield
    
    # Shutdown
    logger.info("Backend shutting down...")
    if run_manager.state.value != "IDLE":
        logger.warning(f"Shutdown requested while in state: {run_manager.state.value}")
        run_manager.abort()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="IV Test Software",
    description="Backend API for IV curve measurement and device characterization",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware for Streamlit UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Streamlit runs on different port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(status.router)
app.include_router(smu.router)
app.include_router(relays.router)
app.include_router(protocol.router)
app.include_router(data.router)
app.include_router(calibration.router)


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "IV Test Software API",
        "version": "0.1.0",
        "docs": "/docs",
        "status": "/status"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
