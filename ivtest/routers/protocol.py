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


class SaveProtocolRequest(BaseModel):
    """Request to save a protocol to a file."""
    name: str = Field(..., description="Filename without extension")
    content: Dict[str, Any] = Field(..., description="Protocol YAML content")
    folder: str = Field(default="Custom", description="Subfolder name")


class CreateUserRequest(BaseModel):
    """Request to create a new user (folder in protocols/)."""
    name: str = Field(..., description="User name")


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
    steps_completed: int = 0
    total_steps: int = 0


# --- Endpoints ---

@router.get("/list", response_model=ProtocolListResponse)
async def list_protocols():
    """
    List all available protocol files.
    """
    protocols = protocol_loader.list_protocols()
    return ProtocolListResponse(protocols=protocols)


@router.get("/users")
async def list_users():
    """List available users (folders in protocols/)."""
    from ..protocol_loader import PROTOCOLS_DIR
    if not PROTOCOLS_DIR.exists():
        return {"users": []}
    
    users = [d.name for d in PROTOCOLS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
    return {"users": sorted(users)}


@router.post("/create-user")
async def create_user(request: CreateUserRequest):
    """Create a new user folder."""
    from ..protocol_loader import PROTOCOLS_DIR
    user_dir = PROTOCOLS_DIR / request.name
    
    if user_dir.exists():
        return {"success": False, "message": "User already exists"}
    
    try:
        user_dir.mkdir(parents=True, exist_ok=True)
        return {"success": True, "message": f"User {request.name} created"}
    except Exception as e:
        logger.error(f"Failed to create user {request.name}: {e}")
        return {"success": False, "message": str(e)}


@router.get("/calibration-files")
async def list_calibration_files():
    """List available calibration files (cal*.txt) in root."""
    from pathlib import Path
    root = Path(".").resolve()
    files = list(root.glob("cal*.txt"))
    return {"files": [f.name for f in files]}


@router.get("/calibration-data/{filename}")
async def get_calibration_data(filename: str):
    """Get content of a calibration file."""
    from pathlib import Path
    import numpy as np
    
    # Security: basic check
    if not filename.startswith("cal") or not filename.endswith(".txt"):
        return {"success": False, "message": "Invalid filename"}
        
    path = Path(".").resolve() / filename
    if not path.exists():
        return {"success": False, "message": "File not found"}
        
    try:
        # Try new format first: 3 columns with header (LED_Current, PD_Current, Irradiance)
        try:
            data = np.loadtxt(path, delimiter='\t', skiprows=1)
            if data.ndim == 2 and data.shape[1] >= 3:
                return {
                    "success": True,
                    "format": "3-column",
                    "currents": data[:, 0].tolist(),
                    "voltages": data[:, 1].tolist(),
                    "irradiances": data[:, 2].tolist()
                }
        except:
            pass

        # Fall back to old format: 2 columns, no header (Current, Irradiance)
        data = np.loadtxt(path, delimiter='\t', skiprows=0)
        if data.ndim == 2 and data.shape[1] >= 2:
            return {
                "success": True,
                "format": "2-column",
                "currents": data[:, 0].tolist(),
                "irradiances": data[:, 1].tolist()
            }
        elif data.ndim == 1: # Single row calibration maybe?
             return {
                "success": True,
                "format": "single-row",
                "currents": [data[0]],
                "irradiances": [data[1]]
            }
            
        return {"success": False, "message": "Unsupported file format"}

    except Exception as e:
        logger.error(f"Failed to load calibration data {filename}: {e}")
        return {"success": False, "message": str(e)}


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
    status = run_manager.get_status()
    return ProtocolStatusResponse(
        state=status["state"],
        run_duration_seconds=status["run_duration_seconds"] or 0.0,
        abort_requested=status["abort_requested"],
        steps_completed=status["steps_completed"],
        total_steps=status["total_steps"]
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


@router.get("/get/{protocol_id:path}")
async def get_protocol(protocol_id: str):
    """
    Get the content of a protocol file.
    """
    logger.info(f"Loading protocol content: {protocol_id}")
    try:
        proto = protocol_loader.load(protocol_id)
        return {
            "success": True,
            "id": protocol_id,
            "content": {
                "name": proto.name,
                "description": proto.description,
                "version": proto.version,
                "steps": proto.steps
            }
        }
    except Exception as e:
        logger.error(f"Failed to load protocol {protocol_id}: {e}")
        return {"success": False, "message": str(e)}


@router.post("/save")
async def save_protocol(request: SaveProtocolRequest):
    """
    Save a protocol to a file.
    """
    logger.info(f"Saving protocol: {request.name} in {request.folder}")
    
    try:
        filepath = await protocol_loader.save(request.name, request.content, request.folder)
        return {
            "success": True, 
            "message": f"Protocol saved to {request.folder}/{request.name}.yaml",
            "filepath": filepath
        }
    except Exception as e:
        logger.error(f"Failed to save protocol: {e}")
        return {"success": False, "message": str(e)}
