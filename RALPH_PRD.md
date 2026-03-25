# MiroFish Prediction Engine Optimization PRD

## Status Tracking

Each item uses: `[ ]` = pending, `[~]` = in progress, `[x]` = done

---

## Phase 1: Prediction Accuracy & Calibration

- [x] **1.1 Structured prediction schema** — Extend `report_agent.py` predictions section to output machine-readable JSON predictions (event, probability, timeframe, confidence_interval, reasoning) alongside the Markdown report. Store in `predictions.json` per report.

- [x] **1.2 Consensus strength scoring** — Enhance `ConsensusAnalysis` in `graph_tools.py` to compute a weighted consensus score that factors in agent diversity (persona type spread), conviction intensity (sentiment magnitude), and temporal stability (did consensus hold across rounds or flip-flop?). Surface this in the report.

- [x] **1.3 Contrarian agent injection** — Add a "Devil's Advocate" persona type in `oasis_profile_generator.py` that deliberately challenges emerging consensus. 5-10% of agents should be contrarians. Track whether contrarian arguments shift group opinion (a signal of weak consensus).

- [x] **1.4 Prediction confidence calibration** — Add a `PredictionCalibrator` service that compares agent consensus distribution to confidence bands. If 90% of agents agree → high confidence, but if contrarians successfully shifted opinion → downgrade. Wire into `report_agent.py` structured predictions.

## Phase 2: Real-Time & Temporal Intelligence

- [x] **2.1 News/RSS ingestion endpoint** — Add `POST /api/graph/ingest-url` that accepts URLs (news articles, RSS feeds), extracts text via `trafilatura` or `newspaper3k`, and feeds through existing `text_processor.py` → ontology → graph pipeline. Enables current-event prediction without manual PDF upload.

- [x] **2.2 Temporal event modeling** — Extend `simulation_config_generator.py` to model event cascades: when a major event fires at round N, generate follow-up derivative events at rounds N+2, N+5 based on graph relationships. E.g., "trade war announced" → "supply chain disruption" → "price increases".

- [x] **2.3 Time-decay relevance scoring** — Add recency weighting to `graph_tools.py` retrieval tools. Entities/episodes added more recently should rank higher in search results. Use episode timestamps from Graphiti.

- [~] **2.4 Multi-wave simulation** — Add ability to run sequential simulation waves where wave N+1 inherits the final state (opinion positions, relationships) of wave N but injects new events. Enables modeling how predictions evolve as situations develop.

## Phase 3: Swarm Intelligence Improvements

- [ ] **3.1 Faction detection & tracking** — Enhance `RoundMetricsTracker` in `action_logger.py` to identify emergent factions (clusters of agents with similar stances) per round. Track faction size, stability, and drift. Export to `faction_metrics.jsonl`.

- [ ] **3.2 Influence propagation analysis** — Track which agents' posts get the most engagement and how opinions spread through the follow graph. Add an `InfluenceTracker` that logs opinion adoption chains. Helps identify which agent archetypes drive prediction outcomes.

- [ ] **3.3 Sentiment momentum indicators** — Compute rate-of-change of sentiment per round in `RoundMetricsTracker`. If sentiment is accelerating in one direction, flag as "strong momentum". If decelerating, flag as "potential reversal". Include in round metrics.

- [ ] **3.4 Agent memory & learning** — Extend simulation scripts to give agents a short memory of their last 3-5 posts and interactions. Currently agents are stateless per round. Memory enables opinion evolution and more realistic prediction dynamics.

## Phase 4: Report & Output Quality

- [ ] **4.1 Prediction comparison view** — Add frontend component in Step 4 that renders structured predictions as a sortable table with probability bars, confidence indicators, and faction breakdown per prediction.

- [ ] **4.2 Prediction diff across runs** — When multiple simulations exist for a project, add a comparison view showing how predictions shifted between runs. Helps users see prediction stability.

- [ ] **4.3 Evidence chain linking** — Each prediction in the report should link back to specific agent posts, consensus moments, and graph entities that support it. Add citation IDs to structured predictions that reference action log entries.

- [ ] **4.4 Executive summary with risk matrix** — Auto-generate a 1-page executive summary with a 2x2 risk matrix (probability vs impact) from structured predictions. Add as first section of report.

---

## Ralph Loop Instructions

**When all items above are `[x]` done:**
1. Create a new section "## Phase N+1" with the next set of improvements
2. Focus on: advanced prediction techniques, external data integration, backtesting, multi-model ensemble, and user feedback loops
3. Continue working through the new items

**Work rules:**
- Pick the next `[ ]` item, mark it `[~]`, implement it, run tests, commit, mark `[x]`
- One item at a time, fully complete before moving on
- Run `cd backend && uv run pytest` after each change to ensure no regressions
- Commit after each completed item with `feat:` or `fix:` prefix
- If an item requires a new dependency, add it to `pyproject.toml` and run `uv sync`
- Keep changes focused — don't refactor unrelated code
- When creating new files, add tests in the appropriate test file
