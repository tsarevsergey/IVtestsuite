"""
Protocol API Endpoints - Protocol Designer system.

Supports:
- Loading protocols from YAML files
- Running named or inline protocols
- Execution status tracking
"""
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from ..protocol_engine import protocol_engine
from ..protocol_loader import protocol_loader
from ..run_manager import run_manager
from ..logging_config import get_logger

logger = get_logger("routers.protocol")
router = APIRouter(prefix="/protocol", tags=["protocol"])


# --- Request Models ---

class RunProtocolRequest(BaseModel):
    """Request to run a named protocol."""
    name: str = Field(..., description="Protocol name (filename without .yaml)")


class RunInlineRequest(BaseModel):
    """Request to run an inline protocol (steps passed directly)."""
    steps: List[Dict[str, Any]] = Field(..., description="Protocol steps")
    name: str = Field(default="inline", description="Protocol name for logging")
    skip_cleanup: bool = Field(default=False, description="Skip safety cleanup (keep outputs on)")


class ProtocolStepInfo(BaseModel):
    """Information about a protocol step result."""
    step_index: int
    action: str
    success: bool
    duration_ms: float
    error: Optional[str] = None


class ProtocolResponse(BaseModel):
    """Response from protocol execution."""
    success: bool
    name: str = ""
    steps_completed: int = 0
    total_steps: int = 0
    aborted: bool = False
    error: Optional[str] = None
    captured_data: Dict[str, Any] = {}


class ProtocolListResponse(BaseModel):
    """Response listing available protocols."""
    protocols: List[Dict[str, str]]


class ProtocolStatusResponse(BaseModel):
    """Current protocol execution status."""
    state: str
    run_duration_seconds: Optional[float] = 0.0
    abort_requested: bool


# --- Endpoints ---

@router.get("/list", response_model=ProtocolListResponse)
async def list_protocols():
    """
    List all available protocol files.
    
    Protocols are loaded from the ./protocols/ directory.
    """
    protocols = protocol_loader.list_protocols()
    return ProtocolListResponse(protocols=protocols)


@router.post("/run", response_model=ProtocolResponse)
async def run_protocol(request: RunProtocolRequest, background_tasks: BackgroundTasks):
    """
    Start a named protocol in the background.
    """
    logger.info(f"Starting protocol: {request.name}")
    
    try:
        # Load protocol
        proto = protocol_loader.load(request.name)
        
        # Start in background
        background_tasks.add_task(protocol_engine.run, proto.steps)
        
        return ProtocolResponse(
            success=True,
            name=proto.name,
            total_steps=len(proto.steps),
            captured_data={}
        )
        
    except FileNotFoundError as e:
        logger.error(f"Protocol not found: {request.name}")
        return ProtocolResponse(
            success=False,
            name=request.name,
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Protocol start failed: {e}")
        return ProtocolResponse(
            success=False,
            name=request.name,
            error=str(e)
        )


@router.post("/run-inline", response_model=ProtocolResponse)
async def run_inline_protocol(request: RunInlineRequest, background_tasks: BackgroundTasks):
    """
    Start an inline protocol in the background.
    """
    logger.info(f"Starting inline protocol: {request.name} ({len(request.steps)} steps, skip_cleanup={request.skip_cleanup})")
    
    try:
        background_tasks.add_task(protocol_engine.run, request.steps, request.skip_cleanup)
        
        return ProtocolResponse(
            success=True,
            name=request.name,
            total_steps=len(request.steps),
            captured_data={}
        )
        
    except Exception as e:
        logger.error(f"Inline protocol start failed: {e}")
        return ProtocolResponse(
            success=False,
            name=request.name,
            error=str(e)
        )


@router.get("/data")
async def get_protocol_data():
    """Get currently captured data variables."""
    return protocol_engine.get_captured_data()


@router.get("/history")
async def get_protocol_history(limit: Optional[int] = None):
    """
    Get history of all captured data events.
    
    Args:
        limit: Return only the last N events.
    """
    return protocol_engine.get_history(limit=limit)


@router.get("/status", response_model=ProtocolStatusResponse)
async def get_protocol_status():
    """Get current protocol execution status."""
    return ProtocolStatusResponse(
        state=run_manager.state.value,
        run_duration_seconds=run_manager.run_duration_seconds or 0.0,
        abort_requested=run_manager.is_abort_requested()
    )


@router.post("/abort")
async def abort_protocol():
    """Abort the currently running protocol."""
    run_manager.abort()
    return {"success": True, "message": "Abort requested"}


@router.post("/reload")
async def reload_protocols():
    """Clear the protocol cache and reload all protocols."""
    protocol_loader.clear_cache()
    return {"success": True, "message": "Protocol cache cleared"}
