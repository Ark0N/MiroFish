# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MiroFish** is an AI-powered swarm intelligence prediction engine. Upload seed documents, build a knowledge graph, spawn thousands of AI agents with unique personalities, run social media simulations (Twitter/Reddit), and produce prediction reports from emergent agent behavior.

- **Tech Stack**: Python 3.11+ (Flask), Vue 3 (Vite), CAMEL-AI/OASIS for simulation, Zep Cloud for knowledge graphs, D3.js for visualization
- **LLM**: This fork uses Claude (Anthropic) via native SDK — auto-detected from `sk-ant-` API key prefix. Upstream uses Qwen/OpenAI.
- **License**: AGPL-3.0

## Build & Run Commands

```bash
# Install everything (Node + Python)
npm run setup:all

# Development (both backend + frontend concurrently)
npm run dev

# Individual services
npm run backend    # Flask on port 5001
npm run frontend   # Vite on port 3000

# Build frontend
npm run build

# Run tests
cd backend && uv run pytest

# Backend Python dependencies only
cd backend && uv sync

# Docker
docker compose up
```

## Architecture

### 5-Step Pipeline

1. **Graph Construction** — Upload docs (PDF/MD/TXT) → `OntologyGenerator` extracts entity/relationship types via LLM → `GraphBuilderService` creates Zep knowledge graph
2. **Environment Setup** — `ZepEntityReader` extracts entities → `OasisProfileGenerator` creates agent personas → `SimulationConfigGenerator` generates simulation parameters
3. **Simulation** — `SimulationRunner` launches OASIS as subprocess (Twitter + Reddit in parallel) → agents interact autonomously → `ZepGraphMemoryUpdater` feeds actions back to graph
4. **Report Generation** — `ReportAgent` (ReACT loop) uses 4 retrieval tools (InsightForge, PanoramaSearch, QuickSearch, interviews) → generates structured Markdown report
5. **Deep Interaction** — Chat with ReportAgent or individual agents for follow-up analysis

### Backend (`backend/app/`)

- `api/` — Flask blueprints: `graph.py` (~620 lines, handles ontology + graph building + project CRUD), `simulation.py`, `report.py` (all under `/api/`)
- `services/` — Core business logic. Key services: `ontology_generator.py`, `graph_builder.py` (Zep SDK wrapper), `oasis_profile_generator.py` (entities → OASIS agent profiles as CSV/JSON), `simulation_runner.py` (subprocess-based OASIS execution with IPC), `report_agent.py` (ReACT tool loop)
- `utils/llm_client.py` — Unified LLM client with `chat()` and `chat_json()` methods. Auto-detects Anthropic keys (`sk-ant-*`) vs OpenAI-compatible. Strips `<think>` tags from reasoning models. For JSON mode with Claude, appends system prompt instruction instead of `response_format`.
- `models/` — File-based persistence (JSON on disk under `backend/uploads/projects/`). No database. Project states: `CREATED` → `ONTOLOGY_GENERATED` → `GRAPH_BUILDING` → `GRAPH_COMPLETED`
- `scripts/` — Standalone OASIS simulation runners (`run_twitter_simulation.py`, `run_reddit_simulation.py`, `run_parallel_simulation.py`) launched as subprocesses by `SimulationRunner`

### Frontend (`frontend/src/`)

- Vue 3 Composition API (`<script setup>`) throughout, no state management library (just a simple reactive store in `store/pendingUpload.js`)
- `views/` — Page-level: `Home.vue` (landing + file upload), `MainView.vue` (layout wrapper + multi-step wizard orchestrator), `SimulationRunView.vue`, `ReportView.vue`, `InteractionView.vue`
- `components/Step{1-5}*.vue` — Workflow steps matching the 5-step pipeline. Step4Report.vue is the largest (~5150 lines)
- `components/GraphPanel.vue` — D3.js force-directed graph visualization with interactive node/edge selection
- `api/` — Axios clients with 5-minute timeout, `requestWithRetry()` exponential backoff, proxied to `:5001` via Vite config
- No linting or formatting tools configured
- Custom CSS only (no framework), Google Fonts: Inter, JetBrains Mono, Noto Sans SC, Space Grotesk

