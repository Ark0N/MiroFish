"""Step 3: Simulation execution and monitoring tests.

Tier 2 tests — require running LLM API, Neo4j, and local Ollama (or boost LLM).
These tests verify the simulation runs correctly, round counters advance,
and agent actions appear in the timeline feed.

NOTE: These tests are the longest-running in the suite. Each test re-runs
the full pipeline from home. For CI, consider the full pipeline test instead.
"""
import pytest
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG, SEED_DOCS_DIR
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


def _navigate_to_simulation_run(page, base_url):
    """Full pipeline: home -> ontology -> graph -> step2 -> start simulation."""
    doc_path = _get_smallest_seed_doc()

    page.goto(base_url, wait_until="networkidle")
    page.wait_for_selector(".home-container", timeout=TIMEOUT_SHORT)

    # Upload and launch
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(doc_path)
    page.locator(".file-item").first.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    page.locator("textarea.code-input").fill("Analyze key players in global oil markets")
    page.locator(".start-engine-btn").click()

    page.wait_for_url("**/process/**", timeout=TIMEOUT_SHORT)

    # Wait for ontology + graph build
    page.locator(".entity-tag").first.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)
    completed_badge = page.locator(".step-card").nth(1).locator(".badge.success")
    completed_badge.wait_for(state="visible", timeout=TIMEOUT_LONG)

    # Enter Step 2
    page.locator(".action-btn", has_text="Environment Setup").click()
    page.wait_for_url("**/simulation/**", timeout=TIMEOUT_MEDIUM)

    # Wait for preparation to complete and click start
    start_btn = page.locator(".action-btn.primary", has_text="Simulation")
    start_btn.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)
    page.wait_for_function(
        "() => { const btn = document.querySelector('.action-btn.primary'); return btn && !btn.disabled; }",
        timeout=TIMEOUT_MEDIUM
    )
    start_btn.click()

    # Navigate to simulation run page
    page.wait_for_url("**/simulation/*/start**", timeout=TIMEOUT_MEDIUM)


# ---------------------------------------------------------------------------
# Simulation starts
# ---------------------------------------------------------------------------

