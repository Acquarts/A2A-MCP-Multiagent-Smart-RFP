"""Smart RFP Agent — Main entrypoint.

Interactive CLI that starts the orchestrator, connects to available
agents, and lets you chat with the system.

Usage:
    python -m orchestrator.main
    python orchestrator/main.py
"""

import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator.orchestrator import Orchestrator

# ── Logging Setup ──────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── CLI Interface ──────────────────────────────────────────────────

WELCOME_BANNER = """
╔══════════════════════════════════════════════════════════════╗
║              🤖 Smart RFP/Proposal Agent                    ║
║                                                              ║
║  Commands:                                                   ║
║    /new     — Start a new conversation                       ║
║    /agents  — List connected agents                          ║
║    /quit    — Exit                                           ║
║                                                              ║
║  Just type your request to get started!                      ║
║  Example: "Research Acme Corp for a mobile app proposal"     ║
╚══════════════════════════════════════════════════════════════╝
"""


async def main():
    orchestrator = Orchestrator()

    print(WELCOME_BANNER)

    # Start orchestrator and connect agents
    try:
        await orchestrator.start()
    except RuntimeError as e:
        print(f"\n❌ Startup error: {e}")
        print("   Make sure your .env file has the required API keys.")
        return

    agents = orchestrator.pool.get_available_agents()
    if not agents:
        print("⚠️  No agents connected. Check agent configurations.")
        return

    print(f"✅ Ready! {len(agents)} agent(s) online: {', '.join(agents)}\n")

    # Interactive loop
    try:
        while True:
            try:
                user_input = input("\n🧑 You: ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() == "/quit":
                break
            elif user_input.lower() == "/new":
                orchestrator.reset_conversation()
                print("🔄 Conversation reset.")
                continue
            elif user_input.lower() == "/agents":
                for agent_id in agents:
                    from orchestrator.agent_cards import AGENT_REGISTRY
                    card = AGENT_REGISTRY.get(agent_id)
                    if card:
                        print(f"  {card.name} — {len(card.skills)} skill(s)")
                continue

            # Process through orchestrator
            print("\n⏳ Processing...\n")
            try:
                response = await orchestrator.chat(user_input)
                print(f"🤖 Agent:\n{response}")
            except Exception as e:
                logger.error(f"Error processing request: {e}", exc_info=True)
                print(f"\n❌ Error: {e}")

    finally:
        await orchestrator.stop()
        print("\n👋 Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
