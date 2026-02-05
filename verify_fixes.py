
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "Dropbox", "Antigravity", "SMU")))

from ivtest.protocol_engine import ProtocolEngine
from ivtest.arduino_relays import relay_controller
from smu_base import BaseSMU, SMUState
from smu_keysight_b2901 import KeysightB2901Controller
from unittest.mock import MagicMock

def test_relay_indexing():
    print("Testing Relay Indexing...")
    engine = ProtocolEngine()
    
    # Mock relay_controller methods
    relay_controller.select_pixel = MagicMock()
    relay_controller.select_led_channel = MagicMock()
    
    # Test Pixel 1 (should call select_pixel(0))
    engine._action_relays_pixel({"pixel_id": 1})
    relay_controller.select_pixel.assert_called_with(0)
    print("✓ Pixel 1 -> select_pixel(0) mapping OK")
    
    # Test Pixel 6 (should call select_pixel(5))
    engine._action_relays_pixel({"pixel_id": 6})
    relay_controller.select_pixel.assert_called_with(5)
    print("✓ Pixel 6 -> select_pixel(5) mapping OK")
    
    # Test LED Channel 1 (should call select_led_channel(0))
    engine._action_relays_led({"channel_id": 1})
    relay_controller.select_led_channel.assert_called_with(0)
    print("✓ LED Channel 1 -> select_led_channel(0) mapping OK")

def test_smu_overload():
    print("\nTesting SMU Overload Handling...")
    
    # Mock pyvisa resource
    mock_resource = MagicMock()
    
    # Simulate overload response for both Volt and Curr
    mock_resource.query.side_effect = lambda cmd: "10E37" if "MEAS" in cmd else "STUB"
    
    smu = KeysightB2901Controller(address="GPIB::1", mock=False)
    smu.resource = mock_resource
    
    # Set to RUNNING state using the enum
    smu._state = SMUState.RUNNING
    
    meas = smu.measure()
    print(f"Measurement response: {meas}")
    
    assert meas['voltage'] is None
    assert meas['current'] is None
    print("✓ Overload 10E37 -> None mapping OK")

if __name__ == "__main__":
    try:
        test_relay_indexing()
        test_smu_overload()
        print("\nAll tests passed!")
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
