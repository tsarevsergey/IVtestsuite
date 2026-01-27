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
    print("--- Test: Channel Parameter ---")
    
    # 1. Default channel (1) - should succeed
    print("\n[Test 1] Connect with default channel (1)...")
    resp = json.loads(connect.fn(address="MOCK::ADDRESS", mock=True))
    print(f"Response: {resp}")
    assert resp["status"] == "success", f"Expected success, got: {resp}"
    assert resp["channel"] == 1, f"Expected channel=1, got: {resp.get('channel')}"
    disconnect.fn()
    print("✓ Default channel works")
    
    # 2. Explicit channel 1 - should succeed
    print("\n[Test 2] Connect with explicit channel=1...")
    resp = json.loads(connect.fn(address="MOCK::ADDRESS", mock=True, channel=1))
    assert resp["status"] == "success"
    assert resp["channel"] == 1
    disconnect.fn()
    print("✓ Explicit channel=1 works")
    
    # 3. Channel 2 - should succeed
    print("\n[Test 3] Connect with channel=2...")
    resp = json.loads(connect.fn(address="MOCK::ADDRESS", mock=True, channel=2))
    print(f"Response: {resp}")
    assert resp["status"] == "success", f"Expected success, got: {resp}"
    assert resp["channel"] == 2, f"Expected channel=2, got: {resp.get('channel')}"
    disconnect.fn()
    print("✓ Channel=2 works")
    
    # 4. Invalid channel (3) - should fail
    print("\n[Test 4] Connect with invalid channel=3...")
    resp = json.loads(connect.fn(address="MOCK::ADDRESS", mock=True, channel=3))
    print(f"Response: {resp}")
    assert resp["status"] == "error", f"Expected error for channel=3, got: {resp}"
    assert "Invalid channel" in resp.get("message", ""), f"Expected 'Invalid channel' in message"
    print("✓ Invalid channel correctly rejected")
    
    print("\n--- All Channel Parameter Tests PASSED ---")

if __name__ == "__main__":
    test()
