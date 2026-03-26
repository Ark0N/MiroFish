"""
Report API routes.
Provides simulation report generation, retrieval, and conversation endpoints.
"""

import os
import threading
from flask import request, jsonify, send_file

from . import report_bp
from .. import limiter
from ..config import Config
from ..services.report_agent import ReportAgent, ReportManager, ReportStatus
from ..services.simulation_manager import SimulationManager
from ..models.project import ProjectManager
from ..models.task import TaskManager, TaskStatus
from ..utils.logger import get_logger
from ..utils.cost_tracker import CostTracker, BudgetExceededError
from .helpers import validate_id_param

logger = get_logger('mirofish.api.report')


# ============== Report generation endpoints ==============

@report_bp.route('/generate', methods=['POST'])
@limiter.limit("10 per minute")
def generate_report():
    """
    Generate simulation analysis report (async task).

    This is a time-consuming operation. The endpoint returns task_id immediately.
    Use GET /api/report/generate/status to query progress.

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",    // required, simulation ID
            "force_regenerate": false        // optional, force regeneration
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "task_id": "task_xxxx",
                "status": "generating",
                "message": "Report generation task started"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        err = validate_id_param(simulation_id, "simulation_id")
        if err:
            return err

        force_regenerate = data.get('force_regenerate', False)

        # Get simulation info
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": f"Simulation does not exist: {simulation_id}"
            }), 404

        # Check if report already exists
        if not force_regenerate:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": existing_report.report_id,
                        "status": "completed",
                        "message": "Report already exists",
                        "already_generated": True
                    }
                })

        # Get project info
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"Project does not exist: {state.project_id}"
            }), 404

        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Missing graph ID. Please ensure the graph has been built."
            }), 400

        simulation_requirement = project.simulation_requirement
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": "Missing simulation requirement description"
            }), 400

        # Pre-generate report_id so it can be returned to the frontend immediately
        import uuid
        report_id = f"report_{uuid.uuid4().hex[:12]}"

        # Create async task
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="report_generate",
            metadata={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "report_id": report_id
            }
        )

        # Define background task
        def run_generate():
            try:
                # Reset cost tracker for report generation phase
                CostTracker.get_instance().reset(f"report_{report_id}")

                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message="Initializing Report Agent..."
                )

                # Create Report Agent
                llm_client = None
                if data.get('model_name'):
                    from ..utils.llm_client import LLMClient
                    llm_client = LLMClient(model=data['model_name'], cost_phase="report")
                agent = ReportAgent(
                    graph_id=graph_id,
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement,
                    llm_client=llm_client
                )

                # Progress callback
                def progress_callback(stage, progress, message):
                    task_manager.update_task(
                        task_id,
                        progress=progress,
                        message=f"[{stage}] {message}"
                    )

                # Generate report (pass pre-generated report_id)
                report = agent.generate_report(
                    progress_callback=progress_callback,
                    report_id=report_id
                )

                # Save report
                ReportManager.save_report(report)

                CostTracker.get_instance().log_summary()

                if report.status == ReportStatus.COMPLETED:
                    task_manager.complete_task(
                        task_id,
                        result={
                            "report_id": report.report_id,
                            "simulation_id": simulation_id,
                            "status": "completed",
                            "cost_summary": CostTracker.get_instance().get_summary()
                        }
                    )
                else:
                    task_manager.fail_task(task_id, report.error or "Report generation failed")

            except BudgetExceededError as e:
                logger.error(f"Report generation budget exceeded: {e}")
                CostTracker.get_instance().log_summary()
                task_manager.fail_task(
                    task_id,
                    f"Budget exceeded: {e}. Cost: {CostTracker.get_instance().get_summary()}"
                )

            except Exception as e:
                logger.error(f"Report generation failed: {str(e)}")
                CostTracker.get_instance().log_summary()
                task_manager.fail_task(task_id, str(e))

        # Start background thread
        thread = threading.Thread(target=run_generate, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "report_id": report_id,
                "task_id": task_id,
                "status": "generating",
                "message": "Report generation task started. Query progress via /api/report/generate/status",
                "already_generated": False
            }
        })

    except Exception as e:
        logger.error(f"Failed to start report generation task: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to start report generation task"
        }), 500


@report_bp.route('/generate/status', methods=['GET', 'POST'])
@limiter.limit("60 per minute")
def get_generate_status():
    """
    Query report generation task progress.

    Supports both GET and POST:

    GET /api/report/generate/status?task_id=task_xxxx&simulation_id=sim_xxxx

    POST (JSON):
        {
            "task_id": "task_xxxx",         // optional, task_id returned by generate
            "simulation_id": "sim_xxxx"     // optional, simulation ID
        }

    Returns:
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|failed",
                "progress": 45,
                "message": "..."
            }
        }
    """
    try:
        if request.method == 'GET':
            task_id = request.args.get('task_id')
            simulation_id = request.args.get('simulation_id')
        else:
            data = request.get_json() or {}
            task_id = data.get('task_id')
            simulation_id = data.get('simulation_id')

        if simulation_id:
            err = validate_id_param(simulation_id, "simulation_id")
            if err:
                return err

        # If simulation_id provided, first check if a completed report already exists
        if simulation_id:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": existing_report.report_id,
                        "status": "completed",
                        "progress": 100,
                        "message": "Report generated",
                        "already_completed": True
                    }
                })

        if not task_id:
            return jsonify({
                "success": False,
                "error": "Please provide task_id or simulation_id"
            }), 400

        task_manager = TaskManager()
        task = task_manager.get_task(task_id)

        if not task:
            return jsonify({
                "success": False,
                "error": f"Task does not exist: {task_id}"
            }), 404

        return jsonify({
            "success": True,
            "data": task.to_dict()
        })

    except Exception as e:
        logger.error(f"Failed to query task status: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to query task status"
        }), 500


# ============== Report retrieval endpoints ==============

@report_bp.route('/<report_id>', methods=['GET'])
def get_report(report_id: str):
    """
    Get report details.

    Returns:
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                "simulation_id": "sim_xxxx",
                "status": "completed",
                "outline": {...},
                "markdown_content": "...",
                "created_at": "...",
                "completed_at": "..."
            }
        }
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    try:
        report = ReportManager.get_report(report_id)

        if not report:
            return jsonify({
                "success": False,
                "error": f"Report does not exist: {report_id}"
            }), 404

        return jsonify({
            "success": True,
            "data": report.to_dict()
        })

    except Exception as e:
        logger.error(f"Failed to get report: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to get report"
        }), 500


