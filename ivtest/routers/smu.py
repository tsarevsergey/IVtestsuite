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
    smu_type: str = Field(default="auto", description="SMU type: auto, keysight_b2901, keysight_b2902, keithley_2400")


class ConfigureRequest(BaseModel):
    compliance: float = Field(..., gt=0, description="Compliance limit value")
    compliance_type: str = Field(default="CURR", pattern="^(CURR|VOLT)$")
    nplc: float = Field(default=1.0, gt=0, le=100)
    channel: Optional[int] = Field(None, ge=1, le=2, description="Target channel (optional)")


class SourceModeRequest(BaseModel):
    mode: str = Field(..., pattern="^(VOLT|CURR)$", description="Source mode")
    channel: Optional[int] = Field(None, ge=1, le=2, description="Target channel (optional)")


class SetValueRequest(BaseModel):
    value: float = Field(..., description="Source value (V or A)")
    channel: Optional[int] = Field(None, ge=1, le=2, description="Target channel (optional)")


class OutputRequest(BaseModel):
    enabled: bool = Field(..., description="Enable or disable output")
    channel: Optional[int] = Field(None, ge=1, le=2, description="Target channel (optional)")


class SweepRequest(BaseModel):
    start: float = Field(..., description="Start voltage")
    stop: float = Field(..., description="Stop voltage")
    points: int = Field(default=11, ge=2, le=1000, description="Number of points (one way)")
    compliance: float = Field(default=0.01, gt=0, description="Current compliance (A)")
    delay: float = Field(default=0.05, ge=0, description="Delay between points (s)")
    scale: Literal["linear", "log"] = Field(default="linear", description="Point distribution")
    direction: Literal["forward", "backward"] = Field(default="forward", description="Sweep direction")
    sweep_type: Literal["single", "double"] = Field(default="single", description="Sweep type")
    channel: Optional[int] = Field(None, ge=1, le=2, description="Target channel (optional)")


class ListSweepRequest(BaseModel):
    points: List[float] = Field(..., description="List of voltage or current points")
    source_mode: Literal["VOLT", "CURR"] = Field(default="VOLT", description="Source mode")
    compliance: float = Field(default=0.1, gt=0, description="Compliance limit")
    nplc: float = Field(default=1.0, gt=0, le=100, description="Integration time")
    delay: float = Field(default=0.1, ge=0, description="Delay between points (s)")
    channel: Optional[int] = Field(None, ge=1, le=2, description="Target channel (optional)")


class ListSweepResponse(BaseModel):
    success: bool
    results: Optional[List[Dict[str, Any]]] = None
    points: Optional[int] = None
    aborted: Optional[bool] = None
    message: Optional[str] = None
    channel: Optional[int] = None


class ChannelStatus(BaseModel):
    id: int
    state: str
    output_enabled: bool
    source_mode: Optional[str]
    compliance: Optional[float]
    compliance_type: Optional[str]
    voltage: Optional[float] = None
    current: Optional[float] = None


class SMUStatusResponse(BaseModel):
    connected: bool
    mock: bool
    channel: int  # Active channel
    address: str
    smu_type: str
    state: str
    output_enabled: bool
    source_mode: Optional[str]
    compliance: Optional[float]
    compliance_type: Optional[str]
    channels: Dict[int, ChannelStatus] = {}  # Detailed per-channel status


class OperationResponse(BaseModel):
    success: bool
    message: Optional[str] = None


class MeasurementResponse(BaseModel):
    success: bool
    voltage: Optional[float] = None
    current: Optional[float] = None
    message: Optional[str] = None
    channel: Optional[int] = None


class SweepResponse(BaseModel):
    success: bool
    results: Optional[List[Dict[str, float]]] = None
    points: Optional[int] = None
    aborted: Optional[bool] = None
    message: Optional[str] = None
    channel: Optional[int] = None


# Endpoints
@router.get("/status", response_model=SMUStatusResponse)
async def get_smu_status():
    """Get current SMU connection status."""
    status = smu_client.status
    
    # Map internal SMUStatus.channels (dict of dicts/objects) to ChannelStatus models
    channels_data = {}
    if hasattr(status, 'channels'):
        for ch_id, ch_data in status.channels.items():
            channels_data[ch_id] = ChannelStatus(
                id=ch_id,
                state=ch_data.get('state', 'OFF'),
                output_enabled=ch_data.get('output_enabled', False),
                source_mode=ch_data.get('source_mode'),
                compliance=ch_data.get('compliance'),
                compliance_type=ch_data.get('compliance_type'),
                voltage=ch_data.get('voltage'),
                current=ch_data.get('current')
            )

    return SMUStatusResponse(
        connected=status.connected,
        mock=status.mock,
        channel=status.channel,
        address=status.address,
        smu_type=status.smu_type,
        state=status.state,
        output_enabled=status.output_enabled,
        source_mode=status.source_mode,
        compliance=status.compliance,
        compliance_type=status.compliance_type,
        channels=channels_data
    )


@router.post("/connect")
async def connect_smu(request: ConnectRequest):
    """Connect to SMU hardware or mock."""
    logger.info(f"Connect request: {request.address} (type={request.smu_type}, mock={request.mock})")
    result = smu_client.connect(
        address=request.address,
        mock=request.mock,
        channel=request.channel,
        smu_type=request.smu_type
    )
    return result


@router.post("/disconnect")
async def disconnect_smu():
    """Disconnect from SMU."""
    return smu_client.disconnect()


