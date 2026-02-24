"""
Keithley 2400 Series SMU Controller (Stub for Future Implementation).

This is a placeholder for Keithley 2400/2410/2420/2430/2440 SMUs.
The SCPI syntax differs from Keysight instruments.
"""
from typing import Dict, Any

from smu_base import BaseSMU, SMUState

try:
    import pyvisa
except ImportError:
    pyvisa = None


class Keithley2400Controller(BaseSMU):
    """
    Controller for Keithley 2400 series SMUs.
    
    Note: This is a stub implementation. Full support coming soon.
    
    Keithley 2400 SCPI differences from Keysight:
    - Uses :SOUR:FUNC VOLT or :SOUR:FUNC CURR (not SOUR:FUNC:MODE)
    - Uses :OUTP ON / :OUTP OFF
    - Single channel only
    """
    
    def __init__(
        self,
        address: str,
        channel: int = 1,
        mock: bool = False,
        name: str = "SMU",
        existing_resource=None,
        reset_on_connect: bool = True
    ):
        if channel != 1:
            raise ValueError("Keithley 2400 is single-channel. Only channel=1 is valid.")
        super().__init__(address, channel, mock, name)
        self.existing_resource = existing_resource
        self.resource = existing_resource
        self.rm = None
        self.software_current_limit = None
        self.reset_on_connect = reset_on_connect
        self._owns_resource = existing_resource is None
    
    @staticmethod
    def get_smu_type() -> str:
        return "keithley_2400"
    
    @staticmethod
    def get_smu_description() -> str:
        return "Keithley 2400/2410/2420/2430/2440 series"
    
    def _check_current_limit(self, amps: float):
        """Verify current against software limit."""
        if self.software_current_limit is not None:
            if abs(amps) > self.software_current_limit * 1.001:
                raise ValueError(f"SAFETY: Requested {amps:.2e} A exceeds limit {self.software_current_limit:.2e} A")
    
    def set_software_current_limit(self, limit: float = None):
        """Set software current limit for safety."""
        self.software_current_limit = abs(limit) if limit is not None else None
    
    # -------------------------------------------------------------------------
    # Connection
    # -------------------------------------------------------------------------
    
    def connect(self) -> None:
        """Connect to the Keithley 2400 SMU."""
        if self.mock:
            self.logger.info(f"MOCK: Connected to Keithley 2400 at {self.address}")
            self.to_state(SMUState.IDLE)
            return

        if self.existing_resource is not None:
            self.resource = self.existing_resource
            self.logger.info("Using SHARED resource for Keithley 2400")
            try:
                if self.reset_on_connect:
                    self.resource.write("*RST")
                self.resource.write(":SOUR:FUNC VOLT")
                self._source_mode = "VOLT"
                self.to_state(SMUState.IDLE)
                return
            except Exception as e:
                self.handle_error(f"Failed to init shared resource: {e}")
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
            
            idn = self.resource.query("*IDN?").strip()
            self.logger.info(f"Connected to: {idn}")
            
            # Reset
            self.resource.write("*RST")
            self.resource.write(":SOUR:FUNC VOLT")  # Keithley syntax
            self._source_mode = "VOLT"
            
            self.to_state(SMUState.IDLE)
            
        except Exception as e:
            self.handle_error(f"Failed to connect: {e}")
    
    def disconnect(self) -> None:
        """Disconnect from the SMU."""
        if self._state not in [SMUState.OFF, SMUState.ERROR]:
            try:
                self.disable_output()
            except:
                pass
        
        if self.resource and self._owns_resource:
            try:
                self.resource.close()
            except:
                pass
        
        self.resource = None
        if self.rm and self._owns_resource:
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
        """Set source mode."""
        self.require_state([SMUState.IDLE, SMUState.CONFIGURED, SMUState.ARMED, SMUState.RUNNING])
        
        mode = mode.upper()
        if mode not in ['VOLT', 'CURR']:
            raise ValueError(f"Invalid mode: {mode}")
        
        if self.mock:
            self._source_mode = mode
            return
        
        try:
            # Keithley uses :SOUR:FUNC not :SOUR:FUNC:MODE
            self.resource.write(f":SOUR:FUNC {mode}")
            self._source_mode = mode
        except Exception as e:
            self.handle_error(f"Failed to set mode: {e}")
    
    def set_voltage(self, volts: float) -> None:
        """Set source voltage."""
        self.require_state([SMUState.IDLE, SMUState.CONFIGURED, SMUState.ARMED, SMUState.RUNNING])
        
        if self.mock:
            self._last_set_v = volts
            self._last_set_i = volts / 1000.0 if volts > 0 else 1e-11
            return
        
        try:
            self.resource.write(f":SOUR:VOLT {volts}")
            self._last_set_v = volts
        except Exception as e:
            self.handle_error(f"Failed to set voltage: {e}")
    
    def set_current(self, amps: float) -> None:
        """Set source current."""
        self.require_state([SMUState.IDLE, SMUState.CONFIGURED, SMUState.ARMED, SMUState.RUNNING, SMUState.ERROR])
        
        self._check_current_limit(amps)
        
        if self.mock:
            self._last_set_i = amps
            self._last_set_v = amps * 100
            return
        
        try:
            self.resource.write(":SOUR:FUNC CURR")
            self.resource.write(f":SOUR:CURR {amps}")
            self._source_mode = "CURR"
            self._last_set_i = amps
        except Exception as e:
            self.handle_error(f"Failed to set current: {e}")
    
    def set_compliance(self, limit: float, limit_type: str) -> None:
        """Set compliance limit."""
        self.require_state([SMUState.IDLE, SMUState.CONFIGURED, SMUState.ARMED, SMUState.RUNNING])
        
        limit_type = limit_type.upper()
        if limit_type not in ['VOLT', 'CURR']:
            raise ValueError("Limit type must be VOLT or CURR")
        
        if self.mock:
            return
        
        try:
            # Keithley uses :SENS:xxx:PROT
            self.resource.write(f":SENS:{limit_type}:PROT {limit}")
        except Exception as e:
            self.handle_error(f"Failed to set compliance: {e}")
    
    def set_nplc(self, nplc: float) -> None:
        """Set measurement NPLC."""
        self.require_state([SMUState.IDLE, SMUState.CONFIGURED, SMUState.ARMED, SMUState.RUNNING])
        
        if self.mock:
            return
        
        try:
            self.resource.write(f":SENS:VOLT:NPLC {nplc}")
            self.resource.write(f":SENS:CURR:NPLC {nplc}")
        except Exception as e:
            self.handle_error(f"Failed to set NPLC: {e}")
    
    # -------------------------------------------------------------------------
    # Output Control
    # -------------------------------------------------------------------------
    
    def enable_output(self) -> None:
        """Enable SMU output."""
        self.require_state([SMUState.CONFIGURED, SMUState.ARMED, SMUState.IDLE, SMUState.ERROR])
        
        if self.mock:
            self._output_enabled = True
            self.to_state(SMUState.RUNNING)
            return
        
        try:
            self.resource.write(":OUTP ON")
            self._output_enabled = True
            self.to_state(SMUState.RUNNING)
        except Exception as e:
            self.handle_error(f"Failed to enable output: {e}")
    
    def disable_output(self) -> None:
        """Disable SMU output."""
        if self.mock:
            self._output_enabled = False
            self.to_state(SMUState.IDLE)
            return
        
        try:
            self.resource.write(":OUTP OFF")
            self._output_enabled = False
            self.to_state(SMUState.IDLE)
        except Exception as e:
            self.handle_error(f"Failed to disable output: {e}")
    
    # -------------------------------------------------------------------------
    # Measurement
    # -------------------------------------------------------------------------
    
    def measure(self) -> Dict[str, float]:
        """Perform spot measurement."""
        self.require_state([SMUState.RUNNING, SMUState.ARMED, SMUState.CONFIGURED, SMUState.IDLE])
        
        if self.mock:
            import random
            v_meas = getattr(self, '_last_set_v', 0.0)
            i_meas = getattr(self, '_last_set_i', 0.0) + random.gauss(0, 1e-10)
            return {'voltage': v_meas, 'current': i_meas}
        
        try:
            # Keithley 2400 returns comma-separated values
            # Format depends on :FORM:ELEM setting
            self.resource.write(":FORM:ELEM VOLT,CURR")
            resp = self.resource.query(":READ?").strip()
            parts = resp.split(",")
            
            v = float(parts[0]) if len(parts) > 0 else 1e38
            i = float(parts[1]) if len(parts) > 1 else 1e38
            
            # Handle overload/error values (e.g., 10E37) as None/null
            return {
                'voltage': v if abs(v) < 1e37 else None,
                'current': i if abs(i) < 1e37 else None
            }
        except Exception as e:
            self.handle_error(f"Measurement failed: {e}")
            return {'voltage': None, 'current': None}
