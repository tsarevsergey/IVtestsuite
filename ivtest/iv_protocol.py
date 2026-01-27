"""
IV Sweep Protocol - Core measurement logic.

Supports:
- Dark / Light measurement modes
- Per-pixel scanning with relay control
- SMU compliance enforcement
- Abort-safe shutdown
- Data saving in multiple formats
"""
import os
import json
import csv
import time
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from enum import Enum

from .logging_config import get_logger
from .run_manager import run_manager, RunState
from .smu_client import smu_client
from .arduino_relays import relay_controller

logger = get_logger("iv_protocol")


class MeasurementMode(Enum):
    """Type of IV measurement."""
    DARK = "dark"
    LIGHT = "light"


@dataclass
class SweepConfig:
    """Configuration for an IV sweep."""
    start_voltage: float = 0.0
    stop_voltage: float = 8.0
    num_points: int = 41
    compliance_amps: float = 0.1
    delay_per_point: float = 0.1
    nplc: float = 1.0


@dataclass
class ProtocolConfig:
    """Full protocol configuration."""
    pixels: List[int] = field(default_factory=lambda: [0])
    led_channel: int = 0
    modes: List[str] = field(default_factory=lambda: ["dark", "light"])
    sweep: SweepConfig = field(default_factory=SweepConfig)
    output_dir: str = "data"
    sample_name: str = "sample"


@dataclass
class SweepResult:
    """Result of a single IV sweep."""
    pixel: int
    mode: str
    led_channel: Optional[int]
    timestamp: str
    data: List[Dict[str, float]]
    config: Dict[str, Any]
    aborted: bool = False


