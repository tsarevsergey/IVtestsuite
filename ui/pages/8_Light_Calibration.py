"""
Light Source Calibration Page

Performs LED current sweep and measures Si photodiode response to generate
a calibration curve for LED current → irradiance conversion.
"""

import streamlit as st
import numpy as np
import pandas as pd
import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from api_client import req, BACKEND_URL

st.set_page_config(page_title="Light Calibration", page_icon="💡", layout="wide")

st.title("💡 Light Source Calibration")
st.markdown("Generate calibration curve: LED current → Irradiance (W/cm²)")

# --- Settings persistence ---
SETTINGS_FILE = Path(__file__).parent.parent.parent / "settings" / "calibration_settings.json"

def load_settings():
    """Load calibration settings from file."""
    defaults = {
        "led_wavelengths": [461, 562, 620],
        "default_calibration_name": "calBLUE",
        "pd_channel": 2,
        "led_channel": 1,
        "led_start": 0.001,
        "led_stop": 0.100,
        "num_points": 20,
        "delay": 1.0,
        "nplc": 4.0,
        "pd_bias": 0.0,
        "led_compliance": 9.0,
        "pd_compliance": 0.01,
        "pd_area_cm2": 1.0
    }
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                saved = json.load(f)
                defaults.update(saved)
        except:
            pass
    return defaults

