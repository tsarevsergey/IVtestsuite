"""
Relay Control API Endpoints.

Supports Arduino-based relay boards with LabVIEW-compatible protocol.
NOTE: Future support for HID relay boards will be added.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, Dict

from ..logging_config import get_logger

logger = get_logger("routers.relays")
router = APIRouter(prefix="/relays", tags=["relays"])


def get_relay_controller():
    """Get the current relay controller instance."""
    import ivtest.arduino_relays as relay_module
    return relay_module.relay_controller


# =============================================================================
# REQUEST MODELS
# =============================================================================

class RelayConnectRequest(BaseModel):
    """Legacy connect request (connects both boards)."""
    port: str = Field(default="COM3", description="Serial port (unused in dual-board mode)")
    mock: bool = Field(default=True, description="Use mock mode")


class BoardConnectRequest(BaseModel):
    """Connect to a specific Arduino board."""
    board: str = Field(..., description="Board name: 'pixel' or 'rgb'")
    port: Optional[str] = Field(default=None, description="Override COM port")
    mock: bool = Field(default=False, description="Use mock mode")


class PixelSelectRequest(BaseModel):
    """Select a pixel (0-indexed)."""
    pixel_id: int = Field(..., ge=0, le=5, description="Pixel index (0-5)")


class LEDSelectRequest(BaseModel):
    """Select an LED channel (0-indexed)."""
    channel_id: int = Field(..., ge=0, le=7, description="LED channel index (0-7, per LabVIEW range 1-8)")


class SetRelayRequest(BaseModel):
    """Set individual relay on a board."""
    board: str = Field(..., description="Board name: 'pixel' or 'rgb'")
    relay: int = Field(..., ge=1, le=12, description="Relay number (1-indexed)")
    on: bool = Field(..., description="True for ON, False for OFF")


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/status")
async def get_relay_status():
    """Get current relay status for all boards."""
    return get_relay_controller().get_status()


@router.post("/connect")
async def connect_relays(request: RelayConnectRequest):
    """
    Connect to relay controller (both boards).
    Legacy endpoint for backwards compatibility.
    """
    return get_relay_controller().connect(mock=request.mock)


@router.post("/connect-board")
async def connect_board(request: BoardConnectRequest):
    """Connect to a specific Arduino board (pixel or rgb)."""
    return get_relay_controller().connect_board(
        board=request.board,
        port=request.port,
        mock=request.mock
    )


@router.post("/disconnect")
async def disconnect_relays():
    """Disconnect from all relay boards."""
    return get_relay_controller().disconnect()


@router.post("/pixel")
async def select_pixel(request: PixelSelectRequest):
    """Select a pixel (turns off all others)."""
    return get_relay_controller().select_pixel(request.pixel_id)


@router.post("/led")
async def select_led_channel(request: LEDSelectRequest):
    """Select an LED illumination channel."""
    return get_relay_controller().select_led_channel(request.channel_id)


@router.post("/set-relay")
async def set_relay(request: SetRelayRequest):
    """
    Set individual relay ON or OFF.
    
    Uses LabVIEW protocol:
    - Relay numbers are 1-indexed
    - ON command = 100 + relay_num
    - OFF command = relay_num
    """
    return get_relay_controller().set_relay(
        board=request.board,
        relay_num=request.relay,
        on=request.on
    )


@router.post("/all-off")
async def all_relays_off():
    """Turn all relays off on all boards (safe state)."""
    return get_relay_controller().all_off()


@router.get("/config")
async def get_relay_config():
    """Get current relay configuration (scheme, ports, wavelengths)."""
    return get_relay_controller().get_config()


@router.get("/wavelengths")
async def get_wavelengths():
    """Get LED wavelength mapping."""
    return get_relay_controller().get_wavelengths()


@router.get("/active")
async def get_active_relays():
    """Get currently active (ON) relays on each board."""
    return get_relay_controller().get_active_relays()


@router.post("/safe-disconnect")
async def safe_disconnect():
    """
    Safely disconnect from all relay boards.
    Turns all relays OFF before closing serial ports.
    """
    return get_relay_controller().safe_disconnect()

