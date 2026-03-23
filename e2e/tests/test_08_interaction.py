"""Step 5: Deep Interaction / Chat tests.

Tier 2 tests — require a completed report with LLM API.
These tests verify chat with ReportAgent and interaction UI elements.

NOTE: These tests assume navigation to the interaction page with a valid reportId.
In the full pipeline, the report test would navigate here.
"""
import pytest
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG, SEED_DOCS_DIR
from helpers import take_step_screenshot


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


def _navigate_to_interaction(page, base_url):
    """Full pipeline: home -> ... -> report -> interaction."""
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

    # Ontology + graph build
    page.locator(".entity-tag").first.wait_for(state="visible", timeout=TIMEOUT_MEDIUM)
    page.locator(".step-card").nth(1).locator(".badge.success").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )

    # Enter Step 2
    page.locator(".action-btn", has_text="Environment Setup").click()
    page.wait_for_url("**/simulation/**", timeout=TIMEOUT_MEDIUM)

    # Start simulation
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

    # Generate report
    page.locator(".action-btn.primary", has_text="Generate Report").click()
    page.wait_for_url("**/report/**", timeout=TIMEOUT_MEDIUM)

    # Wait for report to complete
    page.locator(".report-content-wrapper").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )
    page.locator(".next-step-btn", has_text="Deep Interaction").wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )
    page.locator(".next-step-btn").click()

    page.wait_for_url("**/interaction/**", timeout=TIMEOUT_MEDIUM)


# ---------------------------------------------------------------------------
# Interaction page loads
# ---------------------------------------------------------------------------

def test_interaction_page_loads(page, base_url):
    """Interaction page loads with report content and chat interface."""
    _navigate_to_interaction(page, base_url)

    # Interaction panel should be visible
    page.locator(".interaction-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Report content should be on the left panel
    page.locator(".report-content-wrapper").wait_for(
        state="visible", timeout=TIMEOUT_SHORT
    )

    # Chat tab should be visible (default)
    page.locator(".tab-pill", has_text="Chat with Report Agent").wait_for(
        state="visible", timeout=TIMEOUT_SHORT
    )

    take_step_screenshot(page, "step5_interaction_loaded")


# ---------------------------------------------------------------------------
# Chat with ReportAgent — send message
# ---------------------------------------------------------------------------

def test_chat_send_message(page, base_url):
    """Send a message to ReportAgent and receive a response."""
    _navigate_to_interaction(page, base_url)

    page.locator(".interaction-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # The "Chat with Report Agent" tab should be active by default
    chat_input = page.locator(".chat-input")
    chat_input.wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Type a message
    chat_input.fill("What are the key findings from this report?")

    # Click send button
    send_btn = page.locator(".send-btn")
    assert not send_btn.is_disabled()
    send_btn.click()

    # User message should appear in chat history
    user_msg = page.locator(".chat-message.user")
    user_msg.first.wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Wait for assistant response
    assistant_msg = page.locator(".chat-message.assistant")
    assistant_msg.first.wait_for(state="visible", timeout=TIMEOUT_LONG)

    # Response should have content
    response_text = assistant_msg.first.locator(".message-content").text_content()
    assert len(response_text.strip()) > 5, "Assistant response should not be empty"

    take_step_screenshot(page, "step5_chat_response")


# ---------------------------------------------------------------------------
# Chat history maintained
# ---------------------------------------------------------------------------

def test_chat_history_maintained(page, base_url):
    """After sending a message, chat history shows both user and assistant messages."""
    _navigate_to_interaction(page, base_url)

    page.locator(".interaction-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    chat_input = page.locator(".chat-input")
    chat_input.wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Send first message
    chat_input.fill("Summarize the report in one sentence.")
    page.locator(".send-btn").click()

    # Wait for response
    page.locator(".chat-message.assistant").first.wait_for(
        state="visible", timeout=TIMEOUT_LONG
    )

    # Both user and assistant messages should be in history
    user_msgs = page.locator(".chat-message.user")
    assistant_msgs = page.locator(".chat-message.assistant")
    assert user_msgs.count() >= 1
    assert assistant_msgs.count() >= 1


# ---------------------------------------------------------------------------
# Report outline visible in interaction
# ---------------------------------------------------------------------------

def test_report_outline_in_interaction(page, base_url):
    """The left panel should display the full report outline with sections."""
    _navigate_to_interaction(page, base_url)

    page.locator(".interaction-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Report header should show title
    title = page.locator(".main-title")
    title.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    assert title.text_content().strip(), "Report title should be visible"

    # Sections should be listed
    sections = page.locator(".report-section-item")
    assert sections.count() >= 1, "Expected at least 1 section in report outline"


# ---------------------------------------------------------------------------
# Interactive tools card
# ---------------------------------------------------------------------------

def test_interactive_tools_card(page, base_url):
    """The Report Agent tools card should list the 4 specialized tools."""
    _navigate_to_interaction(page, base_url)

    page.locator(".interaction-panel").wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Tools card should be visible when chatting with report agent
    tools_card = page.locator(".report-agent-tools-card")
    tools_card.wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Click toggle to expand
    page.locator(".tools-card-toggle").click()
    page.wait_for_timeout(500)

    # Should show the 4 tools
    tool_items = page.locator(".tool-item")
    assert tool_items.count() == 4, f"Expected 4 tools, got {tool_items.count()}"

    # Verify tool names
    tool_names = []
    for i in range(tool_items.count()):
        name = tool_items.nth(i).locator(".tool-name").text_content()
        tool_names.append(name)

    assert any("InsightForge" in n for n in tool_names)
    assert any("PanoramaSearch" in n for n in tool_names)
    assert any("QuickSearch" in n for n in tool_names)
    assert any("Interview" in n for n in tool_names)
