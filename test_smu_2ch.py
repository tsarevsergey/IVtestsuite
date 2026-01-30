"""
Test script for SMUController2CH - Direct hardware test
"""
import sys
sys.path.insert(0, ".")

from smu_controller_2ch import SMUController2CH

ADDRESS = "USB0::2391::35864::MY51141849::0::INSTR"

def test_channel(channel):
    print(f"\n{'='*60}")
    print(f"Testing Channel {channel}")
    print('='*60)
    
    smu = SMUController2CH(address=ADDRESS, channel=channel, mock=False)
    
    print("\n1. Connecting...")
    smu.connect()
    print(f"   State: {smu.state}")
    
    if smu.state.value == "ERROR":
        print("   Connection failed!")
        return False
    
    print("\n2. Setting source mode to VOLT...")
    smu.set_source_mode("VOLT")
    print(f"   State: {smu.state}")
    
    print(f"\n3. Setting voltage to {channel}.0 V...")
    smu.set_voltage(float(channel))
    print(f"   State: {smu.state}")
    
    print("\n4. Setting current compliance to 10mA...")
    smu.set_compliance(0.01, "CURR")
    print(f"   State: {smu.state}")
    
    print("\n5. Enabling output...")
    smu.enable_output()
    print(f"   State: {smu.state}")
    
    if smu.state.value == "ERROR":
        print("   Enable output failed!")
        smu.disconnect()
        return False
    
    import time
    time.sleep(0.5)
    
    print("\n6. Taking measurement...")
    result = smu.measure()
    print(f"   Voltage: {result['voltage']:.6f} V")
    print(f"   Current: {result['current']:.6e} A")
    print(f"   State: {smu.state}")
    
    print("\n7. Disabling output...")
    smu.disable_output()
    print(f"   State: {smu.state}")
    
    print("\n8. Disconnecting...")
    smu.disconnect()
    print(f"   State: {smu.state}")
    
    return True

if __name__ == "__main__":
    print("SMUController2CH Direct Test")
    print("="*60)
    
    # Test Channel 1
    success1 = test_channel(1)
    
    if success1:
        print("\n" + "="*60)
        print("Channel 1 test PASSED!")
        print("="*60)
        
        # Test Channel 2
        import time
        time.sleep(1)
        success2 = test_channel(2)
        
        if success2:
            print("\n" + "="*60)
            print("Channel 2 test PASSED!")
            print("="*60)
            print("\n*** BOTH CHANNELS WORKING! ***")
        else:
            print("\nChannel 2 test FAILED")
    else:
        print("\nChannel 1 test FAILED")
