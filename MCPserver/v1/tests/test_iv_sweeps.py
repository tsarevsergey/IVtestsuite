import sys
import os
import json

# Add project root and MCP directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from smu_mcp_server import connect, run_iv_sweep, configure
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test():
    print("--- Test 5: IV Sweep Variants ---")
    
    # 1. Setup
    connect.fn(address="MOCK::ADDRESS", mock=True)
    
    # 2. Linear Sweep: 0 to 2V, 5 points
    print("\nRunning Linear Sweep (0 to 2V, 5 points)...")
    resp = json.loads(run_iv_sweep.fn(start=0, stop=2, steps=5, spacing="Linear"))
    print("Linear Status:", resp["status"])
    assert resp["status"] == "success"
    assert len(resp["results"]) == 5
    # Verify spacing
    v_points = [r["set_voltage"] for r in resp["results"]]
    print("Points:", v_points)
    assert v_points == [0.0, 0.5, 1.0, 1.5, 2.0]
    
    # 3. Log Sweep: 1e-3 to 1V, 4 points
    print("\nRunning Log Sweep (0.001 to 1V, 4 points)...")
    resp = json.loads(run_iv_sweep.fn(start=0.001, stop=1, steps=4, spacing="Log"))
    print("Log Status:", resp["status"])
    assert resp["status"] == "success"
    assert len(resp["results"]) == 4
    v_points = [r["set_voltage"] for r in resp["results"]]
    print("Points:", v_points)
    # 10^-3, 10^-2, 10^-1, 10^0
    assert abs(v_points[1] - 0.01) < 1e-5
    
    # 4. Integration Time (NPLC) check
    print("\nSetting NPLC to 10 (Long integration)...")
    resp = json.loads(configure.fn(compliance=0.01, type="CURR", nplc=10.0))
    print("Config Response:", resp)
    assert resp["nplc"] == 10.0
    
    print("\nTest 5 PASSED")

if __name__ == "__main__":
    test()
