import sys
import os
import json

# Add project root and MCP directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from smu_mcp_server import connect, disconnect, get_status
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test():
    print("--- Test 1: Connect / Disconnect Lifecycle ---")
    
    # 1. Start Disconnected
    print("Initial Status:", get_status.fn())
    
    # 2. Connect Mock
    print("\nConnecting Mock...")
    resp = json.loads(connect.fn(address="MOCK::ADDRESS", mock=True))
    print("Response:", resp)
    assert resp["status"] == "success"
    assert resp["mock"] is True
    
    # 3. Check Status
    status = json.loads(get_status.fn())
    print("Status after connect:", status)
    assert status["state"] == "IDLE"
    
    # 4. Disconnect
    print("\nDisconnecting...")
    resp = json.loads(disconnect.fn())
    print("Response:", resp)
    assert resp["status"] == "success"
    
    # 5. Final Status
    status = json.loads(get_status.fn())
    print("Final Status:", status)
    assert status["state"] == "OFF"
    
    print("\nTest 1 PASSED")

if __name__ == "__main__":
    test()
