import sys
import os
import json

# Add project root and MCP directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from smu_mcp_server import connect, disconnect
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test():
    print("--- Test 2: Invalid Instrument Address ---")
    
    # Try to connect with a garbage address in non-mock mode
    # This should fail connection
    print("Connecting to invalid address (non-mock)...")
    resp = json.loads(connect.fn(address="GARBAGE::ADDRESS", mock=False))
    print("Response:", resp)
    
    assert resp["status"] == "error"
    assert "ERROR state" in resp["message"]
    
    print("\nTest 2 PASSED")

if __name__ == "__main__":
    test()
