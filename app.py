"""Smart RFP Agent — Streamlit Frontend.

Run with: streamlit run app.py
"""

import os
import re
import sys
import logging
import atexit

import streamlit as st

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from streamlit_helpers.async_bridge import OrchestratorBridge
from streamlit_helpers.components import render_sidebar, render_chat_history, t
from shared.docx_exporter import export_proposal_to_docx

# ── Logging ─────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# ── Page Config ─────────────────────────────────────────────────────

st.set_page_config(
    page_title="Smart RFP Agent",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session State ───────────────────────────────────────────────────

DEFAULTS = {
    "bridge": None,
    "initialized": False,
    "init_error": None,
    "messages": [],
    "connected_agents": [],
    "language": "EN",
    "last_docx_path": None,
    "pending_export": False,
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ── Orchestrator Bootstrap ──────────────────────────────────────────

def ensure_orchestrator() -> bool:
    """Initialize the orchestrator bridge once per session."""
    if st.session_state["initialized"]:
        return True

    if st.session_state["bridge"] is None:
        try:
            bridge = OrchestratorBridge()
            connected = bridge.start()
            st.session_state["bridge"] = bridge
            st.session_state["connected_agents"] = connected
            st.session_state["initialized"] = True
            atexit.register(bridge.stop)
            return True
        except Exception as e:
            st.session_state["init_error"] = str(e)
            return False
    return True


if not st.session_state["initialized"]:
    with st.spinner("Starting orchestrator and connecting agents..."):
        if not ensure_orchestrator():
            st.error(f"**{t('config_error')}:** {st.session_state['init_error']}")
            st.info("Make sure your `.env` file has `ANTHROPIC_API_KEY` and `TAVILY_API_KEY`.")
            st.stop()

bridge: OrchestratorBridge = st.session_state["bridge"]


# ── Sidebar ─────────────────────────────────────────────────────────

sidebar_action = render_sidebar(st.session_state["connected_agents"])

if sidebar_action == "reset":
    bridge.reset_conversation()
    st.session_state["messages"] = []
    st.session_state["last_docx_path"] = None
    st.session_state["pending_export"] = False
    st.rerun()

if sidebar_action == "export":
    if bridge.pending_proposal_md:
        path = export_proposal_to_docx(
            markdown_content=bridge.pending_proposal_md,
            client_name=bridge.pending_proposal_client or "Client",
        )
        st.session_state["last_docx_path"] = path
        st.session_state["pending_export"] = False
        st.rerun()


# ── Welcome Message ─────────────────────────────────────────────────

if not st.session_state["messages"]:
    st.session_state["messages"].append({
        "role": "assistant",
        "content": t("welcome"),
    })


# ── Chat History ────────────────────────────────────────────────────

render_chat_history(st.session_state["messages"])


# ── Chat Input ──────────────────────────────────────────────────────

if prompt := st.chat_input(t("placeholder")):
    # Show user message
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)

    # Get orchestrator response
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner(t("processing")):
            try:
                response = bridge.chat(prompt)
            except Exception as e:
                response = f"**Error:** {e}"

        st.markdown(response)

    st.session_state["messages"].append({"role": "assistant", "content": response})

    # Detect DOCX file path in response
    docx_match = re.search(r"(exports[/\\][^\s\"']+\.docx)", response)
    if docx_match:
        docx_path = docx_match.group(1)
        if os.path.exists(docx_path):
            st.session_state["last_docx_path"] = docx_path
            st.session_state["pending_export"] = False

    # If a proposal was generated, enable the export button
    if bridge.pending_proposal_md and not st.session_state.get("last_docx_path"):
        st.session_state["pending_export"] = True

    st.rerun()
