import streamlit as st
import requests
import yaml
import time
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from api_client import BACKEND_URL
BACKEND_URL = "http://127.0.0.1:5000"  # Force 127.0.0.1 for reliability

st.set_page_config(page_title="Protocol Runner", page_icon="📈", layout="wide")
st.title("📈 Protocol Runner")

# --- User Context & Filtering ---
user = st.session_state.get("user")
if user:
    st.sidebar.success(f"Session: **{user}**")
else:
    st.sidebar.warning("No user selected")
    if st.sidebar.button("Go to Login"):
        st.switch_page("app.py")

# --- Helper Functions ---
def load_protocols_list():
    try:
        resp = requests.get(f"{BACKEND_URL}/protocol/list")
        if resp.status_code == 200:
            return resp.json()["protocols"]
    except Exception as e:
        st.error(f"Failed to load protocols: {e}")
    return []

def get_protocol_content(proto_id):
    # Try loading from local file system since we share the mount
    # Valid for local deployment
    try:
        # id is "subdir/name"
        # We need to find the file from the list or guess
        # Let's search recursively in protocols/
        root = Path(__file__).parent.parent.parent / "protocols"
        # Try direct match first (if id matches rel path)
        p = root / f"{proto_id}.yaml"
        if p.exists():
            with open(p, "r") as f:
                return yaml.safe_load(f)
        
        # Fallback to searching
        for f in root.glob("**/*.yaml"):
            rel = f.relative_to(root).with_suffix("").as_posix()
            if rel == proto_id:
                with open(f, "r") as f:
                    return yaml.safe_load(f)
    except Exception as e:
        st.error(f"Error reading protocol file: {e}")
    return None

def find_all_steps(steps, target_action):
    """Recursively find all steps with given action."""
    found = []
    for step in steps:
        if step.get("action") == target_action:
            found.append(step)
        if "steps" in step:
            found.extend(find_all_steps(step["steps"], target_action))
    return found

def find_all_loops(steps, target_var="pixel"):
    """Recursively find all loops iterating over the target variable."""
    found = []
    for step in steps:
        if step.get("action") == "control/loop":
            if step.get("params", {}).get("variable") == target_var:
                found.append(step)
        if "steps" in step:
            found.extend(find_all_loops(step["steps"], target_var))
    return found

# --- Sidebar ---
st.sidebar.header("Protocol Selection")
if st.sidebar.button("Refresh List"):
    st.cache_data.clear()

protocols = load_protocols_list()
if not protocols:
    st.warning("No protocols found or backend offline.")
    st.stop()

# 1. Category Selection
if user:
    mode = st.sidebar.radio("Protocols Source", ["User Protocols", "All Protocols"])
else:
    mode = "All Protocols"
    st.sidebar.info("Login for personal protocols")

# 2. Filtering
if mode == "User Protocols" and user:
    # Filter by user subdirectory (id starts with user/)
    filtered_protocols = [p for p in protocols if p["id"].startswith(f"{user}/")]
    if not filtered_protocols:
        st.sidebar.info(f"No protocols in protocols/{user}/")
        # Fallback or stop
else:
    filtered_protocols = protocols

# 3. Selection
if not filtered_protocols:
    st.warning("No protocols available in this category.")
    st.stop()

selected_proto = st.sidebar.selectbox(
    "Select Protocol", 
    options=filtered_protocols, 
    format_func=lambda p: f"{p['name']} ({p.get('id','')})"
)
selected_id_val = selected_proto["id"]

# Load YAML
yaml_content = get_protocol_content(selected_id_val)

if not yaml_content:
    st.error("Could not load protocol content.")
    st.stop()

