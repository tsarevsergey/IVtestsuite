import streamlit as st
import json
from ui.api_client import req, BACKEND_URL

st.set_page_config(page_title="API Tester", page_icon="🧪", layout="wide")

st.title("🧪 API Tester")
st.markdown("Directly interact with the IV Test Software Backend API.")

# --- Endpoint Definitions ---
ENDPOINTS = {
    "Status": {
        "Health Check": {"method": "GET", "path": "/health", "params": {}},
        "Get Status": {"method": "GET", "path": "/status", "params": {}},
        "Abort Run": {"method": "POST", "path": "/abort", "params": {}},
        "Reset State": {"method": "POST", "path": "/reset", "params": {}},
        "Arm System": {"method": "POST", "path": "/arm", "params": {}},
        "Start Run": {"method": "POST", "path": "/start", "params": {}},
        "Complete Run": {"method": "POST", "path": "/complete", "params": {}},
    },
    "SMU": {
        "Get SMU Status": {"method": "GET", "path": "/smu/status", "params": {}},
        "Connect SMU": {
            "method": "POST",
            "path": "/smu/connect",
            "params": {
                "address": {"type": "str", "default": "USB0::0x0957::0xCD18::MY51143841::INSTR"},
                "mock": {"type": "bool", "default": True},
                "channel": {"type": "select", "options": [1, 2], "default": 1},
            }
        },
        "Disconnect SMU": {"method": "POST", "path": "/smu/disconnect", "params": {}},
        "Configure SMU": {
            "method": "POST",
            "path": "/smu/configure",
            "params": {
                "compliance": {"type": "float", "default": 0.1, "min": 0.0},
                "compliance_type": {"type": "select", "options": ["CURR", "VOLT"], "default": "CURR"},
                "nplc": {"type": "float", "default": 1.0, "min": 0.01, "max": 100.0},
            }
        },
        "Set Source Mode": {
            "method": "POST",
            "path": "/smu/source-mode",
            "params": {"mode": {"type": "select", "options": ["VOLT", "CURR"], "default": "VOLT"}}
        },
        "Set Value": {
            "method": "POST",
            "path": "/smu/set",
            "params": {"value": {"type": "float", "default": 0.0}}
        },
        "Control Output": {
            "method": "POST",
            "path": "/smu/output",
            "params": {"enabled": {"type": "bool", "default": False}}
        },
        "Single Measurement": {"method": "GET", "path": "/smu/measure", "params": {}},
        "Run IV Sweep": {
            "method": "POST",
            "path": "/smu/sweep",
            "params": {
                "start": {"type": "float", "default": 0.0},
                "stop": {"type": "float", "default": 8.0},
                "steps": {"type": "int", "default": 11, "min": 2, "max": 1000},
                "compliance": {"type": "float", "default": 0.01, "min": 0.0},
                "delay": {"type": "float", "default": 0.05, "min": 0.0},
            }
        },
    },
    "Relays": {
        "Get Relay Status": {"method": "GET", "path": "/relays/status", "params": {}},
        "Connect Relays": {
            "method": "POST",
            "path": "/relays/connect",
            "params": {
                "port": {"type": "str", "default": "COM3"},
                "mock": {"type": "bool", "default": True},
            }
        },
        "Disconnect Relays": {"method": "POST", "path": "/relays/disconnect", "params": {}},
        "Select Pixel": {
            "method": "POST",
            "path": "/relays/pixel",
            "params": {"pixel_id": {"type": "int", "default": 0, "min": 0, "max": 7}}
        },
        "Select LED": {
            "method": "POST",
            "path": "/relays/led",
            "params": {"channel_id": {"type": "int", "default": 0, "min": 0, "max": 3}}
        },
        "All Relays Off": {"method": "POST", "path": "/relays/all-off", "params": {}},
    },
    "Protocol": {
        "Run Protocol": {
            "method": "POST",
            "path": "/protocol/run",
            "params": {
                "pixels": {"type": "list_int", "default": "0,1"},
                "modes": {"type": "multiselect", "options": ["dark", "light"], "default": ["dark", "light"]},
                "led_channel": {"type": "int", "default": 0, "min": 0, "max": 3},
                "start_voltage": {"type": "float", "default": 0.0},
                "stop_voltage": {"type": "float", "default": 8.0},
                "num_points": {"type": "int", "default": 41, "min": 2, "max": 500},
                "compliance": {"type": "float", "default": 0.1, "min": 0.0},
                "delay": {"type": "float", "default": 0.1, "min": 0.0},
                "output_dir": {"type": "str", "default": "data"},
                "sample_name": {"type": "str", "default": "sample_001"},
            }
        },
        "Get Protocol Status": {"method": "GET", "path": "/protocol/status", "params": {}},
        "Abort Protocol": {"method": "POST", "path": "/protocol/abort", "params": {}},
    }
}

