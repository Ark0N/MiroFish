# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MiroFish** is an AI-powered swarm intelligence prediction engine. Upload seed documents, build a knowledge graph, spawn thousands of AI agents with unique personalities, run social media simulations (Twitter/Reddit), and produce prediction reports from emergent agent behavior.

- **Tech Stack**: Python 3.11+ (Flask), Vue 3 (Vite), CAMEL-AI/OASIS for simulation, Graphiti + Neo4j for knowledge graphs, D3.js for visualization
- **LLM**: Hybrid setup — Claude (Anthropic) for quality-critical phases (ontology, graph, reports), local Ollama on GPU for simulation agents (zero API cost). Auto-detected from `sk-ant-` key prefix. Upstream uses Qwen/OpenAI.
- **License**: AGPL-3.0

## Prerequisites

- Node.js >= 18, Python 3.11–3.12, [uv](https://docs.astral.sh/uv/) (Python package manager)
- Neo4j 5.x (or use `docker compose up` which includes it)
- Ollama with `nomic-embed-text` pulled locally (for embeddings)
- Copy `.env.example` → `.env` and fill in required values

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

# Run all tests (655 tests)
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
2. **Environment Setup** — `GraphEntityReader` extracts entities → `OasisProfileGenerator` creates agent personas (CSV/JSON) with action tendency guidance and initial follow relationships from graph edges → `SimulationConfigGenerator` generates simulation parameters including time dilation, peak activity hours (19:00-22:00 CST), per-agent temperature, power-law activity distribution, and scheduled mid-simulation events.
3. **Simulation** — `SimulationRunner` launches OASIS as subprocess → Twitter + Reddit run concurrently via `asyncio.gather` within a single subprocess → agents interact autonomously with per-agent temperature and network-based feed filtering → `GraphMemoryUpdater` feeds actions back to graph → `RoundMetricsTracker` computes per-round sentiment/activity metrics → scheduled events inject at configured rounds. After rounds complete, simulation enters **Wait Mode** (process stays alive for post-simulation interviews).
4. **Report Generation** — `ReportAgent` (ReACT loop) uses 5 retrieval tools (InsightForge, PanoramaSearch, QuickSearch, ConsensusAnalysis, interviews) → generates structured Markdown report with appended structured predictions (confidence levels derived from agent consensus).
5. **Deep Interaction** — Chat with ReportAgent or individual agents for follow-up analysis.

### Backend (`backend/app/`)

- `api/` — Flask blueprints: `graph.py` (ontology + graph building + project CRUD), `simulation.py` (largest API file), `report.py`, `settings.py` (model catalog + pricing) — all under `/api/`
- `services/` — Core business logic:
  - `ontology_generator.py` — LLM-driven entity/relationship extraction (enforces exactly 10 entity types, excludes reserved field names like `uuid`, `created_at`, `summary`)
  - `graph_builder.py` — Graphiti wrapper. Graph IDs (group_ids) prefixed `mirofish_`. Text chunks sent as episodes via `add_episode()`. Uses `ontology_store.py` to cache entity types per group_id.
  - `oasis_profile_generator.py` — Converts entities to OASIS agent profiles (CSV/JSON) with action tendency prompts (Creator/Engager/Lurker/Influencer) and auto-generated follow relationships from graph edges
  - `simulation_runner.py` — Subprocess-based OASIS execution with file-based IPC
  - `simulation_ipc.py` — Directory-based message queue: writes JSON commands to `ipc_commands/`, polls responses from `ipc_responses/`. Command types: `INTERVIEW`, `BATCH_INTERVIEW`, `INJECT_EVENT`, `CLOSE_ENV`
  - `simulation_manager.py` — Orchestrates simulation lifecycle. `SimulationStatus` enum: `CREATED` → `PREPARING` → `READY` → (running) → `COMPLETED`/`FAILED`
  - `report_agent.py` — ReACT tool loop (largest service file)
  - `graph_entity_reader.py` — Entity reader/filter from Neo4j graph
  - `graph_memory_updater.py` — Feeds simulation activities back to graph in real-time
  - `graph_tools.py` — Report agent retrieval tools (InsightForge, PanoramaSearch, QuickSearch, ConsensusAnalysis, interviews). ConsensusAnalysis reads action logs to compute stance distribution, sentiment trajectory, factions, and agreement scores
  - `simulation_config_generator.py` — Generates OASIS config with time dilation, timezone settings, per-agent temperature, power-law activity distribution, and scheduled mid-simulation events
  - `text_processor.py` — Document text extraction and chunking
  - **Prediction Engine** — 37 stateless, composable services in `services/`. Orchestrated by `prediction_pipeline.py` (with step resumption). Key groups:
    - **Core**: `prediction_calibrator.py` (consensus + contrarian calibration), `bayesian_updater.py`, `ensemble_predictor.py`, `prediction_pipeline.py`
    - **Validation**: `prediction_backtester.py` (Brier scores), `bootstrap_confidence.py`, `cross_validator.py`, `stress_tester.py`
    - **Analysis**: `contradiction_detector.py`, `disagreement_analyzer.py`, `minority_amplifier.py`, `uncertainty_decomposer.py`, `counterfactual.py`
    - **Agent/Network**: `opinion_drift.py`, `network_influence.py`, `echo_chamber.py`, `coalition_detector.py`, `simulation_quality.py`
    - **Lifecycle**: `prediction_decay.py`, `prediction_versioning.py`, `prediction_dedup.py`, `change_notifier.py`
    - **Composition**: `prediction_dependencies.py` (causal graph), `prediction_chaining.py` (AND/OR/THEN), `scenario_tree.py`, `pattern_matcher.py`
    - **Output**: `prediction_narrative.py`, `prediction_digest.py`, `prediction_provenance.py`, `prediction_market.py`, `prediction_graph_bridge.py`
    - **Ingestion**: `rss_monitor.py`, `batch_ingester.py`, `source_credibility.py`, `trend_detector.py`
    - **Meta**: `analytics.py`, `adaptive_rounds.py`, `multi_wave.py`, `parameter_learner.py`
    - See `RALPH_PRD.md` for the full feature list
- `utils/` — `llm_client.py` (unified LLM client, auto-detects Anthropic vs OpenAI), `validation.py` (path traversal prevention), `retry.py` (exponential backoff decorator), `file_parser.py`/`file_utils.py` (multi-stage encoding fallback: UTF-8 → charset_normalizer → chardet → replace mode), `logger.py`, `graphiti_manager.py` (thread-safe Graphiti singleton + async bridge + embedder factory: Voyage AI or local Ollama), `ontology_store.py` (thread-safe ontology cache), `graph_paging.py`, `url_extractor.py` (web page text extraction via trafilatura)
- `models/` — File-based persistence (JSON on disk under `backend/uploads/projects/`). Atomic writes (temp file + `os.replace()`). No database. Project states: `CREATED` → `ONTOLOGY_GENERATED` → `GRAPH_BUILDING` → `GRAPH_COMPLETED`
- `scripts/` (at `backend/scripts/`, not `backend/app/scripts/`) — Standalone OASIS simulation runners (`run_twitter_simulation.py`, `run_reddit_simulation.py`, `run_parallel_simulation.py`) launched as subprocesses by `SimulationRunner`. Also `action_logger.py` (JSONL logging per platform + `RoundMetricsTracker` for per-round sentiment/activity/faction metrics + `InfluenceTracker` for engagement analysis), `agent_memory.py` (per-agent rolling memory buffer for opinion continuity), and `simulation_utils.py` (dual LLM config, model creation, signal handlers).
- `tests/` — 655 tests across 7 files: `test_llm_client.py`, `test_api.py`, `test_project.py`, `test_retry.py`, `test_swarm_intelligence.py`, `test_predictions.py` (prediction engine), `test_integration.py` (cross-service integration). Pytest config in `pyproject.toml` (`[tool.pytest.ini_options]`). No `conftest.py` — tests are self-contained with `unittest.mock` (no real API/DB calls)

### Frontend (`frontend/src/`)

- Vue 3 Composition API (`<script setup>`) throughout, no state management library (reactive stores in `store/` with localStorage persistence)
- `store/pendingUpload.js` — File upload state (uses `reactive()` deliberately since File objects can't be deeply reactive)
- `store/settings.js` — Persists `modelName`, `maxAgents`, `maxRounds` to localStorage; injected into API calls
- `views/` — Page-level components: `Home.vue` (landing + file upload + settings modal), `MainView.vue` (layout wrapper + multi-step wizard orchestrator), `SimulationView.vue`, `SimulationRunView.vue`, `ReportView.vue`, `InteractionView.vue`, `NotFound.vue` (404)
- Router has `beforeEach` navigation guards validating required route params; routes use lazy loading via dynamic imports
- `components/Step{1-5}*.vue` — Workflow steps matching the 5-step pipeline. `Step4Report.vue` includes the full prediction dashboard (PredictionTable, health badges, uncertainty bars, contradiction alerts, scenario comparison)
- **Prediction dashboard components**: `PredictionTable.vue` (sortable predictions with probability bars), `PredictionHealthBadge.vue` (fresh/aging/stale/boosted status), `UncertaintyBar.vue` (epistemic vs aleatoric), `ContradictionAlert.vue` (severity-coded warnings), `ScenarioCompare.vue` (best/worst/most-likely), `PredictionDiffTable.vue` (cross-report comparison with delta arrows), `QualityGradeBadge.vue` (A-F simulation quality in Step3)
- `components/GraphPanel.vue` — D3.js force-directed graph visualization with interactive node/edge selection
- `components/SettingsModal.vue` — Model selection (Haiku/Sonnet/Opus with per-token pricing), cost comparison bars, simulation scale controls (maxAgents 1-10000, maxRounds 1-1000)
- `components/HistoryDatabase.vue` — History/database browser; `Toast.vue` + `composables/useToast.js` for notifications; `composables/useSystemLog.js` for system logging
- `api/` — Axios clients with 5-minute timeout, `requestWithRetry()` exponential backoff, proxied to `:5001` via Vite config. Includes `settings.js` for model catalog endpoint
- Step 5 (Interaction) performs a multi-hop data fetch: `reportId` → `simulation_id` → `project_id` → `graph_id` → graph data
- No linting or formatting tools configured
- Custom CSS only (no framework), Google Fonts: Inter, JetBrains Mono, Noto Sans SC, Space Grotesk

### Key Patterns

**Simulation Architecture**
- **File-based IPC**: Subprocess ↔ Flask via directory-based JSON message queue (`ipc_commands/`/`ipc_responses/`), not pipes or sockets
- **Wait Mode**: After simulation rounds complete, OASIS process stays alive for post-simulation agent interviews
- **Agent behavior**: Power-law activity distribution (Pareto α=1.5, matching 90-9-1 rule), per-agent LLM temperature by persona type (0.3 officials → 0.9 students), network-based feed filtering from graph edges
- **Contrarian agents**: 5-10% injected as "Devil's Advocate" types (`is_contrarian` flag) to challenge consensus and assess fragility
- **Event system**: Scheduled events at configured rounds + real-time injection via `INJECT_EVENT` IPC; cascading derivative events at +2 and +5 rounds
- **JSONL logging**: `actions.jsonl` (per-platform), `round_metrics.jsonl` (sentiment/activity), `faction_metrics.jsonl` (factions), `agent_log.jsonl` (report agent)
- **Sentiment tracking**: Per-round velocity/acceleration, faction detection (supportive/opposing/neutral), momentum signals

**Data & Persistence**
- **No database for projects** — file-based JSON on disk (`backend/uploads/projects/`). Atomic writes via temp file + `os.replace()`
- **Async operations**: Graph building, simulation, and report generation are async with progress polling (not WebSockets)
- **Thread safety**: `SimulationRunner` uses `threading.Lock`; `GraphMemoryUpdater` uses `_counter_lock`
- **State files**: `run_state.json` (crash recovery), `state.json` (metadata) per project upload directory
- **Time-decay search**: Graph results re-ranked by recency (exponential decay, 30-day half-life)

**Predictions**
- Structured JSON predictions alongside markdown reports: event, probability, confidence_interval, timeframe, reasoning, evidence, risk_factors, agent_agreement, impact_level. Saved to `predictions.json` per report
- Full lifecycle: extraction → calibration → Bayesian updating → ensemble aggregation → decay → versioning → backtesting → stress testing → narrative. All 37 services stateless and composable. See `RALPH_PRD.md`

**Safety & Ops**
- **Cost tracking**: `CostTracker` singleton with `BudgetExceededError` at `PIPELINE_BUDGET_LIMIT` ($20 default). HTTP 402 on budget exceeded
- **Process cleanup**: `atexit` handlers kill orphaned subprocesses; `SIGINT`/`SIGTERM` handlers in simulation scripts; frontend calls `checkAndStopRunningSimulation()` on mount
- **Input validation**: `validate_safe_id()` for path traversal; DOMPurify in `utils/markdown.js` for XSS; platform action whitelists in `config.py`
- **UI language**: English (translated from Chinese; some backend comments still in Chinese)

## LLM Integration (Fork-Specific)

### Hybrid Architecture

This fork uses a **two-tier LLM setup** to balance quality and cost:

- **Primary LLM (Claude)** — Used for quality-critical phases: ontology extraction, graph building (Graphiti entity extraction), profile generation, config generation, and report generation. Configured via `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL_NAME`.
- **Simulation LLM (local Ollama)** — Used for all simulation agent calls (both Twitter and Reddit). Configured via `LLM_BOOST_*` env vars. When `LLM_BOOST_API_KEY` is set, both platforms route to it; otherwise falls back to the primary LLM.

### Embeddings

Embeddings for Graphiti semantic search use a configurable backend via `_create_embedder()` in `graphiti_manager.py`:
- **Default**: Local Ollama with `nomic-embed-text` (768 dims, no API key, no rate limits)
- **Optional**: Voyage AI (set `VOYAGE_API_KEY` to enable)

### Key Files

- **`llm_client.py`** — `LLMClient` auto-detects `sk-ant-` keys, separates system messages (Claude requirement), strips `<think>` tags, appends JSON instruction instead of `response_format: json_object`
- **`graphiti_manager.py`** — `_create_embedder()` factory picks Voyage AI or local OpenAI-compatible embedder; `GraphitiManager` singleton with async bridge (`run_async`)
- **`simulation_utils.py`** — `create_model()` supports dual LLM configs; detects Anthropic keys for `ModelPlatformType.ANTHROPIC`, routes boost config to OpenAI-compatible endpoints (Ollama)
- **`run_parallel_simulation.py`** — Both Twitter and Reddit use `create_model(config, use_boost=True)` to route all simulation traffic to the local LLM

## Environment Variables (`.env`)

| Variable | Required | Description |
|---|---|---|
| `LLM_API_KEY` | Yes | Anthropic API key (`sk-ant-...`) |
| `LLM_BASE_URL` | Yes | `https://api.anthropic.com/v1/` |
| `LLM_MODEL_NAME` | Yes | e.g., `claude-haiku-4-5-20251001` |
| `NEO4J_URI` | Yes | Neo4j bolt URI (default: `bolt://localhost:7687`) |
| `NEO4J_USER` | Yes | Neo4j username (default: `neo4j`) |
| `NEO4J_PASSWORD` | Yes | Neo4j password |
| `VOYAGE_API_KEY` | No | Voyage AI API key (if set, uses Voyage instead of local embeddings) |
| `EMBEDDER_BASE_URL` | No | Local embedder URL (default: `http://localhost:11434/v1` for Ollama) |
| `EMBEDDER_MODEL` | No | Local embedding model (default: `nomic-embed-text`) |
| `EMBEDDER_DIM` | No | Embedding dimensions (default: `768`) |
| `LLM_BOOST_API_KEY` | No | Simulation LLM API key (e.g. `ollama` for Ollama) |
| `LLM_BOOST_BASE_URL` | No | Simulation LLM URL (e.g. `http://<gpu-host>:11434/v1`) |
| `LLM_BOOST_MODEL_NAME` | No | Simulation LLM model (e.g. `qwen3-sim` — Qwen3:32b with thinking disabled) |
| `CORS_ORIGINS` | No | Comma-separated origins (default: `http://localhost:3000,http://127.0.0.1:3000`) |
| `OASIS_DEFAULT_MAX_ROUNDS` | No | Simulation rounds (default: 30) |
| `REPORT_AGENT_MAX_TOOL_CALLS` | No | Max tool calls per report generation (default: 10) |
| `REPORT_AGENT_MAX_REFLECTION_ROUNDS` | No | Max reflection rounds (default: 3) |
| `REPORT_AGENT_TEMPERATURE` | No | Report agent LLM temperature (default: 0.5) |
| `PIPELINE_BUDGET_LIMIT` | No | Max USD cost per pipeline run before aborting (default: 20.0) |

## API Endpoints

- `POST /api/graph/ontology/generate` — Upload files + generate ontology (multipart form)
- `POST /api/graph/build` — Build knowledge graph (async, poll via `GET /api/graph/task/{task_id}`)
- `GET /api/graph/data/{graph_id}` — Fetch graph nodes/edges
- `POST /api/simulation/prepare` — Generate agent profiles (async)
- `POST /api/simulation/run` — Execute simulation
- `POST /api/report/generate` — Generate report (async)
- `POST /api/report/chat` — Chat with ReportAgent
- `GET /api/report/{report_id}/predictions` — Get structured predictions JSON
- `POST /api/report/compare-predictions` — Compare predictions across reports
- `GET /api/report/ensemble/{project_id}` — Ensemble predictions from all reports
- `POST /api/report/{report_id}/predictions/{idx}/rate` — Rate prediction quality (1-5)
- `POST /api/report/{report_id}/predictions/{idx}/note` — Add analyst note
- `POST /api/graph/ingest-url` — Ingest text from URLs (news/RSS)
- `POST /api/graph/webhook/event` — External event webhook with optional simulation injection
- `GET /api/report/<report_id>/digest` — Compact one-paragraph prediction summary
- `GET /api/report/<report_id>/scenarios` — Scenario tree (best/worst/most-likely)
- `GET /api/report/<report_id>/predictions/export?format=csv|jsonl` — Export predictions
- `GET /api/report/<report_id>/changes?severity=minor|significant|major` — Recent prediction changes
- `GET /api/report/catalog` — List all prediction services and endpoints
- `GET /api/report/selftest` — Run self-test on all prediction services
- `GET /api/analytics/simulation/{simulation_id}` — Simulation analytics dashboard
- `GET /api/analytics/agents/{simulation_id}` — Agent behavior profiles
- `GET /api/analytics/network/{simulation_id}` — Network influence + echo chambers
- `GET /api/analytics/quality/{simulation_id}` — Simulation quality score (A-F)
- `GET /api/settings/models` — List available Claude models with pricing
- `GET /health` — Health check

## Cost & Infrastructure

- **With local simulation LLM** (`LLM_BOOST_*` configured): Simulation runs at $0 API cost. Only ontology/graph/reports use Claude (~$0.50-1.50/run).
- **Without local LLM**: All calls go through Claude API. A 45-agent, 15-round simulation costs ~$3-4 on Haiku. Start with <40 rounds.
- **Local Ollama setup**: Requires `ollama pull nomic-embed-text` on the local machine (embeddings) and a GPU machine running Ollama with `qwen3-sim` (simulation agents, created from `qwen3:32b` with thinking disabled and 16K context via custom Modelfile).

## CI/CD

- GitHub Actions workflow (`.github/workflows/docker-image.yml`): Builds multi-platform Docker image on tag pushes using QEMU
- Docker production setup: multi-stage build (Node for frontend → Python 3.11-slim with gunicorn), non-root user, 300s request timeout
- E2E tests (`.github/workflows/e2e.yml`): Playwright-based browser tests in `e2e/` directory, tiered by scope:
  - `tier1` — Smoke tests (no external services beyond Flask+Vite)
  - `tier2` — Integration tests (needs Neo4j, Ollama, LLM API key)
  - `pipeline` — Full pipeline tests (long-running, > 5 min)
  - Run locally: `cd e2e && uv run pytest -m tier1` (or `tier2`, `pipeline`)