@report_bp.route('/by-simulation/<simulation_id>', methods=['GET'])
def get_report_by_simulation(simulation_id: str):
    """
    Get report by simulation ID.

    Returns:
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                ...
            }
        }
    """
    err = validate_id_param(simulation_id, "simulation_id")
    if err:
        return err

    try:
        report = ReportManager.get_report_by_simulation(simulation_id)

        if not report:
            return jsonify({
                "success": False,
                "error": f"No report available for this simulation: {simulation_id}",
                "has_report": False
            }), 404

        return jsonify({
            "success": True,
            "data": report.to_dict(),
            "has_report": True
        })

    except Exception as e:
        logger.error(f"Failed to get report: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to get report"
        }), 500


@report_bp.route('/list', methods=['GET'])
def list_reports():
    """
    List all reports.

    Query parameters:
        simulation_id: Filter by simulation ID (optional)
        limit: Limit number of results (default 50)

    Returns:
        {
            "success": true,
            "data": [...],
            "count": 10
        }
    """
    try:
        simulation_id = request.args.get('simulation_id')
        limit = request.args.get('limit', 50, type=int)

        reports = ReportManager.list_reports(
            simulation_id=simulation_id,
            limit=limit
        )

        return jsonify({
            "success": True,
            "data": [r.to_dict() for r in reports],
            "count": len(reports)
        })

    except Exception as e:
        logger.error(f"Failed to list reports: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to list reports"
        }), 500


@report_bp.route('/<report_id>/download', methods=['GET'])
def download_report(report_id: str):
    """
    Download report (Markdown format).

    Returns Markdown file.
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    try:
        report = ReportManager.get_report(report_id)

        if not report:
            return jsonify({
                "success": False,
                "error": f"Report does not exist: {report_id}"
            }), 404

        md_path = ReportManager._get_report_markdown_path(report_id)

        if not os.path.exists(md_path):
            # Serve from memory if MD file doesn't exist on disk
            import io
            buf = io.BytesIO(report.markdown_content.encode('utf-8'))
            return send_file(
                buf,
                as_attachment=True,
                download_name=f"{report_id}.md",
                mimetype='text/markdown'
            )

        return send_file(
            md_path,
            as_attachment=True,
            download_name=f"{report_id}.md"
        )

    except Exception as e:
        logger.error(f"Failed to download report: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to download report"
        }), 500


@report_bp.route('/<report_id>/predictions', methods=['GET'])
def get_predictions(report_id: str):
    """
    Get structured predictions JSON for a report.

    Returns:
        {
            "success": true,
            "data": {
                "predictions": [...],
                "overall_confidence": "...",
                "generated_at": "..."
            }
        }
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    try:
        predictions = ReportManager.load_predictions(report_id)
        if not predictions:
            return jsonify({
                "success": False,
                "error": f"No predictions found for report: {report_id}"
            }), 404

        return jsonify({
            "success": True,
            "data": predictions.to_dict()
        })

    except Exception as e:
        logger.error(f"Failed to get predictions: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to get predictions"
        }), 500


