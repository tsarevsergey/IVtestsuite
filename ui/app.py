import streamlit as st

st.set_page_config(
    page_title="IV Test Software",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ IV Test Software")

st.sidebar.success("Select a page above.")

st.markdown("""
### Welcome to the IV Test Software Control Center

This application allows you to:
- **Control SMU Hardware**: Configure and monitor Source Measure Units.
- **Manage Relays**: Select pixels and LED channels.
- **Run Protocols**: Execute automated IV measurement sequences.
- **Test API**: Directly interact with backend endpoints.

Use the sidebar on the left to navigate between different modules.
""")
