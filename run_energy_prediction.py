#!/usr/bin/env python3
"""
MiroFish Energy Crisis Prediction Pipeline
==========================================
Automates the full pipeline: upload seed docs → ontology → graph → simulation → report

Predicts:
- Energy market direction (oil, gas, electricity)
- War impact on global energy infrastructure
- Which US economic sector will collapse first

Usage:
    python run_energy_prediction.py [--base-url http://localhost:5001] [--max-rounds 15]
"""

import argparse
import glob
import os
import sys
import time

import requests

DEFAULT_BASE_URL = "http://localhost:5001"
SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_documents")

SIMULATION_REQUIREMENT = """
Analyze the current global energy crisis and predict market outcomes. Focus on:

1. **Energy Price Trajectories**: Where are oil, natural gas, and electricity prices headed
   in the next 3-12 months? Consider OPEC+ decisions, infrastructure damage from military
   conflicts, and seasonal demand patterns.

2. **War Impact on Energy Infrastructure**: Multiple oil fields and gas facilities have been
   attacked and destroyed in ongoing conflicts (Russia-Ukraine, Middle East). Quantify the
   supply disruption and predict which regions will face the worst shortages.

3. **US Economic Vulnerability**: Which sector of the US economy will collapse first under
   sustained energy price pressure? Analyze:
   - Agriculture (fertilizer costs, diesel for farming equipment)
   - Transportation & logistics (fuel costs, airline industry)
   - Manufacturing (energy-intensive industries like steel, chemicals, aluminum)
   - Housing & construction (heating costs, material prices)
   - Retail & consumer spending (inflation pass-through)
   - Technology (data center energy costs, semiconductor supply chain)

4. **Cascading Failures**: Model how an energy price shock propagates through the US economy.
   Which domino falls first? What are the second and third order effects?

5. **Market Predictions**: Provide specific price range forecasts for:
   - WTI crude oil (30/60/90 day outlook)
   - Henry Hub natural gas
   - US average gasoline price
   - Diesel fuel
   - Electricity (key ISOs: ERCOT, PJM, CAISO)

Agents should debate these scenarios on Twitter and Reddit, challenging each other's
assumptions. Include energy traders, geopolitical analysts, military intelligence analysts,
agricultural economists, transportation industry experts, and macroeconomic forecasters.
"""


def wait_for_server(base_url, timeout=30):
    """Wait for the Flask server to be available."""
    print(f"Waiting for MiroFish server at {base_url}...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/health", timeout=3)
            if r.status_code == 200:
                print("Server is up!")
                return True
        except requests.ConnectionError:
            pass
        time.sleep(1)
    print("ERROR: Server did not start in time")
    return False


def check_api_credits():
    """Pre-flight check that the LLM API key has available credits.

    Uses the backend venv (which has the correct anthropic SDK version) via subprocess.
    """
    import subprocess

    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(script_dir, "backend")

    check_script = """
import os, sys
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath('.')), '.env'))

api_key = os.environ.get('LLM_API_KEY', '')
if not api_key:
    print('NO_KEY')
    sys.exit(1)

model = os.environ.get('LLM_MODEL_NAME', 'claude-haiku-4-5-20251001')

if api_key.startswith('sk-ant-'):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    try:
        client.messages.create(model=model, max_tokens=5, messages=[{'role':'user','content':'hi'}])
        print('OK')
    except Exception as e:
        err = str(e).lower()
        if 'credit balance' in err:
            print('NO_CREDITS')
        elif 'authentication' in err:
            print('AUTH_FAIL')
        else:
            print(f'ERROR:{str(e)[:200]}')
        sys.exit(1)
else:
    from openai import OpenAI
    base_url = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        client.chat.completions.create(model=model, max_tokens=5, messages=[{'role':'user','content':'hi'}])
        print('OK')
    except Exception as e:
        print(f'ERROR:{str(e)[:200]}')
        sys.exit(1)
"""

    result = subprocess.run(
        ["uv", "run", "python", "-c", check_script],
        capture_output=True, text=True, cwd=backend_dir, timeout=30,
    )
    output = result.stdout.strip()

    if output == "OK":
        print("  LLM API: OK (credits available)")
        return True
    elif output == "NO_KEY":
        print("ERROR: LLM_API_KEY not set in .env")
    elif output == "NO_CREDITS":
        print("ERROR: Anthropic API key has no credits.")
        print("  -> Go to https://console.anthropic.com/settings/billing to add credits")
        print("  -> Or set LLM_API_KEY / LLM_BASE_URL to an OpenAI-compatible provider")
    elif output == "AUTH_FAIL":
        print("ERROR: Anthropic API key is invalid")
    elif output.startswith("ERROR:"):
        print(f"ERROR: LLM API check failed: {output[6:]}")
    else:
        stderr = result.stderr.strip()
        print(f"ERROR: LLM API check failed: {stderr[:300]}")
    return False


