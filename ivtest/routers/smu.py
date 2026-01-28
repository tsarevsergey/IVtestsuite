"""
SMU Control API Endpoints.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal

from ..smu_client import smu_client, DEFAULT_SMU_ADDRESS
from ..logging_config import get_logger

logger = get_logger("routers.smu")
router = APIRouter(prefix="/smu", tags=["smu"])


# Request/Response Models
class ConnectRequest(BaseModel):
    address: str = Field(default=DEFAULT_SMU_ADDRESS, description="VISA resource address")
    mock: bool = Field(default=False, description="Use mock mode")
    channel: int = Field(default=1, ge=1, le=2, description="SMU channel (1 or 2)")


class ConfigureRequest(BaseModel):
    compliance: float = Field(..., gt=0, description="Compliance limit value")
    compliance_type: str = Field(default="CURR", pattern="^(CURR|VOLT)$")
    nplc: float = Field(default=1.0, gt=0, le=100)


class SourceModeRequest(BaseModel):
    mode: str = Field(..., pattern="^(VOLT|CURR)$", description="Source mode")


class SetValueRequest(BaseModel):
    value: float = Field(..., description="Source value (V or A)")


class OutputRequest(BaseModel):
    enabled: bool = Field(..., description="Enable or disable output")


class SweepRequest(BaseModel):
    start: float = Field(..., description="Start voltage")
    stop: float = Field(..., description="Stop voltage")
    points: int = Field(default=11, ge=2, le=1000, description="Number of points (one way)")
    compliance: float = Field(default=0.01, gt=0, description="Current compliance (A)")
    delay: float = Field(default=0.05, ge=0, description="Delay between points (s)")
    scale: Literal["linear", "log"] = Field(default="linear", description="Point distribution")
    direction: Literal["forward", "backward"] = Field(default="forward", description="Sweep direction")
    sweep_type: Literal["single", "double"] = Field(default="single", description="Sweep type")


class ListSweepRequest(BaseModel):
    points: List[float] = Field(..., description="List of voltage or current points")
    source_mode: Literal["VOLT", "CURR"] = Field(default="VOLT", description="Source mode")
    compliance: float = Field(default=0.1, gt=0, description="Compliance limit")
    nplc: float = Field(default=1.0, gt=0, le=100, description="Integration time")
    delay: float = Field(default=0.1, ge=0, description="Delay between points (s)")


class ListSweepResponse(BaseModel):
    success: bool
    results: Optional[List[Dict[str, Any]]] = None
    points: Optional[int] = None
    aborted: Optional[bool] = None
    message: Optional[str] = None


class SMUStatusResponse(BaseModel):
    connected: bool
    mock: bool
    channel: int
    address: str
    state: str
    output_enabled: bool
    source_mode: Optional[str]
    compliance: Optional[float]
    compliance_type: Optional[str]


class OperationResponse(BaseModel):
    success: bool
    message: Optional[str] = None


class MeasurementResponse(BaseModel):
    success: bool
    voltage: Optional[float] = None
    current: Optional[float] = None
    message: Optional[str] = None


class SweepResponse(BaseModel):
    success: bool
    results: Optional[List[Dict[str, float]]] = None
    points: Optional[int] = None
    aborted: Optional[bool] = None
    message: Optional[str] = None


# Endpoints
@router.get("/status", response_model=SMUStatusResponse)
async def get_smu_status():
    """Get current SMU connection status."""
    status = smu_client.status
    return SMUStatusResponse(
        connected=status.connected,
        mock=status.mock,
        channel=status.channel,
        address=status.address,
        state=status.state,
        output_enabled=status.output_enabled,
        source_mode=status.source_mode,
        compliance=status.compliance,
        compliance_type=status.compliance_type
    )


@router.post("/connect")
async def connect_smu(request: ConnectRequest):
    """Connect to SMU hardware or mock."""
    logger.info(f"Connect request: {request.address} (mock={request.mock})")
    result = smu_client.connect(
        address=request.address,
        mock=request.mock,
        channel=request.channel
    )
    return result


@router.post("/disconnect")
async def disconnect_smu():
    """Disconnect from SMU."""
    result = smu_client.disconnect()
    return result


@router.post("/configure")
async def configure_smu(request: ConfigureRequest):
    """Configure SMU compliance and NPLC."""
    result = smu_client.configure(
        compliance=request.compliance,
        compliance_type=request.compliance_type,
        nplc=request.nplc
    )
    return result


@router.post("/source-mode")
async def set_source_mode(request: SourceModeRequest):
    """Set source mode (VOLT or CURR)."""
    result = smu_client.set_source_mode(request.mode)
    return result


@router.post("/set")
async def set_value(request: SetValueRequest):
    """Set source value (voltage or current)."""
    result = smu_client.set_value(request.value)
    return result


@router.post("/output")
async def control_output(request: OutputRequest):
    """Enable or disable SMU output."""
    result = smu_client.output_control(request.enabled)
    return result


@router.get("/measure", response_model=MeasurementResponse)
async def measure():
    """Perform a single measurement."""
    result = smu_client.measure()
    return MeasurementResponse(**result)


@router.post("/sweep", response_model=SweepResponse)
async def run_sweep(request: SweepRequest):
    """
    Execute an advanced IV sweep.
    
    Sweeps voltage with configurable direction, scale, and type.
    """
    logger.info(f"Sweep request: {request.start}V to {request.stop}V, scale={request.scale}, dir={request.direction}, type={request.sweep_type}")
    result = smu_client.run_iv_sweep(
        start=request.start,
        stop=request.stop,
        steps=request.points,
        compliance=request.compliance,
        delay=request.delay,
        scale=request.scale,
        direction=request.direction,
        sweep_type=request.sweep_type
    )
    return SweepResponse(**result)


@router.post("/list-sweep", response_model=ListSweepResponse)
async def run_list_sweep(request: ListSweepRequest):
    """
    Execute a sweep across an arbitrary list of points.
    
    Supports voltage or current sweeps.
    """
    logger.info(f"List sweep request: {len(request.points)} points, mode={request.source_mode}")
    result = smu_client.run_list_sweep(
        points=request.points,
        source_mode=request.source_mode,
        compliance=request.compliance,
        nplc=request.nplc,
        delay=request.delay
    )
    return ListSweepResponse(**result)
