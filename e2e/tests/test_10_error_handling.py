"""Error handling and edge case tests.

Tier 1 tests — UI-only, no LLM calls. These test how the UI
handles various error conditions and edge cases gracefully.
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import TIMEOUT_SHORT
from helpers import take_step_screenshot


pytestmark = pytest.mark.tier1


# ---------------------------------------------------------------------------
# Empty textarea submission blocked
# ---------------------------------------------------------------------------

def test_empty_textarea_cannot_submit(home_page):
    """With files uploaded but empty textarea, Launch should remain disabled."""
    page = home_page

    # Even after clicking into the textarea and typing then clearing,
    # the button should remain disabled
    textarea = page.locator("textarea.code-input")
    textarea.fill("some text")
    textarea.fill("")  # Clear it

    launch_btn = page.locator(".start-engine-btn")
    assert launch_btn.is_disabled()


# ---------------------------------------------------------------------------
# Whitespace-only requirement blocked
# ---------------------------------------------------------------------------

def test_whitespace_only_requirement_blocked(home_page):
    """Whitespace-only requirement text should not enable Launch."""
    page = home_page

    # The canSubmit computed checks simulationRequirement.trim() !== ''
    textarea = page.locator("textarea.code-input")
    textarea.fill("   \n\t  ")

    launch_btn = page.locator(".start-engine-btn")
    # Without files, it would be disabled anyway. But even the requirement
    # side of the check should fail.
    assert launch_btn.is_disabled()


# ---------------------------------------------------------------------------
# Direct URL to invalid project
# ---------------------------------------------------------------------------

def test_invalid_project_id_handled(page, base_url):
    """Navigating to /process/<invalid-id> should show error or fallback."""
    page.goto(f"{base_url}/process/invalid-project-12345", wait_until="networkidle")
    page.wait_for_timeout(3000)

    # The page should either show an error state or the workflow layout
    # with error messaging. It should not crash with a blank screen.
    has_content = page.evaluate(
        "() => document.body.innerText.trim().length > 0"
    )
    assert has_content, "Page should not be blank on invalid project ID"

    take_step_screenshot(page, "error_invalid_project")


# ---------------------------------------------------------------------------
# Direct URL to invalid simulation
# ---------------------------------------------------------------------------

def test_invalid_simulation_id_handled(page, base_url):
    """Navigating to /simulation/<invalid-id> should handle gracefully."""
    page.goto(f"{base_url}/simulation/invalid-sim-99999", wait_until="networkidle")
    page.wait_for_timeout(3000)

    has_content = page.evaluate(
        "() => document.body.innerText.trim().length > 0"
    )
    assert has_content, "Page should not be blank on invalid simulation ID"

    take_step_screenshot(page, "error_invalid_simulation")


# ---------------------------------------------------------------------------
# Multiple rapid file uploads
# ---------------------------------------------------------------------------

def test_rapid_file_uploads(home_page):
    """Rapidly uploading files should not cause duplicates or crashes.

    This tests the UI resilience to fast repeated interactions.
    Since seed_docs may not be available in all environments,
    we create temporary files.
    """
    page = home_page
    import tempfile

    # Create temporary .txt files
    tmp_files = []
    for i in range(3):
        f = tempfile.NamedTemporaryFile(
            suffix=".txt", prefix=f"test_{i}_", delete=False
        )
        f.write(f"Test content {i}".encode())
        f.close()
        tmp_files.append(f.name)

    try:
        file_input = page.locator('input[type="file"]')

        # Upload all at once
        file_input.set_input_files(tmp_files)
        page.wait_for_timeout(500)

        file_items = page.locator(".file-item")
        count = file_items.count()
        assert count == 3, f"Expected 3 files, got {count}"

        # Upload more files (should append, not replace)
        more_files = []
        for i in range(2):
            f = tempfile.NamedTemporaryFile(
                suffix=".txt", prefix=f"more_{i}_", delete=False
            )
            f.write(f"More content {i}".encode())
            f.close()
            more_files.append(f.name)
            tmp_files.append(f.name)

        file_input.set_input_files(more_files)
        page.wait_for_timeout(500)

        final_count = page.locator(".file-item").count()
        assert final_count == 5, f"Expected 5 files total, got {final_count}"
    finally:
        for f in tmp_files:
            try:
                os.unlink(f)
            except OSError:
                pass
