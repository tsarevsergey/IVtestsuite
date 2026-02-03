"""
Live Monitor Service - Backend-side buffered data collection.

Runs measurements in a background thread at configurable rate,
stores data in a circular buffer. UI can poll for latest data
without affecting measurement timing.
"""
import threading
import time
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from collections import deque

from .logging_config import get_logger
from .smu_client import smu_client

logger = get_logger("live_monitor")

MAX_BUFFER_SIZE = 1000  # Keep last 1000 measurements


@dataclass
class MonitorConfig:
    """Configuration for live monitoring."""
    channel: int = 2
    bias_voltage: float = 0.0
    nplc: float = 1.0
    compliance: float = 0.1
    rate_hz: float = 10.0  # Measurements per second


@dataclass
class MonitorState:
    """Current state of the monitor."""
    running: bool = False
    configured: bool = False
    config: MonitorConfig = field(default_factory=MonitorConfig)
    buffer: deque = field(default_factory=lambda: deque(maxlen=MAX_BUFFER_SIZE))
    last_value: Optional[Dict] = None
    error: Optional[str] = None
    measurement_count: int = 0
    start_time: float = 0.0


class LiveMonitorService:
    """
    Background monitoring service.
    
    Collects measurements in a thread, stores in buffer.
    UI polls for data at its own pace.
    """
    
    _instance: Optional["LiveMonitorService"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.state = MonitorState()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._initialized = True
        logger.info("LiveMonitorService initialized")
    
    def configure(self, config: MonitorConfig) -> Dict[str, Any]:
        """Configure monitoring parameters."""
        with self._lock:
            if self.state.running:
                return {"success": False, "message": "Cannot configure while running"}
            
            self.state.config = config
            
            # Configure SMU
            result = smu_client.configure(
                compliance=config.compliance,
                nplc=config.nplc,
                channel=config.channel
            )
            
            if not result.get("success", False):
                self.state.error = result.get("message", "SMU configure failed")
                return result
            
            smu_client.set_source_mode("VOLT", channel=config.channel)
            smu_client.set_value(config.bias_voltage, channel=config.channel)
            
            self.state.configured = True
            self.state.error = None
            logger.info(f"Monitor configured: ch={config.channel}, rate={config.rate_hz}Hz")
            
            return {"success": True, "message": "Configured", "config": config.__dict__}
    
    def start(self) -> Dict[str, Any]:
        """Start background monitoring."""
        with self._lock:
            if self.state.running:
                return {"success": False, "message": "Already running"}
            
            if not self.state.configured:
                return {"success": False, "message": "Not configured - call configure first"}
            
            # Enable output
            smu_client.output_control(True, channel=self.state.config.channel)
            
            # Clear buffer and start
            self.state.buffer.clear()
            self.state.measurement_count = 0
            self.state.start_time = time.time()
            self.state.running = True
            self.state.error = None
            
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._measurement_loop, daemon=True)
            self._thread.start()
            
            logger.info(f"Monitor started at {self.state.config.rate_hz}Hz")
            return {"success": True, "message": "Monitoring started"}
    
    def stop(self) -> Dict[str, Any]:
        """Stop background monitoring."""
        with self._lock:
            if not self.state.running:
                return {"success": False, "message": "Not running"}
            
            self._stop_event.set()
            self.state.running = False
        
        # Wait for thread outside lock
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        
        # Disable output
        smu_client.output_control(False, channel=self.state.config.channel)
        
        logger.info(f"Monitor stopped. Total measurements: {self.state.measurement_count}")
        return {
            "success": True, 
            "message": "Stopped",
            "total_measurements": self.state.measurement_count
        }
    
    def get_data(self, last_n: int = 60) -> Dict[str, Any]:
        """
        Get latest measurements from buffer.
        
        Args:
            last_n: Number of most recent measurements to return
        """
        with self._lock:
            data = list(self.state.buffer)[-last_n:] if self.state.buffer else []
            
            return {
                "running": self.state.running,
                "configured": self.state.configured,
                "measurement_count": self.state.measurement_count,
                "buffer_size": len(self.state.buffer),
                "last_value": self.state.last_value,
                "error": self.state.error,
                "data": data,
                "config": self.state.config.__dict__ if self.state.configured else None
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current monitor status (without data)."""
        with self._lock:
            return {
                "running": self.state.running,
                "configured": self.state.configured,
                "measurement_count": self.state.measurement_count,
                "buffer_size": len(self.state.buffer),
                "last_value": self.state.last_value,
                "error": self.state.error,
                "rate_hz": self.state.config.rate_hz if self.state.configured else None,
                "channel": self.state.config.channel if self.state.configured else None
            }
    
    def _measurement_loop(self):
        """Background measurement loop."""
        interval = 1.0 / self.state.config.rate_hz
        channel = self.state.config.channel
        
        logger.info(f"Measurement loop started: interval={interval*1000:.1f}ms")
        
        while not self._stop_event.is_set():
            loop_start = time.perf_counter()
            
            try:
                result = smu_client.measure(channel=channel)
                
                if result.get("success", False):
                    measurement = {
                        "time": time.time(),
                        "voltage": result.get("voltage", 0.0),
                        "current": result.get("current", 0.0)
                    }
                    
                    with self._lock:
                        self.state.buffer.append(measurement)
                        self.state.last_value = measurement
                        self.state.measurement_count += 1
                else:
                    logger.warning(f"Measurement failed: {result.get('message')}")
                    
            except Exception as e:
                logger.error(f"Measurement loop error: {e}")
                self.state.error = str(e)
            
            # Sleep for remaining interval
            elapsed = time.perf_counter() - loop_start
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)


# Singleton instance
live_monitor = LiveMonitorService()
