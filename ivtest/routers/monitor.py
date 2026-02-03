"""
Live Monitor API Endpoints.

Provides endpoints for backend-buffered live monitoring:
- Configure monitoring parameters
- Start/stop background collection
- Poll for data (UI-friendly)
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

from ..live_monitor import live_monitor, MonitorConfig
from ..logging_config import get_logger

logger = get_logger("routers.monitor")
router = APIRouter(prefix="/monitor", tags=["monitor"])


class MonitorConfigRequest(BaseModel):
    channel: int = Field(default=2, ge=1, le=2, description="SMU channel")
    bias_voltage: float = Field(default=0.0, description="Bias voltage (V)")
    nplc: float = Field(default=1.0, gt=0, le=100, description="Integration time")
    compliance: float = Field(default=0.1, gt=0, description="Compliance limit (A)")
    rate_hz: float = Field(default=10.0, gt=0, le=100, description="Measurement rate (Hz)")


@router.post("/configure")
async def configure_monitor(request: MonitorConfigRequest):
    """Configure live monitoring parameters."""
    config = MonitorConfig(
        channel=request.channel,
        bias_voltage=request.bias_voltage,
        nplc=request.nplc,
        compliance=request.compliance,
        rate_hz=request.rate_hz
    )
    return live_monitor.configure(config)


@router.post("/start")
async def start_monitor():
    """Start background monitoring."""
    return live_monitor.start()


@router.post("/stop")
async def stop_monitor():
    """Stop background monitoring."""
    return live_monitor.stop()


@router.get("/data")
async def get_monitor_data(last_n: int = 60):
    """
    Get latest measurements from buffer.
    
    Args:
        last_n: Number of most recent points to return (default 60)
    """
    return live_monitor.get_data(last_n=last_n)


@router.get("/status")
async def get_monitor_status():
    """Get current monitor status (without data)."""
    return live_monitor.get_status()


@router.get("/latest")
async def get_latest_value():
    """Get just the latest measurement (fast poll)."""
    status = live_monitor.get_status()
    return {
        "running": status["running"],
        "value": status["last_value"],
        "count": status["measurement_count"]
    }
