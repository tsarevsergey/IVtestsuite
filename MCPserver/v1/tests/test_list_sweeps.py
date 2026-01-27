import sys
import os
import json

# Add project root and MCP directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from smu_mcp_server import connect, run_list_sweep
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test():
    print("--- Test 6: List Sweep Variants ---")
    
    # 1. Setup
    connect.fn(address="MOCK::ADDRESS", mock=True)
    
    # 2. Custom Point List
    points = [0.0, 1.0, 0.5, 1.5, 0.0]
    print(f"\nRunning List Sweep with {len(points)} points...")
    # Mock mode list sweep just sleeps and returns success
    resp = json.loads(run_list_sweep.fn(points=points, mode="VOLT", time_per_step=0.1))
    
    print("Response:", resp)
    assert resp["status"] == "success"
    assert resp["points_count"] == len(points)
    assert resp["duration"] > 0
    
    # 3. Test with different integration time (simulated via time_per_step here as it is the dwell)
    print("\nRunning List Sweep with slower dwell (0.5s per step)...")
    resp = json.loads(run_list_sweep.fn(points=[1.0, 2.0], mode="VOLT", time_per_step=0.5))
    print("Response:", resp)
    assert resp["duration"] == 1.0 # 2 * 0.5
    
    print("\nTest 6 PASSED")

if __name__ == "__main__":
    test()
