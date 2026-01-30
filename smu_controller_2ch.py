"""
SMU Controller for Keysight B2902A/B2912A Dual-Channel SMUs.

Uses the correct B2900 series SCPI syntax:
- Write commands: Channel in path (e.g., SOUR1:VOLT, OUTP1, SENS2:CURR:PROT)
- Query commands: Channel as suffix (e.g., MEAS:VOLT? (@1), OUTP1?)
"""
from typing import Optional, Dict, Any
import time
from base_controller import BaseInstrumentController, InstrumentState

try:
    import pyvisa
except ImportError:
    pyvisa = None


class SMUController2CH(BaseInstrumentController):
    """
    Controller for Keysight B2902A/B2912A dual-channel SMUs.
    
    This controller uses the correct SCPI channel addressing:
    - Source commands use SOURn: prefix (e.g., SOUR1:VOLT, SOUR2:FUNC:MODE)
    - Output commands use OUTPn (e.g., OUTP1 ON, OUTP2 OFF)
    - Sense commands use SENSn: prefix (e.g., SENS1:CURR:PROT)
    - Query commands use (@n) suffix (e.g., MEAS:VOLT? (@1))
    
    Attributes:
        address (str): VISA resource address (e.g., 'USB0::0x0957::...::INSTR').
        channel (int): Channel number (1 or 2).
        resource (pyvisa.resources.MessageBasedResource): The VISA resource object.
    """

    def __init__(self, address: str, name: str = "SMU", mock: bool = False, channel: int = 1):
        super().__init__(name, mock)
        self.address = address
        self.resource = None
        self.rm = None
        
        # Channel support (1 or 2 for dual-channel SMUs)
        if channel not in [1, 2]:
            raise ValueError(f"Invalid channel: {channel}. Must be 1 or 2.")
        self.channel = channel
        
        # B2900 series channel addressing formats
        self._ch_num = str(channel)  # For path-based commands (SOUR1:, OUTP1)
        self._ch_suffix = f"(@{channel})"  # For queries (MEAS:VOLT? (@1))
        
        # Cache for current settings
        self._current_source_amps = 0.0
        self._voltage_limit_volts = 2.0
        self._output_enabled = False
        self._source_mode = "VOLT"  # Track current source mode
        
        # Software Safety Limit
        self.software_current_limit = None

    # -------------------------------------------------------------------------
    # SCPI Command Formatters
    # -------------------------------------------------------------------------
    
    def _sour(self, subcmd: str) -> str:
        """Format SOUR subsystem command with channel in path.
        
        Example: _sour("VOLT 1.0") -> "SOUR1:VOLT 1.0"
        """
        return f"SOUR{self._ch_num}:{subcmd}"
    
    def _sens(self, subcmd: str) -> str:
        """Format SENS subsystem command with channel in path.
        
        Example: _sens("CURR:PROT 0.01") -> "SENS1:CURR:PROT 0.01"
        """
        return f"SENS{self._ch_num}:{subcmd}"
    
    def _outp(self, state: str) -> str:
        """Format OUTP command with channel number.
        
        Example: _outp("ON") -> "OUTP1 ON"
        """
        return f"OUTP{self._ch_num} {state}"
    
    def _outp_query(self) -> str:
        """Format OUTP? query for this channel."""
        return f"OUTP{self._ch_num}?"
    
    def _meas_query(self, meas_type: str) -> str:
        """Format measurement query with channel suffix.
        
        Example: _meas_query("VOLT") -> "MEAS:VOLT? (@1)"
        """
        return f"MEAS:{meas_type}? {self._ch_suffix}"
    
    def _init_cmd(self) -> str:
        """Format INIT command for this channel."""
        return f"INIT {self._ch_suffix}"
    
    def _trig(self, subcmd: str) -> str:
        """Format TRIG subsystem command with channel suffix."""
        return f"TRIG:{subcmd} {self._ch_suffix}"
    
    def _arm(self, subcmd: str) -> str:
        """Format ARM subsystem command with channel suffix."""
        return f"ARM:{subcmd} {self._ch_suffix}"

    # -------------------------------------------------------------------------
    # Safety
    # -------------------------------------------------------------------------

    def set_software_current_limit(self, limit: float = None):
        """
        Sets a software-level high-water mark for Current Source.
        Any attempt to set a current higher than this (abs) will raise ValueError.
        Set to None to disable.
        """
        self.software_current_limit = abs(limit) if limit is not None else None
        if self.software_current_limit is not None:
            self.logger.info(f"SAFETY: Software Current Limit set to {self.software_current_limit:.2e} A")
        else:
            self.logger.info("SAFETY: Software Current Limit DISABLED")

    def _check_current_limit(self, amps: float):
        """Internal helper to verify current against software limit."""
        if self.software_current_limit is not None:
            if abs(amps) > self.software_current_limit * 1.001:
                raise ValueError(f"SAFETY INTERLOCK: Requested {amps:.2e} A exceeds Software Limit {self.software_current_limit:.2e} A")

    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------

    def connect(self) -> None:
        """Connects to the SMU via PyVISA or mocks the connection."""
        if self.mock:
            self.logger.info(f"MOCK: Connected to SMU at {self.address} (Channel {self.channel})")
            self.to_state(InstrumentState.IDLE)
            return

        if pyvisa is None:
            self.handle_error("PyVISA not installed, cannot connect to real hardware.")
            return

        try:
            self.rm = pyvisa.ResourceManager()
            self.resource = self.rm.open_resource(self.address, open_timeout=20000)
            self.resource.timeout = 20000

            try:
                self.resource.clear()
            except:
                pass

            # Verify connection
            try:
                idn = self.resource.query("*IDN?")
            except Exception as e:
                self.logger.warning(f"IDN query failed ({e}), retrying after clear...")
                self.resource.clear()
                time.sleep(0.5)
                idn = self.resource.query("*IDN?")

            self.logger.info(f"Connected to SMU: {idn.strip()}")
            
            # Verify this is a dual-channel SMU
            if "B2901" in idn or "B2911" in idn:
                self.handle_error(f"Single-channel SMU detected. Use SMUController instead of SMUController2CH.")
                return
            elif "B2902" in idn or "B2912" in idn:
                self.logger.info(f"Dual-channel SMU detected, using channel {self.channel}")
            else:
                self.logger.warning(f"Unknown SMU model: {idn.strip()}. Assuming dual-channel support.")

            # Reset to known state
            self.resource.write("*RST")
            time.sleep(0.1)
            
            # Set default mode to voltage source
            self.resource.write(self._sour("FUNC:MODE VOLT"))
            self._source_mode = "VOLT"
            
            self.to_state(InstrumentState.IDLE)

        except Exception as e:
            msg = str(e)
            if "VI_ERROR_NCIC" in msg:
                self.handle_error(f"SMU Locked (NCIC). Please Power-Cycle Instrument. Details: {msg}")
            else:
                self.handle_error(f"Failed to connect to SMU: {msg}")

    def disconnect(self) -> None:
        """Safely disables output and closes connection."""
        if self._state not in [InstrumentState.OFF, InstrumentState.ERROR]:
            try:
                self.disable_output()
            except:
                pass

        if self.resource:
            try:
                self.resource.close()
                self.logger.info("Closed SMU VISA resource.")
            except Exception as e:
                self.logger.warning(f"Error closing resource: {e}")

        self.resource = None
        if self.rm:
            try:
                self.rm.close()
            except:
                pass
            self.rm = None

        self.to_state(InstrumentState.OFF)

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    def configure(self, settings: Dict[str, Any]) -> None:
        """
        Configures source settings.
        
        Expected keys:
            - compliance_voltage (float): Voltage limit in Volts (for current source mode).
            - compliance_current (float): Current limit in Amps (for voltage source mode).
        """
        self.require_state([InstrumentState.IDLE, InstrumentState.CONFIGURED, InstrumentState.ARMED, InstrumentState.RUNNING])
        
        compliance_v = settings.get("compliance_voltage")
        compliance_i = settings.get("compliance_current")
        
        if self.mock:
            self.logger.info(f"MOCK: Configured SMU. V_comp={compliance_v}, I_comp={compliance_i}")
            if compliance_v:
                self._voltage_limit_volts = compliance_v
            self.to_state(InstrumentState.CONFIGURED)
            return

        try:
            if compliance_v is not None:
                self.set_compliance(compliance_v, "VOLT")
            if compliance_i is not None:
                self.set_compliance(compliance_i, "CURR")
            self.to_state(InstrumentState.CONFIGURED)
        except Exception as e:
            self.handle_error(f"Configuration failed: {e}")

    def set_compliance(self, limit: float, limit_type: str) -> None:
        """
        Sets compliance limit.
        
        Args:
            limit: Value of limit
            limit_type: 'VOLT' or 'CURR'
        """
        self.require_state([InstrumentState.IDLE, InstrumentState.CONFIGURED, InstrumentState.ARMED, InstrumentState.RUNNING])
        limit_type = limit_type.upper()
        if limit_type not in ['VOLT', 'CURR']:
            raise ValueError("Limit type must be VOLT or CURR")

        if self.mock:
            self.logger.info(f"MOCK: Set {limit_type} Compliance to {limit}")
            if limit_type == 'VOLT':
                self._voltage_limit_volts = limit
            return

        try:
            # B2900 uses SENSn:CURR:PROT or SENSn:VOLT:PROT
            self.resource.write(self._sens(f"{limit_type}:PROT {limit}"))
        except Exception as e:
            self.handle_error(f"Failed to set compliance: {e}")

    def set_nplc(self, nplc: float) -> None:
        """
        Sets measurement speed in Number of Power Line Cycles (NPLC).
        0.01 (Fast) to 100 (High Accuracy). Default is usually 1.0.
        """
        self.require_state([InstrumentState.IDLE, InstrumentState.CONFIGURED, InstrumentState.ARMED, InstrumentState.RUNNING])

        if self.mock:
            self.logger.info(f"MOCK: Set NPLC to {nplc}")
            return

        try:
            self.resource.write(self._sens(f"VOLT:NPLC {nplc}"))
            self.resource.write(self._sens(f"CURR:NPLC {nplc}"))
        except Exception as e:
            self.handle_error(f"Failed to set NPLC: {e}")

    # -------------------------------------------------------------------------
    # Source Control
    # -------------------------------------------------------------------------

    def set_source_mode(self, mode: str) -> None:
        """
        Sets the source mode: 'VOLT' or 'CURR'.
        """
        self.require_state([InstrumentState.IDLE, InstrumentState.CONFIGURED, InstrumentState.ARMED, InstrumentState.RUNNING])

        mode = mode.upper()
        if mode not in ['VOLT', 'CURR']:
            raise ValueError(f"Invalid mode: {mode}. Must be 'VOLT' or 'CURR'.")

        if self.mock:
            self.logger.info(f"MOCK: Set Source Mode to {mode}")
            self._source_mode = mode
            return

        try:
            self.resource.write(self._sour(f"FUNC:MODE {mode}"))
            self._source_mode = mode
            self.logger.info(f"Set Source Mode to {mode} (Channel {self.channel})")
        except Exception as e:
            self.handle_error(f"Failed to set source mode: {e}")

    def set_voltage(self, volts: float) -> None:
        """Sets the DC source voltage immediately."""
        self.require_state([InstrumentState.IDLE, InstrumentState.CONFIGURED, InstrumentState.ARMED, InstrumentState.RUNNING])

        if self.mock:
            self.logger.info(f"MOCK: Setting voltage to {volts} V")
            self._last_set_v = volts
            self._last_set_i = volts / 1000.0 if volts > 0 else 1e-11
            return

        try:
            self.resource.write(self._sour(f"VOLT {volts}"))
            self._last_set_v = volts
        except Exception as e:
            self.handle_error(f"Failed to set voltage: {e}")

    def set_current(self, amps: float) -> None:
        """Sets the DC source current immediately."""
        self.require_state([InstrumentState.IDLE, InstrumentState.CONFIGURED, InstrumentState.ARMED, InstrumentState.RUNNING, InstrumentState.ERROR])

        if self.mock:
            self._check_current_limit(amps)
            self.logger.info(f"MOCK: Set Current {amps} A")
            self._current_source_amps = amps
            self._last_set_i = amps
            self._last_set_v = amps * 100.0
            return

        try:
            self._check_current_limit(amps)
            self.resource.write(self._sour("FUNC:MODE CURR"))
            self.resource.write(self._sour(f"CURR {amps}"))
            self._current_source_amps = amps
            self._source_mode = "CURR"
            if self.state == InstrumentState.ERROR:
                self.to_state(InstrumentState.IDLE)
        except Exception as e:
            self.handle_error(f"Failed to set current: {e}")

    # -------------------------------------------------------------------------
    # Output Control
    # -------------------------------------------------------------------------

    def enable_output(self) -> None:
        """Turns the SMU output ON for this channel."""
        self.require_state([InstrumentState.CONFIGURED, InstrumentState.ARMED, InstrumentState.IDLE, InstrumentState.ERROR])

        if self.mock:
            self.logger.info("MOCK: Output ENABLED")
            self._output_enabled = True
            self.to_state(InstrumentState.RUNNING)
            return

        try:
            self.resource.write(self._outp("ON"))
            self._output_enabled = True
            
            # Verify output is on
            resp = self.resource.query(self._outp_query()).strip()
            if "1" not in resp and "ON" not in resp.upper():
                self.logger.warning(f"SMU Channel {self.channel} did not report Output ON after command! Response: {resp}")
            
            self.to_state(InstrumentState.RUNNING)
        except Exception as e:
            self.handle_error(f"Failed to enable output: {e}")

    def disable_output(self) -> None:
        """Turns the SMU output OFF for this channel."""
        if self.mock:
            self.logger.info("MOCK: Output DISABLED")
            self._output_enabled = False
            self.to_state(InstrumentState.IDLE)
            return

        try:
            try:
                self.resource.write("ABOR")
            except:
                pass

            self.resource.write(self._outp("OFF"))
            self._output_enabled = False
            self.to_state(InstrumentState.IDLE)
        except Exception as e:
            if "VI_ERROR_TMO" in str(e) or "Timeout" in str(e):
                self.logger.critical("VISA Timeout during disable. Attempting Interface Clear.")
                try:
                    self.resource.clear()
                except:
                    pass
            self.handle_error(f"Failed to disable output: {e}")

    # -------------------------------------------------------------------------
    # Measurement
    # -------------------------------------------------------------------------

    def measure(self) -> Dict[str, float]:
        """
        Performs a spot measurement of Voltage and Current.
        
        Returns:
            dict: {'voltage': float, 'current': float}
        """
        self.require_state([InstrumentState.RUNNING, InstrumentState.ARMED, InstrumentState.CONFIGURED, InstrumentState.IDLE])

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
        """
        Configures a List Sweep (Arbitrary Waveform).
        
        Args:
            points: List of values (Volts or Amps).
            source_mode: 'VOLT' or 'CURR'.
            time_per_step: Duration of each point in seconds.
            trigger_count: Number of times to repeat the list.
        """
        self.require_state([InstrumentState.IDLE, InstrumentState.CONFIGURED, InstrumentState.RUNNING, InstrumentState.ERROR])

        source_mode = source_mode.upper()
        if source_mode not in ['VOLT', 'CURR']:
            raise ValueError("Mode must be VOLT or CURR")

        if len(points) == 0:
            raise ValueError("List points cannot be empty")

        if source_mode == 'CURR':
            for p in points:
                self._check_current_limit(p)

        points_str = ",".join([f"{x:.6e}" for x in points])

        if self.mock:
            self.logger.info(f"MOCK: Configured List Sweep ({source_mode}). Points={len(points)}, Step={time_per_step}s")
            self.to_state(InstrumentState.ARMED)
            return

        try:
            # Set function mode
            self.resource.write(self._sour(f"FUNC:MODE {source_mode}"))
            
            # Set to LIST mode
            self.resource.write(self._sour(f"{source_mode}:MODE LIST"))
            
            # Clear trace buffer
            self.resource.write("TRAC:CLE")
            
            # Upload points
            self.resource.write(self._sour(f"LIST:{source_mode} {points_str}"))
            
            # Timing config - Note: TRIG commands may need different format
            self.resource.write(f"TRIG:TRAN:SOUR TIM, {self._ch_suffix}")
            self.resource.write(f"TRIG:TRAN:TIM {time_per_step}, {self._ch_suffix}")
            self.resource.write(f"TRIG:TRAN:COUN {len(points)}, {self._ch_suffix}")
            self.resource.write(f"ARM:TRAN:COUN {trigger_count}, {self._ch_suffix}")

            self.to_state(InstrumentState.ARMED)
            self.logger.info("SMU Armed for List Sweep")

        except Exception as e:
            self.handle_error(f"Failed to setup list sweep: {e}")

    def trigger_list(self):
        """Starts the configured list sweep."""
        self.require_state([InstrumentState.ARMED, InstrumentState.RUNNING, InstrumentState.ERROR])

        if self.mock:
            self.logger.info("MOCK: Trigger List Sequence")
            self.to_state(InstrumentState.RUNNING)
            return

        try:
            self.resource.write("*WAI")
            self.resource.write(self._init_cmd())
            self.to_state(InstrumentState.RUNNING)
        except Exception as e:
            self.handle_error(f"Trigger failed: {e}")

    def generate_square_wave(self, high_level: float, low_level: float, period: float, duty_cycle: float, total_cycles: int, mode: str = "CURR"):
        """
        Generates a square wave using List Sweep.
        
        Args:
            high_level: Value during ON phase
            low_level: Value during OFF phase
            period: Total period in seconds
            duty_cycle: 0.0 to 1.0 (e.g. 0.5 = 50%)
            total_cycles: Number of full periods to generate
            mode: 'CURR' or 'VOLT'
        """
        if not (0 < duty_cycle < 1):
            raise ValueError("Duty cycle must be between 0 and 1")

        if mode == 'CURR':
            self._check_current_limit(high_level)
            self._check_current_limit(low_level)

        res = 50
        on_points = int(res * duty_cycle)
        off_points = res - on_points

        cycle_points = [high_level] * on_points + [low_level] * off_points
        dt = period / res

        self.logger.info(f"Generating Square Wave: {on_points} High / {off_points} Low steps. dt={dt*1000:.2f}ms")
        self.setup_list_sweep(cycle_points, mode, time_per_step=dt, trigger_count=total_cycles)

    def setup_pulse(self, high_amps: float, low_amps: float, pulse_width: float, period: float):
        """
        Configures a pulse train.
        """
        self.require_state([InstrumentState.IDLE, InstrumentState.CONFIGURED, InstrumentState.RUNNING])

        if self.mock:
            self.logger.info(f"MOCK: Configured Pulse. High={high_amps}, Low={low_amps}, Width={pulse_width}, Period={period}")
            return

        self.logger.warning("Real hardware pulse generation requires specific model implementation. Using DC fallback.")


# Alias for backward compatibility
SMUController = SMUController2CH