@report_bp.route('/<report_id>/predictions/export', methods=['GET'])
def export_predictions(report_id: str):
    """Export predictions as CSV or JSONL.

    Query params:
        format: "csv" or "jsonl" (default "csv")
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    fmt = request.args.get("format", "csv").lower()
    if fmt not in ("csv", "jsonl"):
        return jsonify({"success": False, "error": "format must be csv or jsonl"}), 400

    try:
        predictions = ReportManager.load_predictions(report_id)
        if not predictions or not predictions.predictions:
            return jsonify({"success": False, "error": "No predictions found"}), 404

        import io
        pred_dicts = [p.to_dict() for p in predictions.predictions]

        if fmt == "jsonl":
            import json as _json
            lines = [_json.dumps(p, ensure_ascii=False) for p in pred_dicts]
            content = "\n".join(lines) + "\n"
            mimetype = "application/x-ndjson"
            filename = f"{report_id}_predictions.jsonl"
        else:
            import csv as _csv
            output = io.StringIO()
            fields = ["event", "probability", "confidence_interval", "timeframe",
                       "agent_agreement", "impact_level", "reasoning"]
            writer = _csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for p in pred_dicts:
                row = dict(p)
                row["confidence_interval"] = f"{p.get('confidence_interval', [0,1])[0]:.2f}-{p.get('confidence_interval', [0,1])[1]:.2f}"
                writer.writerow(row)
            content = output.getvalue()
            mimetype = "text/csv"
            filename = f"{report_id}_predictions.csv"

        from flask import Response
        return Response(
            content,
            mimetype=mimetype,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"Export failed: {e}")
        return jsonify({"success": False, "error": "Export failed"}), 500


@report_bp.route('/<report_id>/scenarios', methods=['GET'])
def get_scenarios(report_id: str):
    """Build scenario tree from a report's predictions."""
    err = validate_id_param(report_id, "report_id")
    if err:
        return err
    try:
        predictions = ReportManager.load_predictions(report_id)
        if not predictions or not predictions.predictions:
            return jsonify({"success": False, "error": "No predictions found"}), 404

        from ..services.scenario_tree import ScenarioTreeBuilder
        builder = ScenarioTreeBuilder()
        result = builder.build_tree(
            [p.to_dict() for p in predictions.predictions],
            max_predictions=6,
        )
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"Scenario tree failed: {e}")
        return jsonify({"success": False, "error": "Scenario generation failed"}), 500


