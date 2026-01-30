import streamlit as st
import yaml
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from api_client import req, BACKEND_URL

st.set_page_config(page_title="Protocol Builder", page_icon="🏗️", layout="wide")

st.title("🏗️ Protocol Builder")
st.markdown("Visually compose measurement protocols and export to YAML.")

# --- Action Definitions ---
# Schema for each action to generate UI forms
ACTIONS = {
    "Communication": {
        "smu/connect": {
            "description": "Connect to SMU",
            "params": {
                "mock": {"type": "bool", "default": False, "label": "Use Mock Mode"},
                "channel": {"type": "int", "default": 1, "min": 1, "max": 2, "label": "Channel"}
            }
        },
        "smu/disconnect": {
            "description": "Disconnect from SMU",
            "params": {}
        },
        "relays/connect": {
            "description": "Connect to Relay Controller",
            "params": {
                "mock": {"type": "bool", "default": False, "label": "Use Mock Mode"}
            }
        },
        "relays/disconnect": {
            "description": "Disconnect from Relays",
            "params": {}
        }
    },
    "SMU Configuration": {
        "smu/configure": {
            "description": "Set Compliance & Speed",
            "params": {
                "channel": {"type": "int", "default": 1, "min": 1, "max": 2, "label": "Channel"},
                "compliance": {"type": "float", "default": 0.1, "label": "Compliance Limit"},
                "compliance_type": {"type": "select", "options": ["CURR", "VOLT"], "default": "CURR", "label": "Compliance Type"},
                "nplc": {"type": "float", "default": 1.0, "label": "NPLC (Speed)"}
            }
        },
        "smu/source-mode": {
            "description": "Set Source Mode",
            "params": {
                "channel": {"type": "int", "default": 1, "min": 1, "max": 2, "label": "Channel"},
                "mode": {"type": "select", "options": ["VOLT", "CURR"], "default": "VOLT", "label": "Source Mode"}
            }
        },
        "smu/output": {
            "description": "Enable/Disable Output",
            "params": {
                "channel": {"type": "int", "default": 1, "min": 1, "max": 2, "label": "Channel"},
                "enabled": {"type": "bool", "default": True, "label": "Output Enabled"}
            }
        }
    },
    "SMU Operations": {
        "smu/set": {
            "description": "Set Source Value",
            "params": {
                "value": {"type": "float", "default": 0.0, "label": "Value (V or A)"}
            }
        },
        "smu/measure": {
            "description": "Single Measurement",
            "params": {},
            "can_capture": True
        },
        "smu/sweep": {
            "description": "Single Channel IV Sweep",
            "params": {
                "channel": {"type": "int", "default": 1, "min": 1, "max": 2, "label": "Channel"},
                "start": {"type": "float", "default": 0.0, "label": "Start (V/A)"},
                "stop": {"type": "float", "default": 1.0, "label": "Stop (V/A)"},
                "points": {"type": "int", "default": 11, "label": "Points"},
                "delay": {"type": "float", "default": 0.1, "label": "Delay (s)"},
                "compliance": {"type": "float", "default": 0.1, "label": "Compliance"},
                
                # Advanced Params
                "scale": {"type": "select", "options": ["linear", "log"], "default": "linear", "label": "Scale"},
                "direction": {"type": "select", "options": ["forward", "backward"], "default": "forward", "label": "Direction"},
                "sweep_type": {"type": "select", "options": ["single", "double"], "default": "single", "label": "Type (Single/Double)"},
                "keep_output_on": {"type": "bool", "default": False, "label": "Keep Output On"}
            },
            "can_capture": True
        },
        "smu/bias-sweep": {
            "description": "Bias Ch A, Sweep Ch B",
            "params": {
                "bias_channel": {"type": "int", "default": 2, "label": "Bias Ch ID"},
                "bias_source_mode": {"type": "select", "options": ["VOLT", "CURR"], "default": "VOLT", "label": "Bias Mode"},
                "bias_value": {"type": "float", "default": 0.0, "label": "Bias Value"},
                "bias_compliance": {"type": "float", "default": 0.1, "label": "Bias Compliance"},
                
                "sweep_channel": {"type": "int", "default": 1, "label": "Sweep Ch ID"},
                "sweep_source_mode": {"type": "select", "options": ["VOLT", "CURR"], "default": "VOLT", "label": "Sweep Mode"},
                "start": {"type": "float", "default": 0.0, "label": "Sweep Start"},
                "stop": {"type": "float", "default": 1.0, "label": "Sweep Stop"},
                "points": {"type": "int", "default": 11, "label": "Points"},
                "sweep_compliance": {"type": "float", "default": 0.1, "label": "Sweep Compliance"},
                
                "delay": {"type": "float", "default": 0.1, "label": "Delay (s)"},
                "keep_output_on": {"type": "bool", "default": False, "label": "Keep On"}
            },
            "can_capture": True
        },
        "smu/list-sweep": {
            "description": "Single Channel List Sweep",
            "params": {
                "channel": {"type": "int", "default": 1, "min": 1, "max": 2, "label": "Channel"},
                "points": {"type": "code", "default": "[0.0, 0.5, 1.0, 0.5, 0.0]", "label": "Points List"},
                "source_mode": {"type": "select", "options": ["VOLT", "CURR"], "default": "VOLT", "label": "Source Mode"},
                "delay": {"type": "float", "default": 0.05, "label": "Delay (s)"},
                "compliance": {"type": "float", "default": 0.1, "label": "Compliance"},
                "nplc": {"type": "float", "default": 1.0, "label": "NPLC"}
            },
            "can_capture": True
        },
        "smu/simultaneous-list-sweep": {
            "description": "Custom List Sweep",
            "params": {
                 "ch1_points": {"type": "code", "default": "[0.0, 0.5, 1.0]", "label": "Ch1 Points (List or None)"},
                 "ch2_points": {"type": "code", "default": "[0.0, 0.2, 0.4]", "label": "Ch2 Points (List or None)"},
                 "delay": {"type": "float", "default": 0.05, "label": "Delay (s)"},
                 "compliance": {"type": "float", "default": 0.1, "label": "Compliance"}
            },
            "can_capture": True
        },
        "smu/simultaneous-sweep-custom": {
            "description": "Simultaneous 2-Ch Sweep",
            "params": {
                "ch1_start": {"type": "float", "default": 0.0, "label": "Ch1 Start (V)"},
                "ch1_stop": {"type": "float", "default": 1.0, "label": "Ch1 Stop (V)"},
                "ch2_start": {"type": "float", "default": 0.0, "label": "Ch2 Start (V)"},
                "ch2_stop": {"type": "float", "default": 1.0, "label": "Ch2 Stop (V)"},
                "points": {"type": "int", "default": 11, "label": "Points (Shared)"},
                "scale": {"type": "select", "options": ["linear", "log"], "default": "linear", "label": "Scale"},
                "delay": {"type": "float", "default": 0.05, "label": "Delay (s)"},
                "compliance": {"type": "float", "default": 0.1, "label": "Compliance"}
            },
            "can_capture": True
        }
    },
    "Relay Control": {
        "relays/pixel": {
            "description": "Select Pixel",
            "params": {
                "pixel_id": {"type": "int", "default": 0, "label": "Pixel ID (0-7)"}
            }
        },
        "relays/led": {
            "description": "Select LED",
            "params": {
                "channel_id": {"type": "int", "default": 0, "label": "LED Channel"}
            }
        },
        "relays/all-off": {
            "description": "Turn All Relays OFF",
            "params": {}
        }
    },
    "Utility": {
        "wait": {
            "description": "Wait / Delay",
            "params": {
                "seconds": {"type": "float", "default": 1.0, "label": "Seconds"}
            }
        },
        "data/save": {
            "description": "Save Captured Data",
            "params": {
                "data": {"type": "var_ref", "default": "$iv_data", "label": "Variable to Save"},
                "filename": {"type": "str", "default": "data_output", "label": "Filename"},
                "folder": {"type": "str", "default": "./data", "label": "Folder"}
            }
        }
    }
}

