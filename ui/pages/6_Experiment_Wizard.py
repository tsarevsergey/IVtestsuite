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
                "params": {"compliance": compliance, "nplc": nplc}
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
                            "keep_output_on": True
                        },
                        "capture_as": "iv_data"
                    },
                    {
                        "action": "data/save",
                        "params": {
                            "data": "$iv_data",
                            # String interpolation for filename
                            "filename": f"{sample_name}_pixel_{{$pixel}}", 
                            "folder": "./data"
                        }
                    }
                ]
            },
            # 4. Cleanup
            {
                "action": "smu/output",
                "params": {"enabled": False}
            },
            {
                "action": "relays/all-off"
            }
        ]
    }
    return protocol


# --- UI Logic ---

TEMPLATES = {
    "Multipixel IV Sweep": generate_multipixel_sweep
}

st.sidebar.header("Select Template")
selected_template = st.sidebar.selectbox("Experiment Type", list(TEMPLATES.keys()))

st.subheader(f"Configure: {selected_template}")

params = {}
if selected_template == "Multipixel IV Sweep":
    st.markdown("#### Sample settings")
    col1, col2 = st.columns(2)
    with col1:
        params["sample_name"] = st.text_input("Sample Name", "AA1")
    with col2:
        params["pixel_str"] = st.text_input("Pixels (e.g., '1-6', '1,3,5')", "1-6")
        
    st.divider()
    st.markdown("#### Sweep settings")
    col3, col4, col5 = st.columns(3)
    
    with col3:
        params["start_v"] = st.number_input("Start (V)", value=0.0)
        params["stop_v"] = st.number_input("Stop (V)", value=8.0)
        params["points"] = st.number_input("Points", value=41)
        
    with col4:
        params["compliance"] = st.number_input("Compliance (A)", value=0.1, format="%.4f")
        params["nplc"] = st.number_input("NPLC (Speed)", value=1.0)
        params["delay"] = st.number_input("Step Delay (s)", value=0.05)
        
    with col5:
        params["sweep_type"] = st.selectbox("Type", ["single", "double"], index=1)
        params["scale"] = st.selectbox("Scale", ["linear", "log"], index=0)
        params["direction"] = st.selectbox("Direction", ["forward", "backward"], index=0)


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
                filepath = Path(__file__).parent.parent.parent / "protocols" / f"{filename}.yaml"
                with open(filepath, "w") as f:
                    f.write(st.session_state.generated_yaml)
                st.success(f"Saved to {filepath}")
                
                # Reload cache
                try:
                    import requests
                    requests.post(f"{BACKEND_URL}/protocol/reload")
                except:
                    pass
             except Exception as e:
                st.error(f"Save failed: {e}")
