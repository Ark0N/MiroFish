# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MiroFish** is an AI-powered swarm intelligence prediction engine. It uploads seed documents, builds a knowledge graph, spawns thousands of AI agents with unique personalities, runs social media simulations (Twitter/Reddit), and produces prediction reports from emergent agent behavior.

- **Tech Stack**: Python 3.11+ (Flask), Vue 3 (Vite), CAMEL-AI/OASIS for simulation, Zep Cloud for knowledge graphs, D3.js for visualization
- **LLM**: Configured to use Claude (Anthropic) via native SDK — auto-detected from `sk-ant-` API key prefix
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
```

## Architecture

### 5-Step Pipeline

1. **Graph Construction** — Upload docs (PDF/MD/TXT) → `OntologyGenerator` extracts entity/relationship types via LLM → `GraphBuilderService` creates Zep knowledge graph
2. **Environment Setup** — `ZepEntityReader` extracts entities → `OasisProfileGenerator` creates agent personas → `SimulationConfigGenerator` generates simulation parameters
3. **Simulation** — `SimulationRunner` launches OASIS as subprocess (Twitter + Reddit in parallel) → agents interact autonomously → `ZepGraphMemoryUpdater` feeds actions back to graph
4. **Report Generation** — `ReportAgent` (ReACT loop) uses 4 retrieval tools (InsightForge, PanoramaSearch, QuickSearch, interviews) → generates structured Markdown report
5. **Deep Interaction** — Chat with ReportAgent or individual agents for follow-up analysis

### Backend Structure (`backend/app/`)

- `api/` — Flask blueprints: `graph.py`, `simulation.py`, `report.py` (all under `/api/`)
- `services/` — Core business logic (graph building, ontology, profiles, simulation management, report agent)
- `utils/llm_client.py` — Unified LLM client, auto-detects Anthropic keys and uses native SDK
- `models/` — File-based persistence (JSON on disk, no database)
- `scripts/` — OASIS simulation runners (launched as subprocesses)

### Frontend Structure (`frontend/src/`)

- `components/Step{1-5}*.vue` — Workflow steps matching the 5-step pipeline
- `components/GraphPanel.vue` — D3.js knowledge graph visualization
- `api/` — Axios clients with retry logic, proxied to `:5001` via Vite config
- `views/` — Page-level components (Home, MainView, SimulationRunView, ReportView, InteractionView)

### Key Data Flow

```
Documents → LLM (Ontology) → Zep (Knowledge Graph) → Entity Extraction
→ Agent Profiles → OASIS Simulation (Twitter/Reddit subprocess)
→ Actions feed back to Zep Graph → ReACT Report Agent → Markdown Report
→ Interactive Chat
```

### Persistence

All data is file-based JSON under `backend/uploads/projects/`. No SQL database.

## Claude API Integration (Custom)

This fork is adapted to use Claude instead of the default Qwen/OpenAI models:

- **`backend/app/utils/llm_client.py`** — `LLMClient` auto-detects `sk-ant-` keys, uses Anthropic native SDK with proper system message separation and JSON prompting
- **`backend/app/services/oasis_profile_generator.py`** — Patched `_enhance_with_llm` to call Anthropic API natively
- **`backend/app/services/simulation_config_generator.py`** — Patched `_call_llm_with_retry` for Anthropic
- **`backend/scripts/run_*.py`** — All 3 simulation scripts detect Anthropic keys and use `ModelPlatformType.ANTHROPIC` in CAMEL-AI instead of `OPENAI`
- **JSON mode**: Claude doesn't support `response_format: json_object` — instead, a system prompt instruction is appended asking for pure JSON output

## Environment Variables (`.env`)

| Variable | Required | Description |
|---|---|---|
| `LLM_API_KEY` | Yes | Anthropic API key (`sk-ant-...`) |
| `LLM_BASE_URL` | Yes | `https://api.anthropic.com/v1/` |
| `LLM_MODEL_NAME` | Yes | e.g., `claude-haiku-4-5-20251001` |
| `ZEP_API_KEY` | Yes | Zep Cloud API key |
| `LLM_BOOST_*` | No | Optional second LLM for parallel simulation speedup |

## API Endpoints

- `/api/graph/*` — Ontology generation, graph building, graph data retrieval
- `/api/simulation/*` — Entity reading, simulation lifecycle, interviews, action history
- `/api/report/*` — Report generation, progress, sections, chat, agent logs
- `/health` — Health check

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
