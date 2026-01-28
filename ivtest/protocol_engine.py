"""
Protocol Engine - Executes protocol steps sequentially.

Supports:
- Low-level API action dispatch (smu, relays, status)
- Wait commands
- Variable capture from action results
- Abort-aware execution
"""
import time
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .logging_config import get_logger
from .run_manager import run_manager
from .smu_client import smu_client, DEFAULT_SMU_ADDRESS
from .arduino_relays import relay_controller

logger = get_logger("protocol_engine")


@dataclass
class StepResult:
    """Result of a single protocol step."""
    step_index: int
    action: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class ProtocolResult:
    """Result of a full protocol execution."""
    success: bool
    steps_completed: int
    total_steps: int
    aborted: bool = False
    error: Optional[str] = None
    step_results: List[StepResult] = field(default_factory=list)
    captured_data: Dict[str, Any] = field(default_factory=dict)


class ProtocolEngine:
    """
    Executes protocol steps sequentially.
    
    Actions are mapped to low-level API calls.
    """
    
    def __init__(self):
        self._running = False
        self._captured: Dict[str, Any] = {}
        
        # Action dispatch table
        self._actions = {
            "wait": self._action_wait,
            "smu/connect": self._action_smu_connect,
            "smu/disconnect": self._action_smu_disconnect,
            "smu/configure": self._action_smu_configure,
            "smu/source-mode": self._action_smu_source_mode,
            "smu/set": self._action_smu_set,
            "smu/output": self._action_smu_output,
            "smu/measure": self._action_smu_measure,
            "smu/sweep": self._action_smu_sweep,
            "smu/list-sweep": self._action_smu_list_sweep,
            "relays/connect": self._action_relays_connect,
            "relays/disconnect": self._action_relays_disconnect,
            "relays/pixel": self._action_relays_pixel,
            "relays/led": self._action_relays_led,
            "relays/all-off": self._action_relays_all_off,
            "status/arm": self._action_status_arm,
            "status/start": self._action_status_start,
            "status/complete": self._action_status_complete,
            "status/abort": self._action_status_abort,
            "data/save": self._action_data_save,
        }
    
    def run(self, steps: List[Dict[str, Any]]) -> ProtocolResult:
        """
        Execute a list of protocol steps.
        
        Args:
            steps: List of step dicts with 'action', 'params', optional 'capture_as'
        
        Returns:
            ProtocolResult with execution details
        """
        self._running = True
        self._captured = {}
        step_results = []
        
        logger.info(f"Starting protocol execution: {len(steps)} steps")
        
        try:
            for i, step in enumerate(steps):
                # Check for abort
                if run_manager.is_abort_requested():
                    logger.warning(f"Protocol aborted at step {i}")
                    return ProtocolResult(
                        success=False,
                        steps_completed=i,
                        total_steps=len(steps),
                        aborted=True,
                        step_results=step_results,
                        captured_data=self._captured
                    )
                
                # Execute step
                result = self._execute_step(i, step)
                step_results.append(result)
                
                if not result.success:
                    logger.error(f"Step {i} failed: {result.error}")
                    return ProtocolResult(
                        success=False,
                        steps_completed=i,
                        total_steps=len(steps),
                        error=result.error,
                        step_results=step_results,
                        captured_data=self._captured
                    )
                
                # Capture result if requested
                if "capture_as" in step and result.result:
                    var_name = step["capture_as"]
                    self._captured[var_name] = result.result
                    logger.info(f"Captured '{var_name}' from step {i}")
            
            logger.info(f"Protocol completed successfully: {len(steps)} steps")
            return ProtocolResult(
                success=True,
                steps_completed=len(steps),
                total_steps=len(steps),
                step_results=step_results,
                captured_data=self._captured
            )
            
        except Exception as e:
            logger.error(f"Protocol execution error: {e}")
            return ProtocolResult(
                success=False,
                steps_completed=len(step_results),
                total_steps=len(steps),
                error=str(e),
                step_results=step_results,
                captured_data=self._captured
            )
        finally:
            self._running = False
    
    def _execute_step(self, index: int, step: Dict[str, Any]) -> StepResult:
        """Execute a single protocol step."""
        action = step.get("action", "")
        params = step.get("params", {})
        
        # Resolve variable references in params
        params = self._resolve_params(params)
        
        logger.info(f"Step {index}: {action}")
        
        if action not in self._actions:
            return StepResult(
                step_index=index,
                action=action,
                success=False,
                error=f"Unknown action: {action}"
            )
        
        start_time = time.time()
        try:
            result = self._actions[action](params)
            duration_ms = (time.time() - start_time) * 1000
            
            success = result.get("success", True) if isinstance(result, dict) else True
            error_msg = None
            if not success and isinstance(result, dict):
                error_msg = result.get("message") or result.get("error")
            
            return StepResult(
                step_index=index,
                action=action,
                success=success,
                result=result if isinstance(result, dict) else {"value": result},
                error=error_msg,
                duration_ms=duration_ms
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return StepResult(
                step_index=index,
                action=action,
                success=False,
                error=str(e),
                duration_ms=duration_ms
            )
    
    def _resolve_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve variable references ($var_name) in params."""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$"):
                var_name = value[1:]
                if var_name in self._captured:
                    resolved[key] = self._captured[var_name]
                else:
                    resolved[key] = value  # Keep as-is if not found
            else:
                resolved[key] = value
        return resolved
    
    # --- Action Implementations ---
    
    def _action_wait(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for specified seconds."""
        seconds = params.get("seconds", 1.0)
        logger.info(f"Waiting {seconds}s...")
        time.sleep(seconds)
        return {"success": True, "waited": seconds}
    
    def _action_smu_connect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        address = params.get("address", "") or DEFAULT_SMU_ADDRESS
        return smu_client.connect(
            address=address,
            mock=params.get("mock", False),
            channel=params.get("channel", 1)
        )
    
    def _action_smu_disconnect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.disconnect()
    
    def _action_smu_configure(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.configure(
            compliance=params.get("compliance", 0.1),
            compliance_type=params.get("compliance_type", "CURR"),
            nplc=params.get("nplc", 1.0)
        )
    
    def _action_smu_source_mode(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.set_source_mode(params.get("mode", "VOLT"))
    
    def _action_smu_set(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.set_value(params.get("value", 0.0))
    
    def _action_smu_output(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.output_control(params.get("enabled", True))
    
    def _action_smu_measure(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.measure()
    
    def _action_smu_sweep(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.run_iv_sweep(
            start=params.get("start", 0.0),
            stop=params.get("stop", 1.0),
            steps=params.get("points", 11),
            compliance=params.get("compliance", 0.01),
            delay=params.get("delay", 0.05),
            scale=params.get("scale", "linear"),
            direction=params.get("direction", "forward"),
            sweep_type=params.get("sweep_type", "single")
        )
    
    def _action_smu_list_sweep(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.run_list_sweep(
            points=params.get("points", [0.0]),
            source_mode=params.get("source_mode", "VOLT"),
            compliance=params.get("compliance", 0.1),
            nplc=params.get("nplc", 1.0),
            delay=params.get("delay", 0.1)
        )
    
    def _action_relays_connect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return relay_controller.connect(
            port=params.get("port", ""),
            mock=params.get("mock", False)
        )
    
    def _action_relays_disconnect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return relay_controller.disconnect()
    
    def _action_relays_pixel(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return relay_controller.select_pixel(params.get("pixel_id", 0))
    
    def _action_relays_led(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return relay_controller.select_led_channel(params.get("channel_id", 0))
    
    def _action_relays_all_off(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return relay_controller.all_off()
    
    def _action_status_arm(self, params: Dict[str, Any]) -> Dict[str, Any]:
        success = run_manager.arm()
        return {"success": success}
    
    def _action_status_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        success = run_manager.start()
        return {"success": success}
    
    def _action_status_complete(self, params: Dict[str, Any]) -> Dict[str, Any]:
        success = run_manager.complete()
        return {"success": success}
    
    def _action_status_abort(self, params: Dict[str, Any]) -> Dict[str, Any]:
        success = run_manager.abort()
        return {"success": success}


    def _action_data_save(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Save captured data to CSV file."""
        import csv
        from pathlib import Path
        
        data = params.get("data", {})
        filename = params.get("filename", "output")
        folder = params.get("folder", "./data")
        
        # Handle variable reference for data
        if isinstance(data, str) and data.startswith("$"):
            var_name = data[1:]
            data = self._captured.get(var_name, {})
        
        # Extract results from sweep data
        if isinstance(data, dict) and "results" in data:
            results = data["results"]
        elif isinstance(data, list):
            results = data
        else:
            results = []
        
        if not results:
            return {"success": False, "message": "No data to save"}
        
        # Ensure folder exists
        folder_path = Path(folder)
        folder_path.mkdir(parents=True, exist_ok=True)
        
        # Add .csv extension if not present
        if not filename.endswith(".csv"):
            filename = f"{filename}.csv"
        
        filepath = folder_path / filename
        
        # Write CSV
        keys = list(results[0].keys()) if results else []
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(results)
        
        logger.info(f"Saved {len(results)} rows to {filepath}")
        return {"success": True, "filepath": str(filepath), "rows": len(results)}


# Global singleton instance
protocol_engine = ProtocolEngine()
