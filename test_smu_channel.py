import requests
import time

BASE = "http://localhost:5000"

def test_smu_channel(channel):
    print(f"\n{'='*50}")
    print(f"Testing SMU Channel {channel}")
    print('='*50)
    
    # Connect
    print("\n1. Connecting...")
    r = requests.post(f"{BASE}/smu/connect", json={
        "mock": False,
        "channel": channel,
        "address": "USB0::2391::35864::MY51141849::0::INSTR"
    })
    print(f"   Response: {r.json()}")
    if not r.json().get("success"):
        return False
    
    # Check status
    print("\n2. Checking status...")
    r = requests.get(f"{BASE}/smu/status")
    print(f"   Status: {r.json()}")
    
    # Set source mode
    print("\n3. Setting source mode to VOLT...")
    r = requests.post(f"{BASE}/smu/source-mode", json={"mode": "VOLT"})
    print(f"   Response: {r.json()}")
    
    # Set voltage
    print("\n4. Setting voltage to 1.0V...")
    r = requests.post(f"{BASE}/smu/set", json={"value": 1.0})
    print(f"   Response: {r.json()}")
    
    # Check status before enabling output
    print("\n5. Checking status before output...")
    r = requests.get(f"{BASE}/smu/status")
    print(f"   Status: {r.json()}")
    
    # Enable output
    print("\n6. Enabling output...")
    r = requests.post(f"{BASE}/smu/output", json={"enabled": True})
    print(f"   Response: {r.json()}")
    
    # Check status after enabling
    print("\n7. Checking status after output enabled...")
    r = requests.get(f"{BASE}/smu/status")
    print(f"   Status: {r.json()}")
    
    time.sleep(0.5)  # Small delay
    
    # Measure
    print("\n8. Taking measurement...")
    r = requests.get(f"{BASE}/smu/measure")
    print(f"   Measurement: {r.json()}")
    
    # Disable output
    print("\n9. Disabling output...")
    r = requests.post(f"{BASE}/smu/output", json={"enabled": False})
    print(f"   Response: {r.json()}")
    
    # Disconnect
    print("\n10. Disconnecting...")
    r = requests.post(f"{BASE}/smu/disconnect")
    print(f"   Response: {r.json()}")
    
    return True

if __name__ == "__main__":
    print("SMU 2-Channel Test Script")
    print("="*50)
    
    # Test Channel 1
    test_smu_channel(1)
