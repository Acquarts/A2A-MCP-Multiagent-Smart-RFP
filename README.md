# Smart RFP/Proposal Agent

> Multi-agent system that automates the creation of professional commercial and technical proposals using A2A (Agent-to-Agent) orchestration and MCP (Model Context Protocol).

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Anthropic](https://img.shields.io/badge/Anthropic-Claude_Sonnet_4-6B4FBB?logo=anthropic&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-Model_Context_Protocol-00ADD8?logo=data:image/svg+xml;base64,&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)
![Tavily](https://img.shields.io/badge/Tavily-Web_Search-FF6B35)
![httpx](https://img.shields.io/badge/httpx-Async_HTTP-2D3748)
![python-docx](https://img.shields.io/badge/python--docx-DOCX_Export-2B579A?logo=microsoftword&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-FF4B4B?logo=streamlit&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## What Problem Does It Solve?

Writing commercial and technical proposals is a **time-consuming, repetitive process** that involves:

- Researching the prospective client (company profile, key decision-makers, industry context)
- Analyzing RFP documents to extract requirements, budget constraints, and evaluation criteria
- Searching internal records for relevant past projects and case studies
- Estimating costs based on team composition, complexity, and project scope
- Writing a structured, professional proposal that ties everything together

This system **automates the entire pipeline** — from client research to final deliverable — by coordinating four specialized AI agents through a single conversational interface. What traditionally takes days of manual work is reduced to a single interactive session.

---

## Architecture

The system follows an **A2A (Agent-to-Agent)** pattern where a central orchestrator powered by Claude coordinates four independent agents, each running as an **MCP (Model Context Protocol)** server.

```
                         ┌─────────────────────────────┐
                         │        User (CLI Chat)       │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │   Orchestrator (Claude LLM)  │
                         │   A2A Coordination Engine     │
                         │   Agentic Loop (max 10 iter) │
                         └──┬───────┬───────┬───────┬───┘
                            │       │       │       │
                  ┌─────────▼──┐ ┌──▼─────┐ ┌▼──────┐ ┌▼────────┐
                  │  Client    │ │Knowledge│ │Proposal│ │ Pricing │
                  │  Research  │ │  Base   │ │ Writer │ │  Agent  │
                  │  Agent     │ │  Agent  │ │ Agent  │ │         │
                  │ (MCP Srv)  │ │(MCP Srv)│ │(MCP Sv)│ │(MCP Srv)│
                  └────────────┘ └────────┘ └────────┘ └─────────┘
```

### How It Works

1. The user submits a request through the **interactive CLI** (e.g., _"Create a proposal for Acme Corp for a mobile app project"_)
2. The **Orchestrator** analyzes the request using Claude and determines which agents and tools to invoke
3. Agents are called via **MCP tool execution** — each agent runs as a subprocess communicating over stdio
4. The orchestrator loops (up to 10 iterations), calling tools and accumulating context until Claude produces a final synthesized response
5. The user receives a **complete, professional proposal** ready for client submission
6. Optionally, the proposal is **exported to a .docx file** with cover page, branding, and professional formatting

---

## Agent Cards (A2A Discovery)

The system uses **Agent Cards** to implement the A2A discovery pattern. Each agent publishes a card (defined via Pydantic models in [agent_cards.py](orchestrator/agent_cards.py)) that declares its identity, capabilities, and how to start it. The orchestrator reads these cards at runtime to discover available agents and route tasks.

```python
class AgentCard(BaseModel):
    agent_id: str           # Unique identifier (e.g., "client_research")
    name: str               # Human-readable name
    description: str        # What the agent does
    version: str            # Semantic version
    status: AgentStatus     # available | busy | offline
    skills: list[AgentSkill]        # List of capabilities with MCP tool mappings
    mcp_server_command: list[str]   # Command to launch the MCP server subprocess
    dependencies: list[str]         # Other agent IDs this agent depends on
```

Each **AgentSkill** maps a high-level capability to a specific MCP tool and includes example queries that help the orchestrator understand when to invoke it:

| Agent Card | Skills | Dependencies |
|------------|--------|--------------|
| `client_research` | `company_research`, `rfp_analysis`, `linkedin_research` | — |
| `knowledge_base` | `project_search`, `project_details`, `tech_stack_search`, `case_studies` | — |
| `proposal_writer` | `full_proposal`, `timeline`, `executive_summary`, `export_docx` | `client_research`, `knowledge_base` |
| `pricing` | `project_estimation`, `custom_estimation`, `rate_card` | — |

All cards are registered in `AGENT_REGISTRY`, making it easy to add new agents — just define a new `AgentCard` and register it.

---

## Agents

### Client Research Agent
Investigates prospective clients using web search and AI analysis.

| Tool | Description |
|------|-------------|
| `search_company_info` | Searches the web via Tavily and extracts a structured company profile using Claude |
| `analyze_rfp_document` | Parses RFP text to extract requirements, budget, timeline, and evaluation criteria |
| `search_linkedin_company` | Finds key decision-makers and company info via LinkedIn proxy search |

### Knowledge Base Agent
Searches an internal database of past projects for relevant experience and case studies.

| Tool | Description |
|------|-------------|
| `search_past_projects` | Keyword matching + Claude semantic ranking of internal projects |
| `get_project_details` | Retrieves full details for a specific project by ID |
| `search_tech_stack` | Finds projects that used specific technologies |
| `get_case_studies` | Retrieves case studies relevant to a client's industry sector |

### Proposal Writer Agent
Generates professional, structured proposals with bilingual support (English/Spanish).

| Tool | Description |
|------|-------------|
| `generate_proposal` | Creates a full 8-section proposal from gathered context |
| `generate_timeline` | Builds project phases with milestones and deliverables |
| `generate_executive_summary` | Distills the proposal into key executive talking points |
| `export_proposal_docx` | Exports the markdown proposal to a professional Word (.docx) file |

**Proposal Sections:** Executive Summary, Understanding, Proposed Solution, Methodology, Team, Case Studies, Investment, Next Steps

### Pricing Agent
Estimates project costs with configurable team composition, complexity multipliers, and discount tiers.

| Tool | Description |
|------|-------------|
| `estimate_project` | AI analyzes scope, recommends team composition, and calculates total cost |
| `estimate_from_roles` | Manual team-based pricing with custom role selection |
| `get_rate_card` | Returns hourly rates, complexity multipliers, and discount rules |

**Pricing Features:**
- 9 predefined roles with hourly rates (EUR 60–100/hr)
- Complexity multipliers: low (0.8x) to very high (1.6x)
- Discount tiers: standard, long-term, strategic (up to 10%)
- Phase-based cost distribution (discovery 8%, design 12%, development 50%, testing 15%, deployment 15%)

---

## Tech Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| **LLM** | [Anthropic Claude API](https://docs.anthropic.com/) | Reasoning, analysis, content generation |
| **Agent Framework** | [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) / FastMCP | Agent server framework and tool registration |
| **Orchestration** | A2A Protocol | Multi-agent coordination and routing |
| **Web Search** | [Tavily API](https://tavily.com/) | Company research and LinkedIn proxy search |
| **HTTP Client** | [httpx](https://www.python-httpx.org/) | Async HTTP requests to external APIs |
| **Validation** | [Pydantic v2](https://docs.pydantic.dev/) | Input/output data validation and serialization |
| **Document Export** | [python-docx](https://python-docx.readthedocs.io/) | Export proposals to professional Word (.docx) files |
| **Frontend** | [Streamlit](https://streamlit.io/) | Web-based chat UI with agent visibility |
| **Config** | [python-dotenv](https://pypi.org/project/python-dotenv/) | Environment variable management |
| **Language** | Python 3.10+ | Async/await, type hints, structural pattern matching |

---

## Project Structure

```
smart-rfp-agent/
├── agents/
│   ├── client_research/          # Client & RFP research agent
│   │   ├── server.py             # MCP server definition & entrypoint
│   │   ├── tools.py              # Tool implementations (Tavily + Claude)
│   │   └── models.py             # Pydantic input/output models
│   ├── knowledge_base/           # Internal project database agent
│   │   ├── server.py             # MCP server definition
│   │   ├── tools.py              # Search & ranking logic
│   │   ├── models.py             # Pydantic models
│   │   └── data/
│   │       └── projects.json     # Past projects database
│   ├── proposal_writer/          # Proposal generation agent
│   │   ├── server.py             # MCP server definition
│   │   ├── tools.py              # Proposal generation logic
│   │   ├── models.py             # Pydantic models (bilingual support)
│   │   └── templates/
│   │       └── proposal_structure.json  # 8-section proposal template
│   └── pricing/                  # Cost estimation agent
│       ├── server.py             # MCP server definition
│       ├── tools.py              # Pricing calculation logic
│       ├── models.py             # Pydantic models
│       └── data/
│           └── rate_card.json    # Rates, multipliers & discounts
├── orchestrator/
│   ├── main.py                   # Interactive CLI entrypoint
│   ├── orchestrator.py           # A2A engine (Claude + agentic loop)
│   ├── agent_cards.py            # Agent capability registry
│   └── mcp_client.py             # MCP subprocess connection manager
├── streamlit_helpers/
│   ├── async_bridge.py           # Async-to-sync bridge (background event loop)
│   └── components.py             # Reusable UI components (sidebar, chat, i18n)
├── shared/
│   ├── utils.py                  # Shared error handling utilities
│   └── docx_exporter.py          # Markdown → DOCX converter with branding
├── config/
│   └── settings.py               # Environment variables & configuration
├── app.py                        # Streamlit web frontend
├── requirements.txt
└── .env.example
```

---

## Setup

### Prerequisites
- Python 3.10+
- [Anthropic API key](https://console.anthropic.com/)
- [Tavily API key](https://tavily.com/) (for web search)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/smart-rfp-agent.git
cd smart-rfp-agent

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and add your API keys
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API access key |
| `TAVILY_API_KEY` | Yes | Tavily web search API key |
| `LINKEDIN_CLIENT_ID` | No | LinkedIn API client ID |
| `LINKEDIN_CLIENT_SECRET` | No | LinkedIn API client secret |
| `MCP_TRANSPORT` | No | Transport protocol (default: `stdio`) |
| `MCP_PORT` | No | Server port (default: `8000`) |

### Running

**Web UI (Streamlit) — Recommended:**

```bash
streamlit run app.py
```

This opens a browser-based chat interface with:
- Real-time conversation with the AI orchestrator
- Sidebar showing connected agents and their skills
- Language selector (English / Spanish)
- One-click DOCX export and download
- New conversation button

**CLI (Terminal):**

```bash
python orchestrator/main.py
```

| Command | Description |
|---------|-------------|
| `/new` | Start a new conversation |
| `/agents` | List available agents and their tools |
| `/quit` | Exit the application |

### Running Agents Standalone

Each agent can be run independently as an MCP server for testing or integration:

```bash
python agents/client_research/server.py
python agents/knowledge_base/server.py
python agents/proposal_writer/server.py
python agents/pricing/server.py
```

---

## Example Usage

```
> Research Acme Corp and create a proposal for a mobile e-commerce app

[Orchestrator calls Client Research Agent → searches company info]
[Orchestrator calls Knowledge Base Agent → finds similar past projects]
[Orchestrator calls Pricing Agent → estimates project cost]
[Orchestrator calls Proposal Writer Agent → generates full proposal]

✅ Complete 8-section proposal generated with:
   - Company analysis and context
   - Technical solution architecture
   - Relevant case studies from past projects
   - Detailed cost breakdown and timeline
   - Executive summary and next steps

> Export the proposal to Word

[Proposal Writer Agent → exports to DOCX]

✅ Saved to exports/proposal_acme_corp_20260207_143022.docx
```

---

## Key Design Decisions

- **MCP over REST**: Agents communicate via stdio-based MCP rather than HTTP, eliminating network overhead and simplifying local deployment
- **Agentic loop**: The orchestrator lets Claude decide which tools to call and in what order, enabling flexible multi-step reasoning
- **Bilingual support**: Proposals can be generated in English or Spanish via a simple language parameter
- **Configurable pricing**: Rate cards, complexity multipliers, and discount tiers are stored in JSON files for easy customization without code changes
- **DOCX export**: Proposals can be exported to professional Word documents with cover page, branded styling, headers/footers, and page numbers via `python-docx`
- **Agent Cards (A2A discovery)**: Each agent publishes a structured card declaring its skills, MCP tool mappings, and dependencies, enabling dynamic discovery and extensibility
- **Modular agents**: Each agent is fully independent and can be developed, tested, or replaced without affecting the rest of the system
