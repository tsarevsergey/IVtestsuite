import streamlit as st
import yaml
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from api_client import req, BACKEND_URL

st.set_page_config(page_title="Experiment Wizard", page_icon="🧙‍♂️", layout="wide")

st.title("🧙‍♂️ Experiment Wizard")
st.markdown("Generate complex experiment protocols from high-level templates.")

# --- Template Definitions ---

TEMPLATE_DESCRIPTIONS = {
    "Multipixel IV Sweep": "Perform a standard IV sweep on a series of pixels sequentially. Each pixel is connected via relay, swept, and the data is saved.",
    "Dark -> Light (Batch)": "Batch operation: Firstly scans ALL specified pixels in the dark (light source OFF), then scans ALL pixels again with the light source ON. This minimizes relay switching and light source stabilization waits.",
    "Light -> Dark (Batch)": "Batch operation: Firstly scans ALL specified pixels with the light source ON, then scans ALL pixels again in the dark. Useful for measuring decay or stabilization effects."
}

# Helper to parse pixel string
def parse_pixel_string(pixel_str: str) -> List[int]:
    pixels = []
    for part in pixel_str.split(','):
        part = part.strip()
        if not part: continue
        if '-' in part:
            start, end = map(int, part.split('-'))
            pixels.extend(range(start, end + 1))
        else:
            pixels.append(int(part))
    return sorted(list(set(pixels)))

def generate_multipixel_sweep(params: Dict[str, Any]) -> Dict[str, Any]:
    """Generates a YAML protocol for multipixel IV sweep."""
    sample_name = params.get("sample_name", "Sample")
    pixel_list = parse_pixel_string(params.get("pixel_str", "1-6"))
    
    start_v = params.get("start_v", 0.0)
    stop_v = params.get("stop_v", 1.0)
    points = params.get("points", 11)
    delay = params.get("delay", 0.05)
    
    # Advanced
    compliance = params.get("compliance", 0.1)
    nplc = params.get("nplc", 1.0)
    sweep_type = params.get("sweep_type", "double") # single, double
    scale = params.get("scale", "linear")
    direction = params.get("direction", "forward")
    keep_output_on = params.get("keep_output_on", False)
    
    # Construct Protocol
    protocol = {
        "name": f"Multipixel Sweep - {sample_name}",
        "description": f"IV sweep on pixels {pixel_list} for {sample_name}. {start_v}V to {stop_v}V.",
        "version": 1.2,
        "steps": [
            # 1. Connect
            {
                "action": "smu/connect",
                "params": {"mock": False, "channel": 1}
            },
            {
                "action": "relays/connect",
                "params": {"mock": True}
            },
            # 2. Configure
            {
                "action": "smu/configure",
                "params": {"compliance": compliance, "compliance_type": "CURR", "nplc": nplc}
            },
            {
                "action": "smu/source-mode",
                "params": {"mode": "VOLT"}
            },
            {
                 "action": "relays/all-off"
            },
            # 3. Main Loop
            {
                "action": "control/loop",
                "params": {
                    "variable": "pixel",
                    "sequence": pixel_list
                },
                "steps": [
                    {
                        "action": "relays/pixel",
                        "params": {"pixel_id": "$pixel"}
                    },
                    {
                        "action": "wait",
                        "params": {"seconds": 0.5}
                    },
                    {
                        "action": "smu/sweep",
                        "params": {
                            "start": start_v,
                            "stop": stop_v,
                            "points": points,
                            "delay": delay,
                            "sweep_type": sweep_type,
                            "scale": scale,
                            "direction": direction,
                            "compliance": compliance,
                            "nplc": nplc,
                            "keep_output_on": keep_output_on
                        },
                        "capture_as": "iv_data"
                    },
                    {
                        "action": "data/save",
                        "params": {
                            "data": "$iv_data",
                            # String interpolation for filename
                            "filename": f"{sample_name}_{{$pixel}}", 
                            "folder": "./data"
                        }
                    }
                ]
            },
            # 4. Cleanup
            {
                "action": "smu/output",
                "params": {"enabled": False, "channel": 1}
            },
            {
                "action": "smu/output",
                "params": {"enabled": False, "channel": 2}
            },
            {
                "action": "relays/all-off"
            }
        ]
    }
    return protocol


