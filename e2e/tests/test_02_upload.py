"""File upload and form validation tests.

Tier 1 tests — no backend processing needed. Tests the upload UI,
file listing, removal, and Launch Engine button enable/disable logic.
"""
import pytest
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import TIMEOUT_SHORT, SEED_DOCS_DIR
from helpers import take_step_screenshot


pytestmark = pytest.mark.tier1


def _get_seed_doc_paths():
    """Get seed doc paths, or skip if seed_docs dir is missing."""
    if not os.path.isdir(SEED_DOCS_DIR):
        pytest.skip(f"seed_docs directory not found at {SEED_DOCS_DIR}")
    docs = sorted([
        os.path.join(SEED_DOCS_DIR, f)
        for f in os.listdir(SEED_DOCS_DIR)
        if f.endswith(('.md', '.txt', '.pdf'))
    ])
    if len(docs) == 0:
        pytest.skip("No seed docs found")
    return docs


# ---------------------------------------------------------------------------
# Single file upload
# ---------------------------------------------------------------------------

def test_upload_single_file(home_page):
    """Upload a single file -> it appears in the file list."""
    page = home_page
    docs = _get_seed_doc_paths()

    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(docs[0])

    # File should appear in the file list
    file_items = page.locator(".file-item")
    file_items.first.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    assert file_items.count() == 1

    # File name should be visible
    file_name = os.path.basename(docs[0])
    assert page.locator(".file-name", has_text=file_name).is_visible()


# ---------------------------------------------------------------------------
# Multiple files upload
# ---------------------------------------------------------------------------

def test_upload_multiple_files(home_page):
    """Upload all seed docs -> all appear in the list."""
    page = home_page
    docs = _get_seed_doc_paths()

    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(docs)

    # Wait for file items to appear
    page.locator(".file-item").first.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    file_items = page.locator(".file-item")
    assert file_items.count() == len(docs)

    # Each file name should be visible
    for doc_path in docs:
        name = os.path.basename(doc_path)
        assert page.locator(".file-name", has_text=name).is_visible()


# ---------------------------------------------------------------------------
# Remove file from list
# ---------------------------------------------------------------------------

def test_remove_file_from_list(home_page):
    """Upload 3 files -> remove 2nd -> only 2 remain."""
    page = home_page
    docs = _get_seed_doc_paths()

    if len(docs) < 3:
        pytest.skip("Need at least 3 seed docs")

    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(docs[:3])

    page.locator(".file-item").first.wait_for(state="visible", timeout=TIMEOUT_SHORT)
    assert page.locator(".file-item").count() == 3

    # Get the name of the 2nd file before removing
    removed_name = os.path.basename(docs[1])

    # Click the remove button on the 2nd file item
    remove_buttons = page.locator(".file-item .remove-btn")
    remove_buttons.nth(1).click()

    # Should now have 2 files
    page.wait_for_timeout(500)
    assert page.locator(".file-item").count() == 2

    # The removed file should no longer appear
    remaining_names = []
    for i in range(page.locator(".file-name").count()):
        remaining_names.append(page.locator(".file-name").nth(i).text_content().strip())
    assert removed_name not in remaining_names


# ---------------------------------------------------------------------------
# Invalid file type rejected
# ---------------------------------------------------------------------------

def test_invalid_file_type_rejected(home_page):
    """Attempt to upload a .jpg file -> not added to the list."""
    page = home_page

    # Create a temporary .jpg file
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(b"\xff\xd8\xff\xe0")  # Minimal JPEG header
        tmp_path = f.name

    try:
        file_input = page.locator('input[type="file"]')
        # The file input has accept=".pdf,.md,.txt" which filters in the browser,
        # but set_input_files bypasses the native dialog. The addFiles() JS function
        # filters by extension, so .jpg should be rejected.
        file_input.set_input_files(tmp_path)

        page.wait_for_timeout(500)
        file_items = page.locator(".file-item")
        assert file_items.count() == 0
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Launch button disabled without requirement
# ---------------------------------------------------------------------------

def test_launch_disabled_without_requirement(home_page):
    """Upload files but no requirement text -> Launch Engine disabled."""
    page = home_page
    docs = _get_seed_doc_paths()

    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(docs[0])
    page.locator(".file-item").first.wait_for(state="visible", timeout=TIMEOUT_SHORT)

    # Leave textarea empty
    launch_btn = page.locator(".start-engine-btn")
    assert launch_btn.is_disabled()


# ---------------------------------------------------------------------------
# Launch button disabled without files
# ---------------------------------------------------------------------------

def test_launch_disabled_without_files(home_page):
    """Type requirement text but no files -> Launch Engine disabled."""
    page = home_page

    textarea = page.locator("textarea.code-input")
    textarea.fill("Predict energy market trends for Q2 2026")

    launch_btn = page.locator(".start-engine-btn")
    assert launch_btn.is_disabled()


# ---------------------------------------------------------------------------
# Launch enabled with both files and requirement
# ---------------------------------------------------------------------------

def test_launch_enabled_with_files_and_requirement(home_page):
    """Upload file + type requirement -> Launch Engine becomes enabled."""
    page = home_page
    docs = _get_seed_doc_paths()

    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(docs[0])
    page.locator(".file-item").first.wait_for(state="visible", timeout=TIMEOUT_SHORT)

    textarea = page.locator("textarea.code-input")
    textarea.fill("Predict energy market trends for Q2 2026")

    launch_btn = page.locator(".start-engine-btn")
    # Button should now be enabled (not disabled)
    assert not launch_btn.is_disabled()
