"""
SMU Client - Abstraction layer for SMU hardware control.

Wraps SMUController with a clean async-friendly interface for the FastAPI backend.
Supports both real hardware and mock mode.
"""
import sys
import os
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import threading

# Add parent directory to path for SMUController import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from smu_controller import SMUController, InstrumentState
from .logging_config import get_logger
from .run_manager import run_manager

logger = get_logger("smu_client")

# Default SMU address (can be overridden)
DEFAULT_SMU_ADDRESS = "USB0::0x0957::0xCD18::MY51143841::INSTR"


@dataclass
class SMUStatus:
    """Current status of the SMU connection."""
    connected: bool = False
    mock: bool = False
    channel: int = 1
    address: str = ""
    state: str = "OFF"
    output_enabled: bool = False
    source_mode: Optional[str] = None
    compliance: Optional[float] = None
    compliance_type: Optional[str] = None


class SMUClient:
    """
    High-level client for controlling the SMU.
    
    Thread-safe singleton that wraps SMUController.
    """
    _instance: Optional["SMUClient"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._smu: Optional[SMUController] = None
        self._status = SMUStatus()
        self._op_lock = threading.Lock()
        
        # Register shutdown callback with run manager
        run_manager.register_shutdown_callback(self._emergency_shutdown)
        
        self._initialized = True
        logger.info("SMUClient initialized")
    
    def _emergency_shutdown(self):
        """Emergency shutdown callback for abort scenarios."""
        if self._smu and self._status.connected:
            logger.warning("Emergency shutdown: disabling SMU output")
            try:
                self._smu.disable_output()
            except Exception as e:
                logger.error(f"Emergency shutdown failed: {e}")
    
    @property
    def status(self) -> SMUStatus:
        """Get current SMU status."""
        if self._smu:
            self._status.state = self._smu.state.value
            self._status.output_enabled = getattr(self._smu, '_output_enabled', False)
        return self._status
    
    def connect(
        self, 
        address: str = DEFAULT_SMU_ADDRESS, 
        mock: bool = False, 
        channel: int = 1
    ) -> Dict[str, Any]:
        """
        Connect to SMU hardware or mock.
        
        Args:
            address: VISA resource address
            mock: Use mock mode (no hardware)
            channel: SMU channel (1 or 2)
        
        Returns:
            Connection result dict
        """
        with self._op_lock:
            # Disconnect existing connection
            if self._smu:
                try:
                    self._smu.disconnect()
                except:
                    pass
            
            try:
                self._smu = SMUController(
                    address=address,
                    mock=mock,
                    channel=channel
                )
                self._smu.connect()
                
                if self._smu.state == InstrumentState.ERROR:
                    return {
                        "success": False,
                        "message": "Connection resulted in ERROR state"
                    }
                
                self._status.connected = True
                self._status.mock = mock
                self._status.channel = channel
                self._status.address = address
                self._status.state = self._smu.state.value
                
                logger.info(f"SMU connected: {address} (mock={mock}, channel={channel})")
                
                return {
                    "success": True,
                    "message": f"Connected to {'mock' if mock else 'real'} SMU",
                    "address": address,
                    "channel": channel,
                    "mock": mock
                }
                
            except Exception as e:
                logger.error(f"SMU connection failed: {e}")
                self._status.connected = False
                return {
                    "success": False,
                    "message": str(e)
                }
    
    def disconnect(self) -> Dict[str, Any]:
        """Safely disconnect from SMU."""
        with self._op_lock:
            if not self._smu:
                return {"success": True, "message": "Not connected"}
            
            try:
                self._smu.disconnect()
                self._smu = None
                self._status = SMUStatus()
                logger.info("SMU disconnected")
                return {"success": True, "message": "Disconnected"}
            except Exception as e:
                logger.error(f"Disconnect error: {e}")
                return {"success": False, "message": str(e)}
    
    def configure(
        self, 
        compliance: float, 
        compliance_type: str = "CURR",
        nplc: float = 1.0
    ) -> Dict[str, Any]:
        """
        Configure SMU compliance and measurement speed.
        
        Args:
            compliance: Compliance limit value
            compliance_type: "CURR" or "VOLT"
            nplc: Integration time in power line cycles
        """
        if not self._smu or not self._status.connected:
            return {"success": False, "message": "Not connected"}
        
        with self._op_lock:
            try:
                self._smu.set_compliance(compliance, compliance_type)
                self._smu.set_nplc(nplc)
                
                self._status.compliance = compliance
                self._status.compliance_type = compliance_type
                
                logger.info(f"SMU configured: {compliance_type} compliance={compliance}, NPLC={nplc}")
                
                return {
                    "success": True,
                    "compliance": compliance,
                    "compliance_type": compliance_type,
                    "nplc": nplc
                }
            except Exception as e:
                logger.error(f"Configure error: {e}")
                return {"success": False, "message": str(e)}
    
    def set_source_mode(self, mode: str) -> Dict[str, Any]:
        """Set source mode (VOLT or CURR)."""
        if not self._smu or not self._status.connected:
            return {"success": False, "message": "Not connected"}
        
        with self._op_lock:
            try:
                self._smu.set_source_mode(mode)
                self._status.source_mode = mode
                logger.info(f"Source mode set to {mode}")
                return {"success": True, "mode": mode}
            except Exception as e:
                logger.error(f"Set source mode error: {e}")
                return {"success": False, "message": str(e)}
    
    def set_value(self, value: float) -> Dict[str, Any]:
        """Set source value (voltage or current depending on mode)."""
        if not self._smu or not self._status.connected:
            return {"success": False, "message": "Not connected"}
        
        with self._op_lock:
            try:
                mode = self._status.source_mode or "VOLT"
                if mode == "VOLT":
                    self._smu.set_voltage(value)
                else:
                    self._smu.set_current(value)
                logger.debug(f"Set {mode} value: {value}")
                return {"success": True, "value": value, "mode": mode}
            except Exception as e:
                logger.error(f"Set value error: {e}")
                return {"success": False, "message": str(e)}
    
    def output_control(self, enabled: bool) -> Dict[str, Any]:
        """Enable or disable SMU output."""
        if not self._smu or not self._status.connected:
            return {"success": False, "message": "Not connected"}
        
        with self._op_lock:
            try:
                if enabled:
                    self._smu.enable_output()
                else:
                    self._smu.disable_output()
                
                self._status.output_enabled = enabled
                logger.info(f"Output {'enabled' if enabled else 'disabled'}")
                return {"success": True, "output_enabled": enabled}
            except Exception as e:
                logger.error(f"Output control error: {e}")
                return {"success": False, "message": str(e)}
    
    def measure(self) -> Dict[str, Any]:
        """Perform a single measurement."""
        if not self._smu or not self._status.connected:
            return {"success": False, "message": "Not connected"}
        
        with self._op_lock:
            try:
                data = self._smu.measure()
                return {
                    "success": True,
                    "voltage": data["voltage"],
                    "current": data["current"]
                }
            except Exception as e:
                logger.error(f"Measurement error: {e}")
                return {"success": False, "message": str(e)}
    
    def run_iv_sweep(
        self,
        start: float,
        stop: float,
        steps: int,
        compliance: float = 0.01,
        delay: float = 0.05,
        source_mode: str = "VOLT"
    ) -> Dict[str, Any]:
        """
        Execute a voltage sweep and measure current.
        
        Args:
            start: Starting voltage
            stop: Ending voltage
            steps: Number of measurement points
            compliance: Current compliance (A)
            delay: Delay between points (s)
            source_mode: "VOLT" for voltage sweep
        
        Returns:
            Dict with results list containing {set_voltage, voltage, current}
        """
        if not self._smu or not self._status.connected:
            return {"success": False, "message": "Not connected"}
        
        import numpy as np
        
        with self._op_lock:
            try:
                points = np.linspace(start, stop, steps).tolist()
                results = []
                
                # Configure
                self._smu.set_source_mode(source_mode)
                self._smu.set_compliance(compliance, "CURR")
                self._smu.enable_output()
                
                logger.info(f"Starting IV sweep: {start}V to {stop}V, {steps} points")
                
                for i, v in enumerate(points):
                    # Check for abort
                    if run_manager.is_abort_requested():
                        logger.warning("IV sweep aborted by user")
                        break
                    
                    self._smu.set_voltage(v)
                    time.sleep(delay)
                    meas = self._smu.measure()
                    meas["set_voltage"] = v
                    results.append(meas)
                
                self._smu.disable_output()
                
                logger.info(f"IV sweep complete: {len(results)} points collected")
                
                return {
                    "success": True,
                    "results": results,
                    "points": len(results),
                    "aborted": run_manager.is_abort_requested()
                }
                
            except Exception as e:
                logger.error(f"IV sweep error: {e}")
                # Safety: try to disable output
                try:
                    self._smu.disable_output()
                except:
                    pass
                return {"success": False, "message": str(e)}


# Global singleton instance
smu_client = SMUClient()
