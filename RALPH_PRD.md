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

- [x] **2.4 Multi-wave simulation** — Add ability to run sequential simulation waves where wave N+1 inherits the final state (opinion positions, relationships) of wave N but injects new events. Enables modeling how predictions evolve as situations develop.

## Phase 3: Swarm Intelligence Improvements

- [x] **3.1 Faction detection & tracking** — Enhance `RoundMetricsTracker` in `action_logger.py` to identify emergent factions (clusters of agents with similar stances) per round. Track faction size, stability, and drift. Export to `faction_metrics.jsonl`.

- [x] **3.2 Influence propagation analysis** — Track which agents' posts get the most engagement and how opinions spread through the follow graph. Add an `InfluenceTracker` that logs opinion adoption chains. Helps identify which agent archetypes drive prediction outcomes.

- [x] **3.3 Sentiment momentum indicators** — Compute rate-of-change of sentiment per round in `RoundMetricsTracker`. If sentiment is accelerating in one direction, flag as "strong momentum". If decelerating, flag as "potential reversal". Include in round metrics.

- [x] **3.4 Agent memory & learning** — Extend simulation scripts to give agents a short memory of their last 3-5 posts and interactions. Currently agents are stateless per round. Memory enables opinion evolution and more realistic prediction dynamics.

## Phase 4: Report & Output Quality

- [x] **4.1 Prediction comparison view** — Add frontend component in Step 4 that renders structured predictions as a sortable table with probability bars, confidence indicators, and faction breakdown per prediction.

- [x] **4.2 Prediction diff across runs** — When multiple simulations exist for a project, add a comparison view showing how predictions shifted between runs. Helps users see prediction stability.

- [x] **4.3 Evidence chain linking** — Each prediction in the report should link back to specific agent posts, consensus moments, and graph entities that support it. Add citation IDs to structured predictions that reference action log entries.

- [x] **4.4 Executive summary with risk matrix** — Auto-generate a 1-page executive summary with a 2x2 risk matrix (probability vs impact) from structured predictions. Add as first section of report.

## Phase 5: Advanced Prediction Techniques

- [x] **5.1 Bayesian prediction updating** — Add a `BayesianUpdater` service that adjusts prediction probabilities as new evidence arrives. When a new simulation wave completes or new data is ingested, update prior probabilities using Bayes' theorem with the new consensus data as likelihood. Store update history for transparency.

- [x] **5.2 Ensemble prediction aggregation** — When multiple simulations exist for the same project, automatically aggregate predictions across all simulations using weighted averaging. Weight by simulation recency, agent count, and consensus strength. Expose via `GET /api/report/ensemble/<project_id>`.

- [x] **5.3 Historical pattern matching** — Add a `PatternMatcher` service that compares current simulation dynamics (sentiment trajectory, faction evolution, momentum) against previously completed simulations. Identify similar historical patterns and use their outcomes to adjust current predictions.

- [x] **5.4 Prediction backtesting framework** — Add ability to mark predictions as "resolved" (correct/incorrect) with actual outcomes. Compute calibration curves (predicted vs actual probability) across resolved predictions. Store in `prediction_outcomes.json` per project.

## Phase 6: External Data Integration

- [x] **6.1 RSS feed monitor** — Add a background service that periodically checks configured RSS feeds for new articles. When new content is detected, automatically extract text and queue it for graph enrichment. Store feed config in project settings.

- [x] **6.2 Trend detection from ingested data** — Add a `TrendDetector` that analyzes temporal patterns in ingested content. Identify emerging topics, sentiment shifts in source material, and new entity appearances. Surface as alerts in the prediction pipeline.

- [x] **6.3 Real-time event webhook** — Add `POST /api/graph/webhook/event` that accepts structured event notifications from external systems. Events flow through the cascade engine and can trigger mid-simulation injections.

- [x] **6.4 Source credibility scoring** — Track source reliability based on prediction accuracy. Sources that consistently provide information leading to accurate predictions get higher credibility weights. Apply credibility to graph entity episode weighting.

## Phase 7: User Feedback Loops

- [x] **7.1 Prediction rating system** — Add `POST /api/report/<report_id>/predictions/<idx>/rate` endpoint where users can rate prediction quality (1-5 stars) and provide brief feedback. Aggregate ratings influence future calibration.

- [x] **7.2 Analyst notes on predictions** — Allow users to attach notes to individual predictions via `POST /api/report/<report_id>/predictions/<idx>/note`. Notes persist alongside predictions and appear in comparison views.

- [x] **7.3 Simulation parameter learning** — Track which simulation configurations (agent count, round count, temperature settings) produce the most accurate predictions. Use historical accuracy data to recommend optimal simulation parameters for new projects.

- [x] **7.4 Feedback-driven prompt tuning** — When predictions are marked as correct/incorrect, analyze which agent prompts and persona types contributed most to accurate predictions. Automatically adjust persona generation to weight successful archetypes.

## Phase 8: Prediction Pipeline Robustness

- [x] **8.1 Automated prediction pipeline** — Add a `PredictionPipeline` orchestrator that chains: URL ingestion → ontology → graph build → simulation → report → prediction extraction → calibration → backtesting in a single API call. Include progress tracking and resumption on failure.

- [x] **8.2 Prediction confidence bands** — Enhance prediction output with statistical confidence bands using bootstrap resampling of agent opinions. Run 100 bootstrap samples of agent sentiment to compute true confidence intervals rather than LLM-estimated ones.

- [x] **8.3 Cross-validation prediction scoring** — Split agents into train/test groups. Train group runs the simulation, test group evaluates independently. Compare train predictions vs test predictions for internal validation without waiting for real-world outcomes.

- [~] **8.4 Prediction decay tracking** — Track how predictions age over time. Predictions with no supporting evidence after N days get automatically downgraded. Predictions with new supporting evidence get boosted. Add `prediction_health.json` per report.

## Phase 9: Advanced Analytics Dashboard

- [ ] **9.1 Simulation analytics API** — Add `GET /api/analytics/simulation/<simulation_id>` returning comprehensive analytics: round-by-round sentiment curves, faction evolution charts, influence networks, momentum indicators, all in a single response for dashboard rendering.

- [ ] **9.2 Project-level insights** — Add `GET /api/analytics/project/<project_id>` aggregating across all simulations: prediction accuracy trends, consensus evolution, most influential agent types, parameter effectiveness heatmap.

- [ ] **9.3 Agent behavior profiling** — Add `GET /api/analytics/agents/<simulation_id>` returning per-agent analytics: posting frequency, sentiment consistency, influence score, faction membership history, opinion change events.

- [ ] **9.4 Prediction timeline visualization data** — Add `GET /api/analytics/prediction-timeline/<project_id>` returning time-series data of how each prediction's probability evolved across waves, backtesting outcomes, and Bayesian updates.

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
