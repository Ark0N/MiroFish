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

- [x] **8.4 Prediction decay tracking** — Track how predictions age over time. Predictions with no supporting evidence after N days get automatically downgraded. Predictions with new supporting evidence get boosted. Add `prediction_health.json` per report.

## Phase 9: Advanced Analytics Dashboard

- [x] **9.1 Simulation analytics API** — Add `GET /api/analytics/simulation/<simulation_id>` returning comprehensive analytics: round-by-round sentiment curves, faction evolution charts, influence networks, momentum indicators, all in a single response for dashboard rendering.

- [x] **9.2 Project-level insights** — Add `GET /api/analytics/project/<project_id>` aggregating across all simulations: prediction accuracy trends, consensus evolution, most influential agent types, parameter effectiveness heatmap.

- [x] **9.3 Agent behavior profiling** — Add `GET /api/analytics/agents/<simulation_id>` returning per-agent analytics: posting frequency, sentiment consistency, influence score, faction membership history, opinion change events.

- [x] **9.4 Prediction timeline visualization data** — Add `GET /api/analytics/prediction-timeline/<project_id>` returning time-series data of how each prediction's probability evolved across waves, backtesting outcomes, and Bayesian updates.

## Phase 10: Prediction Quality & Reliability

- [x] **10.1 Prediction deduplication** — Detect and merge duplicate/near-duplicate predictions across reports using semantic similarity. Prevents the same event from appearing multiple times with different probabilities in ensemble views.

- [x] **10.2 Prediction dependency graph** — Model causal dependencies between predictions. If Prediction A ("trade war") causes Prediction B ("supply chain disruption"), a change in A's probability should propagate to B. Store as a directed graph in predictions.json.

- [x] **10.3 Minority opinion amplification** — Weight contrarian/minority agent opinions more heavily when they provide unique information not captured by the majority. Use information-theoretic measures (surprise/entropy) to identify high-value dissenting signals.

- [x] **10.4 Prediction uncertainty decomposition** — Decompose total prediction uncertainty into epistemic (model/data uncertainty) and aleatoric (inherent randomness). Epistemic uncertainty should decrease with more data; aleatoric cannot. Report both to users.

## Phase 11: Integration & Scale

- [x] **11.1 Batch URL ingestion with rate limiting** — Enhance the URL ingestion endpoint to handle large batches (100+ URLs) with internal rate limiting, progress tracking, and partial failure recovery. Queue URLs and process asynchronously.

- [x] **11.2 Simulation warm-start from graph** — When starting a new simulation, pre-seed agent opinions from the knowledge graph entity sentiments rather than starting neutral. Agents connected to negative entities start with negative bias.

- [x] **11.3 Prediction export formats** — Add export endpoints for predictions in CSV, JSONL, and structured Markdown formats for integration with external tools and dashboards.

- [x] **11.4 Webhook notification on prediction changes** — When a prediction's probability changes significantly (>10% delta from Bayesian update, decay, or calibration), fire a webhook notification to configured URLs.

## Phase 12: Simulation Quality & Realism