# --- State Management ---
if "protocol_steps" not in st.session_state:
    st.session_state.protocol_steps = []

if "protocol_name" not in st.session_state:
    st.session_state.protocol_name = "New Protocol"

if "protocol_desc" not in st.session_state:
    st.session_state.protocol_desc = "Created with Protocol Builder"

def add_step(action_name, category):
    schema = ACTIONS[category][action_name]
    new_step = {
        "action": action_name,
        "params": {k: v.get("default") for k, v in schema["params"].items()},
        "id": len(st.session_state.protocol_steps) # Simple ID
    }
    st.session_state.protocol_steps.append(new_step)

def remove_step(index):
    st.session_state.protocol_steps.pop(index)

def move_step(index, direction):
    if direction == "up" and index > 0:
        st.session_state.protocol_steps[index], st.session_state.protocol_steps[index-1] = \
            st.session_state.protocol_steps[index-1], st.session_state.protocol_steps[index]
    elif direction == "down" and index < len(st.session_state.protocol_steps) - 1:
        st.session_state.protocol_steps[index], st.session_state.protocol_steps[index+1] = \
            st.session_state.protocol_steps[index+1], st.session_state.protocol_steps[index]

# --- UI Layout ---

# Sidebar: Action Palette
with st.sidebar:
    st.header("Add Actions")
    for category, actions in ACTIONS.items():
        with st.expander(category, expanded=True):
            for action_name, schema in actions.items():
                if st.button(f"➕ {action_name.split('/')[-1]}", key=f"add_{action_name}", help=schema["description"]):
                    add_step(action_name, category)