@report_bp.route('/selftest', methods=['GET'])
def prediction_selftest():
    """Run minimal self-test on all prediction services."""
    results = {}

    tests = [
        ("PredictionCalibrator", lambda: __import__('app.services.prediction_calibrator', fromlist=['PredictionCalibrator']).PredictionCalibrator().calibrate([])),
        ("BayesianUpdater", lambda: __import__('app.services.bayesian_updater', fromlist=['BayesianUpdater']).BayesianUpdater().update_from_consensus(0.5, 0.5, {}, 0)),
        ("BootstrapConfidence", lambda: __import__('app.services.bootstrap_confidence', fromlist=['BootstrapConfidence']).BootstrapConfidence().compute_confidence_interval([])),
        ("CrossValidator", lambda: __import__('app.services.cross_validator', fromlist=['CrossValidator']).CrossValidator().validate({})),
        ("PredictionDeduplicator", lambda: __import__('app.services.prediction_dedup', fromlist=['PredictionDeduplicator']).PredictionDeduplicator().deduplicate([])),
        ("ContradictionDetector", lambda: __import__('app.services.contradiction_detector', fromlist=['ContradictionDetector']).ContradictionDetector().detect_contradictions([])),
        ("PredictionNarrativeGenerator", lambda: __import__('app.services.prediction_narrative', fromlist=['PredictionNarrativeGenerator']).PredictionNarrativeGenerator().generate_narrative({"event": "test", "probability": 0.5, "evidence": []})),
        ("UncertaintyDecomposer", lambda: __import__('app.services.uncertainty_decomposer', fromlist=['UncertaintyDecomposer']).UncertaintyDecomposer().decompose(0.5, [])),
        ("PredictionStressTester", lambda: __import__('app.services.stress_tester', fromlist=['PredictionStressTester']).PredictionStressTester().stress_test({}, 0.5)),
        ("ScenarioTreeBuilder", lambda: __import__('app.services.scenario_tree', fromlist=['ScenarioTreeBuilder']).ScenarioTreeBuilder().build_tree([])),
        ("PredictionMarket", lambda: __import__('app.services.prediction_market', fromlist=['PredictionMarket']).PredictionMarket().create_market("test", {})),
        ("TrendDetector", lambda: __import__('app.services.trend_detector', fromlist=['TrendDetector']).TrendDetector().detect_trends([])),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        try:
            test_fn()
            results[name] = "pass"
            passed += 1
        except Exception as e:
            results[name] = f"fail: {str(e)[:100]}"
            failed += 1

    return jsonify({
        "success": failed == 0,
        "data": {
            "results": results,
            "passed": passed,
            "failed": failed,
            "total": len(tests),
        }
    })


@report_bp.route('/catalog', methods=['GET'])
def prediction_catalog():
    """List all available prediction services and endpoints."""
    return jsonify({
        "success": True,
        "data": {
            "services": [
                {"name": "PredictionCalibrator", "description": "Consensus + contrarian confidence calibration"},
                {"name": "BayesianUpdater", "description": "Bayes' theorem probability updates"},
                {"name": "EnsemblePredictor", "description": "Multi-simulation weighted aggregation"},
                {"name": "PredictionBacktester", "description": "Calibration curves and Brier scores"},
                {"name": "BootstrapConfidence", "description": "Statistical confidence bands via resampling"},
                {"name": "CrossValidator", "description": "K-fold agent train/test validation"},
                {"name": "PredictionDecayTracker", "description": "Time-based freshness with evidence boost"},
                {"name": "PredictionVersionManager", "description": "Version history with regression detection"},
                {"name": "PredictionDeduplicator", "description": "Jaccard similarity deduplication"},
                {"name": "PredictionDependencyManager", "description": "Causal graph with probability propagation"},
                {"name": "PredictionChainingEngine", "description": "Joint probabilities (AND/OR/THEN)"},
                {"name": "ProvenanceTracker", "description": "Evidence chain DAG tracing"},
                {"name": "PredictionNarrativeGenerator", "description": "Plain English explanation generation"},
                {"name": "PredictionMarket", "description": "Virtual betting pool and crowd aggregation"},
                {"name": "PatternMatcher", "description": "Historical simulation fingerprint comparison"},
                {"name": "ScenarioTreeBuilder", "description": "Mutually exclusive future scenario generation"},
                {"name": "ContradictionDetector", "description": "Antonym-pair contradiction detection + impact"},
                {"name": "CounterfactualAnalyzer", "description": "What-if sensitivity analysis"},
                {"name": "DisagreementAnalyzer", "description": "Root cause disagreement classification"},
                {"name": "MinorityAmplifier", "description": "Shannon surprise for minority signals"},
                {"name": "UncertaintyDecomposer", "description": "Epistemic vs aleatoric decomposition"},
                {"name": "PredictionStressTester", "description": "Robustness scoring via extreme scenarios"},
                {"name": "OpinionDriftModel", "description": "Mathematical opinion evolution model"},
                {"name": "NetworkInfluenceScorer", "description": "PageRank-based agent influence"},
                {"name": "EchoChamberDetector", "description": "Network insularity detection"},
                {"name": "SimulationQualityScorer", "description": "Multi-dimensional quality grading (A-F)"},
                {"name": "CoalitionDetector", "description": "Spontaneous agent coalition detection"},
                {"name": "AdaptiveRoundController", "description": "Consensus-based early stopping"},
                {"name": "AnalyticsService", "description": "Comprehensive simulation dashboard data"},
                {"name": "SourceCredibilityTracker", "description": "Accuracy-based source reliability"},
                {"name": "TrendDetector", "description": "Emerging topic and sentiment shift detection"},
                {"name": "RSSMonitor", "description": "RSS feed subscription management"},
                {"name": "BatchIngester", "description": "Rate-limited batch URL processing"},
                {"name": "MultiWaveManager", "description": "Sequential simulation wave orchestration"},
                {"name": "ParameterLearner", "description": "Simulation parameter optimization"},
                {"name": "PredictionPipeline", "description": "Full pipeline orchestrator with resumption"},
            ],
            "endpoints": [
                {"method": "GET", "path": "/api/report/<id>/predictions", "description": "Structured predictions JSON"},
                {"method": "GET", "path": "/api/report/<id>/health", "description": "Prediction health dashboard"},
                {"method": "POST", "path": "/api/report/compare-predictions", "description": "Compare across reports"},
                {"method": "GET", "path": "/api/report/ensemble/<project_id>", "description": "Ensemble aggregation"},
                {"method": "POST", "path": "/api/report/<id>/predictions/<idx>/rate", "description": "Rate prediction"},
                {"method": "POST", "path": "/api/report/<id>/predictions/<idx>/note", "description": "Add analyst note"},
                {"method": "POST", "path": "/api/graph/ingest-url", "description": "URL text ingestion"},
                {"method": "POST", "path": "/api/graph/webhook/event", "description": "External event webhook"},
                {"method": "GET", "path": "/api/analytics/simulation/<id>", "description": "Simulation analytics"},
                {"method": "GET", "path": "/api/analytics/agents/<id>", "description": "Agent profiles"},
                {"method": "GET", "path": "/api/analytics/network/<id>", "description": "Network + echo chambers"},
                {"method": "GET", "path": "/api/analytics/quality/<id>", "description": "Quality score"},
                {"method": "GET", "path": "/api/report/catalog", "description": "This endpoint"},
            ],
            "total_services": 36,
            "total_endpoints": 13,
        }
    })


@report_bp.route('/<report_id>/health', methods=['GET'])
def get_prediction_health(report_id: str):
    """
    Get prediction health dashboard: decay, stability, contradictions,
    and uncertainty decomposition for all predictions in a report.
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    try:
        predictions = ReportManager.load_predictions(report_id)
        if not predictions:
            return jsonify({"success": False, "error": "No predictions found"}), 404

        report = ReportManager.get_report(report_id)
        pred_dicts = [p.to_dict() for p in predictions.predictions]

        # Decay health
        from ..services.prediction_decay import PredictionDecayTracker
        decay_tracker = PredictionDecayTracker()
        health = decay_tracker.compute_health(
            pred_dicts,
            predictions.generated_at or (report.created_at if report else ""),
        )

        # Contradictions
        from ..services.contradiction_detector import ContradictionDetector
        detector = ContradictionDetector()
        contradictions = detector.detect_contradictions(pred_dicts)

        # Uncertainty decomposition
        from ..services.uncertainty_decomposer import UncertaintyDecomposer
        decomposer = UncertaintyDecomposer()
        uncertainties = []
        for p in pred_dicts:
            u = decomposer.decompose(
                p.get("probability", 0.5),
                [],  # No agent sentiments available at API level
                n_agents=0,
            )
            uncertainties.append(u)

        # Stress test summary
        from ..services.stress_tester import PredictionStressTester
        tester = PredictionStressTester()
        version_probs = [p.get("probability", 0.5) for p in pred_dicts]
        stability = tester.compute_stability_index(version_probs) if len(version_probs) >= 2 else {"stability_index": "insufficient_data"}

        return jsonify({
            "success": True,
            "data": {
                "prediction_health": [h.to_dict() for h in health],
                "contradictions": contradictions,
                "uncertainties": uncertainties,
                "stability": stability,
                "num_predictions": len(pred_dicts),
            }
        })

    except Exception as e:
        logger.error(f"Failed to compute prediction health: {str(e)}")
        return jsonify({"success": False, "error": "Health check failed"}), 500


@report_bp.route('/<report_id>/predictions/<int:idx>/rate', methods=['POST'])
def rate_prediction(report_id: str, idx: int):
    """
    Rate a prediction's quality (1-5 stars) with optional feedback.

    Request JSON:
        { "rating": 4, "feedback": "Very accurate prediction" }
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "JSON body required"}), 400

    rating = data.get("rating")
    if not isinstance(rating, (int, float)) or rating < 1 or rating > 5:
        return jsonify({"success": False, "error": "rating must be 1-5"}), 400

    feedback = data.get("feedback", "")

    try:
        import json as _json
        from datetime import datetime
        ratings_path = ReportManager._get_report_folder(report_id)
        os.makedirs(ratings_path, exist_ok=True)
        ratings_file = os.path.join(ratings_path, "prediction_ratings.jsonl")

        entry = {
            "prediction_idx": idx,
            "rating": int(rating),
            "feedback": str(feedback)[:500],
            "rated_at": datetime.now().isoformat(),
        }

        with open(ratings_file, 'a', encoding='utf-8') as f:
            f.write(_json.dumps(entry, ensure_ascii=False) + '\n')

        return jsonify({"success": True, "data": entry})

    except Exception as e:
        logger.error(f"Failed to rate prediction: {str(e)}")
        return jsonify({"success": False, "error": "Rating failed"}), 500


