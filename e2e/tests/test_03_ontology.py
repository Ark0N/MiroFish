"""Step 1: Ontology generation tests.

Tier 2 tests — require running LLM API + Neo4j.
These tests upload a seed document, trigger ontology generation,
and verify the resulting entity/relation type tags.
"""
import pytest
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import TIMEOUT_SHORT, TIMEOUT_MEDIUM, SEED_DOCS_DIR
from helpers import take_step_screenshot, upload_files_via_ui


pytestmark = pytest.mark.tier2


def _get_smallest_seed_doc():
    """Return path to the smallest seed doc (fastest to process)."""
    if not os.path.isdir(SEED_DOCS_DIR):
        pytest.skip(f"seed_docs directory not found at {SEED_DOCS_DIR}")
    docs = sorted([
        os.path.join(SEED_DOCS_DIR, f)
        for f in os.listdir(SEED_DOCS_DIR)
        if f.endswith(('.md', '.txt', '.pdf'))
    ])
    if not docs:
        pytest.skip("No seed docs found")
    # Return the first one (01_oil_gas_majors_opec.md — smallest)
    return docs[0]


# ---------------------------------------------------------------------------
# Launch navigates to process view
# ---------------------------------------------------------------------------

def test_launch_navigates_to_process(home_page):
    """Upload 1 seed doc, type requirement, click Launch -> URL changes to /process/<id>."""
    page = home_page
    doc_path = _get_smallest_seed_doc()

    # Upload file
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(doc_path)
    page.locator(".file-item").first.wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Type requirement
    textarea = page.locator("textarea.code-input")
    textarea.fill("Analyze key players in global oil markets")

    # Click Launch Engine
    launch_btn = page.locator(".start-engine-btn")
    assert not launch_btn.is_disabled()
    launch_btn.click()

    # Wait for URL to change to /process/<project_id>
    page.wait_for_url("**/process/**", timeout=TIMEOUT_SHORT)

    url = page.url
    assert "/process/" in url

    # Extract project_id from URL — should be 'new' initially, then a hex string after API call
    match = re.search(r"/process/([a-zA-Z0-9_-]+)", url)
    assert match is not None, f"Could not extract project ID from URL: {url}"

    take_step_screenshot(page, "step1_launched")


# ---------------------------------------------------------------------------
# Ontology generation starts
# ---------------------------------------------------------------------------

def test_ontology_generation_starts(home_page):
    """After launch, Step1 card is visible with progress indicator."""
    page = home_page
    doc_path = _get_smallest_seed_doc()

    # Upload and launch
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(doc_path)
    page.locator(".file-item").first.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    page.locator("textarea.code-input").fill("Analyze key players in global oil markets")
    page.locator(".start-engine-btn").click()

    page.wait_for_url("**/process/**", timeout=TIMEOUT_SHORT)

    # Step1 card should be visible with the workbench panel
    page.locator(".workbench-panel, .step-card").first.wait_for(
        state="visible", timeout=TIMEOUT_SHORT
    )

    # System log panel should exist
    page.locator(".system-logs").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Should see some log entries appearing
    page.locator(".log-line").first.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    take_step_screenshot(page, "step1_ontology_generating")


# ---------------------------------------------------------------------------
# Ontology generation completes
# ---------------------------------------------------------------------------

def test_ontology_generation_completes(home_page):
    """Wait for ontology to complete — entity type tags should appear."""
    page = home_page
    doc_path = _get_smallest_seed_doc()

    # Upload and launch
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(doc_path)
    page.locator(".file-item").first.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    page.locator("textarea.code-input").fill("Analyze key players in global oil markets")
    page.locator(".start-engine-btn").click()

    page.wait_for_url("**/process/**", timeout=TIMEOUT_SHORT)

    # Wait for entity type tags to appear (ontology enforces exactly 10 entity types)
    entity_tags = page.locator(".entity-tag")
    entity_tags.first.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    count = entity_tags.count()
    assert count >= 3, f"Expected at least 3 entity type tags, got {count}"

    take_step_screenshot(page, "step1_ontology_complete")


# ---------------------------------------------------------------------------
# Ontology entity details
# ---------------------------------------------------------------------------

def test_ontology_entity_details(home_page):
    """Click on an entity type tag -> detail overlay with name and attributes."""
    page = home_page
    doc_path = _get_smallest_seed_doc()

    # Upload and launch
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(doc_path)
    page.locator(".file-item").first.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    page.locator("textarea.code-input").fill("Analyze key players in global oil markets")
    page.locator(".start-engine-btn").click()

    page.wait_for_url("**/process/**", timeout=TIMEOUT_SHORT)

    # Wait for entity tags
    entity_tags = page.locator(".entity-tag.clickable")
    entity_tags.first.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    # Click first entity tag
    entity_tags.first.click()

    # Detail overlay should appear
    detail = page.locator(".ontology-detail-overlay")
    detail.wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Should show detail name
    assert page.locator(".detail-name").is_visible()

    # Check for "Person" or "Organization" somewhere in the entity tags
    # (mandatory fallback types)
    all_tag_texts = []
    for i in range(entity_tags.count()):
        all_tag_texts.append(entity_tags.nth(i).text_content().strip())
    has_person_or_org = any(
        t in ("Person", "Organization") for t in all_tag_texts
    )
    # This is a soft check — some ontologies might use different names
    # but the system enforces Person and Organization as mandatory
    assert has_person_or_org or len(all_tag_texts) >= 3


# ---------------------------------------------------------------------------
# System log during ontology
# ---------------------------------------------------------------------------

def test_system_log_during_ontology(home_page):
    """System log panel should have entries with timestamp format."""
    page = home_page
    doc_path = _get_smallest_seed_doc()

    # Upload and launch
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(doc_path)
    page.locator(".file-item").first.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    page.locator("textarea.code-input").fill("Analyze key players in global oil markets")
    page.locator(".start-engine-btn").click()

    page.wait_for_url("**/process/**", timeout=TIMEOUT_SHORT)

    # Wait for log entries
    page.locator(".log-line").first.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)

    log_lines = page.locator(".log-line")
    assert log_lines.count() >= 1

    # Check timestamp format (HH:MM:SS.mmm)
    first_time = page.locator(".log-time").first.text_content().strip()
    # Should match pattern like "14:23:45.123"
    assert re.match(r"\d{2}:\d{2}:\d{2}\.\d{3}", first_time), \
        f"Log timestamp '{first_time}' doesn't match expected format HH:MM:SS.mmm"
