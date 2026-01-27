"""
Arduino Relay Controller - Mock Framework.

Controls relay boards for:
- Pixel selection (which device under test)
- LED channel selection (which illumination channel)

Supports mock mode for development without hardware.
"""
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import time

from .logging_config import get_logger

logger = get_logger("arduino_relays")


class RelayState(Enum):
    """State of a single relay."""
    OFF = 0
    ON = 1


@dataclass
class RelayChannel:
    """Single relay channel."""
    id: int
    name: str
    state: RelayState = RelayState.OFF
    
    def set(self, on: bool):
        self.state = RelayState.ON if on else RelayState.OFF


@dataclass
class RelayBoard:
    """A relay board with multiple channels."""
    name: str
    num_channels: int
    channels: List[RelayChannel] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.channels:
            self.channels = [
                RelayChannel(id=i, name=f"{self.name}_CH{i}")
                for i in range(self.num_channels)
            ]
    
    def set_channel(self, channel_id: int, on: bool) -> bool:
        """Set a specific channel on or off."""
        if 0 <= channel_id < len(self.channels):
            self.channels[channel_id].set(on)
            return True
        return False
    
    def all_off(self):
        """Turn all channels off."""
        for ch in self.channels:
            ch.set(False)
    
    def get_state(self) -> Dict[int, str]:
        """Get state of all channels."""
        return {ch.id: ch.state.name for ch in self.channels}


class ArduinoRelayController:
    """
    Controller for Arduino-based relay boards.
    
    Supports:
    - Pixel selection (8 pixels typically)
    - LED channel selection (multiple wavelengths)
    - Mock mode for testing without hardware
    """
    
    def __init__(
        self, 
        port: str = "COM3",
        mock: bool = True,
        num_pixels: int = 8,
        num_led_channels: int = 4
    ):
        """
        Initialize the relay controller.
        
        Args:
            port: Serial port for real hardware
            mock: Use mock mode (no hardware)
            num_pixels: Number of pixel selection relays
            num_led_channels: Number of LED channel relays
        """
        self.port = port
        self.mock = mock
        self._connected = False
        self._serial = None
        self._lock = threading.Lock()
        
        # Relay boards
        self.pixel_board = RelayBoard(name="PIXEL", num_channels=num_pixels)
        self.led_board = RelayBoard(name="LED", num_channels=num_led_channels)
        
        # Currently selected
        self._selected_pixel: Optional[int] = None
        self._selected_led_channel: Optional[int] = None
        
        logger.info(f"ArduinoRelayController initialized (mock={mock})")
    
    def connect(self) -> Dict:
        """Connect to Arduino (or mock)."""
        with self._lock:
            if self.mock:
                # Simulate connection delay
                time.sleep(0.1)
                self._connected = True
                logger.info(f"MOCK: Connected to relay controller")
                return {"success": True, "message": "Mock relay connected", "mock": True}
            
            # Real hardware connection
            try:
                import serial
                self._serial = serial.Serial(self.port, 9600, timeout=1)
                time.sleep(2)  # Arduino reset delay
                self._connected = True
                logger.info(f"Connected to relay controller on {self.port}")
                return {"success": True, "message": f"Connected to {self.port}"}
            except Exception as e:
                logger.error(f"Relay connection failed: {e}")
                return {"success": False, "message": str(e)}
    
    def disconnect(self) -> Dict:
        """Disconnect from Arduino."""
        with self._lock:
            self.all_off()
            
            if self._serial:
                try:
                    self._serial.close()
                except:
                    pass
                self._serial = None
            
            self._connected = False
            logger.info("Relay controller disconnected")
            return {"success": True, "message": "Disconnected"}
    
    def select_pixel(self, pixel_id: int) -> Dict:
        """
        Select a pixel (exclusive - only one at a time).
        
        Args:
            pixel_id: 0-indexed pixel number
        """
        with self._lock:
            if not self._connected:
                return {"success": False, "message": "Not connected"}
            
            if pixel_id < 0 or pixel_id >= self.pixel_board.num_channels:
                return {"success": False, "message": f"Invalid pixel ID: {pixel_id}"}
            
            # Turn off all pixels first
            self.pixel_board.all_off()
            
            # Turn on selected pixel
            self.pixel_board.set_channel(pixel_id, True)
            self._selected_pixel = pixel_id
            
            if self.mock:
                time.sleep(0.02)  # Simulate relay switching time
                logger.info(f"MOCK: Selected pixel {pixel_id}")
            else:
                self._send_command(f"P{pixel_id}")
            
            return {"success": True, "pixel": pixel_id}
    
    def select_led_channel(self, channel_id: int) -> Dict:
        """
        Select an LED illumination channel.
        
        Args:
            channel_id: 0-indexed LED channel
        """
        with self._lock:
            if not self._connected:
                return {"success": False, "message": "Not connected"}
            
            if channel_id < 0 or channel_id >= self.led_board.num_channels:
                return {"success": False, "message": f"Invalid LED channel: {channel_id}"}
            
            # Turn off all LED channels first
            self.led_board.all_off()
            
            # Turn on selected channel
            self.led_board.set_channel(channel_id, True)
            self._selected_led_channel = channel_id
            
            if self.mock:
                time.sleep(0.02)  # Simulate relay switching time
                logger.info(f"MOCK: Selected LED channel {channel_id}")
            else:
                self._send_command(f"L{channel_id}")
            
            return {"success": True, "led_channel": channel_id}
    
    def all_off(self) -> Dict:
        """Turn all relays off (safe state)."""
        with self._lock:
            self.pixel_board.all_off()
            self.led_board.all_off()
            self._selected_pixel = None
            self._selected_led_channel = None
            
            if self.mock:
                time.sleep(0.02)
                logger.info("MOCK: All relays OFF")
            else:
                self._send_command("OFF")
            
            return {"success": True, "message": "All relays off"}
    
    def get_status(self) -> Dict:
        """Get current relay status."""
        return {
            "connected": self._connected,
            "mock": self.mock,
            "selected_pixel": self._selected_pixel,
            "selected_led_channel": self._selected_led_channel,
            "pixel_states": self.pixel_board.get_state(),
            "led_states": self.led_board.get_state()
        }
    
    def _send_command(self, cmd: str):
        """Send command to real hardware."""
        if not self._serial:
            return
        
        try:
            self._serial.write(f"{cmd}\n".encode())
            time.sleep(0.05)  # Command processing time
        except Exception as e:
            logger.error(f"Serial write error: {e}")


# Global singleton instance (default mock mode)
relay_controller = ArduinoRelayController(mock=True)
