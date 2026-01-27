"""
IV Protocol API Endpoints.
"""
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional

from ..iv_protocol import run_iv_protocol, ProtocolConfig, SweepConfig
from ..run_manager import run_manager
from ..logging_config import get_logger

logger = get_logger("routers.protocol")
router = APIRouter(prefix="/protocol", tags=["protocol"])


class ProtocolRequest(BaseModel):
    """Request to run an IV protocol."""
    pixels: List[int] = Field(default=[0], description="Pixel indices to measure")
    modes: List[str] = Field(default=["dark", "light"], description="Measurement modes")
    led_channel: int = Field(default=0, ge=0, le=3, description="LED channel for light mode")
    start_voltage: float = Field(default=0.0, description="Start voltage (V)")
    stop_voltage: float = Field(default=8.0, description="Stop voltage (V)")
    num_points: int = Field(default=41, ge=2, le=500, description="Number of measurement points")
    compliance: float = Field(default=0.1, gt=0, description="Current compliance (A)")
    delay: float = Field(default=0.1, ge=0, description="Delay per point (s)")
    output_dir: str = Field(default="data", description="Output directory")
    sample_name: str = Field(default="sample", description="Sample identifier")


class ProtocolResponse(BaseModel):
    """Response from protocol execution."""
    success: bool
    message: Optional[str] = None
    aborted: Optional[bool] = None
    num_sweeps: Optional[int] = None
    output_dir: Optional[str] = None


# Store for background task results
_last_result = {}


def _run_protocol_task(request: ProtocolRequest):
    """Background task to run protocol."""
    global _last_result
    _last_result = run_iv_protocol(
        pixels=request.pixels,
        modes=request.modes,
        led_channel=request.led_channel,
        start_v=request.start_voltage,
        stop_v=request.stop_voltage,
        num_points=request.num_points,
        compliance=request.compliance,
        delay=request.delay,
        output_dir=request.output_dir,
        sample_name=request.sample_name
    )


@router.post("/run", response_model=ProtocolResponse)
async def run_protocol(request: ProtocolRequest):
    """
    Run an IV measurement protocol synchronously.
    
    For long protocols, consider using /run-async instead.
    """
    logger.info(f"Protocol request: {request.sample_name}, pixels={request.pixels}, modes={request.modes}")
    
    result = run_iv_protocol(
        pixels=request.pixels,
        modes=request.modes,
        led_channel=request.led_channel,
        start_v=request.start_voltage,
        stop_v=request.stop_voltage,
        num_points=request.num_points,
        compliance=request.compliance,
        delay=request.delay,
        output_dir=request.output_dir,
        sample_name=request.sample_name
    )
    
    return ProtocolResponse(**result)


@router.post("/run-async")
async def run_protocol_async(request: ProtocolRequest, background_tasks: BackgroundTasks):
    """
    Run an IV measurement protocol in the background.
    
    Use /protocol/status to check progress.
    """
    logger.info(f"Async protocol request: {request.sample_name}")
    
    # Check if already running
    if run_manager.state == run_manager.state.RUNNING:
        return {"success": False, "message": "Protocol already running"}
    
    background_tasks.add_task(_run_protocol_task, request)
    
    return {"success": True, "message": "Protocol started in background"}


@router.get("/status")
async def get_protocol_status():
    """Get current protocol status."""
    return {
        "state": run_manager.state.value,
        "run_duration_seconds": run_manager.run_duration_seconds,
        "abort_requested": run_manager.is_abort_requested(),
        "last_result": _last_result
    }


@router.post("/abort")
async def abort_protocol():
    """Abort the running protocol."""
    run_manager.abort()
    return {"success": True, "message": "Abort requested"}