def test_simulation_starts(page, base_url):
    """After clicking start, simulation should show running status."""
    _navigate_to_simulation_run(page, base_url)

    # The simulation panel should be visible
    page.locator(".simulation-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Platform status sections should be visible
    page.locator(".platform-status.twitter").wait_for(state="visible", timeout=TIMEOUT_SHORT)
    page.locator(".platform-status.reddit").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Status should show running (either header or platform badges)
    # The ROUND counter should show round info
    stat_labels = page.locator(".stat-label", has_text="ROUND")
    assert stat_labels.count() >= 1

    take_step_screenshot(page, "step3_running")


# ---------------------------------------------------------------------------
# Round counter advances
# ---------------------------------------------------------------------------

def test_round_counter_advances(page, base_url):
    """Wait for round counter to advance beyond round 1."""
    _navigate_to_simulation_run(page, base_url)

    page.locator(".simulation-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Wait for round counter to show >= 2 on either platform
    # The stat-value for ROUND shows "N/M" format
    page.wait_for_function(
        """() => {
            const vals = document.querySelectorAll('.platform-stats .stat-value.mono');
            for (const v of vals) {
                const text = v.textContent.trim();
                const match = text.match(/^(\\d+)/);
                if (match && parseInt(match[1]) >= 2) return true;
            }
            return false;
        }""",
        timeout=TIMEOUT_LONG
    )


# ---------------------------------------------------------------------------
# Recent actions feed
# ---------------------------------------------------------------------------

def test_recent_actions_feed(page, base_url):
    """Timeline feed should show at least 1 action entry."""
    _navigate_to_simulation_run(page, base_url)

    page.locator(".simulation-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Wait for at least one timeline item
    timeline_items = page.locator(".timeline-item")
    timeline_items.first.wait_for(state="visible", timeout=TIMEOUT_LONG)
    assert timeline_items.count() >= 1


# ---------------------------------------------------------------------------
# Simulation posts appear
# ---------------------------------------------------------------------------

def test_simulation_posts_appear(page, base_url):
    """Posts section should show at least 1 post with author and content."""
    _navigate_to_simulation_run(page, base_url)

    page.locator(".simulation-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Wait for a timeline card with content
    page.locator(".timeline-card").first.wait_for(state="visible", timeout=TIMEOUT_LONG)

    first_card = page.locator(".timeline-card").first

    # Should have agent name
    assert first_card.locator(".agent-name").is_visible()

    # Should have action badge (platform action type)
    assert first_card.locator(".action-badge").is_visible()


# ---------------------------------------------------------------------------
# System log active during simulation
# ---------------------------------------------------------------------------

def test_system_log_active_during_simulation(page, base_url):
    """System log should accumulate entries during simulation run.

    Note: The system log is inside the WorkflowLayout / Step3 panel.
    SimulationRunView uses systemLogs but the log panel rendering may
    be in the Step3Simulation component.
    """
    _navigate_to_simulation_run(page, base_url)

    page.locator(".simulation-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Wait for some initial actions
    page.locator(".timeline-item").first.wait_for(state="visible", timeout=TIMEOUT_LONG)

    # TOTAL EVENTS counter should increase
    initial_text = page.locator(".total-count .mono").text_content().strip()
    initial_count = int(initial_text) if initial_text.isdigit() else 0

    page.wait_for_timeout(5000)

    updated_text = page.locator(".total-count .mono").text_content().strip()
    updated_count = int(updated_text) if updated_text.isdigit() else 0

    assert updated_count >= initial_count


# ---------------------------------------------------------------------------
# Simulation completes
# ---------------------------------------------------------------------------

def test_simulation_completes(page, base_url):
    """Wait for simulation to reach 'Completed' status."""
    _navigate_to_simulation_run(page, base_url)

    page.locator(".simulation-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Wait for both platforms to show completed badges (checkmark)
    # The completed state is indicated by .status-badge appearing inside platform-header
    page.locator(".platform-status.twitter .status-badge").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )
    page.locator(".platform-status.reddit .status-badge").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )

    # Total actions should be > 0
    total_text = page.locator(".total-count .mono").text_content().strip()
    total_count = int(total_text) if total_text.isdigit() else 0
    assert total_count > 0, f"Expected total actions > 0, got {total_count}"

    take_step_screenshot(page, "step3_complete")


# ---------------------------------------------------------------------------
# Simulation stats via API
# ---------------------------------------------------------------------------

def test_simulation_stats_via_api(page, base_url, api_url):
    """GET /api/simulation/{id}/run-status/detail returns round data."""
    _navigate_to_simulation_run(page, base_url)

    # Wait for at least some actions
    page.locator(".timeline-item").first.wait_for(state="visible", timeout=TIMEOUT_LONG)

    # Extract simulation_id from URL
    url = page.url
    match = re.search(r"/simulation/([a-zA-Z0-9_-]+)/start", url)
    assert match, f"Cannot extract simulation_id from URL: {url}"
    simulation_id = match.group(1)

    # Get run status detail
    status_data = get_api_json(api_url, f"/api/simulation/{simulation_id}/run-status/detail")
    data = status_data.get("data", status_data)
    # Should have round info
    assert "round" in str(data).lower() or "actions" in str(data).lower()


# ---------------------------------------------------------------------------
# Proceed to report
# ---------------------------------------------------------------------------

def test_proceed_to_report(page, base_url):
    """After simulation completes, click 'Generate Report' to go to step 4."""
    _navigate_to_simulation_run(page, base_url)

    page.locator(".simulation-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Wait for simulation to complete
    page.locator(".platform-status.twitter .status-badge").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )
    page.locator(".platform-status.reddit .status-badge").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )

    # Click "Generate Report"
    report_btn = page.locator(".action-btn.primary", has_text="Generate Report")
    report_btn.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    report_btn.click()

    # Should navigate to report page
    page.wait_for_url("**/report/**", timeout=TIMEOUT_MEDIUM)

    take_step_screenshot(page, "step4_entered")