### Key Patterns

- **Async operations**: Graph building, simulation, and report generation are all async tasks with progress polling (not WebSockets)
- **Subprocess isolation**: OASIS simulations run in separate Python processes with IPC to avoid blocking Flask
- **Bilingual UI**: Chinese primary with English support
- **Simulation actions**: Twitter (CREATE_POST, LIKE_POST, REPOST, FOLLOW, QUOTE_POST, DO_NOTHING), Reddit (LIKE_POST, DISLIKE_POST, CREATE_POST, CREATE_COMMENT, etc.)

## Claude API Integration (Fork-Specific)

This fork adapts all LLM calls for Anthropic's native SDK:

- **`llm_client.py`** — `LLMClient` auto-detects `sk-ant-` keys, separates system messages (Claude requirement), appends JSON instruction instead of `response_format: json_object`
- **`oasis_profile_generator.py`** — `_generate_profile_with_llm` calls Anthropic API natively
- **`simulation_config_generator.py`** — `_call_llm_with_retry` patched for Anthropic
- **`run_*.py` scripts** — Detect Anthropic keys and use `ModelPlatformType.ANTHROPIC` in CAMEL-AI instead of `OPENAI`

## Environment Variables (`.env`)

| Variable | Required | Description |
|---|---|---|
| `LLM_API_KEY` | Yes | Anthropic API key (`sk-ant-...`) |
| `LLM_BASE_URL` | Yes | `https://api.anthropic.com/v1/` |
| `LLM_MODEL_NAME` | Yes | e.g., `claude-haiku-4-5-20251001` |
| `ZEP_API_KEY` | Yes | Zep Cloud API key |
| `LLM_BOOST_*` | No | Optional second LLM for parallel simulation speedup |
| `OASIS_DEFAULT_MAX_ROUNDS` | No | Simulation rounds (default: 10) |

## API Endpoints

- `POST /api/graph/ontology/generate` — Upload files + generate ontology (multipart form)
- `POST /api/graph/build` — Build knowledge graph (async, poll via `GET /api/graph/task/{task_id}`)
- `GET /api/graph/data/{graph_id}` — Fetch graph nodes/edges
- `POST /api/simulation/prepare` — Generate agent profiles (async)
- `POST /api/simulation/run` — Execute simulation
- `POST /api/report/generate` — Generate report (async)
- `POST /api/report/chat` — Chat with ReportAgent
- `GET /health` — Health check

## Cost Warning

Simulations run hundreds/thousands of LLM calls. Start with <40 rounds. Use `claude-haiku-4-5-20251001` for testing.

---

## Codeman Environment

This session is managed by **Codeman** and runs within a tmux session.

**Important**: Check for `CODEMAN_MUX=1` environment variable to confirm.
- Do NOT attempt to kill your own tmux session
- The session persists across disconnects - your work is safe

## Work Principles

### Autonomy
Full permissions granted. Act decisively without asking.

### Git Discipline
- **Commit after every meaningful change**
- Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`

### Task Tracking (TodoWrite)
**ALWAYS use TodoWrite** for multi-step tasks (3+ steps). Mark each todo `in_progress` before starting, `completed` when done. One at a time.

### Planning Mode (Automatic)
Enter planning mode automatically for multi-file changes (3+), architectural decisions, unclear requirements, or new features. Skip only for single-file fixes, typos, and simple config changes.

## Session Log

| Date | Tasks Completed | Files Changed | Notes |
|------|-----------------|---------------|-------|
| 2026-03-22 | Project created | CLAUDE.md | Initial setup |
| 2026-03-22 | Claude API integration | llm_client.py, oasis_profile_generator.py, simulation_config_generator.py, run_*.py, .env | Adapted all LLM calls for Anthropic native SDK |
