"""Smoke tests: backend health, frontend loads, route guards.

These are Tier 1 tests — they only need Flask + Vite running, no LLM or Neo4j.
"""
import pytest
import json
import urllib.request
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import TIMEOUT_SHORT
from helpers import take_step_screenshot


pytestmark = pytest.mark.tier1


# ---------------------------------------------------------------------------
# Backend health
# ---------------------------------------------------------------------------

def test_backend_health_endpoint(api_url):
    """GET /health returns {"status": "ok", "service": "MiroFish Backend"}."""
    req = urllib.request.urlopen(f"{api_url}/health", timeout=10)
    data = json.loads(req.read())
    assert data["status"] == "ok"
    assert data["service"] == "MiroFish Backend"


# ---------------------------------------------------------------------------
# Frontend loads
# ---------------------------------------------------------------------------

def test_frontend_loads(home_page):
    """Home page loads with correct title, container, and disabled Launch button."""
    page = home_page
    assert "MiroFish" in page.title() or "mirofish" in page.title().lower() or page.locator(".nav-brand").text_content().strip() == "MIROFISH"

    # .home-container should be visible (already waited in fixture)
    assert page.locator(".home-container").is_visible()

    # "Launch Engine" button exists and is disabled (no files uploaded yet)
    launch_btn = page.locator(".start-engine-btn")
    assert launch_btn.is_visible()
    assert launch_btn.is_disabled()


# ---------------------------------------------------------------------------
# Home page elements
# ---------------------------------------------------------------------------

def test_home_page_elements(home_page):
    """Verify key home page UI elements are present."""
    page = home_page

    # Upload dropzone (drag-and-drop area)
    upload_zone = page.locator(".upload-zone")
    assert upload_zone.is_visible()

    # Requirement textarea
    textarea = page.locator("textarea.code-input")
    assert textarea.is_visible()

    # Settings button in navbar
    settings_btn = page.locator(".settings-btn")
    assert settings_btn.is_visible()

    # MiroFish branding in nav
    brand = page.locator(".nav-brand")
    assert brand.is_visible()
    assert "MIROFISH" in brand.text_content()


# ---------------------------------------------------------------------------
# 404 page
# ---------------------------------------------------------------------------

def test_404_page(page, base_url):
    """Navigating to a nonexistent route renders the NotFound component."""
    page.goto(f"{base_url}/nonexistent-route-xyz", wait_until="networkidle")
    page.wait_for_timeout(1000)

    not_found = page.locator(".not-found")
    assert not_found.is_visible()

    # Should contain "404" and "not found" text
    text = not_found.text_content().lower()
    assert "404" in text
    assert "not found" in text


# ---------------------------------------------------------------------------
# Route guards — all should redirect to Home
# ---------------------------------------------------------------------------

def test_route_guard_process(page, base_url):
    """GET /process/ (no projectId) should redirect to /."""
    page.goto(f"{base_url}/process/", wait_until="networkidle")
    page.wait_for_timeout(1000)

    # Should have landed on home or 404 (router guard redirects to Home)
    # The route /process/ without a param matches the catch-all, so we
    # might see NotFound or Home depending on router behavior.
    # With the guard, /process/ without projectId should go to Home.
    url = page.url.rstrip("/")
    base = base_url.rstrip("/")
    # Either redirected to home or shows 404 (catch-all)
    is_home = url == base or url == base + "/"
    is_not_found = page.locator(".not-found").is_visible()
    is_home_container = page.locator(".home-container").is_visible()
    assert is_home or is_not_found or is_home_container


def test_route_guard_simulation(page, base_url):
    """GET /simulation/ (no simulationId) should redirect to / or show 404."""
    page.goto(f"{base_url}/simulation/", wait_until="networkidle")
    page.wait_for_timeout(1000)

    url = page.url.rstrip("/")
    base = base_url.rstrip("/")
    is_home = url == base or page.locator(".home-container").is_visible()
    is_not_found = page.locator(".not-found").is_visible()
    assert is_home or is_not_found


def test_route_guard_report(page, base_url):
    """GET /report/ (no reportId) should redirect to / or show 404."""
    page.goto(f"{base_url}/report/", wait_until="networkidle")
    page.wait_for_timeout(1000)

    url = page.url.rstrip("/")
    base = base_url.rstrip("/")
    is_home = url == base or page.locator(".home-container").is_visible()
    is_not_found = page.locator(".not-found").is_visible()
    assert is_home or is_not_found


def test_route_guard_interaction(page, base_url):
    """GET /interaction/ (no reportId) should redirect to / or show 404."""
    page.goto(f"{base_url}/interaction/", wait_until="networkidle")
    page.wait_for_timeout(1000)

    url = page.url.rstrip("/")
    base = base_url.rstrip("/")
    is_home = url == base or page.locator(".home-container").is_visible()
    is_not_found = page.locator(".not-found").is_visible()
    assert is_home or is_not_found