def generate_dark_light_sweep_batch(params: Dict[str, Any], order: str = "dark_first") -> Dict[str, Any]:
    """
    Generates a YAML protocol for batch Dark/Light IV sweep.
    Mode: "dark_first" or "light_first".
    Structure: Loop All Pixels (Mode 1) -> Loop All Pixels (Mode 2).
    """
    sample_name = params.get("sample_name", "Sample")
    pixel_list = parse_pixel_string(params.get("pixel_str", "1-6"))
    
    # Sweep Config (SMU 1 - typically Sweep)
    sweep_ch = params.get("sweep_channel", 1)
    sm1_mode = params.get("sm1_mode", "VOLT")
    sm1_comp = params.get("sm1_compliance", 0.1)
    sm1_comp_type = params.get("sm1_compliance_type", "CURR")
    
    # IV Parameters
    iv_start = params.get("start_v", 0.0)
    iv_stop = params.get("stop_v", 1.0)
    iv_points = params.get("points", 11)
    iv_delay = params.get("delay", 0.05)
    
    # Advanced IV
    nplc = params.get("nplc", 1.0)
    sweep_type = params.get("sweep_type", "double")
    scale = params.get("scale", "linear")
    direction = params.get("direction", "forward")
    
    # Light Config (SMU 2 - typically Bias)
    light_ch = params.get("light_channel", 2)
    sm2_mode = params.get("sm2_mode", "CURR")
    light_current = params.get("light_current", 0.001) 
    sm2_comp = params.get("sm2_compliance", 5.0)
    sm2_comp_type = params.get("sm2_compliance_type", "VOLT")
    
    # Steady State Config
    do_steady = params.get("enable_steady_state", False)
    steady_time = params.get("steady_time", 10.0)
    steady_delay = params.get("steady_delay", 0.1)
    dark_hold_v = params.get("dark_hold_v", 0.0)
    light_hold_v = params.get("light_hold_v", 0.0)
    
    steady_points = int(steady_time / steady_delay)
    if steady_points < 1: steady_points = 1
    
    wait_time = params.get("wait_time", 0.5) # Stabilization wait
    keep_output_on = params.get("keep_output_on", False)
    
    # --- Helper to generate a measurement sequence (Dark or Light) ---
    def make_loop_step(is_light: bool, is_last: bool = False):
        mode_name = "light" if is_light else "dark"
        hold_v = light_hold_v if is_light else dark_hold_v
        
        # Steps inside the pixel loop
        loop_steps = [
            # Select Pixel
            { "action": "relays/pixel", "params": {"pixel_id": "$pixel"} },
            { "action": "wait", "params": {"seconds": wait_time} },
        ]
        
        # 1. Steady State (Optional)
        if do_steady:
             loop_steps.extend([
                # Configure for Hold
                { "action": "smu/configure", "params": {"channel": sweep_ch, "compliance": sm1_comp, "compliance_type": sm1_comp_type, "nplc": nplc} },
                { "action": "smu/source-mode", "params": {"channel": sweep_ch, "mode": sm1_mode} },
                # Sweep (Constant Hold)
                {
                    "action": "smu/sweep",
                    "params": {
                        "channel": sweep_ch,
                        "start": hold_v, "stop": hold_v, "points": steady_points,
                        "delay": steady_delay, "compliance": sm1_comp,
                        "sweep_type": "single", "scale": "linear",
                        "keep_output_on": True # Keep ON for the subsequent IV
                    },
                    "capture_as": f"{mode_name}_steady_data"
                },
                {
                    "action": "data/save",
                    "params": {
                        "data": f"${mode_name}_steady_data",
                        "filename": f"{sample_name}_steady_{hold_v}V_{mode_name}_{{$pixel}}",
                        "folder": "./data"
                    }
                }
             ])
             
        # 2. IV Sweep
        loop_steps.extend([
            { "action": "smu/configure", "params": {"channel": sweep_ch, "compliance": sm1_comp, "compliance_type": sm1_comp_type, "nplc": nplc} },
            { "action": "smu/source-mode", "params": {"channel": sweep_ch, "mode": sm1_mode} },
            {
                "action": "smu/sweep",
                "params": {
                    "channel": sweep_ch,
                    "start": iv_start, "stop": iv_stop, "points": iv_points,
                    "delay": iv_delay, "compliance": sm1_comp, "nplc": nplc,
                    "sweep_type": sweep_type, "scale": scale, "direction": direction,
                    "source_mode": sm1_mode,
                    "keep_output_on": keep_output_on if is_last else False 
                },
                "capture_as": f"{mode_name}_iv_data"
            },
            {
                "action": "data/save",
                "params": {
                    "data": f"${mode_name}_iv_data",
                    "filename": f"{sample_name}_{{$pixel}}{mode_name.upper()}",
                    "folder": "./data"
                }
            }
        ])
        
        return {
            "action": "control/loop",
            "params": {"variable": "pixel", "sequence": pixel_list},
            "steps": loop_steps
        }

    # Sequence Construction
    steps = [
        # Connect
        { "action": "smu/connect", "params": {"mock": False, "channel": 1} },
        { "action": "smu/connect", "params": {"mock": False, "channel": 2} },
        { "action": "relays/connect", "params": {"mock": True} },
        { "action": "relays/all-off" },
    ]
    
    # Define Mode Blocks
    # Define Mode Blocks (Pre-loop setup)
    block_dark = [
        # Ensure Light OFF
        { "action": "smu/output", "params": {"channel": light_ch, "enabled": False} },
    ]
    
    block_light = [
        # Turn Light ON (Bias Ch)
        { "action": "smu/configure", "params": {"channel": light_ch, "compliance": sm2_comp, "compliance_type": sm2_comp_type, "nplc": nplc} },
        { "action": "smu/source-mode", "params": {"channel": light_ch, "mode": sm2_mode} },
        { "action": "smu/set", "params": {"channel": light_ch, "value": light_current} },
        { "action": "smu/output", "params": {"channel": light_ch, "enabled": True} },
        { "action": "wait", "params": {"seconds": 2.0} }, # Warmup
    ]
    
    if order == "dark_first":
        steps.extend(block_dark)
        steps.append(make_loop_step(is_light=False))
        steps.extend(block_light)
        steps.append(make_loop_step(is_light=True, is_last=True))
    else:
        steps.extend(block_light)
        steps.append(make_loop_step(is_light=True))
        steps.extend(block_dark)
        steps.append(make_loop_step(is_light=False, is_last=True))
    
    # Cleanup
    steps.append({ "action": "smu/output", "params": {"channel": sweep_ch, "enabled": False} })
    steps.append({ "action": "smu/output", "params": {"channel": light_ch, "enabled": False} })
    steps.append({ "action": "relays/all-off" })

    return {
        "name": f"{'Dark-Light' if order=='dark_first' else 'Light-Dark'}_{sample_name}",
        "description": f"Batch sweep on pixels {pixel_list}. {order}. SteadyState={do_steady}.",
        "version": 2.0,
        "steps": steps
    }