# --- Custom Styling (Native Compatible) ---
st.markdown("""
    <style>
    /* Premium Metric Cards - Semi-transparent to adapt to native themes */
    .metric-card {
        background-color: rgba(128, 128, 128, 0.1);
        padding: 1.2rem;
        border-radius: 12px;
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-left: 5px solid #10b981;
        margin-bottom: 1rem;
    }
    .metric-label {
        font-size: 0.8rem;
        opacity: 0.7;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 600;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
    }
    
    /* Vibrant Execution Buttons */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        transition: all 0.2s ease;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.05em;
        border: none !important;
        height: 3.5rem;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    div[data-testid="stVerticalBlock"] > div:has(button:contains("RUN PROTOCOL")) button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        color: white !important;
    }
    div[data-testid="stVerticalBlock"] > div:has(button:contains("STOP SCAN")) button {
        background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%) !important;
        color: white !important;
    }
    
    /* Professional Expanders */
    .stExpander {
        border-radius: 12px !important;
        border: 1px solid rgba(128, 128, 128, 0.2) !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- Overrides Section ---
st.subheader("🛠️ Setup & Parameters")

with st.expander("Run Parameters (Overrides)", expanded=True):
    col1, col2 = st.columns(2)
    
    # Override copies
    new_yaml = yaml_content.copy() # Shallow copy of structure
    # Deep copy steps is better actually, but let's just modify carefully
    import copy
    new_steps = copy.deepcopy(new_yaml.get("steps", []))
    
    save_steps = find_all_steps(new_steps, "data/save")
    if save_steps:
        # Use first step as default for UI reference
        current_fname_sample = save_steps[0]["params"].get("filename", "data")
        current_folder = save_steps[0]["params"].get("folder", "./data")
        
        st.markdown("### 1. Filename & Folder Replacement")
        c_mode = st.radio("Mode", ["Find & Replace", "Literal (Global)"], horizontal=True, key="fname_mode")
        
        f1, f2 = st.columns(2)
        if c_mode == "Literal (Global)":
            with f1:
                new_fname = st.text_input("New Filename (Global)", current_fname_sample, help="Updates ALL save steps to this exact string. Use {$pixel} for variables.")
                for step in save_steps:
                    step["params"]["filename"] = new_fname
        else:
            with f1:
                s_find = st.text_input("Find", "TEST", help="Usually 'TEST'")
                s_replace = st.text_input("Replace with", "AA1")
                if st.checkbox("Apply Replacement", value=True):
                    for step in save_steps:
                        old_f = step["params"].get("filename", "")
                        step["params"]["filename"] = old_f.replace(s_find, s_replace)
        
        with f2:
            new_folder = st.text_input("Data Folder (Global)", current_folder)
            for step in save_steps:
                step["params"]["folder"] = new_folder

    st.divider()
    # 2. Pixels (Loops)
    loop_steps = find_all_loops(new_steps, "pixel")
    if loop_steps:
        # Use first loop as default for UI reference
        current_seq = loop_steps[0]["params"].get("sequence", [])
        seq_str_init = ",".join(map(str, current_seq)) if isinstance(current_seq, list) else "1-6"
        
        new_seq_str = st.text_input("Pixels (Global Override)", seq_str_init, help="Updates ALL loops with the 'pixel' variable.")
        # Parse logic
        try:
            pixels = []
            for part in new_seq_str.split(','):
                part = part.strip()
                if part:
                    if '-' in part:
                        s_p, e_p = map(int, part.split('-'))
                        pixels.extend(range(s_p, e_p+1))
                    else:
                        pixels.append(int(part))
            final_pixels = sorted(list(set(pixels)))
            for step in loop_steps:
                step["params"]["sequence"] = final_pixels
        except:
            st.error("Invalid pixel format")
            
# --- Execution & Plotting ---
st.divider()

# Session State for Plotting
if "traces" not in st.session_state:
    st.session_state.traces = []
if "running" not in st.session_state:
    st.session_state.running = False
if "history_cursor" not in st.session_state:
    st.session_state.history_cursor = 0

col_run, col_status = st.columns([1, 5])

with col_run:
    if st.button("RUN PROTOCOL", type="primary", disabled=st.session_state.running):
        # Prepare request
        req_body = {
            "name": f"Manual Run: {new_yaml.get('name')}",
            "steps": new_steps
        }
        
        # Start
        try:
            resp = requests.post(f"{BACKEND_URL}/protocol/run-inline", json=req_body)
            if resp.status_code == 200:
                st.session_state.running = True
                st.session_state.traces = [] 
                st.session_state.history_cursor = 0
                st.session_state.run_start_time = time.time()
                st.success("Started!")
                st.rerun()
            else:
                st.error(f"Failed: {resp.text}")
        except Exception as e:
            st.error(f"Connection error: {e}")

# --- Status Dashboard ---
with col_status:
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""<div class="metric-card"><div class="metric-label">System State</div><div class="metric-value">{st.session_state.get('system_state', 'IDLE')}</div></div>""", unsafe_allow_html=True)
    with m2:
        dur = time.time() - st.session_state.get("run_start_time", time.time()) if st.session_state.running else 0
        st.markdown(f"""<div class="metric-card"><div class="metric-label">Duration</div><div class="metric-value">{dur:.1f}s</div></div>""", unsafe_allow_html=True)
    with m3:
        points = sum(len(t["data"]) for t in st.session_state.traces)
        st.markdown(f"""<div class="metric-card"><div class="metric-label">Data Points</div><div class="metric-value">{points}</div></div>""", unsafe_allow_html=True)
    with m4:
        # Progress calculation if possible
        progress = 0
        if st.session_state.running:
            # Estimate progress based on traces vs expected pixels if loop is used
            # Use the first loop found as a reference for expected count
            expected_pixels = len(loop_steps[0]["params"]["sequence"]) if loop_steps else 1
            progress = min(100, int((len(st.session_state.traces) / expected_pixels) * 100))
        st.markdown(f"""<div class="metric-card"><div class="metric-label">Progress</div><div class="metric-value">{progress}%</div></div>""", unsafe_allow_html=True)