@router.post("/configure")
async def configure_smu(request: ConfigureRequest):
    """Configure SMU settings."""
    return smu_client.configure(
        compliance=request.compliance, 
        compliance_type=request.compliance_type,
        nplc=request.nplc,
        channel=request.channel
    )


@router.post("/source-mode")
async def set_source_mode(request: SourceModeRequest):
    """Set source mode (VOLT or CURR)."""
    return smu_client.set_source_mode(request.mode, channel=request.channel)


@router.post("/set")
async def set_value(request: SetValueRequest):
    """Set source value."""
    return smu_client.set_value(request.value, channel=request.channel)


@router.post("/output")
async def output_control(request: OutputRequest):
    """Enable or disable output."""
    return smu_client.output_control(request.enabled, channel=request.channel)


@router.get("/measure")
async def measure(channel: Optional[int] = None):
    """Perform single measurement."""
    import time
    _t_start = time.perf_counter()
    result = smu_client.measure(channel=channel)
    _t_elapsed = (time.perf_counter() - _t_start) * 1000
    logger.info(f"[TIMING] /smu/measure: {_t_elapsed:.1f}ms")
    return result


@router.post("/sweep", response_model=SweepResponse)
async def run_sweep(request: SweepRequest):
    """Run IV sweep."""
    # Run in thread pool to avoid blocking, but SMUClient handles internal locking
    # For long sweeps, we rely on the client method being synchronous but check run_manager
    return smu_client.run_iv_sweep(
        start=request.start,
        stop=request.stop,
        steps=request.points,
        compliance=request.compliance,
        delay=request.delay,
        scale=request.scale,
        direction=request.direction,
        sweep_type=request.sweep_type,
        channel=request.channel
    )


@router.post("/list-sweep", response_model=ListSweepResponse)
async def run_list_sweep(request: ListSweepRequest):
    """Run sweep from list."""
    return smu_client.run_list_sweep(
        points=request.points,
        source_mode=request.source_mode,
        compliance=request.compliance,
        nplc=request.nplc,
        delay=request.delay,
        channel=request.channel
    )


class SimultaneousSweepRequest(BaseModel):
    channels: List[int] = Field(..., description="List of channels to sweep (e.g. [1, 2])")
    start: float = Field(default=0.0, description="Start voltage (V)")
    stop: float = Field(default=1.0, description="Stop voltage (V)")
    points: int = Field(default=11, gt=1, description="Number of points")
    compliance: float = Field(default=0.01, gt=0, description="Compliance limit (A)")
    delay: float = Field(default=0.05, ge=0, description="Delay between points (s)")
    scale: Literal["linear", "log"] = Field(default="linear", description="Point distribution")
    direction: Literal["forward", "backward"] = Field(default="forward", description="Sweep direction")
    sweep_type: Literal["single", "double"] = Field(default="single", description="Sweep type")
    keep_output_on: bool = Field(default=False, description="Keep output on after sweep")
    source_mode: Literal["VOLT"] = Field(default="VOLT", description="Source mode (VOLT only)")


class SimultaneousSweepResponse(BaseModel):
    success: bool
    results: Optional[Dict[int, List[Dict[str, float]]]] = None
    points: Optional[int] = None
    aborted: Optional[bool] = None
    message: Optional[str] = None
    channels: Optional[List[int]] = None


@router.post("/simultaneous-sweep", response_model=SimultaneousSweepResponse)
async def run_simultaneous_sweep(request: SimultaneousSweepRequest):
    """
    Run simultaneous IV sweep on multiple channels.
    """
    result = smu_client.run_simultaneous_sweep(
        channels=request.channels,
        start=request.start,
        stop=request.stop,
        steps=request.points,
        compliance=request.compliance,
        delay=request.delay,
        scale=request.scale,
        direction=request.direction,
        sweep_type=request.sweep_type,
        source_mode=request.source_mode,
        keep_output_on=request.keep_output_on
    )
    
    return SimultaneousSweepResponse(
        success=result.get("success", False),
        results=result.get("results"),
        points=result.get("points"),
        aborted=result.get("aborted", False),
        message=result.get("message"),
        channels=result.get("channels")
    )


class SimultaneousListSweepRequest(BaseModel):
    points_map: Dict[int, List[float]] = Field(..., description="Map of Channel ID to list of points")
    compliance: float = Field(default=0.01, gt=0, description="Compliance limit (A)")
    delay: float = Field(default=0.05, ge=0, description="Delay between points (s)")
    source_mode: Literal["VOLT"] = Field(default="VOLT", description="Source mode (VOLT only)")
    keep_output_on: bool = Field(default=False, description="Keep output on after sweep")


@router.post("/simultaneous-list-sweep", response_model=SimultaneousSweepResponse)
async def run_simultaneous_list_sweep(request: SimultaneousListSweepRequest):
    """
    Run simultaneous sweep with custom point lists.
    """
    result = smu_client.run_simultaneous_list_sweep(
        points_map=request.points_map,
        compliance=request.compliance,
        delay=request.delay,
        source_mode=request.source_mode,
        keep_output_on=request.keep_output_on
    )
    
    return SimultaneousSweepResponse(
        success=result.get("success", False),
        results=result.get("results"),
        points=result.get("points"),
        aborted=result.get("aborted", False),
        message=result.get("message"),
        channels=result.get("channels")
    )
