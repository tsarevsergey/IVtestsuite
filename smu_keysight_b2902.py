"""
Keysight B2902A/B2912A Dual-Channel SMU Controller.

Uses B2900 series dual-channel SCPI syntax:
- Write commands: Channel in path (SOUR1:VOLT, OUTP1 ON, SENS2:CURR:PROT)
- Query commands: Channel suffix (MEAS:VOLT? (@1), OUTP1?)
"""
from typing import Dict, Any
import time

from smu_base import BaseSMU, SMUState

try:
    import pyvisa
except ImportError:
    pyvisa = None


class KeysightB2902Controller(BaseSMU):
    """
    Controller for Keysight B2902A/B2912A dual-channel SMUs.
    
    Uses B2900 series channel-indexed SCPI syntax:
    - SOUR1:VOLT, SOUR2:FUNC:MODE, OUTP1 ON, SENS2:CURR:PROT
    - MEAS:VOLT? (@1), OUTP1?
    """
    
    def __init__(self, address: str, channel: int = 1, mock: bool = False, name: str = "SMU", existing_resource=None):
        if channel not in [1, 2]:
            raise ValueError(f"Invalid channel: {channel}. Must be 1 or 2.")
        super().__init__(address, channel, mock, name)
        
        # Resource sharing
        self.existing_resource = existing_resource
        self.resource = existing_resource
        
        self.rm = None
        self.software_current_limit = None
        self.reset_on_connect = True  # Default to resetting state
        
        # Channel formatting
        self._ch_num = str(channel)
        self._ch_suffix = f"(@{channel})"
    
    @staticmethod
    def get_smu_type() -> str:
        return "keysight_b2902"
    
    @staticmethod
    def get_smu_description() -> str:
        return "Keysight B2902A/B2912A (Dual-channel)"
    
    # -------------------------------------------------------------------------
    # SCPI Formatters
    # -------------------------------------------------------------------------
    
    def _sour(self, subcmd: str) -> str:
        """Format SOUR command: SOUR1:VOLT 1.0"""
        return f"SOUR{self._ch_num}:{subcmd}"
    
    def _sens(self, subcmd: str) -> str:
        """Format SENS command: SENS1:CURR:PROT 0.01"""
        return f"SENS{self._ch_num}:{subcmd}"
    
    def _outp(self, state: str) -> str:
        """Format OUTP command: OUTP1 ON"""
        return f"OUTP{self._ch_num} {state}"
    
    def _outp_query(self) -> str:
        """Format OUTP query: OUTP1?"""
        return f"OUTP{self._ch_num}?"
    
    def _meas_query(self, meas_type: str) -> str:
        """Format MEAS query: MEAS:VOLT? (@1)"""
        return f"MEAS:{meas_type}? {self._ch_suffix}"
    
    def _init_cmd(self) -> str:
        """Format INIT command: INIT (@1)"""
        return f"INIT {self._ch_suffix}"
    
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
        """Connect to the B2902A SMU."""
        if self.mock:
            self.logger.info(f"MOCK: Connected to B2902A at {self.address} (Channel {self.channel})")
            self.to_state(SMUState.IDLE)
            return
        
        # If sharing resource, skip opening new one
        if self.existing_resource:
            self.resource = self.existing_resource
            self.logger.info(f"Using SHARED resource for Channel {self.channel}")
            # We skip IDN check assuming the primary holder verified it
            # We still need to configure initial state if requested
            
            # Reset logic (only if requested)
            if self.reset_on_connect:
                try:
                    self.resource.write("*RST")
                    time.sleep(0.1)
                except Exception as e:
                    self.logger.warning(f"Reset failed on shared resource: {e}")
            
            try:
                self.resource.write(self._sour("FUNC:MODE VOLT"))
                self._source_mode = "VOLT"
                self.to_state(SMUState.IDLE)
            except Exception as e:
                self.handle_error(f"Failed to init shared channel: {e}")
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
            
            # Verify this is a dual-channel SMU
            if "B2901" in idn or "B2911" in idn:
                self.logger.warning("Single-channel SMU detected. Consider using KeysightB2901Controller.")
                if self.channel != 1:
                    self.handle_error(f"Single-channel SMU detected. Channel {self.channel} not available.")
                    return
            
            # Reset to known state (only if requested)
            if self.reset_on_connect:
                self.resource.write("*RST")
                time.sleep(0.1)
                
            self.resource.write(self._sour("FUNC:MODE VOLT"))
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
            self.resource.write(self._sour(f"FUNC:MODE {mode}"))
            self._source_mode = mode
            self.logger.info(f"Set source mode to {mode} (Channel {self.channel})")
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
            self.resource.write(self._sour(f"VOLT {volts}"))
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
            self.resource.write(self._sour("FUNC:MODE CURR"))
            self.resource.write(self._sour(f"CURR {amps}"))
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
            self.resource.write(self._sens(f"{limit_type}:PROT {limit}"))
        except Exception as e:
            self.handle_error(f"Failed to set compliance: {e}")
    
    def set_nplc(self, nplc: float) -> None:
        """Set measurement NPLC."""
        self.require_state([SMUState.IDLE, SMUState.CONFIGURED, SMUState.ARMED, SMUState.RUNNING])
        
        if self.mock:
            self.logger.info(f"MOCK: Set NPLC to {nplc}")
            return
        
        try:
            self.resource.write(self._sens(f"VOLT:NPLC {nplc}"))
            self.resource.write(self._sens(f"CURR:NPLC {nplc}"))
        except Exception as e:
            self.handle_error(f"Failed to set NPLC: {e}")
    
    # -------------------------------------------------------------------------
    # Output Control
    # -------------------------------------------------------------------------
    
    def enable_output(self) -> None:
        """Enable SMU output for this channel."""
        self.require_state([SMUState.CONFIGURED, SMUState.ARMED, SMUState.IDLE, SMUState.ERROR])
        
        if self.mock:
            self.logger.info(f"MOCK: Output ENABLED (Channel {self.channel})")
            self._output_enabled = True
            self.to_state(SMUState.RUNNING)
            return
        
        try:
            self.resource.write(self._outp("ON"))
            self._output_enabled = True
            
            # Verify
            resp = self.resource.query(self._outp_query()).strip()
            if "1" not in resp and "ON" not in resp.upper():
                self.logger.warning(f"Channel {self.channel} did not confirm output ON. Response: {resp}")
            
            self.to_state(SMUState.RUNNING)
        except Exception as e:
            self.handle_error(f"Failed to enable output: {e}")
    
    def disable_output(self) -> None:
        """Disable SMU output for this channel."""
        if self.mock:
            self.logger.info(f"MOCK: Output DISABLED (Channel {self.channel})")
            self._output_enabled = False
            self.to_state(SMUState.IDLE)
            return
        
        try:
            try:
                self.resource.write("ABOR")
            except:
                pass
            
            self.resource.write(self._outp("OFF"))
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
        """Perform spot measurement on this channel."""
        self.require_state([SMUState.RUNNING, SMUState.ARMED, SMUState.CONFIGURED, SMUState.IDLE])
        
        if self.mock:
            import random
            # Simple physics simulation: V = I * R
            # We assume a fixed load resistance for mock consistency
            R_load = 1000.0 if self.channel == 1 else 5000.0 # Different loads for different channels
            
            mode = getattr(self, "_source_mode", "VOLT")
            
            if mode == "VOLT":
                v_set = getattr(self, '_last_set_v', 0.0)
                i_real = v_set / R_load
                
                v_meas = v_set + random.gauss(0, 1e-4) # Small noise
                i_meas = i_real + random.gauss(0, 1e-9)
            
            else: # CURR
                i_set = getattr(self, '_last_set_i', 0.0)
                v_real = i_set * R_load
                
                # Apply compliance if set (mocking compliance clamping)
                # This is tricky without storing compliance, but let's just do basic
                
                i_meas = i_set + random.gauss(0, 1e-10)
                v_meas = v_real + random.gauss(0, 1e-4)

            self.logger.info(f"MOCK Ch{self.channel}: Measured V={v_meas:.4f}, I={i_meas:.4e}")
            return {'voltage': v_meas, 'current': i_meas}
        
        try:
            v_str = self.resource.query(self._meas_query("VOLT")).strip()
            i_str = self.resource.query(self._meas_query("CURR")).strip()
            
            return {
                'voltage': float(v_str),
                'current': float(i_str)
            }
        except Exception as e:
            self.handle_error(f"Measurement failed: {e}")
            return {'voltage': 0.0, 'current': 0.0}
    
    # -------------------------------------------------------------------------
    # List Sweep
    # -------------------------------------------------------------------------
    
    def setup_list_sweep(self, points: list, source_mode: str, time_per_step: float, trigger_count: int = 1) -> None:
        """Configure list sweep for this channel."""
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
            self.logger.info(f"MOCK: List sweep configured: {len(points)} points (Channel {self.channel})")
            self.to_state(SMUState.ARMED)
            return
        
        try:
            self.resource.write(self._sour(f"FUNC:MODE {source_mode}"))
            self.resource.write(self._sour(f"{source_mode}:MODE LIST"))
            self.resource.write("TRAC:CLE")
            self.resource.write(self._sour(f"LIST:{source_mode} {points_str}"))
            
            # Trigger config uses channel suffix
            self.resource.write(f"TRIG:TRAN:SOUR TIM, {self._ch_suffix}")
            self.resource.write(f"TRIG:TRAN:TIM {time_per_step}, {self._ch_suffix}")
            self.resource.write(f"TRIG:TRAN:COUN {len(points)}, {self._ch_suffix}")
            self.resource.write(f"ARM:TRAN:COUN {trigger_count}, {self._ch_suffix}")
            
            self.to_state(SMUState.ARMED)
            self.logger.info(f"SMU Channel {self.channel} Armed for List Sweep")
        except Exception as e:
            self.handle_error(f"Failed to setup list sweep: {e}")
    
    def trigger_list(self) -> None:
        """Start list sweep for this channel."""
        self.require_state([SMUState.ARMED, SMUState.RUNNING, SMUState.ERROR])
        
        if self.mock:
            self.logger.info(f"MOCK: Trigger list (Channel {self.channel})")
            self.to_state(SMUState.RUNNING)
            return
        
        try:
            self.resource.write("*WAI")
            self.resource.write(self._init_cmd())
            self.to_state(SMUState.RUNNING)
        except Exception as e:
            self.handle_error(f"Trigger failed: {e}")


# Backward compatibility aliases
SMUController2CH = KeysightB2902Controller
SMUController = KeysightB2902Controller
