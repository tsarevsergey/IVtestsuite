"""
Global Run Manager with explicit state machine.

States: IDLE → ARMED → RUNNING → ABORTED / ERROR → IDLE

Thread-safe singleton pattern for global access throughout the application.
"""
import time
import threading
from enum import Enum
from typing import Optional, Callable, List
from datetime import datetime

from .logging_config import get_logger

logger = get_logger("run_manager")


class RunState(Enum):
    """Possible states for the run manager."""
    IDLE = "IDLE"
    ARMED = "ARMED"
    RUNNING = "RUNNING"
    ABORTED = "ABORTED"
    ERROR = "ERROR"


# Valid state transitions
VALID_TRANSITIONS = {
    RunState.IDLE: [RunState.ARMED],
    RunState.ARMED: [RunState.RUNNING, RunState.IDLE],  # Can cancel before starting
    RunState.RUNNING: [RunState.IDLE, RunState.ABORTED, RunState.ERROR],
    RunState.ABORTED: [RunState.IDLE],
    RunState.ERROR: [RunState.IDLE],
}


class RunManager:
    """
    Singleton run manager controlling the global execution state.
    
    Thread-safe state machine with abort capability.
    """
    _instance: Optional["RunManager"] = None
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
        
        self._state = RunState.IDLE
        self._state_lock = threading.RLock()
        self._start_time = datetime.now()
        self._run_start_time: Optional[datetime] = None
        self._abort_requested = threading.Event()
        self._shutdown_callbacks: List[Callable] = []
        self._error_message: Optional[str] = None
        
        # Progress tracking
        self._steps_completed = 0
        self._total_steps = 0
        
        self._initialized = True
        logger.info("RunManager initialized")
    
    @property
    def state(self) -> RunState:
        """Current state of the run manager."""
        with self._state_lock:
            return self._state
    
    @property
    def uptime_seconds(self) -> float:
        """Seconds since the run manager was initialized."""
        return (datetime.now() - self._start_time).total_seconds()
    
    @property
    def run_duration_seconds(self) -> Optional[float]:
        """Seconds since current run started, or None if not running."""
        if self._run_start_time is None:
            return None
        return (datetime.now() - self._run_start_time).total_seconds()
    
    @property
    def error_message(self) -> Optional[str]:
        """Last error message, if in ERROR state."""
        return self._error_message
    
    def _can_transition(self, new_state: RunState) -> bool:
        """Check if transition to new_state is valid."""
        return new_state in VALID_TRANSITIONS.get(self._state, [])
    
    def transition_to(self, new_state: RunState, error_msg: Optional[str] = None) -> bool:
        """
        Attempt to transition to a new state.
        
        Args:
            new_state: Target state
            error_msg: Error message (required for ERROR state)
        
        Returns:
            True if transition succeeded, False otherwise
        """
        with self._state_lock:
            if not self._can_transition(new_state):
                logger.warning(f"Invalid transition: {self._state} → {new_state}")
                return False
            
            old_state = self._state
            self._state = new_state
            
            # Handle state-specific logic
            if new_state == RunState.RUNNING:
                self._run_start_time = datetime.now()
                self._abort_requested.clear()
            elif new_state == RunState.ARMED:
                self._abort_requested.clear()
            elif new_state == RunState.ERROR:
                self._error_message = error_msg
            elif new_state == RunState.IDLE:
                self._run_start_time = None
                self._error_message = None
                self._steps_completed = 0
                self._total_steps = 0
                # CRITICAL: We DO NOT clear the abort flag here. 
                # It stays set until ARMED or RUNNING to ensure engines see it.
            
            logger.info(f"State transition: {old_state.value} → {new_state.value}")
            return True
    
    def arm(self) -> bool:
        """Prepare for a run. Transition IDLE → ARMED."""
        return self.transition_to(RunState.ARMED)
    
    def start(self) -> bool:
        """Start the run. Transition ARMED → RUNNING."""
        return self.transition_to(RunState.RUNNING)
    
    def complete(self) -> bool:
        """Complete the run successfully. Transition RUNNING → IDLE."""
        return self.transition_to(RunState.IDLE)
    
    def abort(self) -> bool:
        """
        Request abort of current operation.
        
        Sets abort flag and executes shutdown callbacks.
        Forces transition to ABORTED, then to IDLE.
        """
        logger.warning("ABORT requested")
        self._abort_requested.set()
        
        # Execute shutdown callbacks
        for callback in self._shutdown_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Shutdown callback failed: {e}")
        
        with self._state_lock:
            if self._state == RunState.RUNNING:
                self._state = RunState.ABORTED
                logger.info("State transition: RUNNING → ABORTED")
            
            # Always end in IDLE
            if self._state in [RunState.ABORTED, RunState.ARMED, RunState.IDLE]:
                self._state = RunState.IDLE
                self._run_start_time = None
                # We do NOT clear the flag here. 
                # It must persist until a new run starts to stop the engines.
                logger.info(f"State transition: → IDLE (abort complete)")
        
        return True
    
    def set_error(self, message: str) -> bool:
        """Transition to ERROR state with message."""
        return self.transition_to(RunState.ERROR, error_msg=message)
    
    def reset(self) -> bool:
        """Reset from ERROR or ABORTED to IDLE."""
        with self._state_lock:
            if self._state in [RunState.ERROR, RunState.ABORTED]:
                return self.transition_to(RunState.IDLE)
            elif self._state == RunState.IDLE:
                return True  # Already idle
            return False

    def set_progress(self, completed: int, total: int):
        """Update current execution progress."""
        with self._state_lock:
            self._steps_completed = completed
            self._total_steps = total
    
    def is_abort_requested(self) -> bool:
        """Check if abort has been requested (for long-running operations)."""
        return self._abort_requested.is_set()
    
    def sleep(self, seconds: float, step: float = 0.1):
        """
        Responsive wait that checks the abort flag.
        
        Args:
            seconds: Total time to wait
            step: Interval between abort checks
        """
        start = time.time()
        while time.time() - start < seconds:
            if self.is_abort_requested():
                break
            time.sleep(min(step, seconds - (time.time() - start)))
    
    def register_shutdown_callback(self, callback: Callable) -> None:
        """Register a callback to be called on abort/shutdown."""
        self._shutdown_callbacks.append(callback)
        logger.debug(f"Registered shutdown callback: {callback.__name__}")
    
    def get_status(self) -> dict:
        """Get current status as a dictionary."""
        return {
            "state": self.state.value,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "run_duration_seconds": round(self.run_duration_seconds, 2) if self.run_duration_seconds else None,
            "error_message": self.error_message,
            "abort_requested": self.is_abort_requested(),
            "steps_completed": self._steps_completed,
            "total_steps": self._total_steps
        }


# Global singleton instance
run_manager = RunManager()
