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

def find_step(steps, target_action):
    """Recursively find the first step with given action."""
    for step in steps:
        if step.get("action") == target_action:
            return step
        if "steps" in step:
            res = find_step(step["steps"], target_action)
            if res: return res
    return None

def find_loop(steps, target_var="pixel"):
    for step in steps:
        if step.get("action") == "control/loop":
            if step.get("params", {}).get("variable") == target_var:
                return step
        if "steps" in step:
            res = find_loop(step["steps"], target_var)
            if res: return res
    return None

# --- Sidebar ---
st.sidebar.header("Protocol Selection")
if st.sidebar.button("Refresh List"):
    st.cache_data.clear()

protocols = load_protocols_list()
if not protocols:
    st.warning("No protocols found or backend offline.")
    st.stop()

# Map ID to Name for display
proto_map = {p["id"]: f"{p['name']} ({p['filename']})" for p in protocols}
selected_id = st.sidebar.selectbox("Select Protocol", options=protocols, format_func=lambda p: f"{p['name']} ({p.get('id','')})")
selected_id_val = selected_id["id"]

# Load YAML
yaml_content = get_protocol_content(selected_id_val)

if not yaml_content:
    st.error("Could not load protocol content.")
    st.stop()

# --- Custom Styling ---
st.markdown("""
    <style>
    /* Main Background & Cards */
    .stApp {
        background-color: #0e1117;
    }
    .metric-card {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #4ade80;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
        margin-bottom: 20px;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc;
    }
    
    /* Buttons */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        transition: all 0.2s ease;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
    div[data-testid="stVerticalBlock"] > div:has(button:contains("RUN PROTOCOL")) button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        border: none !important;
        height: 3rem;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
    }
    div[data-testid="stVerticalBlock"] > div:has(button:contains("STOP SCAN")) button {
        background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%) !important;
        border: none !important;
        height: 3rem;
        box-shadow: 0 4px 15px rgba(239, 68, 68, 0.3);
    }
    
    /* Parameters View */
    .stExpander {
        border: 1px solid #334155 !important;
        background-color: #1e293b !important;
        border-radius: 10px !important;
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
    
    # 1. Filename / Folder
    # Look for data/save
    save_step = find_step(new_steps, "data/save")
    if save_step:
        current_fname = save_step["params"].get("filename", "data")
        current_folder = save_step["params"].get("folder", "./data")
        
        with col1:
            new_fname = st.text_input("Filename Pattern", current_fname, help="Use {$pixel} for variables")
            save_step["params"]["filename"] = new_fname
        with col2:
            new_folder = st.text_input("Data Folder", current_folder)
            save_step["params"]["folder"] = new_folder
    
    # 2. Pixels (Loop)
    loop_step = find_loop(new_steps, "pixel")
    if loop_step:
        current_seq = loop_step["params"].get("sequence", [])
        # Format as string
        if isinstance(current_seq, list):
            seq_str = ",".join(map(str, current_seq))
        else:
            seq_str = "1-6"
            
        with col1:
            new_seq_str = st.text_input("Pixels (list/range)", seq_str)
            # Parse logic
            try:
                pixels = []
                for part in new_seq_str.split(','):
                    part = part.strip()
                    if '-' in part:
                        s, e = map(int, part.split('-'))
                        pixels.extend(range(s, e+1))
                    else:
                        pixels.append(int(part))
                loop_step["params"]["sequence"] = sorted(list(set(pixels)))
            except:
                st.error("Invalid pixel format")
                
    # 3. Sweep Params
    sweep_step = find_step(new_steps, "smu/sweep")
    if sweep_step:
        p = sweep_step["params"]
        st.markdown("#### Sweep Settings")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            p["start"] = st.number_input("Start (V)", value=float(p.get("start", 0.0)))
        with c2:
            p["stop"] = st.number_input("Stop (V)", value=float(p.get("stop", 1.0)))
        with c3:
            p["points"] = st.number_input("Points", value=int(p.get("points", 11)))
        with c4:
            p["compliance"] = st.number_input("Compl. (A)", value=float(p.get("compliance", 0.1)), format="%.1e")
            
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
            expected_pixels = len(loop_step["params"]["sequence"]) if loop_step else 1
            progress = min(100, int((len(st.session_state.traces) / expected_pixels) * 100))
        st.markdown(f"""<div class="metric-card"><div class="metric-label">Progress</div><div class="metric-value">{progress}%</div></div>""", unsafe_allow_html=True)

# Plot params
c_plot1, c_plot2 = st.columns([1, 4])
with c_plot1:
    st.markdown("### 📊 Plot View")
    plot_mode = st.radio("Mode", ["Accumulate", "Latest Only"])
    scale_type = st.radio("Y-Axis", ["Linear", "Log"])
    
plot_ph = st.empty()

# --- Scientific Plotly Theme ---
def get_scientific_fig(df, x, y, color):
    fig = px.line(df, x=x, y=y, color=color, markers=True, 
                 template="plotly_dark",
                 color_discrete_sequence=px.colors.qualitative.Antique)
    
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", size=14, color="#f8fafc"),
        xaxis=dict(
            title=dict(text="Voltage (V)", font=dict(size=16, weight="bold")),
            gridcolor="#334155",
            zerolinecolor="#94a3b8",
            showline=True, linewidth=2, linecolor='#475569', mirror=True
        ),
        yaxis=dict(
            title=dict(text="Current (A)", font=dict(size=16, weight="bold")),
            gridcolor="#334155",
            zerolinecolor="#94a3b8",
            showline=True, linewidth=2, linecolor='#475569', mirror=True
        ),
        legend=dict(
            bgcolor="rgba(30, 41, 59, 0.7)",
            bordercolor="#475569",
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
        df = pd.DataFrame(t["data"])
        label = f"Pixel {t['pixel']}" if t['pixel'] is not None else f"Trace {i+1}"
        
        cols = [c.lower() for c in df.columns]
        df.columns = cols 
        df["trace"] = label
        
        if "voltage" in df.columns and "current" in df.columns:
                df_all = pd.concat([df_all, df], ignore_index=True)
    
    if not df_all.empty:
        x_col = "set_voltage" if "set_voltage" in df_all.columns else "voltage"
        y_col = "current"
        
        if scale_type == "Log":
            df_all["abs_current"] = df_all["current"].abs().replace(0, 1e-12)
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
                    if event.get("variable") == "iv_data":
                        val = event.get("value")
                        context = event.get("context", {})
                        pixel_id = context.get("pixel")
                        
                        if val and isinstance(val, dict) and "results" in val:
                            st.session_state.traces.append({
                                "pixel": pixel_id,
                                "data": val["results"]
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