# Main Area: Protocol Steps
col_builder, col_preview = st.columns([3, 2])

with col_builder:
    st.subheader("Protocol Sequence")
    
    st.session_state.protocol_name = st.text_input("Protocol Name", st.session_state.protocol_name)
    st.session_state.protocol_desc = st.text_area("Description", st.session_state.protocol_desc)
    
    st.divider()
    
    if not st.session_state.protocol_steps:
        st.info("No steps added. Click actions in the sidebar to build your protocol.")
        
    for i, step in enumerate(st.session_state.protocol_steps):
        action_name = step["action"]
        
        # Find schema
        schema = None
        for cat in ACTIONS.values():
            if action_name in cat:
                schema = cat[action_name]
                break
        
        with st.expander(f"Step {i+1}: {action_name}", expanded=True):
            cols = st.columns([8, 1, 1])
            with cols[0]:
                st.caption(schema["description"])
            with cols[1]:
                if st.button("⬆️", key=f"up_{i}"):
                    move_step(i, "up")
                    st.rerun()
            with cols[2]:
                if st.button("🗑️", key=f"del_{i}"):
                    remove_step(i)
                    st.rerun()
            
            # Param Form
            params = step["params"]
            for param_key, param_conf in schema["params"].items():
                label = param_conf["label"]
                p_type = param_conf["type"]
                
                if p_type == "bool":
                    params[param_key] = st.checkbox(label, value=params[param_key], key=f"p_{i}_{param_key}")
                elif p_type == "int":
                    params[param_key] = st.number_input(label, value=int(params[param_key]), step=1, key=f"p_{i}_{param_key}")
                elif p_type == "float":
                    params[param_key] = st.number_input(label, value=float(params[param_key]), step=0.1, format="%.4f", key=f"p_{i}_{param_key}")
                elif p_type == "str":
                    params[param_key] = st.text_input(label, value=params[param_key], key=f"p_{i}_{param_key}")
                elif p_type == "var_ref":
                    params[param_key] = st.text_input(label, value=params[param_key], help="Use $variable_name", key=f"p_{i}_{param_key}")
                elif p_type == "select":
                    params[param_key] = st.selectbox(label, options=param_conf["options"], index=param_conf["options"].index(params[param_key]), key=f"p_{i}_{param_key}")
                elif p_type == "code":
                    val_str = st.text_area(label, value=str(params[param_key]), height=100, key=f"p_{i}_{param_key}", help="Enter valid JSON/YAML structure")
                    try:
                        # Try to parse as YAML/JSON so it dumps correctly
                        parsed = yaml.safe_load(val_str)
                        params[param_key] = parsed
                    except:
                        # Fallback to string if invalid (will likely cause runtime error later, but UI stays responsive)
                        params[param_key] = val_str

            # Capture Variable
            if schema.get("can_capture", False):
                capture = step.get("capture_as", "")
                enabled = st.checkbox("Capture Output", value=bool(capture), key=f"cap_en_{i}")
                if enabled:
                    step["capture_as"] = st.text_input("Variable Name", value=capture or "result", key=f"cap_val_{i}")
                elif "capture_as" in step:
                    del step["capture_as"]

# YAML Preview & Save
with col_preview:
    st.subheader("YAML Preview")
    
    protocol_data = {
        "name": st.session_state.protocol_name,
        "description": st.session_state.protocol_desc,
        "version": 1.0,
        "steps": st.session_state.protocol_steps
    }
    
    yaml_str = yaml.dump(protocol_data, sort_keys=False, default_flow_style=False)
    st.code(yaml_str, language="yaml")
    
    st.download_button(
        "Download YAML",
        data=yaml_str,
        file_name=f"{st.session_state.protocol_name.lower().replace(' ', '_')}.yaml",
        mime="text/yaml"
    )
    
    st.divider()
    
    # Save to Server
    filename = st.text_input("Filename (no extension)", st.session_state.protocol_name.lower().replace(" ", "_"))
    if st.button("Save to Server"):
        # We can implement a save endpoint or just notify user to move the file
        # For now, let's just create the file directly via python as we are local
        try:
            user = st.session_state.get("user")
            root = Path(__file__).parent.parent.parent / "protocols"
            
            if user:
                user_dir = root / user
                if not user_dir.exists():
                    user_dir.mkdir(parents=True)
                filepath = user_dir / f"{filename}.yaml"
            else:
                filepath = root / f"{filename}.yaml"
                
            with open(filepath, "w") as f:
                f.write(yaml_str)
            st.success(f"Saved to {filepath}")
            
            # Reload cache
            try:
                import requests
                requests.post(f"{BACKEND_URL}/protocol/reload")
            except:
                pass
                
        except Exception as e:
            st.error(f"Save failed: {e}")
