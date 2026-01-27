"""
Real Hardware Test: Channel Parameter Validation
Tests channel 1 (should work) and channel 2 (should fail on single-channel B2901A)
"""
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from smu_controller import SMUController, InstrumentState

ADDRESS = "USB0::0x0957::0xCD18::MY51143841::INSTR"

def test_channel_1():
    """Channel 1 should work on B2901A"""
    print("\n=== TEST: Channel 1 (Should WORK) ===")
    smu = SMUController(address=ADDRESS, channel=1)
    try:
        smu.connect()
        if smu.state == InstrumentState.ERROR:
            print("FAIL: Channel 1 connection resulted in ERROR state")
            return False
        
        # Quick measurement test
        smu.set_source_mode("VOLT")
        smu.set_compliance(0.001, "CURR")  # 1mA compliance
        smu.set_voltage(0.0)
        smu.enable_output()
        
        result = smu.measure()
        print(f"Measurement: V={result['voltage']:.4f}V, I={result['current']:.2e}A")
        
        smu.disable_output()
        smu.disconnect()
        print("PASS: Channel 1 works correctly")
        return True
    except Exception as e:
        print(f"FAIL: Channel 1 error: {e}")
        try:
            smu.disconnect()
        except:
            pass
        return False

def test_channel_2():
    """Channel 2 should fail on single-channel B2901A"""
    print("\n=== TEST: Channel 2 (Should FAIL on B2901A) ===")
    smu = SMUController(address=ADDRESS, channel=2)
    try:
        smu.connect()
        if smu.state == InstrumentState.ERROR:
            print("PASS: Channel 2 correctly resulted in ERROR (expected for B2901A)")
            return True
        
        # Try to do something - this should fail
        smu.set_source_mode("VOLT")
        smu.set_voltage(0.0)
        smu.enable_output()
        
        result = smu.measure()
        print(f"Unexpected success: V={result['voltage']:.4f}V, I={result['current']:.2e}A")
        
        smu.disable_output()
        smu.disconnect()
        print("UNEXPECTED: Channel 2 worked (this SMU might be a B2902A dual-channel)")
        return False  # Unexpected for B2901A
    except Exception as e:
        print(f"PASS: Channel 2 correctly failed with: {e}")
        try:
            smu.disconnect()
        except:
            pass
        return True  # Expected failure

if __name__ == "__main__":
    print("=" * 50)
    print("Real Hardware Channel Test")
    print("SMU: Keysight B2901A (Single Channel)")
    print("=" * 50)
    
    ch1_ok = test_channel_1()
    ch2_ok = test_channel_2()
    
    print("\n" + "=" * 50)
    print("RESULTS:")
    print(f"  Channel 1: {'PASS' if ch1_ok else 'FAIL'}")
    print(f"  Channel 2: {'PASS (expected fail)' if ch2_ok else 'FAIL (unexpected success)'}")
    print("=" * 50)