# --- Sidebar Selection ---
st.sidebar.header("Endpoint Configuration")
category = st.sidebar.selectbox("Category", list(ENDPOINTS.keys()))
endpoint_name = st.sidebar.selectbox("Endpoint", list(ENDPOINTS[category].keys()))

endpoint = ENDPOINTS[category][endpoint_name]
method = endpoint["method"]
path = endpoint["path"]

# --- Parameter Inputs ---
st.header(f"{endpoint_name} ({method} {path})")

payload = {}
if endpoint["params"]:
    st.subheader("Payload Parameters")
    cols = st.columns(2)
    for i, (param_name, param_info) in enumerate(endpoint["params"].items()):
        col = cols[i % 2]
        p_type = param_info["type"]
        p_default = param_info["default"]
        
        if p_type == "str":
            payload[param_name] = col.text_input(param_name, value=p_default)
        elif p_type == "int":
            kwargs = {"value": int(p_default), "step": 1}
            if "min" in param_info: kwargs["min_value"] = int(param_info["min"])
            if "max" in param_info: kwargs["max_value"] = int(param_info["max"])
            payload[param_name] = col.number_input(param_name, **kwargs)
        elif p_type == "float":
            kwargs = {"value": float(p_default), "step": 0.01, "format": "%.4f"}
            if "min" in param_info: kwargs["min_value"] = float(param_info["min"])
            if "max" in param_info: kwargs["max_value"] = float(param_info["max"])
            payload[param_name] = col.number_input(param_name, **kwargs)
        elif p_type == "bool":
            payload[param_name] = col.checkbox(param_name, value=p_default)
        elif p_type == "select":
            payload[param_name] = col.selectbox(param_name, options=param_info["options"], index=param_info["options"].index(p_default))
        elif p_type == "multiselect":
            payload[param_name] = col.multiselect(param_name, options=param_info["options"], default=p_default)
        elif p_type == "list_int":
            val_str = col.text_input(param_name, value=p_default)
            payload[param_name] = [int(x.strip()) for x in val_str.split(",") if x.strip()]

# --- Tabs: Request Preview & Execute ---
tab_preview, tab_execute = st.tabs(["📄 Request Preview", "🚀 Execute Request"])

with tab_preview:
    st.markdown("### Endpoint URL")
    st.code(f"{BACKEND_URL}{path}")
    
    st.markdown("### HTTP Method")
    st.code(method)
    
    if method == "POST":
        st.markdown("### JSON Payload")
        st.json(payload)
    else:
        st.info("GET requests do not have a JSON payload.")

with tab_execute:
    if st.button("Execute Request", type="primary"):
        with st.spinner("Executing..."):
            response = req(method, path, payload if method == "POST" else None)
            
            st.markdown("### Response Status")
            if response.get("success", True):
                st.success("Success")
            else:
                st.error("Error")
            
            st.markdown("### JSON Response")
            st.json(response)