class IVProtocol:
    """
    IV measurement protocol executor.
    
    Orchestrates SMU, relays, and data collection.
    """
    
    def __init__(self, config: ProtocolConfig):
        self.config = config
        self.results: List[SweepResult] = []
        self._running = False
        
    def run(self) -> Dict[str, Any]:
        """
        Execute the full protocol.
        
        Returns:
            Summary dict with results and status
        """
        # Transition run manager
        if not run_manager.arm():
            return {"success": False, "message": "Failed to arm - check state"}
        
        if not run_manager.start():
            return {"success": False, "message": "Failed to start"}
        
        self._running = True
        self.results = []
        
        try:
            # Create output directory
            os.makedirs(self.config.output_dir, exist_ok=True)
            
            # Ensure SMU is configured
            smu_client.configure(
                compliance=self.config.sweep.compliance_amps,
                compliance_type="CURR",
                nplc=self.config.sweep.nplc
            )
            smu_client.set_source_mode("VOLT")
            
            # Execute for each pixel
            for pixel in self.config.pixels:
                if self._check_abort():
                    break
                
                logger.info(f"=== Pixel {pixel} ===")
                
                # Select pixel via relay (if connected)
                if relay_controller._connected:
                    relay_controller.select_pixel(pixel)
                    time.sleep(0.1)  # Relay settling
                
                # Execute each mode
                for mode in self.config.modes:
                    if self._check_abort():
                        break
                    
                    result = self._run_single_sweep(pixel, mode)
                    self.results.append(result)
                    
                    # Save incrementally
                    self._save_result(result)
            
            # All off for safety
            if relay_controller._connected:
                relay_controller.all_off()
            
            # Complete run
            aborted = run_manager.is_abort_requested()
            run_manager.complete()
            
            # Save summary
            self._save_summary()
            
            return {
                "success": True,
                "aborted": aborted,
                "num_sweeps": len(self.results),
                "output_dir": self.config.output_dir
            }
            
        except Exception as e:
            logger.error(f"Protocol error: {e}")
            run_manager.set_error(str(e))
            return {"success": False, "message": str(e)}
        
        finally:
            self._running = False
            # Safety: ensure output off
            try:
                smu_client.output_control(False)
            except:
                pass
    
    def _check_abort(self) -> bool:
        """Check if abort was requested."""
        if run_manager.is_abort_requested():
            logger.warning("Abort requested - stopping protocol")
            return True
        return False
    
    def _run_single_sweep(self, pixel: int, mode: str) -> SweepResult:
        """Execute a single IV sweep."""
        logger.info(f"Starting {mode.upper()} sweep on pixel {pixel}")
        
        # LED control for light mode
        if mode == "light" and relay_controller._connected:
            relay_controller.select_led_channel(self.config.led_channel)
            time.sleep(0.2)  # LED stabilization
        elif mode == "dark" and relay_controller._connected:
            # Ensure LED off for dark measurement
            relay_controller.led_board.all_off()
            time.sleep(0.1)
        
        # Run sweep
        sweep_result = smu_client.run_iv_sweep(
            start=self.config.sweep.start_voltage,
            stop=self.config.sweep.stop_voltage,
            steps=self.config.sweep.num_points,
            compliance=self.config.sweep.compliance_amps,
            delay=self.config.sweep.delay_per_point
        )
        
        # Turn off LED after light measurement
        if mode == "light" and relay_controller._connected:
            relay_controller.led_board.all_off()
        
        return SweepResult(
            pixel=pixel,
            mode=mode,
            led_channel=self.config.led_channel if mode == "light" else None,
            timestamp=datetime.now().isoformat(),
            data=sweep_result.get("results", []),
            config=asdict(self.config.sweep),
            aborted=sweep_result.get("aborted", False)
        )
    
    def _save_result(self, result: SweepResult):
        """Save a single sweep result."""
        base_name = f"{self.config.sample_name}_P{result.pixel}_{result.mode}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # CSV format
        csv_path = os.path.join(self.config.output_dir, f"{base_name}_{timestamp}.csv")
        with open(csv_path, "w", newline="") as f:
            if result.data:
                writer = csv.DictWriter(f, fieldnames=result.data[0].keys())
                writer.writeheader()
                writer.writerows(result.data)
        logger.info(f"Saved CSV: {csv_path}")
        
        # Legacy DAT format (tab-separated V, I)
        dat_path = os.path.join(self.config.output_dir, f"{base_name}_{timestamp}.dat")
        with open(dat_path, "w") as f:
            f.write("# Voltage(V)\tCurrent(A)\n")
            for row in result.data:
                f.write(f"{row.get('voltage', 0):.6e}\t{row.get('current', 0):.6e}\n")
        
        # JSON with metadata
        json_path = os.path.join(self.config.output_dir, f"{base_name}_{timestamp}.json")
        with open(json_path, "w") as f:
            json.dump(asdict(result), f, indent=2)
    
    def _save_summary(self):
        """Save protocol summary."""
        summary = {
            "sample_name": self.config.sample_name,
            "timestamp": datetime.now().isoformat(),
            "config": asdict(self.config),
            "num_sweeps": len(self.results),
            "sweeps": [
                {
                    "pixel": r.pixel,
                    "mode": r.mode,
                    "num_points": len(r.data),
                    "aborted": r.aborted
                }
                for r in self.results
            ]
        }
        
        summary_path = os.path.join(
            self.config.output_dir, 
            f"{self.config.sample_name}_summary.json"
        )
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Saved summary: {summary_path}")


def run_iv_protocol(
    pixels: List[int] = None,
    modes: List[str] = None,
    led_channel: int = 0,
    start_v: float = 0.0,
    stop_v: float = 8.0,
    num_points: int = 41,
    compliance: float = 0.1,
    delay: float = 0.1,
    output_dir: str = "data",
    sample_name: str = "sample"
) -> Dict[str, Any]:
    """
    Convenience function to run an IV protocol.
    
    Args:
        pixels: List of pixel indices to measure
        modes: List of modes ("dark", "light")
        led_channel: LED channel for light measurements
        start_v: Start voltage
        stop_v: Stop voltage
        num_points: Number of measurement points
        compliance: Current compliance (A)
        delay: Delay between points (s)
        output_dir: Output directory for data
        sample_name: Sample identifier
    
    Returns:
        Protocol result summary
    """
    config = ProtocolConfig(
        pixels=pixels or [0],
        modes=modes or ["dark", "light"],
        led_channel=led_channel,
        sweep=SweepConfig(
            start_voltage=start_v,
            stop_voltage=stop_v,
            num_points=num_points,
            compliance_amps=compliance,
            delay_per_point=delay
        ),
        output_dir=output_dir,
        sample_name=sample_name
    )
    
    protocol = IVProtocol(config)
    return protocol.run()
