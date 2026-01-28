import streamlit as st
import os
import time
from pathlib import Path

# --- Configuration ---
st.set_page_config(
    page_title="IV Test Software - Login",
    page_icon="⚡",
    layout="wide",
)

# Path to protocols
PROTOCOLS_ROOT = Path(__file__).parent.parent / "protocols"
if not PROTOCOLS_ROOT.exists():
    PROTOCOLS_ROOT.mkdir(parents=True, exist_ok=True)

# Helper to get users (subfolders)
def get_users():
    return [d.name for d in PROTOCOLS_ROOT.iterdir() if d.is_dir() and not d.name.startswith(".")]

# --- Logic ---
if "user" not in st.session_state:
    st.session_state.user = None

st.title("⚡ IV Test Software")
st.markdown("---")

col1, col2 = st.columns([2, 1])

with col1:
    st.header("👤 User Selection")
    
    users = get_users()
    
    if not users:
        st.info("No users found. Please create a new user to get started.")
    else:
        # Use selectbox for existing users
        selected = st.selectbox("Select existing user:", options=users, index=0 if st.session_state.user in users else 0)
        
        if st.button("LOGIN AS USER", type="primary", use_container_width=True):
            st.session_state.user = selected
            st.toast(f"Logged in as {selected}")
            st.rerun()

with col2:
    st.header("➕ New User")
    new_user = st.text_input("Enter your name:")
    
    if st.button("CREATE USER", use_container_width=True):
        if not new_user:
            st.error("Name cannot be empty")
        elif new_user in users:
            st.error("User already exists")
        else:
            try:
                # Create directory
                (PROTOCOLS_ROOT / new_user).mkdir()
                st.session_state.user = new_user
                st.toast(f"User {new_user} created")
                st.rerun()
            except Exception as e:
                st.error(f"Error creating user: {e}")

# --- Current Status ---
st.divider()
if st.session_state.user:
    st.success(f"Current Session: **{st.session_state.user}**")
    st.info("You can now go to **Protocol Runner** via the sidebar to see your protocols.")
else:
    st.warning("Please select or create a user to enable personal protocol filtering.")

# Custom CSS for the landing page
st.markdown("""
<style>
    div.stButton > button {
        border-radius: 8px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)