@report_bp.route('/<report_id>/predictions/<int:idx>/note', methods=['POST'])
def add_prediction_note(report_id: str, idx: int):
    """
    Add analyst note to a prediction.

    Request JSON:
        { "note": "Analyst notes about this prediction" }
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    data = request.get_json(silent=True)
    if not data or not data.get("note"):
        return jsonify({"success": False, "error": "note field required"}), 400

    try:
        import json as _json
        from datetime import datetime
        notes_path = ReportManager._get_report_folder(report_id)
        os.makedirs(notes_path, exist_ok=True)
        notes_file = os.path.join(notes_path, "prediction_notes.jsonl")

        entry = {
            "prediction_idx": idx,
            "note": str(data["note"])[:2000],
            "added_at": datetime.now().isoformat(),
        }

        with open(notes_file, 'a', encoding='utf-8') as f:
            f.write(_json.dumps(entry, ensure_ascii=False) + '\n')

        return jsonify({"success": True, "data": entry})

    except Exception as e:
        logger.error(f"Failed to add prediction note: {str(e)}")
        return jsonify({"success": False, "error": "Note failed"}), 500


@report_bp.route('/ensemble/<project_id>', methods=['GET'])
def get_ensemble_predictions(project_id: str):
    """
    Get ensemble predictions aggregated across all reports for a project.
    """
    err = validate_id_param(project_id, "project_id")
    if err:
        return err

    try:
        from ..services.ensemble_predictor import EnsemblePredictor

        # Find all reports for this project's simulations
        all_reports = ReportManager.list_reports()
        project_reports = [r for r in all_reports if r.get("project_id") == project_id or True]

        # Load predictions from each report
        prediction_sets = []
        for report_data in all_reports:
            rid = report_data.get("report_id", "")
            preds = ReportManager.load_predictions(rid)
            if preds:
                prediction_sets.append(preds.to_dict())

        if len(prediction_sets) < 2:
            return jsonify({
                "success": False,
                "error": "Need predictions from at least 2 reports for ensemble"
            }), 404

        predictor = EnsemblePredictor()
        result = predictor.aggregate(project_id, prediction_sets)

        return jsonify({
            "success": True,
            "data": result.to_dict()
        })

    except Exception as e:
        logger.error(f"Failed to compute ensemble: {str(e)}")
        return jsonify({"success": False, "error": "Ensemble computation failed"}), 500


@report_bp.route('/compare-predictions', methods=['POST'])
def compare_predictions():
    """
    Compare predictions across multiple reports.

    Request JSON:
        { "report_ids": ["report_1", "report_2", ...] }

    Returns prediction diffs showing how predictions shifted between reports.
    """
    data = request.get_json(silent=True)
    if not data or not data.get("report_ids"):
        return jsonify({"success": False, "error": "report_ids array required"}), 400

    report_ids = data["report_ids"]
    if len(report_ids) < 2:
        return jsonify({"success": False, "error": "At least 2 report_ids required"}), 400
    if len(report_ids) > 10:
        return jsonify({"success": False, "error": "Maximum 10 report_ids"}), 400

    try:
        comparisons = []
        all_predictions = {}

        for rid in report_ids:
            preds = ReportManager.load_predictions(rid)
            if preds:
                all_predictions[rid] = preds.to_dict()

        if len(all_predictions) < 2:
            return jsonify({"success": False, "error": "Need predictions from at least 2 reports"}), 404

        # Build comparison: match predictions by event text similarity
        report_list = list(all_predictions.keys())
        base_id = report_list[0]
        base_preds = all_predictions[base_id]["predictions"]

        for compare_id in report_list[1:]:
            compare_preds = all_predictions[compare_id]["predictions"]
            diffs = []

            for bp in base_preds:
                # Find best matching prediction in comparison set
                best_match = None
                best_score = 0
                bp_words = set(bp["event"].lower().split())

                for cp in compare_preds:
                    cp_words = set(cp["event"].lower().split())
                    overlap = len(bp_words & cp_words)
                    total = len(bp_words | cp_words)
                    score = overlap / total if total > 0 else 0
                    if score > best_score and score > 0.3:
                        best_score = score
                        best_match = cp

                if best_match:
                    prob_delta = best_match["probability"] - bp["probability"]
                    agreement_delta = best_match["agent_agreement"] - bp["agent_agreement"]
                    diffs.append({
                        "event": bp["event"],
                        "base_probability": bp["probability"],
                        "compare_probability": best_match["probability"],
                        "probability_delta": round(prob_delta, 3),
                        "base_agreement": bp["agent_agreement"],
                        "compare_agreement": best_match["agent_agreement"],
                        "agreement_delta": round(agreement_delta, 3),
                        "match_score": round(best_score, 3),
                    })

            comparisons.append({
                "base_report": base_id,
                "compare_report": compare_id,
                "diffs": diffs,
                "new_in_compare": [
                    cp for cp in compare_preds
                    if not any(d["match_score"] > 0.3 for d in diffs
                               if set(d["event"].lower().split()) & set(cp["event"].lower().split()))
                ],
            })

        return jsonify({
            "success": True,
            "data": {
                "comparisons": comparisons,
                "report_ids": report_list,
            }
        })

    except Exception as e:
        logger.error(f"Failed to compare predictions: {str(e)}")
        return jsonify({"success": False, "error": "Comparison failed"}), 500


@report_bp.route('/<report_id>', methods=['DELETE'])
@limiter.limit("30 per minute")
def delete_report(report_id: str):
    """Delete report."""
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    try:
        success = ReportManager.delete_report(report_id)

        if not success:
            return jsonify({
                "success": False,
                "error": f"Report does not exist: {report_id}"
            }), 404

        return jsonify({
            "success": True,
            "message": f"Report deleted: {report_id}"
        })

    except Exception as e:
        logger.error(f"Failed to delete report: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to delete report"
        }), 500


# ============== Report Agent conversation endpoints ==============

@report_bp.route('/chat', methods=['POST'])
@limiter.limit("20 per minute")
def chat_with_report_agent():
    """
    Chat with Report Agent.

    Report Agent can autonomously call retrieval tools during conversation to answer questions.

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",        // required, simulation ID
            "message": "Explain the trend...",   // required, user message
            "chat_history": [                    // optional, conversation history
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }

    Returns:
        {
            "success": true,
            "data": {
                "response": "Agent response...",
                "tool_calls": [list of tools called],
                "sources": [information sources]
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        message = data.get('message')
        chat_history = data.get('chat_history', [])

        err = validate_id_param(simulation_id, "simulation_id")
        if err:
            return err

        if not message:
            return jsonify({
                "success": False,
                "error": "Please provide message"
            }), 400

        # Get simulation and project info
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": f"Simulation does not exist: {simulation_id}"
            }), 404

        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"Project does not exist: {state.project_id}"
            }), 404

        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Missing graph ID"
            }), 400

        simulation_requirement = project.simulation_requirement or ""

        # Create Agent and start conversation
        llm_client = None
        if data.get('model_name'):
            from ..utils.llm_client import LLMClient
            llm_client = LLMClient(model=data['model_name'], cost_phase="report")
        agent = ReportAgent(
            graph_id=graph_id,
            simulation_id=simulation_id,
            simulation_requirement=simulation_requirement,
            llm_client=llm_client
        )

        result = agent.chat(message=message, chat_history=chat_history)

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error(f"Chat failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Chat failed"
        }), 500


