"""Application settings loaded from environment variables or Streamlit secrets."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    """Read from env vars first, then fall back to Streamlit secrets."""
    value = os.getenv(key, "")
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    # Claude API
    anthropic_api_key: str = ""

    # Tavily Web Search
    tavily_api_key: str = ""

    # LinkedIn API
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""

    # MCP Server
    mcp_transport: str = "stdio"
    mcp_port: int = 8000

    def validate(self) -> list[str]:
        """Return list of missing required keys."""
        missing = []
        if not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        if not self.tavily_api_key:
            missing.append("TAVILY_API_KEY")
        return missing


settings = Settings(
    anthropic_api_key=_get_secret("ANTHROPIC_API_KEY"),
    tavily_api_key=_get_secret("TAVILY_API_KEY"),
    linkedin_client_id=_get_secret("LINKEDIN_CLIENT_ID"),
    linkedin_client_secret=_get_secret("LINKEDIN_CLIENT_SECRET"),
    mcp_transport=_get_secret("MCP_TRANSPORT", "stdio"),
    mcp_port=int(_get_secret("MCP_PORT", "8000")),
)
