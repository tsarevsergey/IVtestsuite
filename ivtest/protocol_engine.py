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
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import copy
import numpy as np

from .logging_config import get_logger
from .run_manager import run_manager, RunState
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
        self._history: List[Dict[str, Any]] = []
        self._data_lock = threading.Lock()
        
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
            "smu/simultaneous-sweep": self._action_smu_simultaneous_sweep,
            "smu/simultaneous-sweep-custom": self._action_smu_simultaneous_sweep_custom,
            "smu/simultaneous-list-sweep": self._action_smu_simultaneous_list_sweep,
            "smu/bias-sweep": self._action_smu_bias_sweep,
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
            "control/loop": self._action_control_loop,
        }
    
    def run(self, steps: List[Dict[str, Any]], skip_cleanup: bool = False) -> ProtocolResult:
        """
        Execute a list of protocol steps.
        
        Args:
            steps: List of step dicts with 'action', 'params', optional 'capture_as'
            skip_cleanup: If True, skip the safety cleanup at end of run
        
        Returns:
            ProtocolResult with execution details
        """
        self._running = True
        with self._data_lock:
            self._captured = {}
            self._history = []
        step_results = []
        
        # Ensure we are in a fresh state to clear abort flags and start duration
        if run_manager.state in [RunState.ABORTED, RunState.ERROR]:
            run_manager.reset()
        if run_manager.state == RunState.IDLE:
            run_manager.arm()
        if run_manager.state == RunState.ARMED:
            run_manager.start()
            
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
                    with self._data_lock:
                        self._captured[var_name] = result.result
                        
                        # Add to history
                        context = {k: v for k, v in self._captured.items() if k != var_name}
                        self._history.append({
                            "timestamp": time.time(),
                            "variable": var_name,
                            "value": result.result,
                            "context": copy.deepcopy(context)
                        })
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
            if not skip_cleanup:
                self._perform_safety_cleanup()
            else:
                logger.info("Safety cleanup skipped (requested).")
            
            # Automatically return to IDLE if we were the ones who started it
            # This is safe because RunManager.complete() only transitions if currently RUNNING
            run_manager.complete()
    
    def _execute_step(self, index: int, step: Dict[str, Any]) -> StepResult:
        """Execute a single protocol step."""
        # Double check abort before starting any action
        if run_manager.is_abort_requested():
            return StepResult(
                step_index=index,
                action=step.get("action", ""),
                success=False,
                error="Aborted before execution"
            )
            
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
            # Special handling for control actions that need access to sub-steps or self
            if action.startswith("control/"):
                sub_steps = step.get("steps", [])
                result = self._actions[action](params, sub_steps)
            else:
                result = self._actions[action](params)
            
            # Capture result if requested
            if "capture_as" in step:
                var_name = step["capture_as"]
                with self._data_lock:
                    self._captured[var_name] = result
                    
                    # Add to history (handles recursive steps)
                    context = {k: v for k, v in self._captured.items() if k != var_name}
                    hist_item = {
                        "timestamp": time.time(),
                        "variable": var_name,
                        "value": result,
                        "context": copy.deepcopy(context)
                    }
                    self._history.append(hist_item)
                    logger.info(f"HISTORY: Appended '{var_name}' (Context keys: {list(context.keys())})")
                
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
        """
        Resolve variable references in params.
        Supports:
        - Exact match: "$var_name" -> value
        - String interpolation: "text_{$var_name}_text" -> "text_value_text"
        """
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str):
                # 1. Exact match check
                if value.startswith("$") and "{" not in value:
                    var_name = value[1:]
                    if var_name in self._captured:
                        resolved[key] = self._captured[var_name]
                        continue
                
                # 2. String interpolation check
                if "$" in value:
                    new_val = value
                    import re
                    
                    # 2a. Handle legacy {$var_name} patterns
                    matches_braced = re.finditer(r'\{\$([a-zA-Z0-9_]+)\}', value)
                    for match in matches_braced:
                        var_name = match.group(1)
                        if var_name in self._captured:
                            new_val = new_val.replace(match.group(0), str(self._captured[var_name]))
                            
                    # 2b. Handle unbraced $var_name patterns (greedy match)
                    # We match $ followed by word characters, but avoid overlapping with already replaced braces
                    # This regex finds $var but not {$var} because { usually precedes $ in the latter
                    matches_unbraced = re.finditer(r'(?<!\{)\$([a-zA-Z0-9_]+)', new_val)
                    for match in matches_unbraced:
                        var_name = match.group(1)
                        if var_name in self._captured:
                            # Use regex sub with word boundary to avoid partial replacement of longer variable names
                            # or tokens that look like variables but aren't
                            pattern = re.escape(match.group(0)) + r'(\b|[^a-zA-Z0-9_]|$)'
                            new_val = re.sub(pattern, str(self._captured[var_name]) + r'\1', new_val, count=1)

                    resolved[key] = new_val
                else:
                     resolved[key] = value
            else:
                resolved[key] = value
        return resolved
    
    # --- Action Implementations ---
    
    def _action_wait(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for specified seconds."""
        seconds = params.get("seconds", 1.0)
        logger.info(f"Waiting {seconds}s (interruptible)...")
        run_manager.sleep(seconds)
        return {"success": True, "waited": seconds, "aborted": run_manager.is_abort_requested()}
    
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
            nplc=params.get("nplc", 1.0),
            channel=params.get("channel", None)
        )
    
    def _action_smu_source_mode(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.set_source_mode(
            mode=params.get("mode", "VOLT"),
            channel=params.get("channel", None)
        )
    
    def _action_smu_set(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.set_value(
            value=params.get("value", 0.0),
            channel=params.get("channel", None)
        )
    
    def _action_smu_output(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.output_control(
            enabled=params.get("enabled", True),
            channel=params.get("channel", None)
        )
    
    def _action_smu_measure(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.measure(
            channel=params.get("channel", None)
        )
    
    def _action_smu_sweep(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.run_iv_sweep(
            start=params.get("start", 0.0),
            stop=params.get("stop", 1.0),
            steps=params.get("points", 11),
            compliance=params.get("compliance", 0.01),
            delay=params.get("delay", 0.05),
            nplc=params.get("nplc", None),
            scale=params.get("scale", "linear"),
            direction=params.get("direction", "forward"),
            sweep_type=params.get("sweep_type", "single"),
            keep_output_on=params.get("keep_output_on", False),
            channel=params.get("channel", None)
        )
    
    def _action_smu_simultaneous_sweep(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute simultaneous sweep on multiple channels."""
        return smu_client.run_simultaneous_sweep(
            channels=params.get("channels", [1, 2]),
            start=params.get("start", 0.0),
            stop=params.get("stop", 1.0),
            steps=params.get("points", 11),
            compliance=params.get("compliance", 0.01),
            delay=params.get("delay", 0.05),
            nplc=params.get("nplc", None),
            scale=params.get("scale", "linear"),
            direction=params.get("direction", "forward"),
            sweep_type=params.get("sweep_type", "single"),
            source_mode=params.get("source_mode", "VOLT"),
            keep_output_on=params.get("keep_output_on", False)
        )
        
    def _action_smu_simultaneous_sweep_custom(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute simultaneous sweep with INDEPENDENT sweep parameters for each channel.
        
        Args:
           sweeps: List of sweep dicts, e.g. [{"channel": 1, "start": 0...}, {"channel": 2...}]
           OR Flat params for Ch1/Ch2 convenience:
           ch1_start, ch1_stop, ch1_points, ch2_start...
           
           compliance: global compliance
           delay: global delay
        """
        sweeps = params.get("sweeps", [])
        
        # Support flat parameters for UI convenience
        if not sweeps:
            # Check for Ch1
            if "ch1_start" in params or "ch1_stop" in params:
                sweeps.append({
                    "channel": 1,
                    "start": params.get("ch1_start", 0.0),
                    "stop": params.get("ch1_stop", 1.0),
                    "points": params.get("points", 11), # Shared points usually
                    "scale": params.get("scale", "linear")
                })
            # Check for Ch2
            if "ch2_start" in params or "ch2_stop" in params:
                 sweeps.append({
                    "channel": 2,
                    "start": params.get("ch2_start", 0.0),
                    "stop": params.get("ch2_stop", 1.0),
                    "points": params.get("points", 11),
                    "scale": params.get("scale", "linear")
                })
                
        if not sweeps:
            return {"success": False, "message": "No sweeps defined (use 'sweeps' list or ch1/ch2 params)"}
            
        points_map = {}
        target_len = None
        
        for s in sweeps:
            ch = s.get("channel")
            if ch is None:
                continue
                
            start = s.get("start", 0.0)
            stop = s.get("stop", 1.0)
            points = s.get("points", 11)
            scale = s.get("scale", "linear")
            direction = s.get("direction", "forward")
            sweep_type = s.get("sweep_type", "single")
            
            # Generate points (logic duplicated from client for now to build list)
            s_val = start if direction == "forward" else stop
            e_val = stop if direction == "forward" else start
            
            if scale.lower() == "log":
                s_log = s_val if s_val != 0 else (1e-6 if e_val > 0 else -1e-6)
                e_log = e_val if e_val != 0 else (1e-6 if s_val > 0 else -1e-6)
                pts_arr = np.logspace(np.log10(abs(s_log)), np.log10(abs(e_log)), points)
                if s_log < 0 or (s_log == 0 and e_log < 0):
                    pts_arr = -pts_arr
            else:
                pts_arr = np.linspace(s_val, e_val, points)
            
            if len(pts_arr) > 0:
                pts_arr[-1] = e_val
            
            if sweep_type.lower() == "double":
                 pts_arr = np.concatenate([pts_arr, pts_arr[::-1][1:]])
                 pts_arr[-1] = s_val
                 
            # Validation
            if target_len is None:
                target_len = len(pts_arr)
            elif len(pts_arr) != target_len:
                return {"success": False, "message": f"Sweep point count mismatch for Ch {ch}. Expected {target_len}, got {len(pts_arr)}"}
                
            points_map[ch] = pts_arr.tolist()
            
        return smu_client.run_simultaneous_list_sweep(
            points_map=points_map,
            compliance=params.get("compliance", 0.1),
            nplc=params.get("nplc", 1.0),
            delay=params.get("delay", 0.05),
            source_mode=params.get("source_mode", "VOLT"),
            keep_output_on=params.get("keep_output_on", False)
        )
            
    def _action_smu_simultaneous_list_sweep(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute simultaneous sweep from custom lists."""
        points_map = params.get("points_map")
        
        # Support separate UI fields
        if not points_map:
            points_map = {}
            if "ch1_points" in params:
                 points_map[1] = params["ch1_points"]
            if "ch2_points" in params:
                 points_map[2] = params["ch2_points"]
                 
        if not points_map:
             return {"success": False, "message": "No points map or channel points defined"}
             
        return smu_client.run_simultaneous_list_sweep(
            points_map=points_map,
            compliance=params.get("compliance", 0.1),
            nplc=params.get("nplc", 1.0),
            delay=params.get("delay", 0.05),
            source_mode=params.get("source_mode", "VOLT"),
            keep_output_on=params.get("keep_output_on", False)
        )

    def _action_smu_bias_sweep(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hold one channel at bias (V or I), sweep another (V or I).
        Supports mixed source modes and independent compliance.
        """
        # Bias Channel Config
        bias_ch = params.get("bias_channel", 2)
        bias_mode = params.get("bias_source_mode", "VOLT")
        bias_val = params.get("bias_value", 0.0) # Generic name
        # Support legacy "bias_voltage" param
        if "bias_voltage" in params and "bias_value" not in params:
             bias_val = params.get("bias_voltage")
             
        bias_comp = params.get("bias_compliance", 0.1)
        
        # Sweep Channel Config
        sweep_ch = params.get("sweep_channel", 1)
        sweep_mode = params.get("sweep_source_mode", "VOLT")
        start = params.get("start", 0.0)
        stop = params.get("stop", 1.0)
        points = params.get("points", 11)
        sweep_comp = params.get("sweep_compliance", 0.1)
        
        # Timing / Output
        delay = params.get("delay", 0.05)
        keep_on = params.get("keep_output_on", False)
        
        # Generate sweep points
        pts_arr = np.linspace(start, stop, points)
        sweep_list = pts_arr.tolist()
        
        # Generate bias points (constant)
        bias_list = [bias_val] * points
        
        # Create map
        points_map = {
            bias_ch: bias_list,
            sweep_ch: sweep_list
        }
        
        # Create Config Map
        config_map = {
            bias_ch: {
                "source_mode": bias_mode,
                "compliance": bias_comp,
                "nplc": params.get("nplc", 1.0)
            },
            sweep_ch: {
                "source_mode": sweep_mode,
                "compliance": sweep_comp,
                "nplc": params.get("nplc", 1.0)
            }
        }
        
        return smu_client.run_simultaneous_list_sweep(
            points_map=points_map,
            delay=delay,
            keep_output_on=keep_on,
            config_map=config_map
        )
    
    def _action_smu_list_sweep(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return smu_client.run_list_sweep(
            points=params.get("points", [0.0]),
            source_mode=params.get("source_mode", "VOLT"),
            compliance=params.get("compliance", 0.1),
            nplc=params.get("nplc", 1.0),
            delay=params.get("delay", 0.1),
            channel=params.get("channel", None)
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
        
        # File versioning: if file exists, append _2, _3, etc.
        if filepath.exists():
            base = filepath.stem  # filename without extension
            ext = filepath.suffix  # .csv
            counter = 2
            while True:
                new_name = f"{base}_{counter}{ext}"
                new_path = folder_path / new_name
                if not new_path.exists():
                    filepath = new_path
                    logger.info(f"File exists, using versioned name: {filepath}")
                    break
                counter += 1
        
        # Write CSV
        keys = list(results[0].keys()) if results else []
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(results)
        
        logger.info(f"Saved {len(results)} rows to {filepath}")
        return {"success": True, "filepath": str(filepath), "rows": len(results)}


    def _action_control_loop(self, params: Dict[str, Any], steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute sub-steps in a loop.
        """
        variable = params.get("variable", "i")
        sequence = params.get("sequence", [])
        rng = params.get("range", {})
        
        # Determine items to iterate
        items = []
        if sequence:
            items = sequence
        elif rng:
            start = rng.get("start", 0)
            stop = rng.get("stop", 1)  # Using stop as inclusive count or pure range? 
            # YAML convention: usually start/stop implies range(start, stop)
            step = rng.get("step", 1)
            items = list(range(int(start), int(stop), int(step)))
            
        if not items:
            return {"success": False, "message": "No items to iterate"}
            
        logger.info(f"Starting loop over '{variable}' with {len(items)} items")
        
        total_iterations = 0
        for val in items:
            # Check for abort first
            if run_manager.is_abort_requested():
                logger.warning("Loop aborted")
                break
                
            # Set loop variable
            with self._data_lock:
                self._captured[variable] = val
            logger.info(f"Loop iteration: {variable}={val}")
            
            # Execute sub-steps recursively
            for i, step in enumerate(steps):
                if run_manager.is_abort_requested():
                    break
                
                # Execute step (recursive call effectively, but flattened logic)
                # We reuse _execute_step but need to be careful about logging/result aggregation?
                # _execute_step returns StepResult. We don't aggregate them all here to avoid memory explosion on huge loops
                # But we should log failures.
                
                result = self._execute_step(i, step)
                if not result.success:
                    logger.error(f"Loop step failed: {result.error}")
                    return {"success": False, "message": f"Loop failed at {variable}={val}: {result.error}"}
            
            total_iterations += 1
            
        return {"success": True, "iterations": total_iterations}


    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return a thread-safe copy of capture history."""
        with self._data_lock:
            if limit and limit > 0:
                # Efficient slicing before copy
                subset = self._history[-limit:]
                return copy.deepcopy(subset)
            logger.info(f"API: get_history called. Returning {len(self._history)} items.")
            return copy.deepcopy(self._history)

    def get_captured_data(self) -> Dict[str, Any]:
        """Return a thread-safe copy of captured data."""
        with self._data_lock:
            return copy.deepcopy(self._captured)

    def _perform_safety_cleanup(self):
        """
        Guaranteed safety routine to ensure hardware is in a safe state.
        Called at the end of every protocol run.
        """
        logger.info("Performing mandatory safety cleanup...")
        try:
            # 1. Disable SMU output
            self._action_smu_output({"enabled": False})
        except Exception as e:
            logger.error(f"Safety cleanup (SMU) failed: {e}")
            
        try:
            # 2. Open all relays
            self._action_relays_all_off({})
        except Exception as e:
            logger.error(f"Safety cleanup (Relays) failed: {e}")
            
        logger.info("Safety cleanup complete.")


# Global singleton instance
protocol_engine = ProtocolEngine()
