"""
Arduino Relay Controller - LabVIEW-Compatible Protocol.

Controls relay boards via Arduino serial with protocol:
- Commands 1-12: Turn relay OFF
- Commands 101-112: Turn relay ON
- Baud rate: 112500

Supports:
- Pixel selection Arduino (COM38, 6 relays)
- RGB/LED selection Arduino (COM39, 3 relays)
- Mock mode for development without hardware

NOTE: Future support for HID-based relay boards will be added.
      The backend router will select the appropriate driver based on config.
"""
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import time

from .logging_config import get_logger

logger = get_logger("arduino_relays")


# =============================================================================
# DATA STRUCTURES
# =============================================================================

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


# =============================================================================
# ARDUINO SERIAL RELAY (LabVIEW Protocol)
# =============================================================================

class ArduinoSerialRelay:
    """
    Single Arduino relay board with LabVIEW-compatible protocol.
    
    Protocol:
    - Baud rate: 112500
    - Commands: ASCII numbers with newline
      - OFF: relay_num (e.g., 1-12)
      - ON: on_offset + relay_num (e.g., 101-112 for offset=100, or 11-18 for offset=10)
    - Response: Read available bytes after delay
    
    Board-specific offsets:
    - Pixel board: on_offset=100 (commands 1-12 OFF, 101-112 ON)
    - RGB board: on_offset=10 (commands 1-8 OFF, 11-18 ON)
    """
    
    DEFAULT_BAUD = 112500
    RELAY_DELAY_MS = 50  # ms to wait after command
    
    def __init__(
        self,
        name: str,
        port: str,
        num_relays: int,
        on_offset: int = 100,
        mock: bool = True,
        baud: int = DEFAULT_BAUD
    ):
        """
        Initialize Arduino relay board.
        
        Args:
            name: Board identifier (e.g., "PIXEL", "RGB")
            port: Serial port (e.g., "COM38")
            num_relays: Number of relays on this board
            on_offset: Value to add for ON command (100 for Pixel, 10 for RGB)
            mock: Use mock mode (no hardware)
            baud: Baud rate (default 112500)
        """
        self.name = name
        self.port = port
        self.num_relays = num_relays
        self.on_offset = on_offset
        self.mock = mock
        self.baud = baud
        
        self._serial = None
        self._connected = False
        self._lock = threading.Lock()
        
        # Track relay states (1-indexed to match protocol)
        self.relay_states: Dict[int, RelayState] = {
            i: RelayState.OFF for i in range(1, num_relays + 1)
        }
        
        self._last_response: str = ""
        
        logger.info(f"ArduinoSerialRelay '{name}' initialized (port={port}, relays={num_relays}, mock={mock})")
    
    def connect(self) -> Dict:
        """Connect to Arduino via serial port."""
        with self._lock:
            if self._connected:
                return {"success": True, "message": f"{self.name} already connected"}
            
            if self.mock:
                time.sleep(0.1)  # Simulate connection delay
                self._connected = True
                logger.info(f"MOCK: {self.name} connected on {self.port}")
                return {"success": True, "message": f"Mock {self.name} connected", "mock": True}
            
            try:
                import serial
                self._serial = serial.Serial(
                    port=self.port,
                    baudrate=self.baud,
                    timeout=1
                )
                time.sleep(2)  # Arduino reset delay after serial connect
                self._connected = True
                logger.info(f"{self.name} connected on {self.port} @ {self.baud} baud")
                return {"success": True, "message": f"{self.name} connected on {self.port}"}
            except Exception as e:
                logger.error(f"{self.name} connection failed: {e}")
                return {"success": False, "message": str(e)}
    
    def disconnect(self) -> Dict:
        """Disconnect from Arduino."""
        with self._lock:
            # Turn all relays off before disconnecting
            self._all_off_internal()
            
            if self._serial:
                try:
                    self._serial.close()
                except:
                    pass
                self._serial = None
            
            self._connected = False
            logger.info(f"{self.name} disconnected")
            return {"success": True, "message": f"{self.name} disconnected"}
    
    def set_relay(self, relay_num: int, on: bool, delay_ms: int = None) -> Dict:
        """
        Set a relay ON or OFF using LabVIEW protocol.
        
        Args:
            relay_num: Relay number (1-indexed, will be coerced to valid range)
            on: True for ON, False for OFF
            delay_ms: Delay after command (default: RELAY_DELAY_MS)
            
        Returns:
            Dict with success, command sent, and response
        """
        with self._lock:
            if not self._connected:
                return {"success": False, "message": f"{self.name} not connected"}
            
            # Coerce relay number to valid range (1 to num_relays)
            relay_num = min(max(relay_num, 1), self.num_relays)
            
            # Calculate command: on_offset + relay for ON, just relay for OFF
            # Pixel board: on_offset=100 -> 101-112 for ON
            # RGB board: on_offset=10 -> 11-18 for ON
            if on:
                command = self.on_offset + relay_num
            else:
                command = relay_num
            
            delay = delay_ms if delay_ms is not None else self.RELAY_DELAY_MS
            
            # Send command
            response = self._send_command(str(command), delay)
            
            # Update state
            self.relay_states[relay_num] = RelayState.ON if on else RelayState.OFF
            
            logger.info(f"{self.name}: Relay {relay_num} -> {'ON' if on else 'OFF'} (cmd={command})")
            
            return {
                "success": True,
                "board": self.name,
                "relay": relay_num,
                "state": "ON" if on else "OFF",
                "command": command,
                "response": response
            }
    
    def all_off(self) -> Dict:
        """Turn all relays off."""
        with self._lock:
            if not self._connected:
                return {"success": False, "message": f"{self.name} not connected"}
            
            results = self._all_off_internal()
            return {"success": True, "message": f"{self.name} all relays off", "results": results}
    
    def _all_off_internal(self) -> List[Dict]:
        """Internal: turn all relays off (called within lock)."""
        results = []
        for relay_num in range(1, self.num_relays + 1):
            if self.relay_states.get(relay_num) == RelayState.ON:
                cmd = str(relay_num)  # OFF command = relay number
                resp = self._send_command(cmd, self.RELAY_DELAY_MS)
                self.relay_states[relay_num] = RelayState.OFF
                results.append({"relay": relay_num, "command": cmd, "response": resp})
        return results
    
    def _send_command(self, cmd: str, delay_ms: int) -> str:
        """
        Send command to Arduino and read response.
        
        Args:
            cmd: Command string (will add newline)
            delay_ms: Delay before reading response
            
        Returns:
            Response string from Arduino (or mock response)
        """
        if self.mock:
            time.sleep(delay_ms / 1000.0)
            response = f"MOCK:{cmd}:OK"
            self._last_response = response
            logger.debug(f"MOCK {self.name}: Sent '{cmd}', got '{response}'")
            return response
        
        if not self._serial:
            return ""
        
        try:
            # Send command with newline
            self._serial.write(f"{cmd}\n".encode())
            
            # Wait for relay switching and Arduino processing
            time.sleep(delay_ms / 1000.0)
            
            # Read response if bytes available (LabVIEW style)
            n = self._serial.in_waiting
            if n > 0:
                response = self._serial.read(n).decode('utf-8', errors='replace').strip()
            else:
                response = ""
            
            self._last_response = response
            logger.debug(f"{self.name}: Sent '{cmd}', got '{response}'")
            return response
            
        except Exception as e:
            logger.error(f"{self.name} serial error: {e}")
            return f"ERROR: {e}"
    
    def get_status(self) -> Dict:
        """Get current status of this Arduino board."""
        return {
            "name": self.name,
            "port": self.port,
            "connected": self._connected,
            "mock": self.mock,
            "num_relays": self.num_relays,
            "relay_states": {k: v.name for k, v in self.relay_states.items()},
            "last_response": self._last_response
        }


