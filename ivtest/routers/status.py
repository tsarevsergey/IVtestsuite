"""
Status and health endpoints for IV Test Software.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..run_manager import run_manager, RunState
from ..logging_config import get_logger

logger = get_logger("routers.status")
router = APIRouter(tags=["status"])


class HealthResponse(BaseModel):
    status: str


class StatusResponse(BaseModel):
    state: str
    uptime_seconds: float
    run_duration_seconds: Optional[float]
    error_message: Optional[str]
    abort_requested: bool


class StateTransitionRequest(BaseModel):
    target_state: str


class AbortResponse(BaseModel):
    success: bool
    message: str
    state: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Simple health check endpoint.
    Returns OK if the server is running.
    """
    return HealthResponse(status="ok")


@router.get("/status", response_model=StatusResponse)
async def get_status():
    """
    Get current run manager status including state and timing information.
    """
    status = run_manager.get_status()
    return StatusResponse(**status)


@router.post("/abort", response_model=AbortResponse)
async def abort_run():
    """
    Abort any running operation and return to IDLE state.
    Safe to call at any time.
    """
    logger.warning("Abort requested via API")
    success = run_manager.abort()
    return AbortResponse(
        success=success,
        message="Abort completed" if success else "Abort failed",
        state=run_manager.state.value
    )


@router.post("/reset", response_model=AbortResponse)
async def reset_state():
    """
    Reset from ERROR or ABORTED state to IDLE.
    """
    success = run_manager.reset()
    return AbortResponse(
        success=success,
        message="Reset completed" if success else "Reset failed - not in ERROR/ABORTED state",
        state=run_manager.state.value
    )


@router.post("/arm", response_model=AbortResponse)
async def arm_run():
    """
    Arm the system for a run (IDLE → ARMED).
    """
    success = run_manager.arm()
    return AbortResponse(
        success=success,
        message="System armed" if success else "Failed to arm - check current state",
        state=run_manager.state.value
    )


@router.post("/start", response_model=AbortResponse)
async def start_run():
    """
    Start the run (ARMED → RUNNING).
    """
    success = run_manager.start()
    return AbortResponse(
        success=success,
        message="Run started" if success else "Failed to start - must be ARMED first",
        state=run_manager.state.value
    )


@router.post("/complete", response_model=AbortResponse)
async def complete_run():
    """
    Mark run as complete (RUNNING → IDLE).
    """
    success = run_manager.complete()
    return AbortResponse(
        success=success,
        message="Run completed" if success else "Failed to complete - not currently running",
        state=run_manager.state.value
    )