def generate_dark_light_wrapper(params): return generate_dark_light_sweep_batch(params, "dark_first")
def generate_light_dark_wrapper(params): return generate_dark_light_sweep_batch(params, "light_first")

# --- UI Logic ---

TEMPLATES = {
    "Multipixel IV Sweep": generate_multipixel_sweep,
    "Dark -> Light (Batch)": generate_dark_light_wrapper,
    "Light -> Dark (Batch)": generate_light_dark_wrapper
}

st.sidebar.header("Select Template")
selected_template = st.sidebar.selectbox("Experiment Type", list(TEMPLATES.keys()))

# Display Description
if selected_template in TEMPLATE_DESCRIPTIONS:
    st.info(TEMPLATE_DESCRIPTIONS[selected_template])

st.subheader(f"Configure: {selected_template}")

params = {}
if selected_template == "Multipixel IV Sweep":
    st.markdown("#### Sample settings")
    col1, col2 = st.columns(2)
    with col1:
        params["sample_name"] = st.text_input("Sample Name", "TEST")
    with col2:
        params["pixel_str"] = st.text_input("Pixels (e.g., '1-6', '1,3,5')", "1-6")
        
    st.divider()
    st.markdown("#### Sweep settings")
    col3, col4, col5 = st.columns(3)
    
    with col3:
        params["start_v"] = st.number_input("Start (V)", value=0.0)
        params["stop_v"] = st.number_input("Stop (V)", value=8.0)
        params["points"] = st.number_input("Points", value=41)
        params["keep_output_on"] = st.checkbox("Keep SMU output ON after measurement", value=False)
        
    with col4:
        params["compliance"] = st.number_input("Compliance (A)", value=0.1, format="%.4f")
        params["nplc"] = st.number_input("NPLC (Speed)", value=1.0)
        params["delay"] = st.number_input("Step Delay (s)", value=0.05)
        
    with col5:
        params["sweep_type"] = st.selectbox("Type", ["single", "double"], index=1)
        params["scale"] = st.selectbox("Scale", ["linear", "log"], index=0)
        params["direction"] = st.selectbox("Direction", ["forward", "backward"], index=0)

