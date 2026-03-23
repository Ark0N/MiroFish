"""Step 2: Environment setup and profile generation tests.

Tier 2 tests — require running LLM API + Neo4j.
These tests verify that after graph building, the simulation environment
setup correctly generates agent profiles and simulation configuration.

NOTE: These tests assume a full pipeline execution. Each test re-runs
the full flow from home through graph build to Step 2. For faster testing,
consider using a session-scoped fixture that preserves a completed project.
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


def _navigate_to_step2(page, base_url):
    """Full pipeline: upload -> ontology -> graph build -> enter step 2."""
    doc_path = _get_smallest_seed_doc()

    # Start from home
    page.goto(base_url, wait_until="networkidle")
    page.wait_for_selector(".home-container", timeout=TIMEOUT_SHORT)

    # Upload and launch
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(doc_path)
    page.locator(".file-item").first.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    page.locator("textarea.code-input").fill("Analyze key players in global oil markets")
    page.locator(".start-engine-btn").click()

    page.wait_for_url("**/process/**", timeout=TIMEOUT_SHORT)

    # Wait for ontology + graph build to complete
    page.locator(".entity-tag").first.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    # Wait for graph build completion
    completed_badge = page.locator(".step-card").nth(1).locator(".badge.success")
    completed_badge.wait_for(state="visible", timeout=TIMEOUT_LONG)

    # Click "Enter Environment Setup" to go to Step 2
    action_btn = page.locator(".action-btn", has_text="Environment Setup")
    action_btn.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    action_btn.click()

    # Wait for navigation to simulation view
    page.wait_for_url("**/simulation/**", timeout=TIMEOUT_MEDIUM)


# ---------------------------------------------------------------------------
# Simulation instance created
# ---------------------------------------------------------------------------

def test_simulation_created(page, base_url):
    """After entering Step 2, a simulation instance should be created."""
    _navigate_to_step2(page, base_url)

    # The env-setup panel should be visible
    page.locator(".env-setup-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # The simulation ID should appear in the info card
    sim_id = page.locator(".info-value.mono")
    sim_id.first.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    # Verify the Simulation ID row exists
    sim_label = page.locator(".info-label", has_text="Simulation ID")
    assert sim_label.is_visible()


# ---------------------------------------------------------------------------
# Profile generation starts
# ---------------------------------------------------------------------------

def test_profile_generation_starts(page, base_url):
    """After simulation created, agent persona generation should begin."""
    _navigate_to_step2(page, base_url)

    # Wait for the "Generate Agent Personas" step card to become active
    persona_card = page.locator(".step-card").nth(1)
    persona_badge = persona_card.locator(".badge.processing")
    persona_badge.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    take_step_screenshot(page, "step2_profiles_generating")


# ---------------------------------------------------------------------------
# Profiles stream in realtime
# ---------------------------------------------------------------------------

def test_profiles_stream_in_realtime(page, base_url):
    """During generation, profile cards should appear incrementally."""
    _navigate_to_step2(page, base_url)

    # Wait for at least 3 profile cards to appear
    profile_cards = page.locator(".profile-card")
    profile_cards.nth(2).wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    # Each profile card should have username, profession, and bio
    first_card = profile_cards.first
    assert first_card.locator(".profile-realname").is_visible()
    assert first_card.locator(".profile-profession").is_visible()
    assert first_card.locator(".profile-bio").is_visible()


# ---------------------------------------------------------------------------
# Profile generation completes
# ---------------------------------------------------------------------------

def test_profile_generation_completes(page, base_url):
    """Wait for profile generation to complete — total profiles >= 5."""
    _navigate_to_step2(page, base_url)

    # Wait for the persona step to show "Completed"
    persona_card = page.locator(".step-card").nth(1)
    persona_completed = persona_card.locator(".badge.success")
    persona_completed.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    # Count profiles
    profile_cards = page.locator(".profile-card")
    count = profile_cards.count()
    assert count >= 5, f"Expected at least 5 profiles, got {count}"

    take_step_screenshot(page, "step2_profiles_complete")


# ---------------------------------------------------------------------------
# Simulation config displayed
# ---------------------------------------------------------------------------

def test_simulation_config_displayed(page, base_url):
    """After profiles, simulation config should be visible with time and platform settings."""
    _navigate_to_step2(page, base_url)

    # Wait for config detail panel to appear
    config_panel = page.locator(".config-detail-panel")
    config_panel.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    # Time config should show simulation duration
    assert page.locator(".config-item-label", has_text="Simulation Duration").is_visible()

    # Platform settings should show Twitter/Reddit configs
    platform_cards = page.locator(".platform-card")
    assert platform_cards.count() >= 1


# ---------------------------------------------------------------------------
# Profiles via API
# ---------------------------------------------------------------------------

def test_profiles_via_api(page, base_url, api_url):
    """Extract simulation_id from URL and verify profiles via API."""
    _navigate_to_step2(page, base_url)

    # Wait for profiles to be generated
    persona_card = page.locator(".step-card").nth(1)
    persona_completed = persona_card.locator(".badge.success")
    persona_completed.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    # Extract simulation_id from URL
    url = page.url
    match = re.search(r"/simulation/([a-zA-Z0-9_-]+)", url)
    assert match, f"Cannot extract simulation_id from URL: {url}"
    simulation_id = match.group(1)

    # GET simulation data via API
    sim_data = get_api_json(api_url, f"/api/simulation/{simulation_id}")
    assert sim_data.get("success") or "data" in sim_data


# ---------------------------------------------------------------------------
# Navigate to simulation run
# ---------------------------------------------------------------------------

def test_navigate_to_simulation_run(page, base_url):
    """Click 'Start Simulation' -> navigate to simulation run page."""
    _navigate_to_step2(page, base_url)

    # Wait for preparation to complete (phase 4 = ready)
    start_btn = page.locator(".action-btn.primary", has_text="Simulation")
    start_btn.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    # Wait for the button to be enabled (phase >= 4)
    page.wait_for_function(
        """() => {
            const btn = document.querySelector('.action-btn.primary');
            return btn && !btn.disabled;
        }""",
        timeout=TIMEOUT_MEDIUM
    )

    start_btn.click()

    # Should navigate to simulation run page
    page.wait_for_url("**/simulation/*/start**", timeout=TIMEOUT_MEDIUM)

    take_step_screenshot(page, "step3_entered")
