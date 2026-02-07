"""Streamlit UI components for the Smart RFP Agent."""

import os
import streamlit as st

from orchestrator.agent_cards import AGENT_REGISTRY


# ── Translations ────────────────────────────────────────────────────

STRINGS = {
    "EN": {
        "title": "Smart RFP Agent",
        "subtitle": "AI-powered proposal generation",
        "new_chat": "New Conversation",
        "export_docx": "Download DOCX",
        "export_btn": "Export to DOCX",
        "agents_header": "Agents",
        "language": "Language",
        "placeholder": "Type your request... (e.g., 'Create a proposal for Acme Corp')",
        "processing": "Agents working on your request...",
        "config_error": "Configuration Error",
        "welcome": (
            "Welcome! I can help you create professional proposals.\n\n"
            "**Try asking me to:**\n"
            "- Research a company\n"
            "- Analyze an RFP document\n"
            "- Estimate project costs\n"
            "- Generate a full proposal\n"
            "- Export to Word (.docx)"
        ),
        "connected": "Connected",
        "disconnected": "Disconnected",
        "skills": "Skills",
    },
    "ES": {
        "title": "Agente Smart RFP",
        "subtitle": "Generacion de propuestas con IA",
        "new_chat": "Nueva Conversacion",
        "export_docx": "Descargar DOCX",
        "export_btn": "Exportar a DOCX",
        "agents_header": "Agentes",
        "language": "Idioma",
        "placeholder": "Escribe tu solicitud... (ej: 'Crea una propuesta para Acme Corp')",
        "processing": "Los agentes estan trabajando en tu solicitud...",
        "config_error": "Error de Configuracion",
        "welcome": (
            "Bienvenido! Puedo ayudarte a crear propuestas profesionales.\n\n"
            "**Prueba pidiendome:**\n"
            "- Investigar una empresa\n"
            "- Analizar un documento RFP\n"
            "- Estimar costos de un proyecto\n"
            "- Generar una propuesta completa\n"
            "- Exportar a Word (.docx)"
        ),
        "connected": "Conectado",
        "disconnected": "Desconectado",
        "skills": "Habilidades",
    },
}


def t(key: str) -> str:
    """Get translated string for current language."""
    lang = st.session_state.get("language", "EN")
    return STRINGS.get(lang, STRINGS["EN"]).get(key, key)


# ── Sidebar ─────────────────────────────────────────────────────────

def render_sidebar(connected_agents: list[str]) -> str | None:
    """Render sidebar with controls and agent cards. Returns action string or None."""
    with st.sidebar:
        st.markdown(
            "<h1 style='text-align: center;'>Smart RFP Agent</h1>",
            unsafe_allow_html=True,
        )
        st.caption(t("subtitle"))
        st.divider()

        # Language selector
        lang_options = ["EN", "ES"]
        current_idx = lang_options.index(st.session_state.get("language", "EN"))
        lang = st.selectbox(
            t("language"),
            options=lang_options,
            index=current_idx,
            key="lang_selector",
        )
        if lang != st.session_state.get("language"):
            st.session_state["language"] = lang
            st.rerun()

        # New conversation
        if st.button(t("new_chat"), use_container_width=True, type="primary"):
            return "reset"

        # DOCX export button
        if st.session_state.get("pending_export"):
            if st.button(t("export_btn"), use_container_width=True, type="secondary"):
                return "export"

        # Download button for generated DOCX
        docx_path = st.session_state.get("last_docx_path")
        if docx_path and os.path.exists(docx_path):
            with open(docx_path, "rb") as f:
                st.download_button(
                    label=t("export_docx"),
                    data=f.read(),
                    file_name=os.path.basename(docx_path),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

        st.divider()

        # Agent status cards
        st.subheader(t("agents_header"))
        for agent_id, card in AGENT_REGISTRY.items():
            is_connected = agent_id in connected_agents
            status_dot = "🟢" if is_connected else "🔴"
            status_text = t("connected") if is_connected else t("disconnected")

            with st.expander(f"{status_dot} {card.name}", expanded=False):
                st.caption(f"_{card.description}_")
                st.markdown(f"**{t('skills')}:**")
                for skill in card.skills:
                    st.markdown(f"- `{skill.mcp_tool_name}` — {skill.description}")

    return None


# ── Chat ────────────────────────────────────────────────────────────

def render_chat_history(messages: list[dict]):
    """Render all chat messages in the main area."""
    for msg in messages:
        role = msg["role"]
        with st.chat_message(role, avatar="🧑" if role == "user" else "🤖"):
            st.markdown(msg["content"])