# =============================================================================
# RELAY CONTROLLER (Manages Multiple Boards)
# =============================================================================

class ArduinoRelayController:
    """
    Controller managing multiple Arduino relay boards.
    
    Default configuration:
    - Pixel Arduino: COM38, 6 relays (for photodetector pixel selection)
    - RGB Arduino: COM39, 8 relays (for LED wavelength selection, per LabVIEW range 1-8)
    """
    
    # Default port configuration
    DEFAULT_PIXEL_PORT = "COM38"
    DEFAULT_RGB_PORT = "COM39"
    DEFAULT_BAUD = 112500
    
    def __init__(self, mock: bool = True):
        """
        Initialize controller with default boards.
        
        Args:
            mock: Use mock mode for all boards
        """
        self.mock = mock
        self._lock = threading.Lock()
        
        # Create board instances with board-specific on_offset values
        # Pixel: ON command = 100 + relay (e.g., 101 for relay 1 ON)
        # RGB: ON command = 10 + relay (e.g., 11 for relay 1 ON)
        self.pixel_board = ArduinoSerialRelay(
            name="PIXEL",
            port=self.DEFAULT_PIXEL_PORT,
            num_relays=6,
            on_offset=100,  # Commands: 1-6 OFF, 101-106 ON
            mock=mock
        )
        
        self.rgb_board = ArduinoSerialRelay(
            name="RGB",
            port=self.DEFAULT_RGB_PORT,
            num_relays=8,  # LabVIEW uses range 1-8 for LED selection
            on_offset=10,  # Commands: 1-8 OFF, 11-18 ON
            mock=mock
        )
        
        # Currently selected (for compatibility with existing API)
        self._selected_pixel: Optional[int] = None
        self._selected_led_channel: Optional[int] = None
        
        logger.info(f"ArduinoRelayController initialized (mock={mock})")
    
    def connect(self, port: Optional[str] = None, mock: Optional[bool] = None) -> Dict:
        """
        Connect both boards (legacy API compatibility).
        For individual board control, use connect_board().
        """
        if mock is not None:
            self.mock = mock
            self.pixel_board.mock = mock
            self.rgb_board.mock = mock
        
        pixel_result = self.pixel_board.connect()
        rgb_result = self.rgb_board.connect()
        
        success = pixel_result["success"] and rgb_result["success"]
        return {
            "success": success,
            "message": "Both boards connected" if success else "Connection failed",
            "pixel": pixel_result,
            "rgb": rgb_result,
            "mock": self.mock
        }
    
    def connect_board(self, board: str, port: Optional[str] = None, mock: Optional[bool] = None) -> Dict:
        """
        Connect a specific board.
        
        Args:
            board: "pixel" or "rgb"
            port: Override port (optional)
            mock: Override mock mode (optional)
        """
        board_lower = board.lower()
        
        if board_lower == "pixel":
            target = self.pixel_board
        elif board_lower in ("rgb", "led"):
            target = self.rgb_board
        else:
            return {"success": False, "message": f"Unknown board: {board}"}
        
        if port:
            target.port = port
        if mock is not None:
            target.mock = mock
        
        return target.connect()
    
    def disconnect(self) -> Dict:
        """Disconnect all boards."""
        with self._lock:
            pixel_result = self.pixel_board.disconnect()
            rgb_result = self.rgb_board.disconnect()
            self._selected_pixel = None
            self._selected_led_channel = None
            return {
                "success": True,
                "message": "All boards disconnected",
                "pixel": pixel_result,
                "rgb": rgb_result
            }
    
    def set_relay(self, board: str, relay_num: int, on: bool) -> Dict:
        """
        Set a specific relay on a specific board.
        
        Args:
            board: "pixel" or "rgb"
            relay_num: Relay number (1-indexed)
            on: True for ON, False for OFF
        """
        board_lower = board.lower()
        
        if board_lower == "pixel":
            return self.pixel_board.set_relay(relay_num, on)
        elif board_lower in ("rgb", "led"):
            return self.rgb_board.set_relay(relay_num, on)
        else:
            return {"success": False, "message": f"Unknown board: {board}"}
    
    def select_pixel(self, pixel_id: int) -> Dict:
        """
        Select a pixel (exclusive - only one at a time).
        
        Args:
            pixel_id: 0-indexed pixel number (will be converted to 1-indexed internally)
        """
        with self._lock:
            if not self.pixel_board._connected:
                return {"success": False, "message": "Pixel board not connected"}
            
            # Convert 0-indexed to 1-indexed for protocol
            relay_num = pixel_id + 1
            
            if relay_num < 1 or relay_num > self.pixel_board.num_relays:
                return {"success": False, "message": f"Invalid pixel ID: {pixel_id}"}
            
            # Turn off previously selected pixel
            if self._selected_pixel is not None:
                prev_relay = self._selected_pixel + 1
                self.pixel_board.set_relay(prev_relay, False)
            
            # Turn on new pixel
            result = self.pixel_board.set_relay(relay_num, True)
            if result["success"]:
                self._selected_pixel = pixel_id
            
            return {"success": result["success"], "pixel": pixel_id, "response": result.get("response", "")}
    
    def select_led_channel(self, channel_id: int) -> Dict:
        """
        Select an LED illumination channel.
        
        Args:
            channel_id: 0-indexed LED channel (will be converted to 1-indexed internally)
        """
        with self._lock:
            if not self.rgb_board._connected:
                return {"success": False, "message": "RGB board not connected"}
            
            # Convert 0-indexed to 1-indexed for protocol
            relay_num = channel_id + 1
            
            if relay_num < 1 or relay_num > self.rgb_board.num_relays:
                return {"success": False, "message": f"Invalid LED channel: {channel_id}"}
            
            # Turn off previously selected channel
            if self._selected_led_channel is not None:
                prev_relay = self._selected_led_channel + 1
                self.rgb_board.set_relay(prev_relay, False)
            
            # Turn on new channel
            result = self.rgb_board.set_relay(relay_num, True)
            if result["success"]:
                self._selected_led_channel = channel_id
            
            return {"success": result["success"], "led_channel": channel_id, "response": result.get("response", "")}
    
    def all_off(self) -> Dict:
        """Turn all relays off on all boards."""
        with self._lock:
            pixel_result = self.pixel_board.all_off()
            rgb_result = self.rgb_board.all_off()
            self._selected_pixel = None
            self._selected_led_channel = None
            return {
                "success": True,
                "message": "All relays off",
                "pixel": pixel_result,
                "rgb": rgb_result
            }
    
    def get_status(self) -> Dict:
        """Get current relay status for all boards."""
        return {
            "connected": self.pixel_board._connected or self.rgb_board._connected,
            "mock": self.mock,
            "selected_pixel": self._selected_pixel,
            "selected_led_channel": self._selected_led_channel,
            "pixel_board": self.pixel_board.get_status(),
            "rgb_board": self.rgb_board.get_status()
        }


# =============================================================================
# GLOBAL SINGLETON
# =============================================================================

# Global singleton instance (default mock mode)
relay_controller = ArduinoRelayController(mock=True)


# =============================================================================
# NOTE: HID BOARD SUPPORT (FUTURE)
# =============================================================================
# Future implementation will add HidRelayBoard class for USB HID relay boards.
# The backend router will select between Arduino and HID based on configuration.
# HID boards typically use different command protocol (e.g., feature reports).
# =============================================================================