# ============== Report progress and section endpoints ==============

@report_bp.route('/<report_id>/progress', methods=['GET'])
def get_report_progress(report_id: str):
    """
    Get report generation progress (real-time).

    Returns:
        {
            "success": true,
            "data": {
                "status": "generating",
                "progress": 45,
                "message": "Generating section: Key Findings",
                "current_section": "Key Findings",
                "completed_sections": ["Executive Summary", "Simulation Background"],
                "updated_at": "2025-12-09T..."
            }
        }
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    try:
        progress = ReportManager.get_progress(report_id)

        if not progress:
            return jsonify({
                "success": False,
                "error": f"Report does not exist or progress info unavailable: {report_id}"
            }), 404

        return jsonify({
            "success": True,
            "data": progress
        })

    except Exception as e:
        logger.error(f"Failed to get report progress: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to get report progress"
        }), 500


@report_bp.route('/<report_id>/sections', methods=['GET'])
def get_report_sections(report_id: str):
    """
    Get list of generated sections (section-by-section output).

    Frontend can poll this endpoint to get generated section content without waiting for the full report.

    Returns:
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                "sections": [
                    {
                        "filename": "section_01.md",
                        "section_index": 1,
                        "content": "## Executive Summary\\n\\n..."
                    },
                    ...
                ],
                "total_sections": 3,
                "is_complete": false
            }
        }
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    try:
        sections = ReportManager.get_generated_sections(report_id)

        # Get report status
        report = ReportManager.get_report(report_id)
        is_complete = report is not None and report.status == ReportStatus.COMPLETED

        return jsonify({
            "success": True,
            "data": {
                "report_id": report_id,
                "sections": sections,
                "total_sections": len(sections),
                "is_complete": is_complete
            }
        })

    except Exception as e:
        logger.error(f"Failed to get section list: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to get section list"
        }), 500


