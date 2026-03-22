<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="75%"/>

**A Simple and Universal Swarm Intelligence Engine, Predicting Anything**

[![GitHub Stars](https://img.shields.io/github/stars/666ghj/MiroFish?style=flat-square&color=DAA520)](https://github.com/666ghj/MiroFish/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/666ghj/MiroFish?style=flat-square)](https://github.com/666ghj/MiroFish/network)
[![Docker](https://img.shields.io/badge/Docker-Build-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)
[![License](https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square)](LICENSE)

</div>

---

## What is MiroFish?

MiroFish is an AI-powered swarm intelligence prediction engine. Upload any seed document — a breaking news article, a policy draft, financial data, even a novel — and MiroFish builds a living digital world around it. Thousands of AI agents with unique personalities, memories, and behavioral patterns simulate realistic social interactions on Twitter and Reddit. The emergent collective behavior produces prediction reports that no single model could generate alone.

> **You provide**: seed documents + a prediction question in plain English.
> **MiroFish returns**: a detailed prediction report and a fully interactive digital world you can interrogate.

This is not toy-scale simulation. MiroFish runs thousands of autonomous agents across dual social platforms simultaneously, with real-time knowledge graph updates and a report agent that can interview any simulated person after the fact. The architecture is production-grade: atomic file persistence, subprocess isolation, graceful process cleanup, and a full 157-test suite.

## What This Fork Adds

This fork rewrites MiroFish's LLM backbone with a **hybrid architecture** that makes it dramatically more practical to run:

### Claude Integration (Quality Where It Matters)

The upstream project targets Chinese LLM providers (Qwen via Alibaba) and requires a Zep Cloud subscription for memory. This fork replaces both with **Anthropic Claude** for all quality-critical phases:

- **Ontology extraction** — Claude analyzes your documents and identifies entity types and relationships
- **Knowledge graph construction** — Graphiti entity extraction powered by Claude
- **Agent profile generation** — Rich, nuanced personality creation
- **Report generation** — ReACT-loop report agent with tool use
- **Configuration generation** — Simulation parameter planning

The `LLMClient` auto-detects Anthropic keys (`sk-ant-` prefix) and handles Claude-specific requirements automatically: system message separation, think-tag stripping, and JSON mode via instruction appending rather than `response_format`.

### Local LLM for Simulation ($0 API Cost)

The expensive part of MiroFish is the simulation — thousands of agent interactions across multiple rounds. This fork routes **all simulation traffic** to a local Ollama instance on your GPU:

- Both Twitter and Reddit platforms use the local model
- Zero API cost for simulation rounds (upstream costs $3-4 per run on Haiku alone)
- Only ontology/graph/reports hit the Claude API (~$0.50-1.50 per full run)
- Configure once with `LLM_BOOST_*` environment variables

### Local Embeddings (No External API Needed)

Upstream MiroFish requires a Voyage AI API key for embeddings. This fork defaults to **local Ollama embeddings** with `nomic-embed-text`:

- 768-dimension embeddings, entirely local
- No rate limits, no API keys, no cost
- Just `ollama pull nomic-embed-text` and you're set
- Voyage AI still supported as an optional upgrade

### No Zep Cloud Dependency

Upstream requires a Zep Cloud subscription for agent memory. This fork replaces it with **Graphiti + Neo4j** — a self-hosted knowledge graph that you control completely. No external memory service, no subscription, no data leaving your infrastructure.

## How It Works

MiroFish follows a 5-step pipeline:

| Step | What Happens |
|------|-------------|
| **1. Graph Construction** | Upload documents (PDF/MD/TXT). Claude extracts an ontology (entity types + relationships), then builds a Graphiti/Neo4j knowledge graph. |
| **2. Environment Setup** | Entities become agent personas. Claude generates detailed personality profiles and simulation parameters (time dilation, activity patterns). |
| **3. Simulation** | OASIS launches Twitter + Reddit simulations concurrently. Thousands of agents interact autonomously. Actions feed back into the knowledge graph in real-time. |
| **4. Report Generation** | A ReACT-loop report agent uses retrieval tools (InsightForge, PanoramaSearch, QuickSearch) and post-simulation interviews to generate a structured prediction report. |
| **5. Deep Interaction** | Chat with the report agent or any individual simulated agent for follow-up analysis. |

## Quick Start

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| **Node.js** | 18+ | Frontend runtime |
| **Python** | 3.11 - 3.12 | Backend runtime |
| **uv** | Latest | Python package manager |
| **Neo4j** | 5.x | Knowledge graph storage |
| **Ollama** | Latest | Local embeddings (+ optional simulation LLM) |

### 1. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Claude API (required)
LLM_API_KEY=sk-ant-your_key_here
LLM_BASE_URL=https://api.anthropic.com/v1/
LLM_MODEL_NAME=claude-haiku-4-5-20251001

# Neo4j (required)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Local embeddings via Ollama (default, no API key needed)
# Just run: ollama pull nomic-embed-text
EMBEDDER_BASE_URL=http://localhost:11434/v1
EMBEDDER_MODEL=nomic-embed-text
EMBEDDER_DIM=768

# Optional: Local simulation LLM for $0 agent costs
# LLM_BOOST_API_KEY=ollama
# LLM_BOOST_BASE_URL=http://your-gpu-machine:11434/v1
# LLM_BOOST_MODEL_NAME=qwen3-sim
```

### 2. Install Dependencies

```bash
npm run setup:all
```

### 3. Start Services

```bash
# Start both frontend and backend
npm run dev
```

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:5001`

```bash
# Or start individually
npm run backend    # Flask on port 5001
npm run frontend   # Vite on port 3000
```

### Docker Deployment

```bash
cp .env.example .env
docker compose up -d
```

Docker Compose includes Neo4j with health checks. Ports `3000` (frontend) and `5001` (backend) are mapped automatically.

## Cost Comparison

| Setup | Simulation Cost | Total Cost per Run |
|-------|----------------|-------------------|
| **This fork (with local LLM)** | $0 | ~$0.50 - $1.50 (Claude for ontology/graph/reports only) |
| **This fork (Claude only)** | ~$3-4 on Haiku | ~$4 - $5.50 |
| **Upstream (Qwen + Zep)** | Variable (Qwen API) | Variable + Zep subscription |

## Tech Stack

- **Backend**: Python 3.11+ / Flask / Graphiti + Neo4j / CAMEL-AI OASIS
- **Frontend**: Vue 3 (Composition API) / Vite / D3.js force-directed graphs / DOMPurify
- **LLMs**: Anthropic Claude (quality phases) + Ollama (simulation + embeddings)
- **Testing**: 157 tests across 4 test suites (pytest)
- **Persistence**: File-based JSON with atomic writes (temp file + `os.replace()`)

## Project Structure

```
backend/
  app/
    api/          # Flask blueprints (graph, simulation, report)
    services/     # Core business logic (11 service modules)
    utils/        # LLM client, Graphiti manager, validation, retry
    models/       # File-based project persistence
  scripts/        # OASIS simulation subprocess runners
  tests/          # 157 unit and integration tests
frontend/
  src/
    views/        # Page-level Vue components
    components/   # Step 1-5 workflow + graph visualization
    api/          # Axios clients with retry logic
    composables/  # Vue composables (toast notifications)
```

## Acknowledgments

MiroFish is built by the [MiroFish team](https://github.com/666ghj/MiroFish) with strategic support from Shanda Group. The simulation engine is powered by **[OASIS](https://github.com/camel-ai/oasis)** from the CAMEL-AI team.

This fork focuses on making MiroFish accessible to English-speaking users with best-in-class LLM integration and minimal external dependencies.

## License

[AGPL-3.0](LICENSE)
