import sys
import os
import time
import json

# Add project root and MCP directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:
    from smu_mcp_server import connect, configure, set_source_mode, set_value, output_control, measure, disconnect
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def run_real_test():
    address = "USB0::0x0957::0xCD18::MY51143841::INSTR"
    print(f"--- Starting REAL SMU Hardware Test ---")
    print(f"Instrument Address: {address}")
    print("Task: Turn SMU ON at 7V with 10mA compliance for 10 seconds")
    
    # Using .fn to access the original function because FastMCP wraps them in FunctionTool objects
    
    # 1. Connect (Real Hardware)
    print("\n[Step 1] Connecting to Real Hardware...")
    resp_str = connect.fn(address=address, mock=False)
    print(f"Response: {resp_str}")
    
    # 2. Configure: 10mA Compliance (0.01 A)
    print("\n[Step 2] Configuring Compliance to 10mA...")
    resp_str = configure.fn(compliance=0.01, type="CURR", nplc=1.0)
    print(f"Response: {resp_str}")
    
    # 3. Set Mode and Voltage
    print("\n[Step 3] Setting Source Mode to VOLT and Value to 7.0V...")
    set_source_mode.fn(mode="VOLT")
    resp_str = set_value.fn(value=7.0)
    print(f"Response: {resp_str}")
    
    # 4. Enable Output
    print("\n[Step 4] Turning Output ON...")
    resp_str = output_control.fn(enabled=True)
    print(f"Response: {resp_str}")
    
    # 5. Measure loop for 10 seconds
    print("\n[Step 5] Measuring for 10 seconds (1s intervals)...")
    for i in range(1, 11):
        resp_json = measure.fn()
        data = json.loads(resp_json)
        if data["status"] == "success":
            v = data["data"]["voltage"]
            i_meas = data["data"]["current"]
            print(f"[{i}s] Measured: {v:.4f} V, {i_meas:.4e} A")
        else:
            print(f"[{i}s] Measure Error: {data.get('message', 'Unknown error')}")
        time.sleep(1)
        
    # 6. Safety Shutdown
    print("\n[Step 6] Disabling Output and Disconnecting...")
    output_control.fn(enabled=False)
    resp_str = disconnect.fn()
    print(f"Response: {resp_str}")
    
    print("\n--- Real Hardware Verification Complete ---")

if __name__ == "__main__":
    run_real_test()