def poll_task(base_url, task_id, label="Task", timeout=600):
    """Poll a task until completion."""
    print(f"  Polling {label} (task_id={task_id})...")
    deadline = time.time() + timeout
    last_msg = ""
    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/api/graph/task/{task_id}", timeout=10)
            data = r.json()
            if data.get("success"):
                task = data["data"]
                status = task.get("status", "unknown")
                msg = task.get("message", "")
                if msg != last_msg:
                    print(f"    [{status}] {msg}")
                    last_msg = msg
                if status == "completed":
                    print(f"  {label} completed!")
                    return task
                elif status == "failed":
                    print(f"  {label} FAILED: {msg}")
                    return None
        except Exception as e:
            print(f"    Poll error: {e}")
        time.sleep(5)
    print(f"  {label} timed out after {timeout}s")
    return None


def poll_simulation(base_url, simulation_id, timeout=1800):
    """Poll simulation run status until completion."""
    print(f"  Polling simulation {simulation_id}...")
    deadline = time.time() + timeout
    last_round = -1
    while time.time() < deadline:
        try:
            r = requests.get(
                f"{base_url}/api/simulation/{simulation_id}/run-status",
                timeout=10
            )
            data = r.json()
            if data.get("success"):
                status = data["data"]
                runner = status.get("runner_status", "unknown")
                current = status.get("current_round", 0)
                total = status.get("total_rounds", "?")
                if current != last_round:
                    print(f"    [Round {current}/{total}] status={runner}")
                    last_round = current
                if runner == "completed":
                    print("  Simulation completed!")
                    return status
                elif runner in ("failed", "error", "stopped"):
                    print(f"  Simulation {runner}")
                    return status
        except Exception as e:
            print(f"    Poll error: {e}")
        time.sleep(10)
    print(f"  Simulation timed out after {timeout}s")
    return None


def poll_report(base_url, task_id, timeout=900):
    """Poll report generation status."""
    print(f"  Polling report generation (task_id={task_id})...")
    deadline = time.time() + timeout
    last_msg = ""
    while time.time() < deadline:
        try:
            r = requests.get(
                f"{base_url}/api/report/generate/status",
                params={"task_id": task_id},
                timeout=10
            )
            data = r.json()
            if data.get("success"):
                info = data["data"]
                status = info.get("status", "unknown")
                msg = info.get("message", "")
                if msg != last_msg:
                    print(f"    [{status}] {msg}")
                    last_msg = msg
                if status == "completed":
                    print("  Report generation completed!")
                    return info
                elif status == "failed":
                    print(f"  Report generation FAILED: {msg}")
                    return None
        except Exception as e:
            print(f"    Poll error: {e}")
        time.sleep(10)
    print(f"  Report generation timed out after {timeout}s")
    return None


