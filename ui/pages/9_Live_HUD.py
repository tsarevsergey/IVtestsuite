import streamlit as st
import requests
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from api_client import BACKEND_URL

st.set_page_config(page_title="Smart Live HUD", page_icon="🕹️", layout="wide")

# ----------------------------
# SESSION STATE
# ----------------------------
if "live_traces" not in st.session_state: st.session_state.live_traces = []
if "monitoring" not in st.session_state: st.session_state.monitoring = False
if "led_state" not in st.session_state: st.session_state.led_state = False
if "selected_pixel" not in st.session_state: st.session_state.selected_pixel = 1
if "last_iv_trace" not in st.session_state: st.session_state.last_iv_trace = None
if "monitor_configured" not in st.session_state: st.session_state.monitor_configured = False
if "conn_smu1" not in st.session_state: st.session_state.conn_smu1 = False
if "conn_smu2" not in st.session_state: st.session_state.conn_smu2 = False
if "conn_relays" not in st.session_state: st.session_state.conn_relays = False

# ----------------------------
# HELPERS
# ----------------------------
def api_call(method, endpoint, json=None, params=None, timeout=5):
    """Direct backend call with short timeout."""
    try:
        url = f"{BACKEND_URL}{endpoint}"
        if method.upper() == "POST":
            return requests.post(url, json=json, timeout=timeout)
        return requests.get(url, params=params, timeout=timeout)
    except Exception as e:
        # Keep UI responsive even if backend down
        print(f"API Error: {e}")
        return None

def fmt_current(a):
    """Match the HUD-ish current formatting."""
    if a is None:
        return "---"
    try:
        a = float(a)
    except Exception:
        return "---"
    aa = abs(a)
    if aa >= 1e-3:
        return f"{a*1e3:.4f} mA"
    if aa >= 1e-6:
        return f"{a*1e6:.4f} µA"
    if aa >= 1e-9:
        return f"{a*1e9:.4f} nA"
    return f"{a:.3e} A"

