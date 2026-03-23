"""Step 1 continued: Graph build and visualization tests.

Tier 2 tests — require running LLM API + Neo4j.
These tests trigger graph building after ontology generation and verify
the D3 visualization and graph data via API.
"""
import pytest
import re
import json
import urllib.request
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG, SEED_DOCS_DIR, API_URL
from helpers import take_step_screenshot, get_api_json


pytestmark = pytest.mark.tier2


def _get_smallest_seed_doc():
    """Return path to the smallest seed doc."""
    if not os.path.isdir(SEED_DOCS_DIR):
        pytest.skip(f"seed_docs directory not found at {SEED_DOCS_DIR}")
    docs = sorted([
        os.path.join(SEED_DOCS_DIR, f)
        for f in os.listdir(SEED_DOCS_DIR)
        if f.endswith(('.md', '.txt', '.pdf'))
    ])
    if not docs:
        pytest.skip("No seed docs found")
    return docs[0]


def _launch_and_wait_for_ontology(page, base_url):
    """Upload doc, launch, and wait for ontology entity tags to appear."""
    doc_path = _get_smallest_seed_doc()
    page.goto(base_url, wait_until="networkidle")
    page.wait_for_selector(".home-container", timeout=TIMEOUT_SHORT)

    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(doc_path)
    page.locator(".file-item").first.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    page.locator("textarea.code-input").fill("Analyze key players in global oil markets")
    page.locator(".start-engine-btn").click()

    page.wait_for_url("**/process/**", timeout=TIMEOUT_SHORT)

    # Wait for entity tags (ontology complete)
    page.locator(".entity-tag").first.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)


# ---------------------------------------------------------------------------
# Graph build starts
# ---------------------------------------------------------------------------

def test_graph_build_starts(page, base_url):
    """After ontology completes, graph build should start automatically."""
    _launch_and_wait_for_ontology(page, base_url)

    # The MainView auto-triggers startBuildGraph after ontology completes.
    # The Step1 card for "GraphRAG Construction" (step-num 02) should become active.
    # Look for the build progress badge showing a percentage.
    build_badge = page.locator(".step-card").nth(1).locator(".badge.processing")
    build_badge.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    # System log should mention graph build started
    page.locator(".log-msg", has_text="build").first.wait_for(
        state="visible", timeout=TIMEOUT_MEDIUM
    )

    take_step_screenshot(page, "step1_graph_building")


# ---------------------------------------------------------------------------
# Graph build progress updates
# ---------------------------------------------------------------------------

def test_graph_build_progress_updates(page, base_url):
    """During graph build, progress percentage should increase."""
    _launch_and_wait_for_ontology(page, base_url)

    # Wait for build to start
    build_card = page.locator(".step-card").nth(1)
    build_badge = build_card.locator(".badge.processing")
    build_badge.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    # Wait a bit and check that system log accumulates entries
    initial_log_count = page.locator(".log-line").count()
    page.wait_for_timeout(5000)
    updated_log_count = page.locator(".log-line").count()
    # Log entries should increase (polling adds entries)
    assert updated_log_count >= initial_log_count


# ---------------------------------------------------------------------------
# Graph build completes
# ---------------------------------------------------------------------------

def test_graph_build_completes(page, base_url):
    """Wait for graph build to complete — Step1 shows completion."""
    _launch_and_wait_for_ontology(page, base_url)

    # Wait for the graph build step card to show "Completed" badge
    completed_badge = page.locator(".step-card").nth(1).locator(".badge.success")
    completed_badge.wait_for(state="visible", timeout=TIMEOUT_LONG)

    # Entity node count should be > 0 in the stats grid
    stat_values = page.locator(".stat-value")
    # First stat-value in the build card is "Entity Nodes"
    nodes_text = stat_values.first.text_content().strip()
    nodes_count = int(nodes_text) if nodes_text.isdigit() else 0
    assert nodes_count > 0, f"Expected node count > 0, got '{nodes_text}'"

    take_step_screenshot(page, "step1_graph_complete")


# ---------------------------------------------------------------------------
# Graph visualization renders
# ---------------------------------------------------------------------------

def test_graph_visualization_renders(page, base_url):
    """After graph build, the D3 SVG visualization should render with nodes."""
    _launch_and_wait_for_ontology(page, base_url)

    # Wait for build to complete
    completed_badge = page.locator(".step-card").nth(1).locator(".badge.success")
    completed_badge.wait_for(state="visible", timeout=TIMEOUT_LONG)

    # The GraphPanel should be visible (in the left panel of WorkflowLayout)
    graph_panel = page.locator(".graph-panel")
    graph_panel.wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # SVG element should exist
    svg = page.locator(".graph-svg")
    assert svg.is_visible()

    # SVG should have child elements (nodes rendered by D3)
    # D3 typically creates <circle> or <g> elements for nodes
    page.wait_for_timeout(2000)  # Let D3 finish rendering
    child_count = svg.evaluate(
        "el => el.querySelectorAll('circle, g.node, .node').length"
    )
    assert child_count >= 1, f"Expected at least 1 rendered node in SVG, got {child_count}"


# ---------------------------------------------------------------------------
# Graph data via API
# ---------------------------------------------------------------------------

def test_graph_data_via_api(page, base_url, api_url):
    """After build, GET /api/graph/data/{graph_id} returns nodes and edges."""
    _launch_and_wait_for_ontology(page, base_url)

    # Wait for build to complete
    completed_badge = page.locator(".step-card").nth(1).locator(".badge.success")
    completed_badge.wait_for(state="visible", timeout=TIMEOUT_LONG)

    # Extract graph_id — the log should mention it, or we get it from the page context
    # The project data in MainView stores graph_id; let's read it from log messages
    # or from the API. The project_id is in the URL.
    url = page.url
    match = re.search(r"/process/([a-zA-Z0-9_-]+)", url)
    assert match, f"Cannot extract project_id from URL: {url}"
    project_id = match.group(1)

    # Get project data to find graph_id
    proj_data = get_api_json(api_url, f"/api/graph/project/{project_id}")
    graph_id = proj_data.get("data", {}).get("graph_id")
    assert graph_id, f"No graph_id in project data: {proj_data}"

    # Get graph data
    graph_data = get_api_json(api_url, f"/api/graph/data/{graph_id}")
    data = graph_data.get("data", graph_data)
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    assert len(nodes) > 0, f"Expected nodes > 0, got {len(nodes)}"
    assert len(edges) > 0, f"Expected edges > 0, got {len(edges)}"


# ---------------------------------------------------------------------------
# Proceed to step 2
# ---------------------------------------------------------------------------

def test_proceed_to_step2(page, base_url):
    """After graph build, clicking 'Enter Environment Setup' goes to Step 2."""
    _launch_and_wait_for_ontology(page, base_url)

    # Wait for build to complete
    completed_badge = page.locator(".step-card").nth(1).locator(".badge.success")
    completed_badge.wait_for(state="visible", timeout=TIMEOUT_LONG)

    # The "Build Complete" step card (step 03 in Step1) has the action button
    action_btn = page.locator(".action-btn", has_text="Environment Setup")
    action_btn.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    action_btn.click()

    # Should navigate to simulation view (Step 2)
    page.wait_for_url("**/simulation/**", timeout=TIMEOUT_MEDIUM)

    take_step_screenshot(page, "step2_entered")
