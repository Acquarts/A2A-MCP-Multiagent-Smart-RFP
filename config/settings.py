"""Application settings loaded from environment variables."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    # Claude API
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Tavily Web Search
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")

    # LinkedIn API
    linkedin_client_id: str = os.getenv("LINKEDIN_CLIENT_ID", "")
    linkedin_client_secret: str = os.getenv("LINKEDIN_CLIENT_SECRET", "")

    # MCP Server
    mcp_transport: str = os.getenv("MCP_TRANSPORT", "stdio")
    mcp_port: int = int(os.getenv("MCP_PORT", "8000"))

    def validate(self) -> list[str]:
        """Return list of missing required keys."""
        missing = []
        if not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        if not self.tavily_api_key:
            missing.append("TAVILY_API_KEY")
        return missing


settings = Settings()
