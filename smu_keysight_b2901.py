"""
Keysight B2901A/B2911A Single-Channel SMU Controller.

Uses standard SCPI syntax without channel suffixes:
- SOUR:VOLT, SOUR:CURR
- OUTP ON, OUTP OFF
- MEAS:VOLT?, MEAS:CURR?
"""
from typing import Dict, Any
import time

from smu_base import BaseSMU, SMUState

try:
    import pyvisa
except ImportError:
    pyvisa = None


class KeysightB2901Controller(BaseSMU):
    """
    Controller for Keysight B2901A/B2911A single-channel SMUs.
    
    Uses standard SCPI syntax without channel suffixes.
    """
    
    def __init__(self, address: str, channel: int = 1, mock: bool = False, name: str = "SMU"):
        if channel != 1:
            raise ValueError("B2901A is single-channel. Only channel=1 is valid.")
        super().__init__(address, channel, mock, name)
        self.resource = None
        self.rm = None
        self.software_current_limit = None
    
    @staticmethod
    def get_smu_type() -> str:
        return "keysight_b2901"
    
    @staticmethod
    def get_smu_description() -> str:
        return "Keysight B2901A/B2911A (Single-channel)"
    
    def _check_current_limit(self, amps: float):
        """Verify current against software limit."""
        if self.software_current_limit is not None:
            if abs(amps) > self.software_current_limit * 1.001:
                raise ValueError(f"SAFETY: Requested {amps:.2e} A exceeds limit {self.software_current_limit:.2e} A")
    
    def set_software_current_limit(self, limit: float = None):
        """Set software current limit for safety."""
        self.software_current_limit = abs(limit) if limit is not None else None
        if self.software_current_limit is not None:
            self.logger.info(f"SAFETY: Software Current Limit set to {self.software_current_limit:.2e} A")
    
    # -------------------------------------------------------------------------
    # Connection
    # -------------------------------------------------------------------------
    
    def connect(self) -> None:
        """Connect to the B2901A SMU."""
        if self.mock:
            self.logger.info(f"MOCK: Connected to B2901A at {self.address}")
            self.to_state(SMUState.IDLE)
            return
        
        if pyvisa is None:
            self.handle_error("PyVISA not installed")
            return
        
        try:
            self.rm = pyvisa.ResourceManager()
            self.resource = self.rm.open_resource(self.address, open_timeout=20000)
            self.resource.timeout = 20000
            
            try:
                self.resource.clear()
            except:
                pass
            
            try:
                idn = self.resource.query("*IDN?")
            except Exception as e:
                self.logger.warning(f"IDN query failed ({e}), retrying...")
                self.resource.clear()
                time.sleep(0.5)
                idn = self.resource.query("*IDN?")
            
            self.logger.info(f"Connected to: {idn.strip()}")
            
            # Verify this is a B2901
            if "B2902" in idn or "B2912" in idn:
                self.logger.warning("Dual-channel SMU detected. Consider using KeysightB2902Controller.")
            
            # Reset to known state
            self.resource.write("*RST")
            self.resource.write("SOUR:FUNC:MODE VOLT")
            self._source_mode = "VOLT"
            
            self.to_state(SMUState.IDLE)
            
        except Exception as e:
            msg = str(e)
            if "VI_ERROR_NCIC" in msg:
                self.handle_error(f"SMU Locked (NCIC). Please Power-Cycle Instrument.")
            else:
                self.handle_error(f"Failed to connect: {msg}")
    
    def disconnect(self) -> None:
        """Disconnect from the SMU."""
        if self._state not in [SMUState.OFF, SMUState.ERROR]:
            try:
                self.disable_output()
            except:
                pass
        
        if self.resource:
            try:
                self.resource.close()
                self.logger.info("Closed SMU connection.")
            except Exception as e:
                self.logger.warning(f"Error closing: {e}")
        
        self.resource = None
        if self.rm:
            try:
                self.rm.close()
            except:
                pass
            self.rm = None
        
        self.to_state(SMUState.OFF)
    
    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    
    def set_source_mode(self, mode: str) -> None:
        """Set source mode: 'VOLT' or 'CURR'."""
        self.require_state([SMUState.IDLE, SMUState.CONFIGURED, SMUState.ARMED, SMUState.RUNNING])
        
        mode = mode.upper()
        if mode not in ['VOLT', 'CURR']:
            raise ValueError(f"Invalid mode: {mode}")
        
        if self.mock:
            self.logger.info(f"MOCK: Set mode to {mode}")
            self._source_mode = mode
            return
        
        try:
            self.resource.write(f"SOUR:FUNC:MODE {mode}")
            self._source_mode = mode
            self.logger.info(f"Set source mode to {mode}")
        except Exception as e:
            self.handle_error(f"Failed to set mode: {e}")
    
    def set_voltage(self, volts: float) -> None:
        """Set source voltage."""
        self.require_state([SMUState.IDLE, SMUState.CONFIGURED, SMUState.ARMED, SMUState.RUNNING])
        
        if self.mock:
            self.logger.info(f"MOCK: Set voltage to {volts} V")
            self._last_set_v = volts
            self._last_set_i = volts / 1000.0 if volts > 0 else 1e-11
            return
        
        try:
            self.resource.write(f"SOUR:VOLT {volts}")
            self._last_set_v = volts
        except Exception as e:
            self.handle_error(f"Failed to set voltage: {e}")
    
    def set_current(self, amps: float) -> None:
        """Set source current."""
        self.require_state([SMUState.IDLE, SMUState.CONFIGURED, SMUState.ARMED, SMUState.RUNNING, SMUState.ERROR])
        
        self._check_current_limit(amps)
        
        if self.mock:
            self.logger.info(f"MOCK: Set current to {amps} A")
            self._last_set_i = amps
            self._last_set_v = amps * 100
            return
        
        try:
            self.resource.write("SOUR:FUNC:MODE CURR")
            self.resource.write(f"SOUR:CURR {amps}")
            self._source_mode = "CURR"
            self._last_set_i = amps
            if self._state == SMUState.ERROR:
                self.to_state(SMUState.IDLE)
        except Exception as e:
            self.handle_error(f"Failed to set current: {e}")
    
    def set_compliance(self, limit: float, limit_type: str) -> None:
        """Set compliance limit."""
        self.require_state([SMUState.IDLE, SMUState.CONFIGURED, SMUState.ARMED, SMUState.RUNNING])
        
        limit_type = limit_type.upper()
        if limit_type not in ['VOLT', 'CURR']:
            raise ValueError("Limit type must be VOLT or CURR")
        
        if self.mock:
            self.logger.info(f"MOCK: Set {limit_type} compliance to {limit}")
            return
        
        try:
            self.resource.write(f"SENS:{limit_type}:PROT {limit}")
        except Exception as e:
            self.handle_error(f"Failed to set compliance: {e}")
    
    def set_nplc(self, nplc: float) -> None:
        """Set measurement NPLC."""
        self.require_state([SMUState.IDLE, SMUState.CONFIGURED, SMUState.ARMED, SMUState.RUNNING])
        
        if self.mock:
            self.logger.info(f"MOCK: Set NPLC to {nplc}")
            return
        
        try:
            self.resource.write(f"SENS:VOLT:NPLC {nplc}")
            self.resource.write(f"SENS:CURR:NPLC {nplc}")
        except Exception as e:
            self.handle_error(f"Failed to set NPLC: {e}")
    
    # -------------------------------------------------------------------------
    # Output Control
    # -------------------------------------------------------------------------
    
    def enable_output(self) -> None:
        """Enable SMU output."""
        self.require_state([SMUState.CONFIGURED, SMUState.ARMED, SMUState.IDLE, SMUState.ERROR])
        
        if self.mock:
            self.logger.info("MOCK: Output ENABLED")
            self._output_enabled = True
            self.to_state(SMUState.RUNNING)
            return
        
        try:
            self.resource.write("OUTP ON")
            self._output_enabled = True
            
            # Verify
            resp = self.resource.query("OUTP?").strip()
            if "1" not in resp:
                self.logger.warning("SMU did not confirm output ON")
            
            self.to_state(SMUState.RUNNING)
        except Exception as e:
            self.handle_error(f"Failed to enable output: {e}")
    
    def disable_output(self) -> None:
        """Disable SMU output."""
        if self.mock:
            self.logger.info("MOCK: Output DISABLED")
            self._output_enabled = False
            self.to_state(SMUState.IDLE)
            return
        
        try:
            try:
                self.resource.write("ABOR")
            except:
                pass
            
            self.resource.write("OUTP OFF")
            self._output_enabled = False
            self.to_state(SMUState.IDLE)
        except Exception as e:
            if "Timeout" in str(e):
                try:
                    self.resource.clear()
                except:
                    pass
            self.handle_error(f"Failed to disable output: {e}")
    
    # -------------------------------------------------------------------------
    # Measurement
    # -------------------------------------------------------------------------
    
    def measure(self) -> Dict[str, float]:
        """Perform spot measurement."""
        self.require_state([SMUState.RUNNING, SMUState.ARMED, SMUState.CONFIGURED, SMUState.IDLE])
        
        if self.mock:
            import random
            noise = random.gauss(0, 1e-10)
            v_meas = getattr(self, '_last_set_v', 0.0)
            i_meas = getattr(self, '_last_set_i', 0.0) + noise
            
            if v_meas == 0.0 and i_meas == 0.0:
                v_meas = random.uniform(0, 0.1)
                i_meas = random.gauss(0, 1e-11)
            
            self.logger.info(f"MOCK: Measured V={v_meas:.4f}, I={i_meas:.4e}")
            return {'voltage': v_meas, 'current': i_meas}
        
        try:
            v_str = self.resource.query("MEAS:VOLT?").strip()
            i_str = self.resource.query("MEAS:CURR?").strip()
            
            v = float(v_str)
            i = float(i_str)
            
            # Handle overload/error values (e.g., 10E37) as None/null
            return {
                'voltage': v if abs(v) < 1e37 else None,
                'current': i if abs(i) < 1e37 else None
            }
        except Exception as e:
            self.handle_error(f"Measurement failed: {e}")
            return {'voltage': None, 'current': None}
    
    # -------------------------------------------------------------------------
    # List Sweep (Optional)
    # -------------------------------------------------------------------------
    
    def setup_list_sweep(self, points: list, source_mode: str, time_per_step: float, trigger_count: int = 1) -> None:
        """Configure list sweep."""
        self.require_state([SMUState.IDLE, SMUState.CONFIGURED, SMUState.RUNNING, SMUState.ERROR])
        
        source_mode = source_mode.upper()
        if source_mode not in ['VOLT', 'CURR']:
            raise ValueError("Mode must be VOLT or CURR")
        
        if len(points) == 0:
            raise ValueError("Points cannot be empty")
        
        if source_mode == 'CURR':
            for p in points:
                self._check_current_limit(p)
        
        points_str = ",".join([f"{x:.6e}" for x in points])
        
        if self.mock:
            self.logger.info(f"MOCK: List sweep configured: {len(points)} points")
            self.to_state(SMUState.ARMED)
            return
        
        try:
            self.resource.write(f"SOUR:FUNC:MODE {source_mode}")
            self.resource.write(f"SOUR:{source_mode}:MODE LIST")
            self.resource.write("TRAC:CLE")
            self.resource.write(f"SOUR:LIST:{source_mode} {points_str}")
            self.resource.write("TRIG:TRAN:SOUR TIM")
            self.resource.write(f"TRIG:TRAN:TIM {time_per_step}")
            self.resource.write(f"TRIG:TRAN:COUN {len(points)}")
            self.resource.write(f"ARM:TRAN:COUN {trigger_count}")
            
            self.to_state(SMUState.ARMED)
            self.logger.info("SMU Armed for List Sweep")
        except Exception as e:
            self.handle_error(f"Failed to setup list sweep: {e}")
    
    def trigger_list(self) -> None:
        """Start list sweep."""
        self.require_state([SMUState.ARMED, SMUState.RUNNING, SMUState.ERROR])
        
        if self.mock:
            self.logger.info("MOCK: Trigger list")
            self.to_state(SMUState.RUNNING)
            return
        
        try:
            self.resource.write("*WAI")
            self.resource.write("INIT")
            self.to_state(SMUState.RUNNING)
        except Exception as e:
            self.handle_error(f"Trigger failed: {e}")


# Backward compatibility alias
SMUController = KeysightB2901Controller
