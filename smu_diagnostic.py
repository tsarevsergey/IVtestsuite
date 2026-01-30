"""
Direct SMU diagnostic script - testing different SCPI syntax formats
"""
import pyvisa
import time

ADDRESS = "USB0::2391::35864::MY51141849::0::INSTR"

def test_command(smu, cmd, description):
    """Test a command and check for errors."""
    print(f"\n{description}")
    print(f"  Command: {cmd}")
    try:
        smu.write(cmd)
        time.sleep(0.1)
        err = smu.query("SYST:ERR?").strip()
        if "+0" in err or "No error" in err.lower():
            print(f"  Result: OK")
            return True
        else:
            print(f"  Result: ERROR - {err}")
            return False
    except Exception as e:
        print(f"  Result: EXCEPTION - {e}")
        return False

def main():
    print("=" * 60)
    print("B2902A SCPI Syntax Tester")
    print("=" * 60)
    
    rm = pyvisa.ResourceManager()
    smu = rm.open_resource(ADDRESS, open_timeout=20000)
    smu.timeout = 20000
    
    try:
        smu.clear()
    except:
        pass
    
    idn = smu.query("*IDN?").strip()
    print(f"\nConnected to: {idn}")
    
    # Clear error queue
    while True:
        err = smu.query("SYST:ERR?").strip()
        if "+0" in err:
            break
    print("Error queue cleared.")
    
    # Reset
    smu.write("*RST")
    time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("Testing SOUR:FUNC:MODE VOLT with different channel formats")
    print("=" * 60)
    
    # Test Format 1: No channel (should work as default channel 1)
    smu.write("*RST")
    test_command(smu, ":SOUR:FUNC:MODE VOLT", "Format 1: No channel suffix")
    
    # Test Format 2: comma-space before channel
    smu.write("*RST")
    test_command(smu, ":SOUR:FUNC:MODE VOLT, (@1)", "Format 2: VOLT, (@1)")
    
    # Test Format 3: space only before channel (like queries)
    smu.write("*RST")
    test_command(smu, ":SOUR:FUNC:MODE VOLT (@1)", "Format 3: VOLT (@1)")
    
    # Test Format 4: Separate command with channel
    smu.write("*RST")
    test_command(smu, ":SOUR1:FUNC:MODE VOLT", "Format 4: SOUR1:FUNC:MODE (channel in path)")
    
    print("\n" + "=" * 60)
    print("Testing SOUR:VOLT with different channel formats")
    print("=" * 60)
    
    # First set mode
    smu.write("*RST")
    smu.write(":SOUR1:FUNC:MODE VOLT")
    
    test_command(smu, ":SOUR:VOLT 1.0", "No channel suffix")
    test_command(smu, ":SOUR:VOLT 1.0, (@1)", "VOLT 1.0, (@1)")
    test_command(smu, ":SOUR:VOLT 1.0 (@1)", "VOLT 1.0 (@1)")
    test_command(smu, ":SOUR1:VOLT 1.0", "SOUR1:VOLT 1.0 (channel in path)")
    
    print("\n" + "=" * 60)
    print("Testing OUTP ON with different channel formats")
    print("=" * 60)
    
    smu.write("*RST")
    smu.write(":SOUR1:FUNC:MODE VOLT")
    smu.write(":SOUR1:VOLT 1.0")
    
    test_command(smu, ":OUTP ON", "No channel suffix")
    smu.write(":OUTP OFF")
    
    test_command(smu, ":OUTP ON, (@1)", "ON, (@1)")
    smu.write(":OUTP OFF")
    
    test_command(smu, ":OUTP ON (@1)", "ON (@1)")
    smu.write(":OUTP OFF")
    
    test_command(smu, ":OUTP1 ON", "OUTP1 ON (channel in command)")
    smu.write(":OUTP1 OFF")
    
    print("\n" + "=" * 60)
    print("Testing complete sequence with SOURn syntax")
    print("=" * 60)
    
    smu.write("*RST")
    test_command(smu, ":SOUR1:FUNC:MODE VOLT", "Set CH1 to voltage mode")
    test_command(smu, ":SOUR1:VOLT 1.0", "Set CH1 voltage to 1.0V")
    test_command(smu, ":SENS1:CURR:PROT 0.01", "Set CH1 current compliance")
    test_command(smu, ":OUTP1 ON", "Enable CH1 output")
    
    # Measure
    print("\nMeasuring...")
    try:
        volt = smu.query(":MEAS:VOLT? (@1)").strip()
        curr = smu.query(":MEAS:CURR? (@1)").strip()
        print(f"  Voltage: {volt} V")
        print(f"  Current: {curr} A")
    except Exception as e:
        print(f"  Measurement error: {e}")
    
    test_command(smu, ":OUTP1 OFF", "Disable CH1 output")
    
    print("\n" + "=" * 60)
    print("Testing Channel 2")
    print("=" * 60)
    
    smu.write("*RST")
    test_command(smu, ":SOUR2:FUNC:MODE VOLT", "Set CH2 to voltage mode")
    test_command(smu, ":SOUR2:VOLT 2.0", "Set CH2 voltage to 2.0V")
    test_command(smu, ":SENS2:CURR:PROT 0.01", "Set CH2 current compliance")
    test_command(smu, ":OUTP2 ON", "Enable CH2 output")
    
    # Measure
    print("\nMeasuring CH2...")
    try:
        volt = smu.query(":MEAS:VOLT? (@2)").strip()
        curr = smu.query(":MEAS:CURR? (@2)").strip()
        print(f"  Voltage: {volt} V")
        print(f"  Current: {curr} A")
    except Exception as e:
        print(f"  Measurement error: {e}")
    
    test_command(smu, ":OUTP2 OFF", "Disable CH2 output")
    
    print("\n" + "=" * 60)
    print("CONCLUSION")
    print("=" * 60)
    print("The B2902A uses SOURn and OUTPn syntax (channel number in command)")
    print("Examples: :SOUR1:VOLT 1.0, :OUTP1 ON, :SOUR2:FUNC:MODE CURR")
    print("Queries use: :MEAS:VOLT? (@1) or :MEAS:CURR? (@2)")
    
    smu.close()
    rm.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
