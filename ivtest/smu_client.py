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
import numpy as np

# Add parent directory to path for SMUController import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Try to import 2-channel controller first (for B2902A), fallback to original
from smu_factory import create_smu, SMUType, create_smu_from_string
from smu_base import SMUState as InstrumentState

from .logging_config import get_logger
from .run_manager import run_manager, RunState

logger = get_logger("smu_client")

# Default SMU address - Updated for 2-channel B2902A
DEFAULT_SMU_ADDRESS = "USB0::2391::35864::MY51141849::0::INSTR"


@dataclass
class SMUStatus:
    """Current status of the SMU connection."""
    connected: bool = False
    mock: bool = False
    channel: int = 1
    address: str = ""
    smu_type: str = "auto"
    state: str = "OFF"
    output_enabled: bool = False
    source_mode: Optional[str] = None
    compliance: Optional[float] = None
    compliance_type: Optional[str] = None
    channels: Dict[int, Dict[str, Any]] = field(default_factory=dict)


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
        
        # Dictionary mapping channel number to controller instance
        self._controllers: Dict[int, Any] = {}
        # Keep track of "active" channel for backward compatibility
        self._active_channel = 1
        
        self._status = SMUStatus()
        self._op_lock = threading.Lock()
        
        # Register shutdown callback with run manager
        run_manager.register_shutdown_callback(self._emergency_shutdown)
        
        self._initialized = True
        logger.info("SMUClient initialized")
    
    def _emergency_shutdown(self):
        """Emergency shutdown callback for abort scenarios."""
        # Disable all output
        for ch, ctrl in self._controllers.items():
            try:
                if getattr(ctrl, '_output_enabled', False):
                    logger.warning(f"Emergency shutdown: disabling Channel {ch}")
                    ctrl.disable_output()
            except Exception as e:
                logger.error(f"Emergency shutdown failed for Ch {ch}: {e}")
    
    @property
    def _smu(self):
        """Property to get active controller for backward compatibility."""
        return self._controllers.get(self._active_channel)
    
    @property
    def status(self) -> SMUStatus:
        """Get current SMU status including all channels."""
        # Update aggregate status from active controller (legacy behavior)
        active_ctrl = self._smu
        
        # If no active controller but we have others, pick one for "main" status
        if not active_ctrl and self._controllers:
            active_ctrl = next(iter(self._controllers.values()))
            
        if active_ctrl:
            self._status.connected = True
            self._status.state = active_ctrl.state.value if hasattr(active_ctrl, 'state') else "UNKNOWN"
            # Ensure safe access to attributes that might not exist on all controllers
            self._status.output_enabled = getattr(active_ctrl, '_output_enabled', False)
            self._status.source_mode = getattr(active_ctrl, '_source_mode', None)
            
            # compliance info depends on implementation
            # We don't easily track current compliance value in base class unless we stored it
            # For now we might return None or cached values if we had them
        
        # Collect detailed status for ALL channels
        channel_status = {}
        for ch, ctrl in self._controllers.items():
            try:
                # Basic status
                ch_stat = {
                    'state': ctrl.state.value if hasattr(ctrl, 'state') else "UNKNOWN",
                    'output_enabled': getattr(ctrl, '_output_enabled', False),
                    'source_mode': getattr(ctrl, '_source_mode', None),
                    # We can try to read cached values if available
                    'compliance': getattr(ctrl, '_last_compliance', None), # Assuming we might add this later
                    'compliance_type': getattr(ctrl, '_last_compliance_type', None),
                    'voltage': getattr(ctrl, '_last_set_v', None),
                    'current': getattr(ctrl, '_last_set_i', None)
                }
                channel_status[ch] = ch_stat
            except Exception as e:
                logger.warning(f"Error reading status for Ch {ch}: {e}")
        
        self._status.channels = channel_status
            
        return self._status
        ctrl = self._smu
        if ctrl:
            self._status.state = ctrl.state.value
            self._status.output_enabled = getattr(ctrl, '_output_enabled', False)
        return self._status
    
    def _get_controller(self, channel: Optional[int]) -> Any:
        """
        Get controller for specific channel.
        
        If channel is None, returns active channel controller.
        Automagically connects secondary channel of same B2902 instrument if possible.
        """
        if channel is None:
            channel = self._active_channel
        
        ctrl = self._controllers.get(channel)
        
        # Lazy connection logic for secondary channel
        if not ctrl and self._status.connected and self._status.smu_type == "keysight_b2902":
            # If we are connected to a B2902, we can try to instantiate the other channel
            # assuming same address.
            with self._op_lock:
                # Double check inside lock
                ctrl = self._controllers.get(channel)
                if not ctrl:
                    logger.info(f"Auto-connecting Channel {channel} on existing B2902 connection")
                    try:
                        # Shared Resource Logic: Find existing controller
                        existing_ctrl = next(iter(self._controllers.values()), None)
                        existing_res = getattr(existing_ctrl, 'resource', None)
                        
                        # Instantiate new controller for this channel
                        new_ctrl = create_smu_from_string(
                            smu_type_str="keysight_b2902",
                            address=self._status.address,
                            channel=channel,
                            mock=self._status.mock,
                            name=f"SMU_{channel}",
                            existing_resource=existing_res
                        )
                        
                        # Connect WITHOUT reset (preserve other channel state)
                        if hasattr(new_ctrl, 'reset_on_connect'):
                            new_ctrl.reset_on_connect = False
                        
                        new_ctrl.connect()
                        self._controllers[channel] = new_ctrl
                        ctrl = new_ctrl
                    except Exception as e:
                        logger.error(f"Failed to auto-connect Channel {channel}: {e}")
                        raise RuntimeError(f"Channel {channel} not connected and auto-connect failed: {e}")
        
        if not ctrl:
             raise RuntimeError(f"Channel {channel} not connected. Connect first.")
             
        return ctrl

    def connect(
        self, 
        address: str = DEFAULT_SMU_ADDRESS, 
        smu_type: str = "auto",
        mock: bool = False, 
        channel: int = 1
    ) -> Dict[str, Any]:
        """
        Connect to SMU hardware or mock.
        """
        with self._op_lock:
            # If address changes or type changes, we should disconnect everything
            if self._controllers and (address != self._status.address):
                self.disconnect()
            
            # If connecting a NEW channel on SAME address, keep others
            try:
                # Shared Resource Logic
                existing_res = None
                # Only share if B2902 (multi-channel capable) and address matches
                # We check smu_type argument OR self._status.smu_type if argument is 'auto'
                
                # Resolving type hint slightly strictly here to enable sharing check
                target_type = smu_type
                if target_type == "auto" and self._status.connected:
                    target_type = self._status.smu_type
                
                if self._controllers and (target_type == "keysight_b2902" or self._status.smu_type == "keysight_b2902") and address == self._status.address:
                    existing_ctrl = next(iter(self._controllers.values()), None)
                    existing_res = getattr(existing_ctrl, 'resource', None)
                
                # Check if this is the FIRST connection
                is_first = len(self._controllers) == 0
                
                new_ctrl = create_smu_from_string(
                    smu_type_str=target_type,
                    address=address,
                    channel=channel,
                    mock=mock,
                    name=f"SMU_{channel}",
                    existing_resource=existing_res
                )
                
                # If adding second channel to known B2902, don't reset
                if not is_first and (smu_type == "keysight_b2902" or new_ctrl.get_smu_type() == "keysight_b2902"):
                     if hasattr(new_ctrl, 'reset_on_connect'):
                        new_ctrl.reset_on_connect = False
                
                new_ctrl.connect()
                
                if new_ctrl.state == InstrumentState.ERROR:
                    return {"success": False, "message": "Connection resulted in ERROR state"}
                
                self._controllers[channel] = new_ctrl
                self._active_channel = channel # Set as active
                
                self._status.connected = True
                self._status.mock = mock
                self._status.channel = channel
                self._status.address = address
                self._status.smu_type = new_ctrl.get_smu_type() # Update with resolved type
                self._status.state = new_ctrl.state.value
                
                logger.info(f"SMU connected: type={self._status.smu_type}, address={address}, ch={channel}, mock={mock}")
                
                return {
                    "success": True, 
                    "message": f"Connected to {new_ctrl.__class__.__name__}",
                    "address": address, "channel": channel, "smu_type": self._status.smu_type, "mock": mock
                }
                
            except Exception as e:
                logger.error(f"SMU connection failed: {e}")
                if len(self._controllers) == 0:
                    self._status.connected = False
                return {"success": False, "message": str(e)}
    
    def disconnect(self) -> Dict[str, Any]:
        """Safely disconnect from SMU."""
        with self._op_lock:
            if not self._controllers:
                return {"success": True, "message": "Not connected"}
            
            for ch, ctrl in self._controllers.items():
                try:
                    ctrl.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting Ch {ch}: {e}")
            
            self._controllers.clear()
            self._active_channel = 1
            self._status = SMUStatus()
            
            logger.info("SMU disconnected")
            return {"success": True, "message": "Disconnected"}
    
    def configure(
        self, 
        compliance: float, 
        compliance_type: str = "CURR",
        nplc: float = 1.0,
        channel: int = None
    ) -> Dict[str, Any]:
        """
        Configure SMU compliance and measurement speed.
        """
        try:
            ctrl = self._get_controller(channel)
        except Exception as e:
            return {"success": False, "message": str(e)}
        
        with self._op_lock:
            try:
                ctrl.set_compliance(compliance, compliance_type)
                ctrl.set_nplc(nplc)
                
                # Update status if this is active channel
                if channel is None or channel == self._active_channel:
                    self._status.compliance = compliance
                    self._status.compliance_type = compliance_type
                
                logger.info(f"SMU Ch {ctrl.channel} configured: {compliance_type} compliance={compliance}, NPLC={nplc}")
                
                return {
                    "success": True,
                    "compliance": compliance,
                    "compliance_type": compliance_type,
                    "nplc": nplc,
                    "channel": ctrl.channel
                }
            except Exception as e:
                logger.error(f"Configure error: {e}")
                return {"success": False, "message": str(e)}
    
    def set_source_mode(self, mode: str, channel: int = None) -> Dict[str, Any]:
        """Set source mode (VOLT or CURR)."""
        try:
            ctrl = self._get_controller(channel)
        except Exception as e:
            return {"success": False, "message": str(e)}
        
        with self._op_lock:
            try:
                ctrl.set_source_mode(mode)
                if channel is None or channel == self._active_channel:
                    self._status.source_mode = mode
                logger.info(f"Source mode set to {mode} on Ch {ctrl.channel}")
                return {"success": True, "mode": mode, "channel": ctrl.channel}
            except Exception as e:
                logger.error(f"Set source mode error: {e}")
                return {"success": False, "message": str(e)}
    
    def set_value(self, value: float, channel: int = None) -> Dict[str, Any]:
        """Set source value (voltage or current depending on mode)."""
        try:
            ctrl = self._get_controller(channel)
        except Exception as e:
            return {"success": False, "message": str(e)}
        
        with self._op_lock:
            try:
                # We need to know the mode. Currently BaseSMU tracks it in _source_mode
                # But let's assume VOLT if unclear? No, better check status.
                # Actually BaseSMU has _source_mode attribute.
                mode = getattr(ctrl, '_source_mode', 'VOLT')
                
                if mode == "VOLT":
                    ctrl.set_voltage(value)
                else:
                    ctrl.set_current(value)
                logger.debug(f"Set {mode} value on Ch {ctrl.channel}: {value}")
                return {"success": True, "value": value, "mode": mode, "channel": ctrl.channel}
            except Exception as e:
                logger.error(f"Set value error: {e}")
                return {"success": False, "message": str(e)}
    
    def output_control(self, enabled: bool, channel: int = None) -> Dict[str, Any]:
        """Enable or disable SMU output."""
        try:
            ctrl = self._get_controller(channel)
        except Exception as e:
            return {"success": False, "message": str(e)}
        
        with self._op_lock:
            try:
                if enabled:
                    ctrl.enable_output()
                else:
                    ctrl.disable_output()
                
                if channel is None or channel == self._active_channel:
                    self._status.output_enabled = enabled
                logger.info(f"Output {'enabled' if enabled else 'disabled'} on Ch {ctrl.channel}")
                return {"success": True, "output_enabled": enabled, "channel": ctrl.channel}
            except Exception as e:
                logger.error(f"Output control error: {e}")
                return {"success": False, "message": str(e)}
    
    def measure(self, channel: int = None) -> Dict[str, Any]:
        """Perform a single measurement."""
        try:
            ctrl = self._get_controller(channel)
        except Exception as e:
            return {"success": False, "message": str(e)}
        
        with self._op_lock:
            try:
                data = ctrl.measure()
                return {
                    "success": True,
                    "voltage": data["voltage"],
                    "current": data["current"],
                    "channel": ctrl.channel
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
        scale: str = "linear",
        direction: str = "forward",
        sweep_type: str = "single",
        source_mode: str = "VOLT",
        keep_output_on: bool = False,
        channel: int = None
    ) -> Dict[str, Any]:
        """
        Execute IV sweep.
        
        Args:
            start: Start voltage
            stop: Stop voltage
            points: Number of points
            compliance: Current compliance (A)
            delay: Delay between points (s)
            sweep_type: "single" or "double"
            scale: "linear" or "log"
            direction: "forward" or "backward"
            source_mode: "VOLT" (currently only supporting voltage sweeps)
            keep_output_on: If True, leave output enabled after sweep
        """
        if not self._status.connected:
            return {"success": False, "message": "Not connected"}
        
        try:
            ctrl = self._get_controller(channel)
        except Exception as e:
            return {"success": False, "message": str(e)}
        
        # Point generation logic
        
        # Automatically move to RUNNING if IDLE or ARMED to clear abort flag and start duration
        auto_started = False
        if run_manager.state in [RunState.ABORTED, RunState.ERROR]:
            run_manager.reset()
        if run_manager.state == RunState.IDLE:
            run_manager.arm()
        if run_manager.state == RunState.ARMED:
            run_manager.start()
            auto_started = True
            
        with self._op_lock:
            try:
                # 1. Handle Direction
                s_val = start if direction == "forward" else stop
                e_val = stop if direction == "forward" else start
                
                # 2. Generate Base Points
                if scale.lower() == "log":
                    # Avoid log(0)
                    s_log = s_val if s_val != 0 else (1e-6 if e_val > 0 else -1e-6)
                    e_log = e_val if e_val != 0 else (1e-6 if s_val > 0 else -1e-6)
                    
                    # Handle sign
                    points_arr = np.logspace(
                        np.log10(abs(s_log)), 
                        np.log10(abs(e_log)), 
                        steps
                    )
                    if s_log < 0 or (s_log == 0 and e_log < 0):
                        points_arr = -points_arr
                else:
                    points_arr = np.linspace(s_val, e_val, steps)
                
                # 3. Ensure precise peak/endpoint
                if len(points_arr) > 0:
                    points_arr[-1] = e_val
                
                # 4. Handle Sweep Type (Double)
                if sweep_type.lower() == "double":
                    # Concatenate the first sweep with its reverse (excluding the last point to avoid duplication)
                    points_arr = np.concatenate([points_arr, points_arr[::-1][1:]])
                    # Ensure start value is reached exactly at the end of the return trip
                    points_arr[-1] = s_val
                
                points_list = points_arr.tolist()
                results = []
                
                # Configure
                ctrl.set_source_mode("VOLT")
                ctrl.set_compliance(compliance, "CURR")
                
                # Only enable output if not already enabled (to support keep_output_on loops)
                if not getattr(ctrl, "_output_enabled", False):
                    ctrl.enable_output()
                
                logger.info(f"Starting {scale} {sweep_type} sweep ({direction}) on Ch {ctrl.channel}: {s_val}V to {e_val}V, {len(points_list)} points")
                
                for i, v in enumerate(points_list):
                    if run_manager.is_abort_requested():
                        logger.warning("IV sweep aborted by user")
                        break
                    
                    ctrl.set_voltage(v)
                    run_manager.sleep(delay)
                    meas = ctrl.measure()
                    meas["set_voltage"] = v
                    results.append(meas)
                
                if not keep_output_on or run_manager.is_abort_requested():
                    ctrl.disable_output()
                
                logger.info(f"IV sweep complete: {len(results)} points collected")
                
                return {
                    "success": True,
                    "results": results,
                    "points": len(results),
                    "aborted": run_manager.is_abort_requested(),
                    "channel": ctrl.channel
                }
                
            except Exception as e:
                logger.error(f"IV sweep error: {e}")
                # Safety: try to disable output
                try:
                    ctrl.disable_output()
                except:
                    pass
                return {"success": False, "message": str(e)}
            finally:
                # Automatically return to IDLE if we were the ones who started it
                if auto_started:
                    run_manager.complete()


    def run_list_sweep(
        self,
        points: List[float],
        source_mode: str = "VOLT",
        compliance: float = 0.1,
        nplc: float = 1.0,
        delay: float = 0.1,
        channel: int = None
    ) -> Dict[str, Any]:
        """
        Execute a sweep across an arbitrary list of points.
        """
        if not self._status.connected:
            return {"success": False, "message": "Not connected"}
        
        try:
            ctrl = self._get_controller(channel)
        except Exception as e:
            return {"success": False, "message": str(e)}
        
        # Automatically move to RUNNING if IDLE or ARMED to clear abort flag and start duration
        auto_started = False
        if run_manager.state in [RunState.ABORTED, RunState.ERROR]:
            run_manager.reset()
        if run_manager.state == RunState.IDLE:
            run_manager.arm()
        if run_manager.state == RunState.ARMED:
            run_manager.start()
            auto_started = True
            
        with self._op_lock:
            try:
                results = []
                
                # Configure
                ctrl.set_source_mode(source_mode)
                comp_type = "CURR" if source_mode == "VOLT" else "VOLT"
                ctrl.set_compliance(compliance, comp_type)
                ctrl.set_nplc(nplc)
                ctrl.enable_output()
                
                logger.info(f"Starting List Sweep on Ch {ctrl.channel}: {len(points)} points, mode={source_mode}")
                
                for i, v in enumerate(points):
                    if run_manager.is_abort_requested():
                        logger.warning("List sweep aborted by user")
                        break
                    
                    if source_mode == "VOLT":
                        ctrl.set_voltage(v)
                    else:
                        ctrl.set_current(v)
                        
                    run_manager.sleep(delay)
                    meas = ctrl.measure()
                    meas["set_value"] = v
                    results.append(meas)
                
                ctrl.disable_output()
                
                logger.info(f"List sweep complete: {len(results)} points collected")
                
                return {
                    "success": True,
                    "results": results,
                    "points": len(results),
                    "aborted": run_manager.is_abort_requested(),
                    "channel": ctrl.channel
                }
                
            except Exception as e:
                logger.error(f"List sweep error: {e}")
                # Safety: try to disable output
                try:
                    ctrl.disable_output()
                except:
                    pass
                return {"success": False, "message": str(e)}
            finally:
                # Automatically return to IDLE if we were the ones who started it
                if auto_started:
                    run_manager.complete()


# Global singleton instance
smu_client = SMUClient()
