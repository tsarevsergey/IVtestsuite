"""
Relay Control API Endpoints.
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


# Request Models
class RelayConnectRequest(BaseModel):
    port: str = Field(default="COM3", description="Serial port")
    mock: bool = Field(default=True, description="Use mock mode")


class PixelSelectRequest(BaseModel):
    pixel_id: int = Field(..., ge=0, le=7, description="Pixel index (0-7)")


class LEDSelectRequest(BaseModel):
    channel_id: int = Field(..., ge=0, le=3, description="LED channel index (0-3)")


# Endpoints
@router.get("/status")
async def get_relay_status():
    """Get current relay status."""
    return get_relay_controller().get_status()


@router.post("/connect")
async def connect_relays(request: RelayConnectRequest):
    """Connect to relay controller."""
    import ivtest.arduino_relays as relay_module
    from ..arduino_relays import ArduinoRelayController
    
    # Create new controller with request params
    new_controller = ArduinoRelayController(
        port=request.port,
        mock=request.mock
    )
    result = new_controller.connect()
    
    if result["success"]:
        # Replace global instance in the module
        relay_module.relay_controller = new_controller
    
    return result


@router.post("/disconnect")
async def disconnect_relays():
    """Disconnect from relay controller."""
    return get_relay_controller().disconnect()


@router.post("/pixel")
async def select_pixel(request: PixelSelectRequest):
    """Select a pixel (turns off all others)."""
    return get_relay_controller().select_pixel(request.pixel_id)


@router.post("/led")
async def select_led_channel(request: LEDSelectRequest):
    """Select an LED illumination channel."""
    return get_relay_controller().select_led_channel(request.channel_id)


@router.post("/all-off")
async def all_relays_off():
    """Turn all relays off (safe state)."""
    return get_relay_controller().all_off()