# Plot params
c_plot1, c_plot2 = st.columns([1, 4])
with c_plot1:
    st.markdown("### 📊 Plot View")
    plot_mode = st.radio("Mode", ["Accumulate", "Latest Only"])
    scale_type = st.radio("Y-Axis", ["Linear", "Log"])
    
    # Channel Selector
    available_channels = sorted(list(set(t.get("channel", 1) for t in st.session_state.traces))) if st.session_state.traces else [1]
    if len(available_channels) > 1:
        selected_channel = st.selectbox("Channel", available_channels)
    else:
        selected_channel = available_channels[0]
        st.caption(f"Showing Channel {selected_channel}")
    
status_ph = st.empty()
plot_ph = st.empty()

# --- Scientific Plotly Theme (Theme Adaptive) ---
def get_scientific_fig(df, x, y, color):
    # Detect if we should use dark or light base template based on streamlit param if possible
    # But usually, 'none' template + transparent bg is most robust for native streamlit
    fig = px.line(df, x=x, y=y, color=color, markers=True, 
                 template="none",
                 color_discrete_sequence=px.colors.qualitative.Safe)
    
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=14),
        xaxis=dict(
            title=dict(text="Voltage (V)", font=dict(size=16, weight="bold")),
            gridcolor="rgba(128, 128, 128, 0.2)",
            zerolinecolor="rgba(128, 128, 128, 0.5)",
            showgrid=True,
            showline=True, linewidth=2, linecolor='rgba(128, 128, 128, 0.5)', mirror=True
        ),
        yaxis=dict(
            title=dict(text="Current (A)", font=dict(size=16, weight="bold")),
            gridcolor="rgba(128, 128, 128, 0.2)",
            zerolinecolor="rgba(128, 128, 128, 0.5)",
            showgrid=True,
            showline=True, linewidth=2, linecolor='rgba(128, 128, 128, 0.5)', mirror=True
        ),
        legend=dict(
            bgcolor="rgba(128, 128, 128, 0.1)",
            bordercolor="rgba(128, 128, 128, 0.2)",
            borderwidth=1,
            title_font=dict(size=14, weight="bold")
        ),
        margin=dict(l=60, r=20, t=40, b=60),
        height=600
    )
    return fig

# --- Rendering (Always render current state) ---
if st.session_state.traces:
    df_all = pd.DataFrame()
    traces_to_plot = st.session_state.traces if plot_mode == "Accumulate" else [st.session_state.traces[-1]]
    
    for i, t in enumerate(traces_to_plot):
        if t.get("channel", 1) != selected_channel:
            continue
            
        df = pd.DataFrame(t["data"])
        v_name = t.get("variable", "iv_data").replace("_iv_data", "").upper()
        label = f"Pixel {t['pixel']} ({v_name})" if t['pixel'] is not None else f"Trace {i+1} ({v_name})"
        
        cols = [c.lower() for c in df.columns]
        df.columns = cols 
        df["trace"] = label
        
        # Check for various voltage/current columns
        v_col = None
        for c in ["set_voltage", "voltage", "voltage (v)", "set_value"]:
            if c in df.columns:
                v_col = c
                break
        
        i_col = None
        for c in ["current", "current (a)", "amp"]:
            if c in df.columns:
                i_col = c
                break

        if v_col and i_col:
                # Rename to standard for concat
                df_to_add = df.rename(columns={v_col: "plot_v", i_col: "plot_i"})
                df_all = pd.concat([df_all, df_to_add], ignore_index=True)
    
    if not df_all.empty:
        x_col = "plot_v"
        y_col = "plot_i"
        
        if scale_type == "Log":
            df_all["abs_current"] = df_all["plot_i"].abs().replace(0, 1e-12)
            y_col = "abs_current"
            
        fig = get_scientific_fig(df_all, x_col, y_col, "trace")
        if scale_type == "Log":
            fig.update_yaxes(type="log", title="|Current| (A)")
        
        # KEY STABILITY: With st.rerun(), we can use a constant key safely!
        plot_ph.plotly_chart(fig, use_container_width=True, key="live_iv_plot")
    else:
        plot_ph.warning("Waiting for valid data structure...")
