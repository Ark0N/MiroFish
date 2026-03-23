"""Step 4: Report generation and validation tests.

Tier 2 tests — require completed simulation with LLM API for report generation.
These tests verify the ReportAgent generates a structured report with outline,
sections, and workflow timeline.

NOTE: These tests assume navigation to the report page with a valid reportId.
In a full pipeline run, the simulation test would navigate here.
For standalone testing, a pre-created report ID can be used.
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


def _navigate_to_report(page, base_url):
    """Full pipeline: home -> ontology -> graph -> step2 -> simulation -> report."""
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

    # Wait for preparation and start simulation
    start_btn = page.locator(".action-btn.primary", has_text="Simulation")
    start_btn.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)
    page.wait_for_function(
        "() => { const btn = document.querySelector('.action-btn.primary'); return btn && !btn.disabled; }",
        timeout=TIMEOUT_MEDIUM
    )
    start_btn.click()
    page.wait_for_url("**/simulation/*/start**", timeout=TIMEOUT_MEDIUM)

    # Wait for simulation to complete
    page.locator(".simulation-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)
    page.locator(".platform-status.twitter .status-badge").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )
    page.locator(".platform-status.reddit .status-badge").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )

    # Click Generate Report
    report_btn = page.locator(".action-btn.primary", has_text="Generate Report")
    report_btn.click()
    page.wait_for_url("**/report/**", timeout=TIMEOUT_MEDIUM)


# ---------------------------------------------------------------------------
# Report generation starts
# ---------------------------------------------------------------------------

def test_report_generation_starts(page, base_url):
    """After navigating to report page, generation should begin."""
    _navigate_to_report(page, base_url)

    # Report panel should be visible
    page.locator(".report-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Should show waiting state or start generating
    # Either "Waiting for Report Agent..." text or report outline starts loading
    waiting = page.locator(".waiting-placeholder")
    outline = page.locator(".report-content-wrapper")

    # One of these should be visible within timeout
    page.wait_for_function(
        """() => {
            return document.querySelector('.waiting-placeholder')?.offsetHeight > 0 ||
                   document.querySelector('.report-content-wrapper')?.offsetHeight > 0;
        }""",
        timeout=TIMEOUT_SHORT
    )

    take_step_screenshot(page, "step4_report_generating")


# ---------------------------------------------------------------------------
# Report outline appears
# ---------------------------------------------------------------------------

def test_report_outline_appears(page, base_url):
    """Report outline (title, summary, sections) should appear."""
    _navigate_to_report(page, base_url)

    # Wait for the report content wrapper to appear (outline loaded)
    page.locator(".report-content-wrapper").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )

    # Report should have a title
    title = page.locator(".main-title")
    title.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    assert title.text_content().strip(), "Report title should not be empty"

    # Should have section items
    sections = page.locator(".report-section-item")
    assert sections.count() >= 1, "Expected at least 1 report section"

    take_step_screenshot(page, "step4_report_outline")


# ---------------------------------------------------------------------------
# Report sections generate
# ---------------------------------------------------------------------------

def test_report_sections_generate(page, base_url):
    """Wait for at least one section to complete generation."""
    _navigate_to_report(page, base_url)

    page.locator(".report-content-wrapper").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )

    # Wait for at least one section to show generated content
    page.locator(".generated-content").first.wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )

    # The content should not be empty
    content = page.locator(".generated-content").first.text_content()
    assert len(content.strip()) > 10, "Generated content should not be empty"


# ---------------------------------------------------------------------------
# Report workflow timeline
# ---------------------------------------------------------------------------

def test_report_workflow_timeline(page, base_url):
    """The right panel should show workflow steps and tool call logs."""
    _navigate_to_report(page, base_url)

    page.locator(".report-content-wrapper").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )

    # Workflow overview should be visible
    workflow = page.locator(".workflow-overview")
    workflow.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    # Should show metrics: sections count, elapsed time, tool calls
    assert page.locator(".metric-label", has_text="Sections").is_visible()
    assert page.locator(".metric-label", has_text="Elapsed").is_visible()


# ---------------------------------------------------------------------------
# Report completes
# ---------------------------------------------------------------------------

def test_report_completes(page, base_url):
    """Wait for all sections to be generated and report to complete."""
    _navigate_to_report(page, base_url)

    page.locator(".report-content-wrapper").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )

    # Wait for the "Enter Deep Interaction" button to appear (indicates completion)
    next_btn = page.locator(".next-step-btn", has_text="Deep Interaction")
    next_btn.wait_for(state="visible", timeout=TIMEOUT_LONG)

    take_step_screenshot(page, "step4_report_complete")


# ---------------------------------------------------------------------------
# Navigate to interaction
# ---------------------------------------------------------------------------

def test_navigate_to_interaction(page, base_url):
    """After report completes, click 'Enter Deep Interaction' to go to Step 5."""
    _navigate_to_report(page, base_url)

    page.locator(".report-content-wrapper").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )

    next_btn = page.locator(".next-step-btn", has_text="Deep Interaction")
    next_btn.wait_for(state="visible", timeout=TIMEOUT_LONG)
    next_btn.click()

    page.wait_for_url("**/interaction/**", timeout=TIMEOUT_MEDIUM)

    take_step_screenshot(page, "step5_entered")
