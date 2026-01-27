import sys
import os
import time
import numpy as np
import matplotlib.pyplot as plt
import json

# Ensure we can import from the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from smu_controller import SMUController, InstrumentState
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def main():
    address = "USB0::0x0957::0xCD18::MY51143841::INSTR"
    print(f"--- IV Scan and Plot (Direct Control) ---")
    
    # User Request: 0 to 6V, 0.5V step, 10mA compliance
    start = 0.0
    stop = 6.0
    steps = 13
    compliance = 0.01
    
    # Create Voltage Points
    points = np.linspace(start, stop, steps)
    
    smu = SMUController(address=address, mock=False)
    
    results = []
    
    try:
        print(f"Connecting to {address}...")
        smu.connect()
        
        if smu.state == InstrumentState.ERROR:
             print("Failed to connect properly (In Error State).")
             sys.exit(1)

        print("Configuring SMU...")
        smu.set_source_mode("VOLT")
        smu.set_compliance(compliance, "CURR")
        smu.enable_output()
        
        print(f"Starting sweep: {start}V -> {stop}V ({steps} points)...")
        
        for v in points:
            smu.set_voltage(v)
            time.sleep(0.1) # Small settling time
            meas = smu.measure()
            meas['set_voltage'] = v
            results.append(meas)
            # print(f" {v:.2f}V -> {meas['current']:.2e}A") # Optional verbose logging
            
        print("Sweep Complete.")
        
    except Exception as e:
        print(f"Runtime Error: {e}")
    finally:
        print("Shutting down output...")
        try:
            smu.disable_output()
            smu.disconnect()
        except:
            pass

    if not results:
        print("No data collected.")
        return

    print(f"Collected {len(results)} points.")
    
    # Prepare data for plotting
    voltages = [r["set_voltage"] for r in results]
    measured_v = [r["voltage"] for r in results]
    currents = [abs(r["current"]) for r in results] 
    
    # Handle zero current for log scale
    currents_log = [max(c, 1e-12) for c in currents]
    
    # Plotting
    plt.figure(figsize=(10, 6))
    plt.plot(measured_v, currents_log, marker='o', linestyle='-', color='b', label='IV Sweep')
    
    plt.yscale('log')
    plt.xlabel('Measured Voltage (V)')
    plt.ylabel('Abs Current (A)')
    plt.title('SMU IV Sweep (0V to 6V, 10mA Compliance)')
    plt.grid(True, which="both", ls="-", alpha=0.5)
    plt.legend()
    
    # Save the plot
    plot_path = os.path.abspath("iv_sweep_plot.png")
    plt.savefig(plot_path)
    print(f"Plot saved to: {plot_path}")
    
    # Save data to JSON for record
    with open("iv_data.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Data saved to iv_data.json")

if __name__ == "__main__":
    main()
