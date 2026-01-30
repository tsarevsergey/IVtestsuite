"""
SMU Base Class - Abstract interface for all SMU controllers.

This module defines the common interface that all SMU drivers must implement,
enabling a unified API across different SMU manufacturers (Keysight, Keithley, etc.).
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum
import logging


class SMUState(Enum):
    """State machine states for SMU controllers."""
    OFF = "OFF"
    IDLE = "IDLE"
    CONFIGURED = "CONFIGURED"
    ARMED = "ARMED"
    RUNNING = "RUNNING"
    ERROR = "ERROR"


class BaseSMU(ABC):
    """
    Abstract base class for all SMU controllers.
    
    All SMU drivers (Keysight B2901, B2902, Keithley 2400, etc.) must inherit
    from this class and implement the abstract methods.
    
    Attributes:
        address (str): VISA resource address
        channel (int): Channel number (1 or 2 for dual-channel SMUs)
        mock (bool): If True, simulate hardware without actual connection
        state (SMUState): Current state of the SMU
    """
    
    def __init__(self, address: str, channel: int = 1, mock: bool = False, name: str = "SMU"):
        self.address = address
        self.channel = channel
        self.mock = mock
        self.name = name
        self._state = SMUState.OFF
        
        # Setup logging
        self.logger = logging.getLogger(f"instrument.{name}")
        
        # Common cached values
        self._output_enabled = False
        self._source_mode = "VOLT"
        self._last_set_v = 0.0
        self._last_set_i = 0.0
    
    @property
    def state(self) -> SMUState:
        """Get current SMU state."""
        return self._state
    
    def to_state(self, new_state: SMUState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self.logger.info(f"State transition: {old_state.value} -> {new_state.value}")
    
    def require_state(self, allowed_states: list) -> None:
        """Verify the SMU is in one of the allowed states."""
        if self._state not in allowed_states:
            state_names = [s.value for s in allowed_states]
            raise RuntimeError(f"Operation not allowed in state {self._state.value}. Required: {state_names}")
    
    def handle_error(self, message: str) -> None:
        """Handle an error condition."""
        self.logger.error(message)
        self._state = SMUState.ERROR
        raise RuntimeError(message)
    
    # -------------------------------------------------------------------------
    # Abstract Methods - Must be implemented by all drivers
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def connect(self) -> None:
        """
        Connect to the SMU hardware.
        
        After successful connection, state should be IDLE.
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """
        Safely disconnect from the SMU.
        
        Should disable output before disconnecting.
        After disconnection, state should be OFF.
        """
        pass
    
    @abstractmethod
    def set_source_mode(self, mode: str) -> None:
        """
        Set the source mode.
        
        Args:
            mode: 'VOLT' for voltage source, 'CURR' for current source
        """
        pass
    
    @abstractmethod
    def set_voltage(self, volts: float) -> None:
        """
        Set the source voltage.
        
        Args:
            volts: Voltage in Volts
        """
        pass
    
    @abstractmethod
    def set_current(self, amps: float) -> None:
        """
        Set the source current.
        
        Args:
            amps: Current in Amps
        """
        pass
    
    @abstractmethod
    def set_compliance(self, limit: float, limit_type: str) -> None:
        """
        Set compliance limit.
        
        Args:
            limit: Compliance value
            limit_type: 'VOLT' or 'CURR'
        """
        pass
    
    @abstractmethod
    def set_nplc(self, nplc: float) -> None:
        """
        Set measurement integration time in power line cycles.
        
        Args:
            nplc: Number of power line cycles (0.01 to 100)
        """
        pass
    
    @abstractmethod
    def enable_output(self) -> None:
        """
        Enable the SMU output.
        
        After enabling, state should be RUNNING.
        """
        pass
    
    @abstractmethod
    def disable_output(self) -> None:
        """
        Disable the SMU output.
        
        After disabling, state should be IDLE.
        """
        pass
    
    @abstractmethod
    def measure(self) -> Dict[str, float]:
        """
        Perform a spot measurement.
        
        Returns:
            dict with 'voltage' and 'current' keys
        """
        pass
    
    # -------------------------------------------------------------------------
    # Optional Methods - Can be overridden by drivers that support these
    # -------------------------------------------------------------------------
    
    def configure(self, settings: Dict[str, Any]) -> None:
        """
        Configure the SMU with multiple settings.
        
        Default implementation extracts common settings.
        Override for SMU-specific configuration.
        """
        if 'compliance_voltage' in settings:
            self.set_compliance(settings['compliance_voltage'], 'VOLT')
        if 'compliance_current' in settings:
            self.set_compliance(settings['compliance_current'], 'CURR')
        if 'nplc' in settings:
            self.set_nplc(settings['nplc'])
        
        self.to_state(SMUState.CONFIGURED)
    
    def setup_list_sweep(self, points: list, source_mode: str, time_per_step: float, trigger_count: int = 1) -> None:
        """
        Configure a list sweep. Optional - not all SMUs support this.
        
        Args:
            points: List of values (Volts or Amps)
            source_mode: 'VOLT' or 'CURR'
            time_per_step: Duration per point in seconds
            trigger_count: Number of repetitions
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support list sweeps")
    
    def trigger_list(self) -> None:
        """Start a configured list sweep."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support list sweeps")
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    @staticmethod
    def get_smu_type() -> str:
        """Return the SMU type identifier."""
        return "base"
    
    @staticmethod
    def get_smu_description() -> str:
        """Return a human-readable description."""
        return "Abstract SMU Base Class"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(address='{self.address}', channel={self.channel}, mock={self.mock})"
