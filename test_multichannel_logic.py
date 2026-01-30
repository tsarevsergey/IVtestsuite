"""
Test script for Multi-Channel Stateful Logic in SMUClient.
"""
import sys
import logging
from ivtest.smu_client import smu_client, SMUStatus

# Setup logging to see output
logging.basicConfig(level=logging.INFO)

def test_multichannel():
    print("Testing Multi-Channel State...")
    
    # 1. Connect Channel 1 (Mock)
    # This should create the first controller
    print("\n1. Connecting Channel 1...")
    res1 = smu_client.connect(mock=True, channel=1, smu_type="keysight_b2902")
    print(f"   Result: {res1}")
    if not res1["success"]: return False
    
    # 2. Configure Channel 1
    print("\n2. Configuring Channel 1...")
    res2 = smu_client.configure(compliance=0.01, channel=1)
    print(f"   Result: {res2}")
    if not res2["success"]: return False
    
    # 3. Configure Channel 2 (Should auto-connect)
    print("\n3. Configuring Channel 2 (Auto-connect)...")
    try:
        res3 = smu_client.configure(compliance=0.05, channel=2)
        print(f"   Result: {res3}")
        if not res3["success"]: 
            print("   FAILED: Could not configure Ch2")
            return False
    except Exception as e:
        print(f"   EXCEPTION: {e}")
        return False

    # 4. Set Values for both
    print("\n4. Setting Ch1 to 1.0V and Ch2 to 2.0V...")
    smu_client.set_value(1.0, channel=1)
    smu_client.set_value(2.0, channel=2)
    
    # 5. Measure both (Mock returns randomish or 0)
    print("\n5. Measuring both...")
    m1 = smu_client.measure(channel=1)
    m2 = smu_client.measure(channel=2)
    print(f"   Ch1: {m1}")
    print(f"   Ch2: {m2}")
    
    if m1["channel"] != 1 or m2["channel"] != 2:
        print("   FAILURE: Channels mixed up in response")
        return False

    # 6. Disconnect
    print("\n6. Disconnecting...")
    smu_client.disconnect()
    
    print("\nSUCCESS: Multi-Channel Logic Verified")
    return True

if __name__ == "__main__":
    test_multichannel()