- [x] **12.1 Agent opinion drift model** — Add a mathematical model for how agent opinions evolve over rounds. Each agent has an opinion inertia (resistance to change) and a susceptibility (how much they're influenced by others). Compute from persona attributes.

- [x] **12.2 Network effect weighting** — Weight agent influence by their position in the follow graph. Agents with many followers have more influence on overall sentiment. Use PageRank-like scoring on the follow network.

- [x] **12.3 Echo chamber detection** — Detect when agent subgroups form echo chambers (only interacting with like-minded agents). Flag this in analytics as it reduces prediction diversity and reliability.

- [x] **12.4 Simulation quality score** — Compute an overall quality metric for each simulation based on: agent diversity, network connectivity, opinion spread, participation rate, and absence of degenerate behaviors (all agents converging to same opinion instantly).

## Phase 13: Production Hardening

- [x] **13.1 Prediction versioning** — Track prediction versions when they're updated (Bayesian updates, decay, calibration). Store full version history for audit trail and regression detection.

- [x] **13.2 Rate limit middleware for analytics** — Add per-project and per-user rate limiting for expensive analytics endpoints. Prevent abuse while allowing legitimate use.

- [x] **13.3 Prediction caching layer** — Cache computed predictions, calibrations, and analytics. Invalidate cache when new simulation data or evidence arrives. Reduces recomputation for dashboard rendering.

- [x] **13.4 Health check for prediction services** — Add a `/api/health/predictions` endpoint that verifies all prediction services are operational: calibrator, Bayesian updater, ensemble, pattern matcher, etc.

## Phase 14: Prediction Explainability

- [x] **14.1 Prediction provenance tracker** — For each prediction, trace the full chain of evidence: which graph entities contributed, which agent posts supported it, which simulation rounds were pivotal. Store as a provenance DAG in `provenance.json` per report.

- [x] **14.2 Counterfactual analysis** — Add a service that asks "what if?" — given a prediction, compute how the probability would change if key factors were different (e.g., remove the most influential agent, flip a faction's stance). Report sensitivity to each factor.

- [x] **14.3 Prediction narrative generator** — Auto-generate a natural language narrative for each prediction explaining the causal chain in plain English: "This prediction is based on X agents who observed Y, supported by graph entity Z, and calibrated by consensus strength W."

- [x] **14.4 Disagreement analysis** — When agents disagree, identify the root cause: different information access, different persona biases, or genuine ambiguity. Classify disagreements to help users understand prediction uncertainty.

## Phase 15: Advanced Simulation Dynamics

- [x] **15.1 Adaptive round count** — Instead of fixed round counts, detect when consensus has stabilized (sentiment velocity < threshold for 3+ rounds) and auto-stop the simulation. Saves compute without losing prediction quality.

- [x] **15.2 Agent coalition formation** — Detect when agents spontaneously form coalitions (coordinated posting, mutual amplification). Track coalition stability and influence on predictions.

- [x] **15.3 Information cascade detection** — Identify when a single agent's post triggers a cascade of opinion changes across the network. These cascades are critical prediction signals — rapid adoption = strong consensus, failed cascades = weak signal.

- [x] **15.4 Simulation replay engine** — Enable replaying a simulation from any round with modified parameters or injected events. Compare alternate timelines to assess prediction robustness.

## Phase 16: Prediction Market Mechanics

- [x] **16.1 Agent betting pool** — Add a virtual prediction market where agents can "bet" on outcomes using karma points. Agents who are more confident in their stance commit more karma. The distribution of bets provides a market-based probability estimate that complements the sentiment-based one.

- [x] **16.2 Prediction arbitrage detector** — When the market-based probability diverges significantly from the sentiment-based probability, flag it as an arbitrage signal. This divergence often reveals that agents' actions (bets) don't match their words (posts), which is a strong predictor of actual behavior.

- [x] **16.3 Information elicitation scoring** — Score agents by how much new information their posts reveal (measured by entropy reduction in the prediction distribution after their post). Agents who consistently provide novel information get higher credibility weights.

- [x] **16.4 Crowd wisdom aggregation** — Implement multiple aggregation methods (mean, median, geometric mean, extremized mean) and compare their accuracy across historical predictions. Auto-select the best method per project based on backtesting data.

## Phase 17: Robustness Testing

- [x] **17.1 Prediction stress tester** — Systematically test how predictions respond to extreme inputs: all agents flipping stance, removing 50% of agents, injecting contradictory events. Reports a robustness score for each prediction.

- [x] **17.2 Simulation reproducibility checker** — Run the same simulation twice with different random seeds and compare outcomes. High divergence suggests the prediction is sensitive to randomness, not robust.

- [x] **17.3 Prediction stability index** — Compute a stability index for each prediction based on how much it changed across: Bayesian updates, calibration, decay, and cross-validation. Stable predictions get a "rock-solid" badge; volatile ones get a warning.

- [x] **17.4 Adversarial agent injection** — Beyond contrarians (who challenge consensus), add adversarial agents that deliberately spread misinformation. Test whether the prediction system is resilient to bad-faith actors.

## Phase 18: Prediction Composition & Reasoning

- [x] **18.1 Prediction chaining engine** — Given a set of predictions with dependency edges, compute joint probabilities for compound events (e.g., P(A AND B), P(A OR B), P(A THEN B)). Uses the dependency graph from 10.2 and conditional probability rules.

- [x] **18.2 Scenario tree builder** — Build a tree of mutually exclusive future scenarios from predictions. Each branch is a combination of prediction outcomes weighted by joint probability. Enables "best case / worst case / most likely" framing.

- [x] **18.3 Prediction contradiction detector** — Identify pairs of predictions that are logically contradictory (e.g., "prices rise" and "deflation occurs"). Flag contradictions with severity levels and suggest which prediction has stronger evidence.

- [x] **18.4 Impact magnitude estimator** — For each prediction, estimate the magnitude of impact (not just probability) using agent engagement intensity, post length, and emotional language markers. Produces a 1-10 impact score.

## Phase 19: System Integration Tests

- [x] **19.1 Service integration smoke tests** — Add integration tests that verify all 35+ services can be imported, instantiated, and their primary methods called without errors. Catches import cycles and missing dependencies.

- [x] **19.2 Data flow integration test** — Test the full data flow: create predictions → calibrate → update via Bayesian → check decay → compute ensemble → generate narrative. Verify data integrity at each step.

- [x] **19.3 Analytics pipeline test** — Test the full analytics path: create simulation metrics → extract fingerprint → detect factions → compute influence → detect echo chambers → score quality. All with synthetic data.

- [x] **19.4 Prediction lifecycle test** — Test a complete prediction lifecycle: create → version → calibrate → add evidence → decay → resolve → backtest → compute stability. Verify state consistency throughout.

## Phase 20: Pipeline Integration & Wiring

- [x] **20.1 Wire prediction engine into report generation** — Integrate the full prediction pipeline into `generate_report()`: after predictions are extracted, automatically run calibration → bootstrap confidence → cross-validation → dependency detection → deduplication → contradiction check → narrative generation → provenance tracking → executive summary. Store all artifacts alongside the report.

- [x] **20.2 Analytics API blueprint** — Create a dedicated `/api/analytics/` Flask blueprint exposing: `GET /simulation/<id>` (simulation analytics), `GET /agents/<id>` (agent profiles), `GET /network/<id>` (influence + echo chambers), `GET /quality/<id>` (quality score). Wire to existing AnalyticsService.

- [x] **20.3 Prediction health dashboard endpoint** — Add `GET /api/report/<id>/health` that returns prediction health (decay), stability index, contradiction warnings, and uncertainty decomposition for all predictions in a report. Single endpoint for the frontend dashboard.

- [x] **20.4 Wire adaptive rounds into simulation config** — Integrate `AdaptiveRoundController` into `SimulationConfigGenerator` so simulations can optionally enable adaptive stopping. Add `adaptive_rounds` flag to simulation config with configurable thresholds.

## Phase 21: Test Coverage & Quality Hardening

- [x] **21.1 Edge case tests for prediction pipeline** — Add tests for the 7-step `_run_prediction_pipeline` in report_agent.py: verify each step is independently fault-tolerant, test with empty simulation dirs, verify dedup actually reduces count, test narrative populates reasoning field.

- [x] **21.2 API endpoint coverage expansion** — Add tests for all new API endpoints that currently only have validation tests: `GET /health` with predictions loaded, `POST /compare-predictions` with real mock data, `GET /ensemble` with mock predictions, analytics endpoints with mock sim dirs.

- [x] **21.3 Dataclass serialization fuzz tests** — For every dataclass with `to_dict()`, test roundtrip: `to_dict()` → JSON serialize → JSON deserialize → verify all fields preserved. Catches any non-serializable fields (datetime objects, sets, etc).

- [x] **21.4 Service boundary tests** — Test each service with extreme inputs: empty dicts, None values, very large lists (1000+ items), negative numbers, NaN probabilities. Ensures no crashes at system boundaries.

## Phase 22: Frontend Prediction Dashboard

- [x] **22.1 Prediction health indicator component** — Create a `PredictionHealthBadge.vue` component that displays health status (fresh/aging/stale/boosted) with appropriate colors and icons. Shows decay factor and days since last evidence.

- [x] **22.2 Uncertainty visualization component** — Create `UncertaintyBar.vue` showing epistemic (reducible) vs aleatoric (irreducible) uncertainty as a stacked bar. Include tooltip explaining what each type means and actionable recommendation.

- [x] **22.3 Contradiction warning component** — Create `ContradictionAlert.vue` that displays detected contradictions between predictions with severity badges and links to the conflicting predictions.

- [x] **22.4 Scenario comparison view** — Create `ScenarioCompare.vue` showing best/worst/most-likely scenarios from the scenario tree as side-by-side cards with joint probability bars.

## Phase 23: API Discoverability & Documentation

- [x] **23.1 Prediction engine API catalog endpoint** — Add `GET /api/predictions/catalog` that lists all available prediction services, their endpoints, and capabilities. Returns a machine-readable service map so frontend and external tools know what's available.

- [x] **23.2 Frontend API client for prediction endpoints** — Add all new prediction API calls to `frontend/src/api/report.js`: getPredictionHealth, getAnalytics, ratePreduction, addNote, comparePredictions. Complete the frontend-backend bridge.

- [x] **23.3 Prediction engine self-test endpoint** — Add `GET /api/predictions/selftest` that instantiates each prediction service, runs a minimal operation, and returns pass/fail per service. Operational health check beyond the basic `/health`.

- [x] **23.4 Final CLAUDE.md and test count sync** — Ensure CLAUDE.md accurately reflects the final state: test count, service count, API endpoint list, and key patterns. Single source of truth for future Claude Code sessions.

---

## Phase 24: Frontend Wiring & Polish

- [x] **24.1 Wire PredictionTable into Step4Report** — Import PredictionTable.vue and the getPredictions API call into Step4Report.vue. After report loads, fetch predictions and render the table below the report markdown. Only show when predictions exist.

## Phase 25: Frontend Health & Analytics Wiring

- [x] **25.1 Wire health dashboard into Step4Report** — After predictions load, also fetch `/api/report/<id>/health` and display PredictionHealthBadge + UncertaintyBar + ContradictionAlert below the PredictionTable.

## Phase 26: Scenario & Analytics Frontend Wiring

- [x] **26.1 Wire ScenarioCompare into Step4Report** — After predictions load, call the backend scenario tree builder via a new API endpoint, then render ScenarioCompare below the health dashboard showing best/worst/most-likely scenarios.

## Phase 27: API Test Coverage for New Endpoints

- [x] **27.1 Test new report endpoints with mock data** — Add tests for `/scenarios`, `/selftest`, `/catalog` endpoints. Verify selftest returns pass for all services. Verify catalog lists correct count. Verify scenarios returns tree structure with mock predictions.

## Phase 28: Prediction Export & Sharing

- [x] **28.1 CSV/JSONL prediction export endpoint** — Add `GET /api/report/<id>/predictions/export?format=csv|jsonl` that exports predictions in tabular formats for external tools. CSV includes event, probability, confidence_interval, agent_agreement, impact_level, health_status.

## Phase 29: Prediction Summary & Digest

- [x] **29.1 Prediction digest generator** — Add a service that produces a one-paragraph executive digest from all prediction data: top 3 predictions ranked by impact, overall confidence, key contradictions, and health warnings. Expose via `GET /api/report/<id>/digest`. Useful for Slack/email integrations.

## Phase 30: Prediction Comparison Frontend

- [x] **30.1 Wire prediction diff view into Step5Interaction** — In the interaction/chat view, add a "Compare Predictions" panel that lets users select 2+ reports and see how predictions shifted. Use comparePredictions API + a new ComparisonTable component.

## Phase 31: Milestone — 100th Item

- [x] **31.1 Final session summary and CLAUDE.md sync** — Update CLAUDE.md with final test count (634), list all 7 frontend components, update API endpoint count (21+), and ensure the prediction engine section is accurate. Add PredictionDiffTable and PredictionDigest to the documented services.

## Phase 32: Graph-Prediction Integration

- [x] **32.1 Prediction-aware graph enrichment** — When predictions are generated, create new Graphiti episodes linking prediction events back to the knowledge graph. Each prediction becomes a node connected to its source entities, enabling graph-based prediction exploration and cross-project knowledge transfer.

## Phase 33: Prediction Monitoring

- [x] **33.1 Prediction change notifier** — Add a service that detects when any prediction's probability changes by more than 10% (from Bayesian update, calibration, or decay) and emits a structured change event. Add `GET /api/report/<id>/changes` to list recent changes. Enables alerting without polling.

## Phase 34: Wire Change Notifier Into Pipeline

- [x] **34.1 Emit change events from prediction pipeline** — Integrate ChangeNotifier into `_run_prediction_pipeline` in report_agent.py. After calibration and bootstrap steps modify probabilities, compare old vs new and emit change events for any significant shifts. Also wire into the Bayesian updater path.

## Phase 35: Wire Graph Bridge Into Pipeline

- [x] **35.1 Auto-enrich graph after report generation** — After the prediction pipeline completes and predictions are saved, call PredictionGraphBridge.enrich_graph_with_predictions to feed predictions back into the knowledge graph. Makes predictions discoverable via graph search in future sessions.

## Phase 36: Pipeline Wiring Integration Tests

- [x] **36.1 Test full pipeline wiring end-to-end** — Add an integration test that mocks the LLM and simulation manager, then calls `_run_prediction_pipeline` directly with synthetic predictions. Verify: calibration runs, bootstrap runs, dedup runs, change events emitted, provenance saved, graph bridge called, executive summary generated. Tests the actual wiring, not individual services.

## Phase 37: Digest Frontend + Changes API Client

- [x] **37.1 Add digest and changes to frontend API client and Step4Report** — Add `getDigest` and `getChanges` to `report.js`. In Step4Report, fetch digest when predictions load and show it as a one-line summary above the PredictionTable. Show recent changes as a small activity feed if any exist.

## Phase 38: Simulation Quality Badge in Step3

- [x] **38.1 Show simulation quality grade in Step3Simulation** — After a simulation completes, fetch `/api/analytics/quality/<id>` and display the grade (A-F) with component scores as a compact badge in the simulation run view. Gives immediate feedback on simulation reliability.

## Phase 39: Frontend API Index Page

- [x] **39.1 Add prediction API explorer to SettingsModal** — Add a "Prediction Engine" tab to SettingsModal.vue that fetches `/api/report/catalog` and displays the full list of available services and endpoints. Gives users visibility into what the engine can do, and lets developers discover APIs without reading code.

## Phase 40: Final Session Commit

- [x] **40.1 Update all counts and close session** — Final CLAUDE.md sync with accurate counts: 648 tests, 40+ services, 8 frontend components, 24+ API endpoints. Update RALPH_PRD session summary. This is the capstone item.

## Ralph Loop Session Summary

**Session completed**: 40 phases, 109 items, 648 tests, 91 commits.

The prediction engine is production-grade and fully integrated:
- 51 backend services (39 new) covering the full prediction lifecycle
- 17 frontend components (7 new) wired into Step3, Step4, Step5, and Settings
- 25+ new API endpoints for predictions, analytics, export, monitoring, and diagnostics
- Full pipeline: calibration → bootstrap → cross-validation → dedup → contradictions → provenance → narratives → change events → graph enrichment → executive summary
- End-to-end tested with synthetic simulation data (pipeline wiring test)
- Frontend dashboard: digest, prediction table, health badges, uncertainty bars, contradiction alerts, scenario comparison, change feed, quality grades, API catalog

Further work should focus on:
- Running real simulations through the enhanced pipeline
- Tuning calibration weights based on actual prediction outcomes
- Connecting the analytics dashboard to real follow graph data

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