@report_bp.route('/<report_id>/section/<int:section_index>', methods=['GET'])
def get_single_section(report_id: str, section_index: int):
    """
    Get single section content.

    Returns:
        {
            "success": true,
            "data": {
                "filename": "section_01.md",
                "content": "## Executive Summary\\n\\n..."
            }
        }
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    try:
        section_path = ReportManager._get_section_path(report_id, section_index)

        if not os.path.exists(section_path):
            return jsonify({
                "success": False,
                "error": f"Section does not exist: section_{section_index:02d}.md"
            }), 404

        with open(section_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return jsonify({
            "success": True,
            "data": {
                "filename": f"section_{section_index:02d}.md",
                "section_index": section_index,
                "content": content
            }
        })

    except Exception as e:
        logger.error(f"Failed to get section content: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to get section content"
        }), 500


# ============== Report status check endpoints ==============

@report_bp.route('/check/<simulation_id>', methods=['GET'])
def check_report_status(simulation_id: str):
    """
    Check whether a simulation has a report and the report status.

    Used by frontend to determine whether to unlock Interview functionality.

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "has_report": true,
                "report_status": "completed",
                "report_id": "report_xxxx",
                "interview_unlocked": true
            }
        }
    """
    err = validate_id_param(simulation_id, "simulation_id")
    if err:
        return err

    try:
        report = ReportManager.get_report_by_simulation(simulation_id)

        has_report = report is not None
        report_status = report.status.value if report else None
        report_id = report.report_id if report else None

        # Only unlock interview after report is completed
        interview_unlocked = has_report and report.status == ReportStatus.COMPLETED

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "has_report": has_report,
                "report_status": report_status,
                "report_id": report_id,
                "interview_unlocked": interview_unlocked
            }
        })

    except Exception as e:
        logger.error(f"Failed to check report status: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to check report status"
        }), 500


# ============== Agent log endpoints ==============

@report_bp.route('/<report_id>/agent-log', methods=['GET'])
def get_agent_log(report_id: str):
    """
    Get Report Agent's detailed execution log.

    Real-time retrieval of each action during report generation, including:
    - Report started, planning started/completed
    - Each section's start, tool calls, LLM responses, completion
    - Report completed or failed

    Query parameters:
        from_line: Start reading from this line (optional, default 0, for incremental retrieval)

    Returns:
        {
            "success": true,
            "data": {
                "logs": [
                    {
                        "timestamp": "2025-12-13T...",
                        "elapsed_seconds": 12.5,
                        "report_id": "report_xxxx",
                        "action": "tool_call",
                        "stage": "generating",
                        "section_title": "Executive Summary",
                        "section_index": 1,
                        "details": {
                            "tool_name": "insight_forge",
                            "parameters": {...},
                            ...
                        }
                    },
                    ...
                ],
                "total_lines": 25,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    try:
        from_line = request.args.get('from_line', 0, type=int)

        log_data = ReportManager.get_agent_log(report_id, from_line=from_line)

        return jsonify({
            "success": True,
            "data": log_data
        })

    except Exception as e:
        logger.error(f"Failed to get agent log: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to get agent log"
        }), 500


@report_bp.route('/<report_id>/agent-log/stream', methods=['GET'])
def stream_agent_log(report_id: str):
    """
    Get complete Agent log (all at once).

    Returns:
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 25
            }
        }
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    try:
        logs = ReportManager.get_agent_log_stream(report_id)

        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })

    except Exception as e:
        logger.error(f"Failed to get agent log: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to get agent log"
        }), 500


# ============== Console log endpoints ==============

@report_bp.route('/<report_id>/console-log', methods=['GET'])
def get_console_log(report_id: str):
    """
    Get Report Agent's console output log.

    Real-time retrieval of console output during report generation (INFO, WARNING, etc.).
    This differs from the agent-log endpoint which returns structured JSON logs;
    this is plain-text console-style logging.

    Query parameters:
        from_line: Start reading from this line (optional, default 0, for incremental retrieval)

    Returns:
        {
            "success": true,
            "data": {
                "logs": [
                    "[19:46:14] INFO: Search complete: found 15 related facts",
                    "[19:46:14] INFO: Graph search: graph_id=xxx, query=...",
                    ...
                ],
                "total_lines": 100,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    try:
        from_line = request.args.get('from_line', 0, type=int)

        log_data = ReportManager.get_console_log(report_id, from_line=from_line)

        return jsonify({
            "success": True,
            "data": log_data
        })

    except Exception as e:
        logger.error(f"Failed to get console log: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to get console log"
        }), 500


@report_bp.route('/<report_id>/console-log/stream', methods=['GET'])
def stream_console_log(report_id: str):
    """
    Get complete console log (all at once).

    Returns:
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 100
            }
        }
    """
    err = validate_id_param(report_id, "report_id")
    if err:
        return err

    try:
        logs = ReportManager.get_console_log_stream(report_id)

        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })

    except Exception as e:
        logger.error(f"Failed to get console log: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to get console log"
        }), 500


