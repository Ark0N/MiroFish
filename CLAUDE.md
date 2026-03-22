# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MiroFish** is an AI-powered swarm intelligence prediction engine. Upload seed documents, build a knowledge graph, spawn thousands of AI agents with unique personalities, run social media simulations (Twitter/Reddit), and produce prediction reports from emergent agent behavior.

- **Tech Stack**: Python 3.11+ (Flask), Vue 3 (Vite), CAMEL-AI/OASIS for simulation, Graphiti + Neo4j for knowledge graphs, D3.js for visualization
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

# Run all tests (157 tests)
cd backend && uv run pytest

# Run specific test file
cd backend && uv run pytest tests/test_llm_client.py -v

# Run single test
cd backend && uv run pytest tests/test_llm_client.py::TestThinkTagStripping::test_single_line -v

# Backend Python dependencies only
cd backend && uv sync

# Docker (multi-stage build, gunicorn, non-root user; also starts Neo4j)
docker compose up --build
```

## Architecture

### 5-Step Pipeline

1. **Graph Construction** — Upload docs (PDF/MD/TXT) → `OntologyGenerator` extracts entity/relationship types via LLM → `GraphBuilderService` creates Graphiti/Neo4j knowledge graph. Ontology enforces exactly 10 entity types with `Person` and `Organization` as mandatory fallbacks.
2. **Environment Setup** — `GraphEntityReader` extracts entities → `OasisProfileGenerator` creates agent personas (CSV/JSON) → `SimulationConfigGenerator` generates simulation parameters including time dilation and peak activity hours (19:00-22:00 CST).
3. **Simulation** — `SimulationRunner` launches OASIS as subprocess → Twitter + Reddit run concurrently via `asyncio.gather` within a single subprocess → agents interact autonomously → `GraphMemoryUpdater` feeds actions back to graph. After rounds complete, simulation enters **Wait Mode** (process stays alive for post-simulation interviews).
4. **Report Generation** — `ReportAgent` (ReACT loop) uses 4 retrieval tools (InsightForge, PanoramaSearch, QuickSearch, interviews) → generates structured Markdown report.
5. **Deep Interaction** — Chat with ReportAgent or individual agents for follow-up analysis.

### Backend (`backend/app/`)

- `api/` — Flask blueprints: `graph.py` (ontology + graph building + project CRUD), `simulation.py` (largest API file), `report.py` — all under `/api/`
- `services/` — Core business logic:
  - `ontology_generator.py` — LLM-driven entity/relationship extraction (enforces exactly 10 entity types, excludes reserved field names like `uuid`, `created_at`, `summary`)
  - `graph_builder.py` — Graphiti wrapper. Graph IDs (group_ids) prefixed `mirofish_`. Text chunks sent as episodes via `add_episode()`. Uses `ontology_store.py` to cache entity types per group_id.
  - `oasis_profile_generator.py` — Converts entities to OASIS agent profiles (CSV/JSON)
  - `simulation_runner.py` — Subprocess-based OASIS execution with file-based IPC
  - `simulation_ipc.py` — Directory-based message queue: writes JSON commands to `ipc_commands/`, polls responses from `ipc_responses/`. Command types: `INTERVIEW`, `BATCH_INTERVIEW`, `CLOSE_ENV`
  - `simulation_manager.py` — Orchestrates simulation lifecycle. `SimulationStatus` enum: `CREATED` → `PREPARING` → `READY` → (running) → `COMPLETED`/`FAILED`
  - `report_agent.py` — ReACT tool loop (largest service file)
  - `graph_entity_reader.py` — Entity reader/filter from Neo4j graph
  - `graph_memory_updater.py` — Feeds simulation activities back to graph in real-time
  - `graph_tools.py` — Report agent retrieval tools (InsightForge, PanoramaSearch, QuickSearch, interviews)
  - `simulation_config_generator.py` — Generates OASIS config with time dilation and timezone settings
  - `text_processor.py` — Document text extraction and chunking
- `utils/` — `llm_client.py` (unified LLM client, auto-detects Anthropic vs OpenAI), `validation.py` (path traversal prevention), `retry.py` (exponential backoff decorator), `file_parser.py`/`file_utils.py` (multi-stage encoding fallback: UTF-8 → charset_normalizer → chardet → replace mode), `logger.py`, `graphiti_manager.py` (thread-safe Graphiti singleton + async bridge), `ontology_store.py`, `graph_paging.py`
- `models/` — File-based persistence (JSON on disk under `backend/uploads/projects/`). Atomic writes (temp file + `os.replace()`). No database. Project states: `CREATED` → `ONTOLOGY_GENERATED` → `GRAPH_BUILDING` → `GRAPH_COMPLETED`
- `scripts/` (at `backend/scripts/`, not `backend/app/scripts/`) — Standalone OASIS simulation runners (`run_twitter_simulation.py`, `run_reddit_simulation.py`, `run_parallel_simulation.py`) launched as subprocesses by `SimulationRunner`. Also `action_logger.py` (JSONL logging per platform) and `simulation_utils.py`.
- `tests/` — 157 unit and integration tests: `test_llm_client.py` (52), `test_api.py` (40), `test_project.py` (39), `test_retry.py` (25)

### Frontend (`frontend/src/`)

- Vue 3 Composition API (`<script setup>`) throughout, no state management library (just a simple reactive store in `store/pendingUpload.js` with localStorage persistence — uses `reactive()` deliberately since File objects can't be deeply reactive)
- `views/` — Page-level components: `Home.vue` (landing + file upload), `MainView.vue` (layout wrapper + multi-step wizard orchestrator), `SimulationRunView.vue`, `ReportView.vue`, `InteractionView.vue`, `NotFound.vue` (404)
- Router has `beforeEach` navigation guards validating required route params; routes use lazy loading via dynamic imports
- `components/Step{1-5}*.vue` — Workflow steps matching the 5-step pipeline. `Step4Report.vue` is the largest (~5046 lines)
- `components/GraphPanel.vue` — D3.js force-directed graph visualization with interactive node/edge selection
- `components/HistoryDatabase.vue` — History/database browser; `Toast.vue` + `composables/useToast.js` for notifications
- `api/` — Axios clients with 5-minute timeout, `requestWithRetry()` exponential backoff, proxied to `:5001` via Vite config
- Step 5 (Interaction) performs a multi-hop data fetch: `reportId` → `simulation_id` → `project_id` → `graph_id` → graph data
- No linting or formatting tools configured
- Custom CSS only (no framework), Google Fonts: Inter, JetBrains Mono, Noto Sans SC, Space Grotesk

### Key Patterns

- **File-based IPC**: Simulation subprocess communicates with Flask via directory-based message queue (`ipc_commands/` and `ipc_responses/` directories with JSON files), not pipes or sockets
- **Simulation Wait Mode**: After rounds complete, OASIS process stays alive for post-simulation agent interviews rather than exiting
- **Async operations**: Graph building, simulation, and report generation are all async tasks with progress polling (not WebSockets)
- **Thread safety**: `SimulationRunner` uses `threading.Lock` for class-level state; `GraphMemoryUpdater` uses `_counter_lock` for counter atomicity
- **Atomic persistence**: All JSON file writes use temp file + `os.replace()` to prevent corruption
- **JSONL action logging**: Agent actions stream to platform-specific `actions.jsonl` files via `PlatformActionLogger`; report agent uses `agent_log.jsonl`
- **Platform action whitelists**: Hardcoded in `config.py` — Twitter: `CREATE_POST`, `LIKE_POST`, `REPOST`, `FOLLOW`, `DO_NOTHING`, `QUOTE_POST`; Reddit: `LIKE_POST`, `DISLIKE_POST`, `CREATE_POST`, `CREATE_COMMENT`, `LIKE_COMMENT`, `DISLIKE_COMMENT`, `SEARCH_POSTS`, `SEARCH_USER`, `TREND`, `REFRESH`, `DO_NOTHING`, `FOLLOW`, `MUTE`
- **Process cleanup**: `atexit` handlers kill orphaned simulation subprocesses on Flask shutdown; simulation scripts handle `SIGINT`/`SIGTERM` for graceful closure; frontend calls `checkAndStopRunningSimulation()` on mount to terminate orphans
- **Simulation state files**: `run_state.json` (recovery after restart), `state.json` (metadata + entity counts) in project upload directory
- **Input validation**: `validate_safe_id()` prevents path traversal; API params have bounds checking
- **XSS prevention**: All `v-html` rendered content is sanitized via DOMPurify in shared `utils/markdown.js`
- **Graphiti communities**: `build_communities()` called after graph build; failure is non-fatal
- **UI language**: English (translated from original Chinese; some backend comments still in Chinese)

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
| `NEO4J_URI` | Yes | Neo4j bolt URI (default: `bolt://localhost:7687`) |
| `NEO4J_USER` | Yes | Neo4j username (default: `neo4j`) |
| `NEO4J_PASSWORD` | Yes | Neo4j password |
| `VOYAGE_API_KEY` | Yes | Voyage AI API key (for Graphiti embeddings) |
| `LLM_BOOST_*` | No | Optional second LLM for parallel simulation speedup |
| `CORS_ORIGINS` | No | Comma-separated origins (default: `http://localhost:3000,http://127.0.0.1:3000`) |
| `OASIS_DEFAULT_MAX_ROUNDS` | No | Simulation rounds (default: 10) |
| `REPORT_AGENT_MAX_TOOL_CALLS` | No | Max tool calls per report generation (default: 5) |
| `REPORT_AGENT_MAX_REFLECTION_ROUNDS` | No | Max reflection rounds (default: 2) |

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