def save_settings(settings):
    """Save calibration settings to file."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

settings = load_settings()

# --- Configuration ---
st.subheader("⚙️ Configuration")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Calibration Output**")
    calibration_name = st.text_input("Calibration Name", value=settings.get("default_calibration_name", "calBLUE"), 
                                      help="Name for the output file (e.g., calBLUE.txt)")
    
    st.markdown("**Channel Assignment**")
    pd_channel = st.number_input("Photodiode Channel", value=settings.get("pd_channel", 2), min_value=1, max_value=2)
    led_channel = st.number_input("LED Channel", value=settings.get("led_channel", 1), min_value=1, max_value=2)

with col2:
    st.markdown("**Sweep Parameters**")
    led_start = st.number_input("LED Start Current (A)", value=settings.get("led_start", 0.001), format="%.4f")
    led_stop = st.number_input("LED Stop Current (A)", value=settings.get("led_stop", 0.100), format="%.4f")
    num_points = st.number_input("Number of Points", value=settings.get("num_points", 20), min_value=2, max_value=100)

with col3:
    st.markdown("**Measurement Settings**")
    delay = st.number_input("Delay per Point (s)", value=settings.get("delay", 1.0), min_value=0.1)
    nplc = st.number_input("NPLC", value=settings.get("nplc", 4.0), min_value=0.1)
    pd_bias = st.number_input("PD Bias Voltage (V)", value=settings.get("pd_bias", 0.0))
    led_compliance = st.number_input("LED Compliance (V)", value=settings.get("led_compliance", 5.0), min_value=0.1, max_value=20.0, help="Max voltage for LED current source")
    pd_compliance = st.number_input("PD Compliance (A)", value=settings.get("pd_compliance", 0.01), format="%.4f", min_value=0.0001, help="Max current for PD voltage source")

st.divider()

# --- Si Diode Responsivity ---
st.subheader("📊 Si Diode Parameters")
col_si1, col_si2 = st.columns(2)

with col_si1:
    # LED wavelength selector from preset values
    led_wavelengths = settings.get("led_wavelengths", [461, 562, 620])
    led_wavelength = st.selectbox("LED Wavelength (nm)", options=led_wavelengths, 
                                   help="Select from available LED wavelengths")
    pd_area_cm2 = st.number_input("PD Active Area (cm²)", value=settings.get("pd_area_cm2", 0.01), format="%.4f")

with col_si2:
    # Load Si responsivity
    si_file = Path(__file__).parent.parent.parent / "SiDiodeResponsivity.csv"
    if si_file.exists():
        si_data = np.loadtxt(si_file, delimiter=',')
        wavelengths_data = si_data[:, 0]
        responsivities = si_data[:, 1]
        
        # Interpolate to get responsivity at selected wavelength
        responsivity = float(np.interp(led_wavelength, wavelengths_data, responsivities))
        st.metric("Si Responsivity", f"{responsivity:.3f} A/W")
    else:
        responsivity = 0.2
        st.warning("SiDiodeResponsivity.csv not found, using default 0.2 A/W")

st.divider()

# --- Run Calibration ---
st.subheader("🚀 Run Calibration")

# Session state for results
if "cal_data" not in st.session_state:
    st.session_state.cal_data = None
if "cal_running" not in st.session_state:
    st.session_state.cal_running = False
if "cal_error" not in st.session_state:
    st.session_state.cal_error = None

# Generate LED current points preview
led_currents = np.linspace(led_start, led_stop, num_points)
st.write(f"Will measure {num_points + 1} points (including dark at 0A)")

col_btn, col_status = st.columns([1, 3])

with col_btn:
    run_clicked = st.button("▶️ Start Calibration", disabled=st.session_state.cal_running, type="primary")

with col_status:
    if st.session_state.cal_running:
        st.info("⏳ Calibration in progress...")
    elif st.session_state.cal_error:
        st.error(f"❌ {st.session_state.cal_error}")
    elif st.session_state.get("cal_message"):
        st.success(f"✅ {st.session_state.cal_message}")
    elif st.session_state.cal_data is not None:
        st.success("✅ Calibration complete!")

if run_clicked:
    st.session_state.cal_running = True
    st.session_state.cal_error = None
    st.session_state.cal_message = None
    
    with st.spinner("Running calibration via API..."):
        try:
            # Call the calibration API endpoint (backend saves the file)
            # Use longer timeout since calibration can take several minutes
            response = req("POST", "/calibration/run", json_data={
                "calibration_name": calibration_name,
                "led_channel": int(led_channel),
                "pd_channel": int(pd_channel),
                "led_start": float(led_start),
                "led_stop": float(led_stop),
                "num_points": int(num_points),
                "delay": float(delay),
                "nplc": float(nplc),
                "pd_bias": float(pd_bias),
                "led_compliance": float(led_compliance),
                "pd_compliance": float(pd_compliance),
                "responsivity": float(responsivity),
                "pd_area_cm2": float(pd_area_cm2)
            }, timeout=300)
            
            if response:
                if response.get("success"):
                    # Convert response points to DataFrame
                    points = response.get("points", [])
                    df = pd.DataFrame(points)
                    st.session_state.cal_data = df
                    st.session_state.dark_current = response.get("dark_current", 0)
                    
                    # Build success message
                    msg = response.get("message", "Calibration complete!")
                    if response.get("saved_file"):
                        msg += f" Saved to: {Path(response.get('saved_file')).name}"
                    st.session_state.cal_message = msg
                    
                    # Save current settings
                    save_settings({
                        "led_wavelengths": led_wavelengths,
                        "default_calibration_name": calibration_name,
                        "pd_channel": pd_channel,
                        "led_channel": led_channel,
                        "led_start": led_start,
                        "led_stop": led_stop,
                        "num_points": num_points,
                        "delay": delay,
                        "nplc": nplc,
                        "pd_bias": pd_bias,
                        "led_compliance": led_compliance,
                        "pd_compliance": pd_compliance,
                        "pd_area_cm2": pd_area_cm2
                    })
                else:
                    # API returned error
                    st.session_state.cal_error = response.get("error") or response.get("message") or "Calibration failed"
            else:
                st.session_state.cal_error = "No response from API"
                
        except Exception as e:
            st.session_state.cal_error = f"Request failed: {str(e)}"
    
    st.session_state.cal_running = False
    st.rerun()

# --- Display Results ---
if st.session_state.cal_data is not None and not st.session_state.cal_data.empty:
    st.divider()
    st.subheader("📈 Results")
    
    df = st.session_state.cal_data
    dark_current = st.session_state.get("dark_current", 0)
    
    st.info(f"Dark current: {dark_current*1e9:.2f} nA")
    
    # Only show charts if DataFrame has required columns
    if "led_current" in df.columns and "irradiance" in df.columns and "pd_current_corrected" in df.columns and len(df) > 0:
        col_plot1, col_plot2 = st.columns(2)
        
        with col_plot1:
            st.markdown("**LED Current vs Irradiance**")
            try:
                st.line_chart(df.set_index("led_current")["irradiance"])
            except Exception as e:
                st.warning(f"Could not plot irradiance: {e}")
        
        with col_plot2:
            st.markdown("**LED Current vs PD Current (corrected)**")
            try:
                st.line_chart(df.set_index("led_current")["pd_current_corrected"])
            except Exception as e:
                st.warning(f"Could not plot PD current: {e}")
    else:
        st.warning("No valid calibration data to plot")
    
    st.markdown("**Raw Data**")
    st.dataframe(df, use_container_width=True)
    
    st.divider()
    st.subheader("💾 Manual Save")
    
    col_s1, col_s2 = st.columns(2)
    
    with col_s1:
        manual_cal_name = st.text_input("Filename", value=calibration_name, key="manual_save_name")
    
    with col_s2:
        save_path = Path(__file__).parent.parent.parent / f"{manual_cal_name}.txt"
        st.write(f"Will save to: `{save_path.name}`")
    
    if st.button("💾 Save Calibration File"):
        try:
            # Save 3-column format: LED current, PD current, irradiance
            save_data = df[["led_current", "pd_current_corrected", "irradiance"]].values
            np.savetxt(save_path, save_data, delimiter='\t', 
                      header="LED_Current(A)\tPD_Current(A)\tIrradiance(W/cm2)",
                      comments='')
            st.success(f"✅ Saved to {save_path}")
        except Exception as e:
            st.error(f"Save failed: {e}")