# ============== Tool call endpoints (for debugging) ==============

@report_bp.route('/tools/search', methods=['POST'])
@limiter.limit("30 per minute")
def search_graph_tool():
    """
    Graph search tool endpoint (for debugging).

    Request (JSON):
        {
            "graph_id": "mirofish_xxxx",
            "query": "search query",
            "limit": 10
        }
    """
    try:
        data = request.get_json() or {}

        graph_id = data.get('graph_id')
        query = data.get('query')
        limit = data.get('limit', 10)

        if not graph_id or not query:
            return jsonify({
                "success": False,
                "error": "Please provide graph_id and query"
            }), 400

        from ..services.graph_tools import GraphToolsService

        tools = GraphToolsService()
        result = tools.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit
        )

        return jsonify({
            "success": True,
            "data": result.to_dict()
        })

    except Exception as e:
        logger.error(f"Graph search failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Graph search failed"
        }), 500


@report_bp.route('/tools/statistics', methods=['POST'])
@limiter.limit("30 per minute")
def get_graph_statistics_tool():
    """
    Graph statistics tool endpoint (for debugging).

    Request (JSON):
        {
            "graph_id": "mirofish_xxxx"
        }
    """
    try:
        data = request.get_json() or {}

        graph_id = data.get('graph_id')

        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Please provide graph_id"
            }), 400

        from ..services.graph_tools import GraphToolsService

        tools = GraphToolsService()
        result = tools.get_graph_statistics(graph_id)

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        logger.error(f"Failed to get graph statistics: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Failed to get graph statistics"
        }), 500
