"""
Test script for Multi-SMU Architecture (Factory + B2902A)
"""
import sys
sys.path.insert(0, ".")

from smu_factory import create_smu, SMUType

ADDRESS = "USB0::2391::35864::MY51141849::0::INSTR"

def test_channel(channel):
    print(f"\n{'='*60}")
    print(f"Testing Channel {channel} (Auto-detect from factory)")
    print('='*60)
    
    # Use Factory to create SMU
    # In real usage we would pass SMUType.AUTO
    try:
        smu = create_smu(SMUType.AUTO, address=ADDRESS, channel=channel, mock=False)
        print(f"Factory created: {smu.__class__.__name__}")
    except Exception as e:
        print(f"Factory creation failed: {e}")
        return False
    
    print("\n1. Connecting...")
    try:
        smu.connect()
        print(f"   State: {smu.state}")
    except Exception as e:
        print(f"   Connection failed: {e}")
        return False
    
    print("\n2. Setting source mode to VOLT...")
    smu.set_source_mode("VOLT")
    
    print(f"\n3. Setting voltage to {channel}.5 V...")
    smu.set_voltage(float(channel) + 0.5)
    
    print("\n4. Setting current compliance to 1mA...")
    smu.set_compliance(0.001, "CURR")
    
    print("\n5. Enabling output...")
    smu.enable_output()
    
    import time
    time.sleep(0.5)
    
    print("\n6. Taking measurement...")
    result = smu.measure()
    print(f"   Voltage: {result['voltage']:.6f} V")
    print(f"   Current: {result['current']:.6e} A")
    
    print("\n7. Disabling output...")
    smu.disable_output()
    
    print("\n8. Disconnecting...")
    smu.disconnect()
    
    return True

if __name__ == "__main__":
    print("Multi-SMU Factory Architecture Test")
    print("="*60)
    
    # Test Channel 1
    success1 = test_channel(1)
    
    # Test Channel 2
    if success1:
        import time
        time.sleep(1)
        success2 = test_channel(2)
        
        if success2:
            print("\n" + "="*60)
            print("SUCCESS: Factory auto-detected B2902A and both channels work!")
            print("="*60)
        else:
            print("\nFAILURE: Channel 2 test failed")
    else:
         print("\nFAILURE: Channel 1 test failed")