# ----------------------------
# CSS: INDUSTRIAL HUD THEME
# ----------------------------
st.markdown(
    """
<style>
/* --- page baseline --- */
:root{
  --background: hsl(220 15% 10%);
  --foreground: hsl(210 20% 95%);
  --border: hsl(220 10% 25%);
  --muted-foreground: hsl(210 10% 60%);
  --radius: 6px;

  --cyan: #47cfeb;
  --cyan2: #19c3e6;
  --green: #22c373;
  --yellow: #f4c025;
  --red: #e05252;

  --panel-bg: linear-gradient(180deg,#1e2229,#16181d);
  --btn-bg: linear-gradient(180deg,#303541,#23272f);
  --btn-bg-hover: linear-gradient(180deg,#383f4c,#2b303b);
}

/* Streamlit chrome */
.stApp { background: var(--background); color: var(--foreground); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: hsl(220 15% 12%); border-right: 1px solid var(--border); }
.main .block-container { padding-top: 1rem; padding-bottom: 1.5rem; max-width: 1400px; }

/* Remove extra whitespace above first element */
div[data-testid="stAppViewContainer"] > .main { padding-top: 0.25rem; }

/* Panels */
.industrial-panel{
  border-radius: var(--radius);
  padding: 1rem;
  background: var(--panel-bg);
  border: 1px solid hsl(220 10% 22%);
  box-shadow: 0 4px 12px rgba(0,0,0,.4), inset 0 1px rgba(255,255,255,.05);
}
.panel-title{
  margin-bottom: .75rem;
  padding-bottom: .5rem;
  font-size: .75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
  color: var(--cyan);
  border-bottom: 1px solid hsl(220 10% 25%);
  text-shadow: 0 0 8px rgba(71,207,235,.30);
}

/* Status badge + LEDs */
.status-badge{
  border-radius: calc(var(--radius) - 2px);
  padding: .125rem .5rem;
  font-size: .75rem;
  font-weight: 600;
  background: #2e3138;
  border: 1px solid hsl(220 10% 30%);
  color: #d1d9e0;
}
.led-indicator{
  display:inline-block;
  height:.75rem; width:.75rem;
  border-radius: 9999px;
  box-shadow: inset 1px 1px 2px rgba(0,0,0,.5), 0 0 2px rgba(0,0,0,.6);
}
.led-green{ background: radial-gradient(circle at 30% 30%, #33cc80, #17824d); }
.led-green.on{ background: radial-gradient(circle at 30% 30%, #47eb99, #14b866); box-shadow: 0 0 10px #19e680, inset 1px 1px 2px rgba(0,0,0,.3); }
.led-red{ background: radial-gradient(circle at 30% 30%, #c65353, #a32929); }
.led-red.on{ background: radial-gradient(circle at 30% 30%, #e46767, #d92626); box-shadow: 0 0 10px #e05252, inset 1px 1px 2px rgba(0,0,0,.3); }
.led-cyan{ background: radial-gradient(circle at 30% 30%, #33b2cc, #1b8398); }
.led-cyan.on{ background: radial-gradient(circle at 30% 30%, #3dd6f5, #0bb8da); box-shadow: 0 0 10px #25d1f4, inset 1px 1px 2px rgba(0,0,0,.3); }

/* Inputs (number/select/text) */
div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] select,
div[data-testid="stSelectbox"] div[role="combobox"],
div[data-testid="stMultiSelect"] div[role="combobox"]{
  border-radius: calc(var(--radius) - 2px) !important;
  background: #111317 !important;
  border: 1px solid hsl(220 10% 25%) !important;
  color: #f0f2f5 !important;
  box-shadow: inset 0 2px 4px rgba(0,0,0,.35) !important;
}
div[data-testid="stNumberInput"] input:focus,
div[data-testid="stTextInput"] input:focus,
div[data-testid="stSelectbox"] select:focus,
div[data-testid="stSelectbox"] div[role="combobox"]:focus-within,
div[data-testid="stMultiSelect"] div[role="combobox"]:focus-within{
  outline: none !important;
  border-color: var(--cyan2) !important;
  box-shadow: inset 0 2px 4px rgba(0,0,0,.35), 0 0 0 2px rgba(25,195,230,.20) !important;
}

/* Labels */
label, .stSelectbox label, .stNumberInput label {
  color: rgba(255,255,255,.85) !important;
  font-size: .75rem !important;
  font-weight: 600 !important;
}

/* Base button (industrial) */
div[data-testid="stButton"] > button{
  position: relative;
  border-radius: calc(var(--radius) - 2px) !important;
  padding: .50rem 1rem !important;
  font-size: .80rem !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: .05em !important;
  background: var(--btn-bg) !important;
  border: 1px solid hsl(220 10% 30%) !important;
  box-shadow: 0 2px 4px rgba(0,0,0,.30), inset 0 1px rgba(255,255,255,.05) !important;
  color: #e0e6eb !important;
  transition: all .15s ease !important;
}
div[data-testid="stButton"] > button:hover{
  background: var(--btn-bg-hover) !important;
  border-color: #5c6370 !important;
}
div[data-testid="stButton"] > button:active{
  background: linear-gradient(180deg,#1e2229,#272c35) !important;
  box-shadow: inset 0 2px 4px rgba(0,0,0,.40) !important;
  transform: translateY(1px) !important;
}

/* Make Streamlit "primary" be cyan HUD primary */
div[data-testid="stButton"] > button[kind="primary"]{
  background: linear-gradient(180deg,#30c9e8,#17b0cf) !important;
  border-color: #149cb8 !important;
  color: #16181d !important;
  font-weight: 800 !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover{
  background: linear-gradient(180deg,#47cfeb,#19c3e6) !important;
  border-color: #19c3e6 !important;
  box-shadow: 0 0 12px rgba(25,195,230,.35) !important;
}

/* Special buttons by ARIA label text */
button[aria-label="▶ RUN SWEEP"]{
  background: linear-gradient(180deg,#f4c025,#daa60b) !important;
  color: #16181d !important;
  border-color: #c2940a !important;
}
button[aria-label="▶ RUN SWEEP"]:hover{
  background: linear-gradient(180deg,#f5c73d,#f2b90d) !important;
  box-shadow: 0 0 12px rgba(244,192,37,.35) !important;
}

button[aria-label="■ STOP MONITORING"],
button[aria-label="⏹ STOP MONITORING"]{
  background: linear-gradient(180deg,#e05252,#d92626) !important;
  border-color: #c32222 !important;
  color: #ffffff !important;
}
button[aria-label="■ STOP MONITORING"]:hover,
button[aria-label="⏹ STOP MONITORING"]:hover{
  background: linear-gradient(180deg,#e46767,#dd3c3c) !important;
  box-shadow: 0 0 12px rgba(224,82,82,.35) !important;
}

button[aria-label="💡 ON"]{
  background: linear-gradient(180deg,#22c373,#1b9859) !important;
  border-color: #17824d !important;
  color: #ffffff !important;
}
button[aria-label="💡 ON"]:hover{ box-shadow: 0 0 12px rgba(34,195,115,.35) !important; }

/* Plotly chart container */
.chart-container{
  overflow:hidden;
  border-radius: var(--radius);
  background:#0c0e12;
  border:1px solid hsl(220 10% 20%);
  box-shadow: inset 0 2px 8px rgba(0,0,0,.50);
  padding: .25rem;
}

/* Metrics */
[data-testid="stMetricValue"]{
  color: var(--cyan) !important;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Courier New", monospace !important;
  font-weight: 800 !important;
  text-shadow: 0 0 8px rgba(71,207,235,.25);
}

/* Toast position readability */
div[data-testid="stToast"]{ filter: drop-shadow(0 8px 14px rgba(0,0,0,.45)); }
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------
# HEADER BAR
# ----------------------------
h1, h2 = st.columns([0.75, 0.25])
with h1:
    st.markdown(
        """
<div style="display:flex; align-items:center; gap:10px; margin-bottom:.25rem;">
  <div style="font-size:1.6rem; font-weight:800; color:hsl(190 80% 60%); text-shadow:0 0 12px rgba(71,207,235,.35);">
    🕹️ Smart Live HUD
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
with h2:
    # Optional "STOP ALL" like the React HUD (no backend endpoint specified in your code)
    if st.button("STOP ALL", key="stop_all", use_container_width=True):
        # Best-effort: turn off both SMUs, stop monitoring, LED off
        st.session_state.monitoring = False
        st.session_state.monitor_configured = False
        st.session_state.led_state = False
        api_call("POST", "/smu/output", json={"channel": 1, "enabled": False})
        api_call("POST", "/smu/output", json={"channel": 2, "enabled": False})
        st.toast("STOP ALL issued (outputs off)")

# ----------------------------
# SYSTEM CONNECTIONS PANEL
# ----------------------------
st.markdown('<div class="industrial-panel" style="margin-bottom:1rem;">', unsafe_allow_html=True)
st.markdown('<div class="panel-title">System Connections</div>', unsafe_allow_html=True)
cc1, cc2, cc3, cc4 = st.columns([1, 1, 1, 2])

def conn_row(col, label, is_on, btn_key, on_click):
    with col:
        led_cls = "led-green on" if is_on else "led-red"
        st.markdown(
            f"""
<div style="display:flex; align-items:center; gap:8px; margin-bottom:.35rem;">
  <span class="led-indicator {led_cls}"></span>
  <span style="font-size:.9rem; font-weight:700;">{label}</span>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button("Reconnect" if is_on else "Connect", key=btn_key, use_container_width=True):
            on_click()

with cc1:
    led_cls = "led-green on" if st.session_state.conn_smu1 else "led-red"
    st.markdown(f'<div style="display:flex; align-items:center; gap:8px; margin-bottom:.35rem;"><span class="led-indicator {led_cls}"></span><span style="font-size:.9rem; font-weight:700;">SMU CH1</span></div>', unsafe_allow_html=True)
    if st.button("Reconnect" if st.session_state.conn_smu1 else "Connect", key="conn1", use_container_width=True):
        api_call("POST", "/smu/connect", json={"channel": 1, "mock": False})
        st.session_state.conn_smu1 = True
        st.rerun()

with cc2:
    led_cls = "led-green on" if st.session_state.conn_smu2 else "led-red"
    st.markdown(f'<div style="display:flex; align-items:center; gap:8px; margin-bottom:.35rem;"><span class="led-indicator {led_cls}"></span><span style="font-size:.9rem; font-weight:700;">SMU CH2</span></div>', unsafe_allow_html=True)
    if st.button("Reconnect" if st.session_state.conn_smu2 else "Connect", key="conn2", use_container_width=True):
        api_call("POST", "/smu/connect", json={"channel": 2, "mock": False})
        st.session_state.conn_smu2 = True
        st.rerun()

with cc3:
    led_cls = "led-green on" if st.session_state.conn_relays else "led-red"
    st.markdown(f'<div style="display:flex; align-items:center; gap:8px; margin-bottom:.35rem;"><span class="led-indicator {led_cls}"></span><span style="font-size:.9rem; font-weight:700;">RELAYS</span></div>', unsafe_allow_html=True)
    if st.button("Reconnect" if st.session_state.conn_relays else "Connect", key="connR", use_container_width=True):
        api_call("POST", "/relays/connect", json={"mock": False})
        st.session_state.conn_relays = True
        st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# MAIN GRID
# ----------------------------
col_left, col_right = st.columns([0.34, 0.66])

# ========== LEFT COLUMN ==========
with col_left:
    # 1) DEVICE SELECTION
    st.markdown('<div class="industrial-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Device Selection</div>', unsafe_allow_html=True)

    g = st.columns(3)
    for i in range(1, 7):
        with g[(i - 1) % 3]:
            is_sel = st.session_state.selected_pixel == i
            # use primary to highlight selected pixel
            if st.button(f"P{i}", key=f"p{i}", type=("primary" if is_sel else "secondary"), use_container_width=True):
                st.session_state.selected_pixel = i
                api_call("POST", "/relays/pixel", json={"pixel_id": i - 1})
                st.rerun()

    st.markdown(
        f"""
<div style="margin-top:.75rem; display:flex; align-items:center; gap:8px;">
  <span style="font-size:.85rem; color: var(--muted-foreground); font-weight:600;">Selected:</span>
  <span class="status-badge">Pixel {st.session_state.selected_pixel}</span>
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # 2) ILLUMINATION CONTROL
    st.markdown('<div class="industrial-panel" style="margin-top:1rem;">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Illumination Control</div>', unsafe_allow_html=True)

    i1, i2 = st.columns(2)
    with i1:
        led_relay_label = st.selectbox("Wavelength", ["None", "LED 1", "LED 2"], index=1, key="led_wave")
        led_cur = st.number_input("Current (A)", value=0.010, format="%.3f", step=0.001, key="led_cur")
    with i2:
        led_smu = st.selectbox("Driver SMU", [1, 2], index=0, key="led_smu")
        led_lim = st.number_input("Limit (V)", value=9.0, step=0.5, key="led_lim")

    if st.button("SET LED CONFIGURATION", key="set_led_cfg", use_container_width=True):
        idx = 0 if led_relay_label == "LED 1" else 1 if led_relay_label == "LED 2" else -1
        if idx >= 0:
            api_call("POST", "/relays/led", json={"channel_id": idx})
        api_call("POST", "/smu/configure", json={"channel": led_smu, "compliance": led_lim, "compliance_type": "VOLT"})
        api_call("POST", "/smu/source-mode", json={"channel": led_smu, "mode": "CURR"})
        api_call("POST", "/smu/set", json={"channel": led_smu, "value": led_cur})
        st.toast(f"LED configured on SMU {led_smu}")

    b1, b2 = st.columns(2)
    with b1:
        if st.button("💡 ON", key="led_on", use_container_width=True):
            api_call("POST", "/smu/output", json={"channel": led_smu, "enabled": True})
            st.session_state.led_state = True
            st.rerun()
    with b2:
        if st.button("⚫ OFF", key="led_off", use_container_width=True):
            api_call("POST", "/smu/output", json={"channel": led_smu, "enabled": False})
            st.session_state.led_state = False
            st.rerun()

    led_cls = "led-cyan on" if st.session_state.led_state else "led-green"
    st.markdown(
        f"""
<div style="margin-top:.75rem; display:flex; align-items:center; gap:8px;">
  <span style="font-size:.85rem; color: var(--muted-foreground); font-weight:600;">Status:</span>
  <span class="led-indicator {led_cls}"></span>
  <span style="font-size:.9rem; font-weight:800;">{"ON" if st.session_state.led_state else "OFF"}</span>
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # 3) IV CHARACTERIZATION
    st.markdown('<div class="industrial-panel" style="margin-top:1rem;">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">IV Characterization</div>', unsafe_allow_html=True)

    iv1, iv2 = st.columns(2)
    with iv1:
        v_start = st.number_input("Start (V)", value=-1.0, step=0.1, key="iv_vstart")
        iv_pts = st.number_input("Points", value=50, step=1, key="iv_vpts")
        iv_scale = st.selectbox("Scale", ["linear", "log"], index=0, key="iv_vscale")
    with iv2:
        v_stop = st.number_input("Stop (V)", value=1.0, step=0.1, key="iv_vstop")
        iv_chan = st.selectbox("Channel", [1, 2], index=1, key="iv_vchan")
        iv_type = st.selectbox("Sweep Type", ["Double", "Single"], index=0, key="iv_vtype")

    if st.button("▶ RUN SWEEP", key="run_sweep", use_container_width=True):
        with st.spinner("Sweeping..."):
            resp = api_call("POST", "/smu/sweep", json={
                "channel": iv_chan,
                "start": v_start, "stop": v_stop, "points": int(iv_pts),
                "nplc": 0.1, "delay": 0.01, "compliance": 0.05,
                "scale": iv_scale, "sweep_type": "double", "direction": "forward"
            }, timeout=30)
            if resp and resp.status_code == 200:
                data = resp.json()
                if "results" in data:
                    st.session_state.last_iv_trace = data["results"]
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ========== RIGHT COLUMN ==========
with col_right:
    # 4) LIVE MONITOR
    st.markdown('<div class="industrial-panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Live Monitor</div>', unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        mon_chan = st.selectbox("Channel", [1, 2], index=1, key="mon_chan_sel")
    with m2:
        mon_v = st.number_input("Bias (V)", value=0.0, step=0.1, key="mon_v_bias")
    with m3:
        mon_nplc = st.number_input("NPLC", value=1.0, step=0.1, key="mon_nplc_val")
    with m4:
        mon_rate = st.number_input("Rate (s)", value=1.0, step=0.1, min_value=0.1, key="mon_rate_val")

    a1, a2 = st.columns(2)
    with a1:
        if st.button("APPLY SETTINGS", key="apply_mon", use_container_width=True):
            api_call("POST", "/smu/configure", json={"channel": mon_chan, "nplc": mon_nplc, "compliance": 0.1})
            api_call("POST", "/smu/set", json={"channel": mon_chan, "value": mon_v})
            api_call("POST", "/smu/output", json={"channel": mon_chan, "enabled": True})
            st.session_state.monitor_configured = True
            st.toast("Monitor Configured")

    with a2:
        btn_label = "■ STOP MONITORING" if st.session_state.monitoring else "▶ START MONITORING"
        # make STOP look "danger" via CSS aria-label selector
        if st.button(btn_label, key="toggle_mon", use_container_width=True):
            st.session_state.monitoring = not st.session_state.monitoring
            if not st.session_state.monitoring:
                api_call("POST", "/smu/output", json={"channel": mon_chan, "enabled": False})
                st.session_state.monitor_configured = False
                st.toast("Monitoring stopped & source OFF")
            else:
                api_call("POST", "/smu/output", json={"channel": mon_chan, "enabled": True})
                st.toast("Monitoring started")
            st.rerun()

    # Current readout block (HUD-style)
    last_current = None
    if st.session_state.live_traces:
        last_current = st.session_state.live_traces[-1].get("current", None)

    led_state_cls = "led-cyan on" if st.session_state.monitoring else "led-green"
    st.markdown(
        f"""
<div style="display:flex; align-items:center; gap:12px; margin:.75rem 0 .5rem 0; padding:.75rem; border-radius:8px;
            background:hsl(220 15% 8%); border:1px solid hsl(220 10% 20%);">
  <span style="font-size:.9rem; font-weight:700; color: var(--muted-foreground);">Current:</span>
  <span style="font-size:1.25rem; font-weight:900; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Courier New', monospace;
               color:hsl(190 90% 55%); text-shadow:0 0 8px rgba(25,195,230,.35);">
    {fmt_current(last_current)}
  </span>
  <span class="led-indicator {led_state_cls}"></span>
</div>
""",
        unsafe_allow_html=True,
    )

    # Plot
    monitor_fig = go.Figure()
    monitor_fig.update_layout(
        template="plotly_dark",
        margin=dict(l=10, r=10, t=10, b=10),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", title="Time (s)", tickfont=dict(color="#888", size=10)),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", title="Current (A)", tickfont=dict(color="#888", size=10)),
        showlegend=False,
    )

    if st.session_state.live_traces:
        df = pd.DataFrame(st.session_state.live_traces)
        df["rel_time"] = df["time"] - df["time"].min()
        monitor_fig.add_trace(
            go.Scatter(
                x=df["rel_time"],
                y=df["current"],
                mode="lines",
                line=dict(color="#00d4ff", width=2),
            )
        )
    else:
        monitor_fig.add_annotation(text="No Live Data", showarrow=False, font=dict(color="#888"))

    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.plotly_chart(monitor_fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # 5) LAST IV SCAN
    st.markdown('<div class="industrial-panel" style="margin-top:1rem;">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Last IV Scan</div>', unsafe_allow_html=True)

    if st.session_state.last_iv_trace:
        df_iv = pd.DataFrame(st.session_state.last_iv_trace)
        iv_fig = px.line(df_iv, x="voltage", y="current", template="plotly_dark")
        iv_fig.update_traces(line=dict(color="#00ff66", width=2))
    else:
        iv_fig = go.Figure()
        iv_fig.add_annotation(text="Waiting for Scan...", showarrow=False, font=dict(color="#888"))

    iv_fig.update_layout(
        height=270,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        template="plotly_dark",
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", title="Voltage (V)", tickfont=dict(color="#888", size=10)),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", title="Current (A)", tickfont=dict(color="#888", size=10)),
        showlegend=False,
    )

    st.markdown('<div class="chart-container">', unsafe_allow_html=True)
    st.plotly_chart(iv_fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div style="margin-top:1rem; text-align:center; font-size:.75rem; color: rgba(255,255,255,.55);">'
        "SMU Control Interface v2.0 | Modern Dark Theme</div>",
        unsafe_allow_html=True,
    )

# ----------------------------
# MEASUREMENT LOOP
# ----------------------------
if st.session_state.monitoring:
    # Auto-configure if not yet configured (fallback safety)
    if not st.session_state.monitor_configured:
        api_call("POST", "/smu/configure", json={"channel": mon_chan, "nplc": 1.0, "compliance": 0.1})
        api_call("POST", "/smu/set", json={"channel": mon_chan, "value": 0.0})
        api_call("POST", "/smu/output", json={"channel": mon_chan, "enabled": True})
        st.session_state.monitor_configured = True
    
    resp = api_call("GET", "/smu/measure", params={"channel": mon_chan})
    if resp and resp.status_code == 200:
        val = resp.json().get("current", 0.0)
        st.session_state.live_traces.append({"time": time.time(), "current": val})
        if len(st.session_state.live_traces) > 60:
            st.session_state.live_traces.pop(0)
    
    time.sleep(mon_rate)
    st.rerun()
