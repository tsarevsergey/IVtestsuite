"""
Relay Test Page - Standalone Arduino Relay Testing

Test relay boards without SMU connection.
Supports:
- Pixel Arduino (COM38, 6 relays)
- RGB Arduino (COM39, 3 relays)

Protocol: LabVIEW-compatible (1-12 OFF, 101-112 ON, 112500 baud)
"""
import streamlit as st
import requests
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from api_client import BACKEND_URL

st.set_page_config(page_title="Relay Test", page_icon="🔌", layout="wide")

# ----------------------------
# SESSION STATE
# ----------------------------
if "pixel_connected" not in st.session_state: st.session_state.pixel_connected = False
if "rgb_connected" not in st.session_state: st.session_state.rgb_connected = False
if "last_response" not in st.session_state: st.session_state.last_response = ""

# ----------------------------
# HELPERS
# ----------------------------
def api_call(method, endpoint, json=None, params=None, timeout=5):
    """Direct backend call."""
    try:
        url = f"{BACKEND_URL}{endpoint}"
        if method.upper() == "POST":
            return requests.post(url, json=json, timeout=timeout)
        return requests.get(url, params=params, timeout=timeout)
    except Exception as e:
        print(f"API Error: {e}")
        return None

# ----------------------------
# CSS: INDUSTRIAL THEME
# ----------------------------
st.markdown(
    """
<style>
:root{
  --background: hsl(220 15% 10%);
  --foreground: hsl(210 20% 95%);
  --border: hsl(220 10% 25%);
  --cyan: #47cfeb;
  --green: #22c373;
  --red: #e05252;
  --panel-bg: linear-gradient(180deg,#1e2229,#16181d);
}
.stApp { background: var(--background); color: var(--foreground); }
.industrial-panel{
  border-radius: 6px;
  padding: 1rem;
  background: var(--panel-bg);
  border: 1px solid hsl(220 10% 22%);
  box-shadow: 0 4px 12px rgba(0,0,0,.4);
  margin-bottom: 1rem;
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
}
.led-indicator{
  display:inline-block;
  height:.75rem; width:.75rem;
  border-radius: 9999px;
}
.led-green{ background: radial-gradient(circle at 30% 30%, #47eb99, #14b866); box-shadow: 0 0 10px #19e680; }
.led-red{ background: radial-gradient(circle at 30% 30%, #e46767, #d92626); box-shadow: 0 0 10px #e05252; }
.led-off{ background: radial-gradient(circle at 30% 30%, #444, #222); }
.response-box{
  background: #0c0e12;
  border: 1px solid hsl(220 10% 20%);
  border-radius: 4px;
  padding: 0.5rem;
  font-family: monospace;
  font-size: 0.8rem;
  color: #00ff66;
  min-height: 60px;
  white-space: pre-wrap;
}
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------
# HEADER
# ----------------------------
st.markdown(
    """
<div style="display:flex; align-items:center; gap:10px; margin-bottom:1rem;">
  <div style="font-size:1.6rem; font-weight:800; color:hsl(190 80% 60%);">
    🔌 Relay Test Page
  </div>
  <div style="font-size:0.9rem; color:#888;">Standalone Arduino Relay Testing</div>
</div>
""",
    unsafe_allow_html=True,
)

# ----------------------------
# CONNECTION PANEL
# ----------------------------
st.markdown('<div class="industrial-panel">', unsafe_allow_html=True)
st.markdown('<div class="panel-title">Arduino Connections</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Pixel Arduino** (COM38, 6 relays)")
    pixel_port = st.text_input("Port", value="COM38", key="pixel_port")
    pixel_mock = st.checkbox("Mock Mode", value=False, key="pixel_mock")
    
    led_cls = "led-green" if st.session_state.pixel_connected else "led-off"
    st.markdown(f'<span class="led-indicator {led_cls}"></span> {"Connected" if st.session_state.pixel_connected else "Disconnected"}', unsafe_allow_html=True)
    
    if st.button("Connect Pixel", key="conn_pixel", use_container_width=True):
        resp = api_call("POST", "/relays/connect-board", json={
            "board": "pixel",
            "port": pixel_port,
            "mock": pixel_mock
        })
        if resp and resp.status_code == 200:
            data = resp.json()
            st.session_state.pixel_connected = data.get("success", False)
            st.session_state.last_response = str(data)
            st.toast(f"Pixel: {data.get('message', 'OK')}")
        st.rerun()

with col2:
    st.markdown("**RGB Arduino** (COM39, 3 relays)")
    rgb_port = st.text_input("Port", value="COM39", key="rgb_port")
    rgb_mock = st.checkbox("Mock Mode", value=False, key="rgb_mock")
    
    led_cls = "led-green" if st.session_state.rgb_connected else "led-off"
    st.markdown(f'<span class="led-indicator {led_cls}"></span> {"Connected" if st.session_state.rgb_connected else "Disconnected"}', unsafe_allow_html=True)
    
    if st.button("Connect RGB", key="conn_rgb", use_container_width=True):
        resp = api_call("POST", "/relays/connect-board", json={
            "board": "rgb",
            "port": rgb_port,
            "mock": rgb_mock
        })
        if resp and resp.status_code == 200:
            data = resp.json()
            st.session_state.rgb_connected = data.get("success", False)
            st.session_state.last_response = str(data)
            st.toast(f"RGB: {data.get('message', 'OK')}")
        st.rerun()

with col3:
    st.markdown("**Quick Actions**")
    if st.button("🔄 Refresh Status", key="refresh_status", use_container_width=True):
        resp = api_call("GET", "/relays/status")
        if resp and resp.status_code == 200:
            data = resp.json()
            st.session_state.last_response = str(data)
            # Update connection states from status
            if "pixel_board" in data:
                st.session_state.pixel_connected = data["pixel_board"].get("connected", False)
            if "rgb_board" in data:
                st.session_state.rgb_connected = data["rgb_board"].get("connected", False)
        st.rerun()
    
    if st.button("⚫ ALL OFF", key="all_off", use_container_width=True):
        resp = api_call("POST", "/relays/all-off")
        if resp and resp.status_code == 200:
            st.session_state.last_response = str(resp.json())
            st.toast("All relays OFF")
        st.rerun()
    
    if st.button("🔌 Disconnect All", key="disconnect_all", use_container_width=True):
        resp = api_call("POST", "/relays/disconnect")
        if resp and resp.status_code == 200:
            st.session_state.pixel_connected = False
            st.session_state.rgb_connected = False
            st.session_state.last_response = str(resp.json())
            st.toast("Disconnected")
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------
# RELAY CONTROL PANELS
# ----------------------------

# PIXEL BOARD
st.markdown('<div class="industrial-panel">', unsafe_allow_html=True)
st.markdown('<div class="panel-title">Pixel Relays (1-6)</div>', unsafe_allow_html=True)

if not st.session_state.pixel_connected:
    st.warning("Pixel Arduino not connected")
else:
    # Row 1: Relays 1-3 with ON/OFF buttons (6 columns = 3 pairs)
    st.markdown("**Relays 1-3**")
    pc1, pc2, pc3, pc4, pc5, pc6 = st.columns(6)
    for i, (on_col, off_col) in enumerate([(pc1, pc2), (pc3, pc4), (pc5, pc6)]):
        relay_num = i + 1
        with on_col:
            if st.button(f"R{relay_num} ON", key=f"pixel_{relay_num}_on", use_container_width=True):
                resp = api_call("POST", "/relays/set-relay", json={"board": "pixel", "relay": relay_num, "on": True})
                if resp and resp.status_code == 200:
                    st.session_state.last_response = str(resp.json())
                st.rerun()
        with off_col:
            if st.button(f"R{relay_num} OFF", key=f"pixel_{relay_num}_off", use_container_width=True):
                resp = api_call("POST", "/relays/set-relay", json={"board": "pixel", "relay": relay_num, "on": False})
                if resp and resp.status_code == 200:
                    st.session_state.last_response = str(resp.json())
                st.rerun()
    
    # Row 2: Relays 4-6
    st.markdown("**Relays 4-6**")
    pc7, pc8, pc9, pc10, pc11, pc12 = st.columns(6)
    for i, (on_col, off_col) in enumerate([(pc7, pc8), (pc9, pc10), (pc11, pc12)]):
        relay_num = i + 4
        with on_col:
            if st.button(f"R{relay_num} ON", key=f"pixel_{relay_num}_on", use_container_width=True):
                resp = api_call("POST", "/relays/set-relay", json={"board": "pixel", "relay": relay_num, "on": True})
                if resp and resp.status_code == 200:
                    st.session_state.last_response = str(resp.json())
                st.rerun()
        with off_col:
            if st.button(f"R{relay_num} OFF", key=f"pixel_{relay_num}_off", use_container_width=True):
                resp = api_call("POST", "/relays/set-relay", json={"board": "pixel", "relay": relay_num, "on": False})
                if resp and resp.status_code == 200:
                    st.session_state.last_response = str(resp.json())
                st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# RGB BOARD
st.markdown('<div class="industrial-panel">', unsafe_allow_html=True)
st.markdown('<div class="panel-title">RGB/LED Relays (1-3)</div>', unsafe_allow_html=True)

if not st.session_state.rgb_connected:
    st.warning("RGB Arduino not connected")
else:
    rc1, rc2, rc3, rc4, rc5, rc6 = st.columns(6)
    for i, (on_col, off_col) in enumerate([(rc1, rc2), (rc3, rc4), (rc5, rc6)]):
        relay_num = i + 1
        with on_col:
            if st.button(f"R{relay_num} ON", key=f"rgb_{relay_num}_on", use_container_width=True):
                resp = api_call("POST", "/relays/set-relay", json={"board": "rgb", "relay": relay_num, "on": True})
                if resp and resp.status_code == 200:
                    st.session_state.last_response = str(resp.json())
                st.rerun()
        with off_col:
            if st.button(f"R{relay_num} OFF", key=f"rgb_{relay_num}_off", use_container_width=True):
                resp = api_call("POST", "/relays/set-relay", json={"board": "rgb", "relay": relay_num, "on": False})
                if resp and resp.status_code == 200:
                    st.session_state.last_response = str(resp.json())
                st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------
# RESPONSE LOG
# ----------------------------
st.markdown('<div class="industrial-panel">', unsafe_allow_html=True)
st.markdown('<div class="panel-title">Last Response</div>', unsafe_allow_html=True)
st.markdown(f'<div class="response-box">{st.session_state.last_response or "No response yet"}</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------
# PROTOCOL INFO
# ----------------------------
with st.expander("📖 Protocol Reference"):
    st.markdown("""
    **LabVIEW-Compatible Arduino Relay Protocol**
    
    | Action | Command | Example |
    |--------|---------|---------|
    | Relay OFF | `relay_num` | `5` turns relay 5 OFF |
    | Relay ON | `100 + relay_num` | `105` turns relay 5 ON |
    
    - **Baud Rate**: 112500
    - **Format**: ASCII number + newline (`\\n`)
    - **Response**: Read available bytes after 50ms delay
    
    **Board Configuration**
    - Pixel Arduino: COM38, Relays 1-6 (photodetector selection)
    - RGB Arduino: COM39, Relays 1-3 (LED wavelength selection)
    """)