def run_pipeline(base_url, max_rounds=15):
    """Execute the full MiroFish prediction pipeline."""
    api = base_url + "/api"

    # ── Step 1: Upload seed documents and generate ontology ──
    print("\n" + "=" * 60)
    print("STEP 1: Upload seed documents & generate ontology")
    print("=" * 60)

    seed_files = sorted(glob.glob(os.path.join(SEED_DIR, "*.md")))
    if not seed_files:
        print(f"ERROR: No seed documents found in {SEED_DIR}")
        return False

    print(f"  Found {len(seed_files)} seed documents:")
    for f in seed_files:
        size_kb = os.path.getsize(f) / 1024
        print(f"    - {os.path.basename(f)} ({size_kb:.0f} KB)")

    files = [("files", (os.path.basename(f), open(f, "rb"), "text/markdown")) for f in seed_files]
    form_data = {
        "simulation_requirement": SIMULATION_REQUIREMENT,
        "project_name": "Energy Crisis Prediction - War Impact & US Economy Collapse",
        "additional_context": (
            "Use real current data from EIA API, oil tanker tracking, and live market feeds. "
            "Focus on concrete price predictions and identify which US economic sector is most "
            "vulnerable to energy price shocks from ongoing military conflicts."
        ),
    }

    try:
        r = requests.post(f"{api}/graph/ontology/generate", files=files, data=form_data, timeout=120)
    finally:
        for _, (_, fh, _) in files:
            fh.close()

    if r.status_code != 200:
        print(f"  ERROR: Ontology generation failed (HTTP {r.status_code})")
        print(f"  Response: {r.text[:500]}")
        return False

    result = r.json()
    if not result.get("success"):
        print(f"  ERROR: {result.get('error', 'Unknown error')}")
        return False

    project_id = result["data"]["project_id"]
    ontology = result["data"].get("ontology", {})
    entity_types = ontology.get("entity_types", [])
    edge_types = ontology.get("edge_types", [])
    print(f"  Project created: {project_id}")
    print(f"  Entity types: {len(entity_types)} - {[e.get('name', e) if isinstance(e, dict) else e for e in entity_types[:5]]}...")
    print(f"  Edge types: {len(edge_types)}")

    # ── Step 2: Build knowledge graph ──
    print("\n" + "=" * 60)
    print("STEP 2: Build knowledge graph")
    print("=" * 60)

    r = requests.post(f"{api}/graph/build", json={
        "project_id": project_id,
        "graph_name": "Energy Crisis & US Economy Prediction Graph",
        "chunk_size": 800,
        "chunk_overlap": 100,
    }, timeout=30)

    if r.status_code != 200:
        print(f"  ERROR: Graph build failed (HTTP {r.status_code}): {r.text[:500]}")
        return False

    result = r.json()
    if not result.get("success"):
        print(f"  ERROR: {result.get('error')}")
        return False

    task_id = result["data"]["task_id"]
    print(f"  Graph build task started: {task_id}")

    task_result = poll_task(base_url, task_id, "Graph Build", timeout=1800)
    if not task_result:
        return False

    # Get project to find graph_id
    r = requests.get(f"{api}/graph/project/{project_id}", timeout=10)
    project_data = r.json()["data"]
    graph_id = project_data.get("graph_id")
    print(f"  Graph ID: {graph_id}")

    # ── Step 3: Create simulation ──
    print("\n" + "=" * 60)
    print("STEP 3: Create simulation")
    print("=" * 60)

    r = requests.post(f"{api}/simulation/create", json={
        "project_id": project_id,
        "graph_id": graph_id,
        "enable_twitter": True,
        "enable_reddit": True,
    }, timeout=30)

    if r.status_code != 200:
        print(f"  ERROR: Simulation create failed (HTTP {r.status_code}): {r.text[:500]}")
        return False

    result = r.json()
    if not result.get("success"):
        print(f"  ERROR: {result.get('error')}")
        return False

    simulation_id = result["data"]["simulation_id"]
    print(f"  Simulation created: {simulation_id}")

    # ── Step 4: Prepare simulation (generate profiles + config) ──
    print("\n" + "=" * 60)
    print("STEP 4: Prepare simulation environment")
    print("=" * 60)

    r = requests.post(f"{api}/simulation/prepare", json={
        "simulation_id": simulation_id,
        "use_llm_for_profiles": True,
        "parallel_profile_count": 3,
    }, timeout=30)

    if r.status_code != 200:
        print(f"  ERROR: Prepare failed (HTTP {r.status_code}): {r.text[:500]}")
        return False

    result = r.json()
    if not result.get("success"):
        print(f"  ERROR: {result.get('error')}")
        return False

    prep_data = result["data"]
    if prep_data.get("already_prepared"):
        print("  Already prepared, skipping...")
    else:
        prep_task_id = prep_data.get("task_id")
        if prep_task_id:
            print(f"  Preparation task started: {prep_task_id}")
            # Poll prepare status
            deadline = time.time() + 600
            while time.time() < deadline:
                try:
                    r = requests.post(
                        f"{api}/simulation/prepare/status",
                        json={"simulation_id": simulation_id},
                        timeout=10
                    )
                    data = r.json()
                    if data.get("success"):
                        info = data["data"]
                        status = info.get("status", "unknown")
                        progress = info.get("progress", "")
                        if progress:
                            print(f"    [{status}] {progress}")
                        if status in ("ready", "completed"):
                            print("  Preparation completed!")
                            break
                        elif status == "failed":
                            print(f"  Preparation FAILED: {info.get('error', 'unknown')}")
                            return False
                except Exception as e:
                    print(f"    Poll error: {e}")
                time.sleep(8)

    # ── Step 5: Run simulation ──
    print("\n" + "=" * 60)
    print(f"STEP 5: Run simulation ({max_rounds} rounds)")
    print("=" * 60)

    r = requests.post(f"{api}/simulation/start", json={
        "simulation_id": simulation_id,
        "platform": "parallel",
        "max_rounds": max_rounds,
        "enable_graph_memory_update": True,
        "force": False,
    }, timeout=30)

    if r.status_code != 200:
        print(f"  ERROR: Start failed (HTTP {r.status_code}): {r.text[:500]}")
        return False

    result = r.json()
    if not result.get("success"):
        print(f"  ERROR: {result.get('error')}")
        return False

    print(f"  Simulation running! PID: {result['data'].get('process_pid', '?')}")

    sim_result = poll_simulation(base_url, simulation_id, timeout=max_rounds * 120 + 300)
    if not sim_result:
        print("  WARNING: Simulation may have issues, attempting report anyway...")

    # ── Step 6: Generate report ──
    print("\n" + "=" * 60)
    print("STEP 6: Generate prediction report")
    print("=" * 60)

    r = requests.post(f"{api}/report/generate", json={
        "simulation_id": simulation_id,
        "force_regenerate": False,
    }, timeout=30)

    if r.status_code != 200:
        print(f"  ERROR: Report generation failed (HTTP {r.status_code}): {r.text[:500]}")
        return False

    result = r.json()
    if not result.get("success"):
        print(f"  ERROR: {result.get('error')}")
        return False

    report_data = result["data"]
    if report_data.get("already_generated"):
        report_id = report_data["report_id"]
        print(f"  Report already exists: {report_id}")
    else:
        report_task_id = report_data.get("task_id")
        if report_task_id:
            report_info = poll_report(base_url, report_task_id, timeout=900)
            if report_info:
                report_id = report_info.get("report_id")
            else:
                print("  Report generation may have failed")
                return False
        else:
            report_id = report_data.get("report_id")

    # ── Step 7: Fetch and display report ──
    print("\n" + "=" * 60)
    print("STEP 7: Fetch prediction report")
    print("=" * 60)

    if report_id:
        r = requests.get(f"{api}/report/{report_id}", timeout=30)
        if r.status_code == 200:
            report = r.json()
            if report.get("success"):
                content = report["data"].get("content", "")
                print(f"\n{'=' * 60}")
                print("ENERGY CRISIS PREDICTION REPORT")
                print(f"{'=' * 60}")
                print(content[:5000])
                if len(content) > 5000:
                    print(f"\n... [Report truncated, full length: {len(content)} chars]")
                    # Save full report
                    report_path = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        "energy_prediction_report.md"
                    )
                    with open(report_path, "w") as f:
                        f.write(content)
                    print(f"\nFull report saved to: {report_path}")

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Project ID:    {project_id}")
    print(f"  Simulation ID: {simulation_id}")
    print(f"  Report ID:     {report_id if 'report_id' in dir() else 'N/A'}")
    print(f"  Dashboard:     http://localhost:3000")
    print(f"\nTo chat with the report agent:")
    print(f'  curl -X POST {base_url}/api/report/chat -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"simulation_id": "{simulation_id}", "message": "Which US sector collapses first?"}}\'')
    return True


def main():
    parser = argparse.ArgumentParser(description="MiroFish Energy Crisis Prediction Pipeline")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="MiroFish API base URL")
    parser.add_argument("--max-rounds", type=int, default=15, help="Max simulation rounds (default: 15)")
    parser.add_argument("--skip-server-check", action="store_true", help="Skip server availability check")
    args = parser.parse_args()

    print("=" * 60)
    print("MiroFish Energy Crisis Prediction Pipeline")
    print("=" * 60)
    print(f"  Server:     {args.base_url}")
    print(f"  Max rounds: {args.max_rounds}")
    print(f"  Seed docs:  {SEED_DIR}")
    print()

    # Pre-flight: check API credits before starting
    print("Pre-flight: checking LLM API credits...")
    if not check_api_credits():
        print("\nPipeline cannot run without a working LLM API key.")
        print("Options:")
        print("  1. Add credits at https://console.anthropic.com/settings/billing")
        print("  2. Use an OpenAI-compatible provider: set LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME in .env")
        sys.exit(1)
    print()

    if not args.skip_server_check:
        if not wait_for_server(args.base_url):
            print("\nStart the server first: cd backend && uv run flask run --port 5001")
            sys.exit(1)

    success = run_pipeline(args.base_url, args.max_rounds)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
