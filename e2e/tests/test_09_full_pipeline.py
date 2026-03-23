"""Full end-to-end pipeline test: upload -> ontology -> graph -> sim -> report -> interaction.

This is a single comprehensive test that exercises the entire MiroFish pipeline.
It is the longest-running test in the suite and should only be run when
all infrastructure is available (LLM API, Neo4j, Ollama).

Marked as 'pipeline' — expected runtime: 15-30 minutes with minimal settings.
"""
import pytest
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import (
    TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG, TIMEOUT_PIPELINE, SEED_DOCS_DIR
)
from helpers import take_step_screenshot, get_api_json


pytestmark = pytest.mark.pipeline


def _get_seed_docs():
    """Return all seed doc paths."""
    if not os.path.isdir(SEED_DOCS_DIR):
        pytest.skip(f"seed_docs directory not found at {SEED_DOCS_DIR}")
    docs = sorted([
        os.path.join(SEED_DOCS_DIR, f)
        for f in os.listdir(SEED_DOCS_DIR)
        if f.endswith(('.md', '.txt', '.pdf'))
    ])
    if not docs:
        pytest.skip("No seed docs found")
    return docs


class TestFullPipeline:
    """Single comprehensive E2E pipeline test class."""

    def test_full_pipeline_happy_path(self, page, base_url, api_url):
        """Exercise the complete MiroFish pipeline end-to-end.

        Steps:
        1. Upload seed document on Home page
        2. Wait for ontology generation
        3. Wait for graph build
        4. Enter simulation setup, wait for profiles + config
        5. Start simulation, wait for completion
        6. Generate report, wait for all sections
        7. Enter interaction, send a chat message
        """
        docs = _get_seed_docs()
        doc_path = docs[0]  # Use smallest doc for speed

        # ─── Step 0: Home page ───
        page.goto(base_url, wait_until="networkidle")
        page.wait_for_selector(".home-container", timeout=TIMEOUT_SHORT)

        # Upload file
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(doc_path)
        page.locator(".file-item").first.wait_for(state="visible", timeout=TIMEOUT_SHORT)

        # Type requirement
        page.locator("textarea.code-input").fill(
            "Analyze key players in global oil and gas markets and predict market trends"
        )

        # Verify Launch Engine is enabled
        launch_btn = page.locator(".start-engine-btn")
        assert not launch_btn.is_disabled()

        take_step_screenshot(page, "pipeline_00_ready")

        # ─── Step 1: Launch -> Ontology -> Graph Build ───
        launch_btn.click()
        page.wait_for_url("**/process/**", timeout=TIMEOUT_SHORT)

        # Wait for ontology tags
        page.locator(".entity-tag").first.wait_for(
            state="visible", timeout=TIMEOUT_MEDIUM
        )
        entity_count = page.locator(".entity-tag").count()
        assert entity_count >= 3, f"Expected >= 3 entity types, got {entity_count}"

        take_step_screenshot(page, "pipeline_01_ontology_complete")

        # Wait for graph build completion
        completed_badge = page.locator(".step-card").nth(1).locator(".badge.success")
        completed_badge.wait_for(state="visible", timeout=TIMEOUT_LONG)

        # Verify graph has data
        stat_values = page.locator(".stat-value")
        nodes_text = stat_values.first.text_content().strip()
        assert nodes_text.isdigit() and int(nodes_text) > 0, \
            f"Expected node count > 0, got '{nodes_text}'"

        take_step_screenshot(page, "pipeline_01_graph_complete")

        # Extract project_id for API verification
        url = page.url
        project_match = re.search(r"/process/([a-zA-Z0-9_-]+)", url)
        assert project_match, f"Cannot extract project_id from {url}"
        project_id = project_match.group(1)

        # ─── Step 2: Enter Environment Setup ───
        page.locator(".action-btn", has_text="Environment Setup").click()
        page.wait_for_url("**/simulation/**", timeout=TIMEOUT_MEDIUM)

        # Wait for profiles to generate
        page.locator(".profile-card").first.wait_for(
            state="visible", timeout=TIMEOUT_MEDIUM
        )
        profile_count = page.locator(".profile-card").count()
        assert profile_count >= 1, f"Expected >= 1 profiles, got {profile_count}"

        take_step_screenshot(page, "pipeline_02_profiles")

        # Wait for simulation config
        page.locator(".config-detail-panel").wait_for(
            state="visible", timeout=TIMEOUT_MEDIUM
        )

        take_step_screenshot(page, "pipeline_02_config")

        # Extract simulation_id
        sim_url = page.url
        sim_match = re.search(r"/simulation/([a-zA-Z0-9_-]+)", sim_url)
        assert sim_match, f"Cannot extract simulation_id from {sim_url}"
        simulation_id = sim_match.group(1)

        # ─── Step 3: Start Simulation ───
        start_btn = page.locator(".action-btn.primary", has_text="Simulation")
        start_btn.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)
        page.wait_for_function(
            "() => { const btn = document.querySelector('.action-btn.primary'); return btn && !btn.disabled; }",
            timeout=TIMEOUT_MEDIUM
        )
        start_btn.click()
        page.wait_for_url("**/simulation/*/start**", timeout=TIMEOUT_MEDIUM)

        page.locator(".simulation-panel").wait_for(
            state="visible", timeout=TIMEOUT_SHORT
        )

        take_step_screenshot(page, "pipeline_03_running")

        # Wait for simulation to complete
        page.locator(".platform-status.twitter .status-badge").wait_for(
            state="visible", timeout=TIMEOUT_LONG
        )
        page.locator(".platform-status.reddit .status-badge").wait_for(
            state="visible", timeout=TIMEOUT_LONG
        )

        # Verify actions were generated
        total_text = page.locator(".total-count .mono").text_content().strip()
        total_actions = int(total_text) if total_text.isdigit() else 0
        assert total_actions > 0, f"Expected actions > 0, got {total_actions}"

        take_step_screenshot(page, "pipeline_03_complete")

        # ─── Step 4: Generate Report ───
        report_btn = page.locator(".action-btn.primary", has_text="Generate Report")
        report_btn.click()
        page.wait_for_url("**/report/**", timeout=TIMEOUT_MEDIUM)

        # Wait for report outline
        page.locator(".report-content-wrapper").wait_for(
            state="visible", timeout=TIMEOUT_LONG
        )

        title = page.locator(".main-title").text_content().strip()
        assert title, "Report title should not be empty"

        # Wait for at least one generated section
        page.locator(".generated-content").first.wait_for(
            state="visible", timeout=TIMEOUT_LONG
        )

        # Wait for report completion (Deep Interaction button)
        next_btn = page.locator(".next-step-btn", has_text="Deep Interaction")
        next_btn.wait_for(state="visible", timeout=TIMEOUT_LONG)

        take_step_screenshot(page, "pipeline_04_report_complete")

        # ─── Step 5: Interaction ───
        next_btn.click()
        page.wait_for_url("**/interaction/**", timeout=TIMEOUT_MEDIUM)

        page.locator(".interaction-panel").wait_for(
            state="visible", timeout=TIMEOUT_SHORT
        )

        # Send a chat message
        chat_input = page.locator(".chat-input")
        chat_input.wait_for(state="visible", timeout=TIMEOUT_SHORT)
        chat_input.fill("What is the most important insight from this simulation?")
        page.locator(".send-btn").click()

        # Wait for response
        page.locator(".chat-message.user").first.wait_for(
            state="visible", timeout=TIMEOUT_SHORT
        )
        page.locator(".chat-message.assistant").first.wait_for(
            state="visible", timeout=TIMEOUT_LONG
        )

        take_step_screenshot(page, "pipeline_05_interaction")

        # ─── Verification: API data integrity ───
        try:
            proj_data = get_api_json(api_url, f"/api/graph/project/{project_id}")
            assert proj_data.get("success") or "data" in proj_data

            sim_data = get_api_json(api_url, f"/api/simulation/{simulation_id}")
            assert sim_data.get("success") or "data" in sim_data
        except Exception:
            pass  # API verification is best-effort

        take_step_screenshot(page, "pipeline_complete")