elif not st.session_state.running:
    # Only show this info if we aren't currently scanning
    plot_ph.info("No data to plot. Select a protocol and click 'RUN PROTOCOL' to start.")
else:
    # Silently wait during scan start
    plot_ph.empty()

# --- Execution Logic (Rerun Loop) ---
if st.session_state.running:
    if st.button("STOP SCAN", type="primary"):
        # Call the global /abort endpoint as requested
        requests.post(f"{BACKEND_URL}/abort")
        st.toast("Abort requested...")
        st.session_state.running = False
        st.rerun()
    
    state = "UNKNOWN"
    run_duration = 0
    
    # 1. Fetch Status
    try:
        r_status = requests.get(f"{BACKEND_URL}/protocol/status")
        if r_status.status_code == 200:
            status_resp = r_status.json()
            state = status_resp["state"]
            st.session_state.system_state = state
            # Update duration
            run_duration = time.time() - st.session_state.get("run_start_time", time.time())
        else:
            status_ph.warning(f"Backend status error: {r_status.status_code}")
    except Exception as e:
        status_ph.error(f"Status connection error: {e}")

    # 2. Fetch History & Update Data (Incremental)
    try:
        r_hist = requests.get(f"{BACKEND_URL}/protocol/history")
        if r_hist.status_code == 200:
            full_history = r_hist.json()
            # Only process things we haven't seen yet
            new_events = full_history[st.session_state.history_cursor:]
            st.session_state.history_cursor = len(full_history)
            
            if new_events:
                # Track last data seen time
                st.session_state.last_data_time = time.time()
                
                # Parse Traces from new events
                for event in new_events:
                    var_name = event.get("variable", "")
                    if var_name.endswith("iv_data"):
                        val = event.get("value")
                        context = event.get("context", {})
                        pixel_id = context.get("pixel")
                        
                        if val and isinstance(val, dict) and "results" in val:
                            results = val["results"]
                            if isinstance(results, dict):
                                # Simultaneous sweep results is {ch: [points]}
                                for ch, data in results.items():
                                    st.session_state.traces.append({
                                        "pixel": pixel_id,
                                        "channel": int(ch),
                                        "data": data,
                                        "variable": var_name
                                    })
                            else:
                                # Normal sweep results is [points]
                                st.session_state.traces.append({
                                    "pixel": pixel_id,
                                    "channel": val.get("channel", 1),
                                    "data": results,
                                    "variable": var_name
                                })
            
            # Debug (optional context)
            with st.expander("History Status (Debug)", expanded=False):
                st.write(f"Total Items: {len(full_history)} | New: {len(new_events)}")
                if new_events: st.write(new_events)
    except Exception:
        pass # Ignore fetch errors

    # 3. Check Finish Condition
    last_data_gap = time.time() - st.session_state.get("last_data_time", st.session_state.run_start_time)
    
    finished = False
    reason = ""
    
    if state in ["COMPLETE", "ERROR"]:
        finished = True
        reason = f"Backend reported {state}"
    elif state == "IDLE" and run_duration > 5.0 and last_data_gap > 15.0:
        finished = True
        reason = "Protocol idle (data timeout)"
    elif run_duration > 300.0:
        finished = True
        reason = "Safety timeout (5m)"
        
    if finished:
        st.session_state.running = False
        st.success(f"Protocol Finished: {reason}")
        st.rerun()
    else:
        # Still running - keep polling
        time.sleep(0.5)
        st.rerun()


