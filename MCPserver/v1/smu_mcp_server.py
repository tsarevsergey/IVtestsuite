import sys
import os
import time
import json
import threading
from typing import Optional, List, Dict, Any, Union

# Add parent directory to path to import SMUController
# Since we are in MCPserver/v1, we need to go up two levels
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

try:
    from smu_controller import SMUController, InstrumentState
except ImportError:
    # Fallback if the path logic is tricky in some environments
    sys.path.append(os.path.abspath(os.getcwd()))
    from smu_controller import SMUController, InstrumentState

from fastmcp import FastMCP

mcp = FastMCP("SMU-Server")

# Global state for the controller
smu: Optional[SMUController] = None
lock = threading.Lock()

@mcp.tool()
def connect(address: str, mock: bool = False, name: str = "SMU", channel: int = 1) -> str:
    """
    Connect to the SMU hardware or start in mock mode.
    
    Args:
        address: VISA resource address (e.g., 'USB0::0x0957::...::INSTR')
        mock: If True, simulate hardware without physical connection
        name: Friendly name for the SMU instance
        channel: SMU channel to use (1 or 2 for dual-channel SMUs like B2902A)
    """
    global smu
    if not lock.acquire(blocking=False):
        return json.dumps({"status": "error", "message": "Server is busy with another operation"})
    try:
        if smu:
            try:
                smu.disconnect()
            except:
                pass
        smu = SMUController(address=address, name=name, mock=mock, channel=channel)
        smu.connect()
        if smu.state == InstrumentState.ERROR:
            return json.dumps({"status": "error", "message": "Connection attempt resulted in ERROR state"})
        return json.dumps({
            "status": "success", 
            "message": f"Connected to {address}", 
            "mock": mock,
            "channel": channel,
            "state": smu.state.value
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        lock.release()

@mcp.tool()
def disconnect() -> str:
    """Safely disable output and disconnect from the SMU."""
    global smu
    if not lock.acquire(blocking=False):
        return json.dumps({"status": "error", "message": "Server is busy with another operation"})
    try:
        if smu:
            smu.disconnect()
            smu = None
            return json.dumps({"status": "success", "message": "Disconnected"})
        return json.dumps({"status": "error", "message": "No active connection"})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        lock.release()

@mcp.tool()
def get_status() -> str:
    """Get the current state and settings of the SMU."""
    global smu
    if not smu:
        return json.dumps({"status": "error", "message": "Not connected", "state": "OFF"})
    
    return json.dumps({
        "status": "success",
        "state": smu.state.value,
        "output_enabled": getattr(smu, '_output_enabled', False),
        "source_current": getattr(smu, '_current_source_amps', 0.0),
        "voltage_compliance": getattr(smu, '_voltage_limit_volts', 2.0),
        "mock": smu.mock
    })

@mcp.tool()
def set_source_mode(mode: str) -> str:
    """
    Set the SMU to Voltage Source or Current Source mode.
    """
    global smu
    if not lock.acquire(blocking=False):
        return json.dumps({"status": "error", "message": "Server is busy with another operation"})
    try:
        if not smu:
            return json.dumps({"status": "error", "message": "Not connected"})
        smu.set_source_mode(mode)
        return json.dumps({"status": "success", "mode": mode})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        lock.release()

@mcp.tool()
def configure(compliance: float, type: str = "CURR", nplc: float = 1.0) -> str:
    """
    Configure compliance limits and measurement speed.
    """
    global smu
    if not lock.acquire(blocking=False):
        return json.dumps({"status": "error", "message": "Server is busy with another operation"})
    try:
        if not smu:
            return json.dumps({"status": "error", "message": "Not connected"})
        smu.set_compliance(compliance, type)
        smu.set_nplc(nplc)
        return json.dumps({
            "status": "success", 
            "compliance": compliance, 
            "compliance_type": type,
            "nplc": nplc
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        lock.release()

@mcp.tool()
def output_control(enabled: bool) -> str:
    """
    Turn the SMU output ON or OFF.
    """
    global smu
    if not lock.acquire(blocking=False):
        return json.dumps({"status": "error", "message": "Server is busy with another operation"})
    try:
        if not smu:
            return json.dumps({"status": "error", "message": "Not connected"})
        if enabled:
            smu.enable_output()
        else:
            smu.disable_output()
        return json.dumps({"status": "success", "output_enabled": enabled})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        lock.release()

@mcp.tool()
def set_value(value: float) -> str:
    """
    Set the DC source value (Voltage or Current depending on current mode).
    """
    global smu
    if not lock.acquire(blocking=False):
        return json.dumps({"status": "error", "message": "Server is busy with another operation"})
    try:
        if not smu:
            return json.dumps({"status": "error", "message": "Not connected"})
        if smu.mock:
            smu.set_voltage(value)
        else:
            mode = smu.resource.query("SOUR:FUNC:MODE?").strip().replace('"', '')
            if "VOLT" in mode:
                smu.set_voltage(value)
            else:
                smu.set_current(value)
        return json.dumps({"status": "success", "value": value})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        lock.release()

@mcp.tool()
def measure() -> str:
    """
    Perform a single spot measurement of Voltage and Current.
    """
    global smu
    if not lock.acquire(blocking=False):
        return json.dumps({"status": "error", "message": "Server is busy with another operation"})
    try:
        if not smu:
            return json.dumps({"status": "error", "message": "Not connected"})
        data = smu.measure()
        return json.dumps({"status": "success", "data": data})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        lock.release()

@mcp.tool()
def run_iv_sweep(start: float, stop: float, steps: int, spacing: str = "Linear", direction: str = "Single", compliance: float = 0.01, delay: float = 0.01) -> str:
    """
    Execute a voltage sweep and measure current (IV Sweep).
    """
    global smu
    if not lock.acquire(blocking=False):
        return json.dumps({"status": "error", "message": "Server is busy with another operation"})
    try:
        if not smu:
            return json.dumps({"status": "error", "message": "Not connected"})
        
        import numpy as np
        
        if spacing.lower() == "linear":
            points = np.linspace(start, stop, steps).tolist()
        else:
            s = start if start != 0 else 1e-9
            e = stop if stop != 0 else 1e-9
            points = np.logspace(np.log10(abs(s)), np.log10(abs(e)), steps).tolist()
            if start < 0: points = [-p for p in points]
        
        if direction.lower() == "double":
            points = points + points[::-1][1:] # Standard double sweep usually avoids repeating the peak point twice

        results = []
        smu.set_source_mode("VOLT")
        smu.set_compliance(compliance, "CURR")
        smu.enable_output()
        
        for v in points:
            smu.set_voltage(v)
            time.sleep(delay)
            meas = smu.measure()
            meas['set_voltage'] = v
            results.append(meas)
            
        smu.disable_output()
        return json.dumps({"status": "success", "results": results})
    except Exception as e:
        if smu:
            try: smu.disable_output()
            except: pass
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        lock.release()

@mcp.tool()
def run_list_sweep(points: List[float], mode: str = "VOLT", time_per_step: float = 0.1, compliance: float = 0.01) -> str:
    """
    Execute a custom list sweep using hardware-timed execution.
    """
    global smu
    if not lock.acquire(blocking=False):
        return json.dumps({"status": "error", "message": "Server is busy with another operation"})
    try:
        if not smu:
            return json.dumps({"status": "error", "message": "Not connected"})
        smu.setup_list_sweep(points, mode, time_per_step)
        smu.set_compliance(compliance, "CURR" if mode == "VOLT" else "VOLT")
        smu.enable_output()
        smu.trigger_list()
        
        total_time = len(points) * time_per_step
        time.sleep(total_time + 0.5)
        
        return json.dumps({
            "status": "success", 
            "message": "List sweep completed", 
            "points_count": len(points),
            "duration": total_time
        })
    except Exception as e:
        if smu:
            try: smu.disable_output()
            except: pass
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        lock.release()

if __name__ == "__main__":
    mcp.run()
