"""Settings modal tests: open/close, model selection, simulation params.

Tier 1 tests — UI-only, no LLM calls. The model list endpoint (/api/settings/models)
must be reachable, but it does not invoke any LLM.
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import TIMEOUT_SHORT
from helpers import take_step_screenshot


pytestmark = pytest.mark.tier1


def _open_settings(page):
    """Click the Settings button in the navbar and wait for the modal."""
    page.locator(".settings-btn").click()
    page.locator(".settings-modal").wait_for(state="visible", timeout=TIMEOUT_SHORT)


# ---------------------------------------------------------------------------
# Modal open / close
# ---------------------------------------------------------------------------

def test_settings_modal_opens(home_page):
    """Click settings gear -> modal visible with model and simulation sections."""
    page = home_page
    _open_settings(page)

    modal = page.locator(".settings-modal")
    assert modal.is_visible()

    # "Analysis Model" section label
    assert page.locator(".section-label", has_text="Analysis Model").is_visible()

    # "Simulation" section label
    assert page.locator(".section-label", has_text="Simulation").is_visible()


def test_settings_modal_closes(home_page):
    """Open modal -> close via overlay click -> modal disappears."""
    page = home_page
    _open_settings(page)

    # Click the overlay (outside the modal content)
    page.locator(".settings-overlay").click(position={"x": 10, "y": 10})
    page.locator(".settings-modal").wait_for(state="hidden", timeout=TIMEOUT_SHORT)

    # Home page should be interactive again
    assert page.locator(".home-container").is_visible()
    assert page.locator(".upload-zone").is_visible()


# ---------------------------------------------------------------------------
# Model list
# ---------------------------------------------------------------------------

def test_model_list_loads(home_page):
    """Open settings -> at least 1 model option with name, description, pricing."""
    page = home_page
    _open_settings(page)

    # Wait for model list to load (not the loading text)
    page.locator(".model-list").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    model_options = page.locator(".model-option")
    count = model_options.count()
    assert count >= 1, "Expected at least 1 model option"

    # Each model should show: name, description, input cost, output cost
    first = model_options.first
    assert first.locator(".model-name").is_visible()
    assert first.locator(".model-desc").is_visible()
    assert first.locator(".price-tag").first.is_visible()

    # Cost comparison bars should be visible
    assert page.locator(".cost-bar-container").is_visible()


# ---------------------------------------------------------------------------
# Model selection persistence
# ---------------------------------------------------------------------------

def test_model_selection_persists(home_page):
    """Select a non-default model -> close -> reopen -> still selected."""
    page = home_page
    _open_settings(page)
    page.locator(".model-list").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    model_options = page.locator(".model-option")
    count = model_options.count()
    if count < 2:
        pytest.skip("Need at least 2 models to test selection persistence")

    # Click the second model option (non-default)
    second_model = model_options.nth(1)
    second_model.click()
    model_name = second_model.locator(".model-name").text_content().strip()

    # Click Apply to save
    page.locator(".save-btn").click()
    page.locator(".settings-modal").wait_for(state="hidden", timeout=TIMEOUT_SHORT)

    # Reopen settings
    _open_settings(page)
    page.locator(".model-list").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # The second model should still be selected (has .selected class)
    selected = page.locator(".model-option.selected")
    assert selected.count() >= 1
    selected_name = selected.first.locator(".model-name").text_content().strip()
    assert selected_name == model_name

    # Verify localStorage was persisted
    ls_value = page.evaluate("() => localStorage.getItem('mirofish_settings')")
    assert ls_value is not None
    import json
    settings = json.loads(ls_value)
    assert "modelName" in settings


# ---------------------------------------------------------------------------
# Max agents input
# ---------------------------------------------------------------------------

def test_max_agents_input(home_page):
    """Set max agents to 50 -> close -> reopen -> value persisted."""
    page = home_page
    _open_settings(page)

    agents_input = page.locator("#max-agents")
    agents_input.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    agents_input.fill("")
    agents_input.fill("50")

    # Apply and close
    page.locator(".save-btn").click()
    page.locator(".settings-modal").wait_for(state="hidden", timeout=TIMEOUT_SHORT)

    # Reopen and verify
    _open_settings(page)
    agents_input = page.locator("#max-agents")
    agents_input.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    value = agents_input.input_value()
    assert value == "50"

    # Verify localStorage
    ls_value = page.evaluate("() => localStorage.getItem('mirofish_settings')")
    assert ls_value is not None
    import json
    settings = json.loads(ls_value)
    assert settings.get("maxAgents") == 50


# ---------------------------------------------------------------------------
# Max rounds input
# ---------------------------------------------------------------------------

def test_max_rounds_input(home_page):
    """Set max rounds to 5 -> close -> reopen -> value persisted."""
    page = home_page
    _open_settings(page)

    rounds_input = page.locator("#max-rounds")
    rounds_input.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    rounds_input.fill("")
    rounds_input.fill("5")

    # Apply and close
    page.locator(".save-btn").click()
    page.locator(".settings-modal").wait_for(state="hidden", timeout=TIMEOUT_SHORT)

    # Reopen and verify
    _open_settings(page)
    rounds_input = page.locator("#max-rounds")
    rounds_input.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    value = rounds_input.input_value()
    assert value == "5"