elif selected_template in ["Dark -> Light (Batch)", "Light -> Dark (Batch)"]:
    st.markdown("#### Sample & Sequence")
    col1, col2 = st.columns(2)
    with col1:
        params["sample_name"] = st.text_input("Sample Name", "TEST")
        params["wait_time"] = st.number_input("Pixel Wait Time (s)", value=0.5, help="Stabilization time after switching relay")
    with col2:
        params["pixel_str"] = st.text_input("Pixels (e.g., '1-6')", "1-6")
        
    st.divider()
    st.markdown("#### IV Sweep Settings")
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        params["sweep_channel"] = st.number_input("Sweep Ch", value=1, min_value=1, max_value=2)
        params["start_v"] = st.number_input("IV Start (V)", value=0.0)
        params["stop_v"] = st.number_input("IV Stop (V)", value=1.0)
        params["keep_output_on"] = st.checkbox("Keep SMU output ON after measurement", value=False)
    with col_s2:
        params["points"] = st.number_input("IV Points", value=21)
        params["compliance"] = st.number_input("IV Compliance (A)", value=0.1, format="%.4f")
        params["nplc"] = st.number_input("NPLC", value=1.0)
    with col_s3:
        params["delay"] = st.number_input("IV Delay (s)", value=0.05)
        params["sweep_type"] = st.selectbox("Type", ["single", "double"], index=1)
        params["scale"] = st.selectbox("Scale", ["linear", "log"], index=0)
        params["direction"] = st.selectbox("Direction", ["forward", "backward"], index=0)
        
    st.divider()
    st.markdown("#### Steady State Measurement")
    params["enable_steady_state"] = st.checkbox("Enable Steady State Measurement")
    
    if params["enable_steady_state"]:
        c_st1, c_st2, c_st3 = st.columns(3)
        with c_st1:
            params["steady_time"] = st.number_input("Duration (s)", value=10.0)
            params["steady_delay"] = st.number_input("Sampling Inteval (s)", value=0.1)
        with c_st2:
            params["dark_hold_v"] = st.number_input("Dark Hold Voltage (V)", value=0.0)
        with c_st3:
             params["light_hold_v"] = st.number_input("Light Hold Voltage (V)", value=0.0)
             
    st.divider()
    st.markdown("#### SMU Configuration")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.write("**SMU 1 (Sweep)**")
        params["sm1_mode"] = st.selectbox("Source Mode (SMU 1)", ["VOLT", "CURR"], index=0)
        params["sm1_compliance"] = st.number_input("Compliance (SMU 1)", value=0.1, format="%.4f")
        params["sm1_compliance_type"] = st.selectbox("Compliance Type (SMU 1)", ["CURR", "VOLT"], index=0 if params["sm1_mode"]=="VOLT" else 1)
        params["sweep_channel"] = st.number_input("Sweep Channel #", value=1, min_value=1, max_value=2)
        
    with col_c2:
        st.write("**SMU 2 (Bias/Light)**")
        params["sm2_mode"] = st.selectbox("Source Mode (SMU 2)", ["VOLT", "CURR"], index=1)
        params["sm2_compliance"] = st.number_input("Compliance (SMU 2)", value=5.0)
        params["sm2_compliance_type"] = st.selectbox("Compliance Type (SMU 2)", ["VOLT", "CURR"], index=0 if params["sm2_mode"]=="CURR" else 1)
        params["light_channel"] = st.number_input("Light Channel #", value=2, min_value=1, max_value=2)

    st.divider()
    st.markdown("#### Light Source Config (Bias Channel)")
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        params["light_current"] = st.number_input("Light Current/Voltage Value", value=0.001, format="%.6f", help="Target value for the bias SMU")
    with col_l2:
        st.empty()

st.divider()

# Generate
if st.button("Generate Protocol"):
    generator = TEMPLATES[selected_template]
    protocol_yaml = generator(params)
    
    st.session_state.generated_yaml = yaml.dump(protocol_yaml, sort_keys=False)
    st.session_state.generated_name = protocol_yaml["name"].lower().replace(' ', '_').replace('-', '_')

if "generated_yaml" in st.session_state:
    st.subheader("Generated YAML")
    st.code(st.session_state.generated_yaml, language="yaml")
    
    col_dl, col_save = st.columns([1, 1])
    
    with col_dl:
        st.download_button(
            "Download YAML", 
            data=st.session_state.generated_yaml,
            file_name=f"{st.session_state.generated_name}.yaml",
            mime="text/yaml"
        )
        
    with col_save:
        filename = st.text_input("Filename (no extension)", st.session_state.generated_name)
        if st.button("Save to Protocols"):
             try:
                user = st.session_state.get("user")
                root = Path(__file__).parent.parent.parent / "protocols"
                
                if user:
                    # Save in user folder
                    user_dir = root / user
                    if not user_dir.exists():
                        user_dir.mkdir(parents=True)
                    filepath = user_dir / f"{filename}.yaml"
                else:
                    filepath = root / f"{filename}.yaml"
                
                # Update the inner protocol name to match the filename
                protocol_data = yaml.safe_load(st.session_state.generated_yaml)
                protocol_data["name"] = filename
                updated_yaml = yaml.dump(protocol_data, sort_keys=False)
                    
                with open(filepath, "w") as f:
                    f.write(updated_yaml)
                st.success(f"Saved to {filepath}")
                
                # Reload cache
                try:
                    import requests
                    requests.post(f"{BACKEND_URL}/protocol/reload")
                except:
                    pass
             except Exception as e:
                st.error(f"Save failed: {e}")
