import pytest
from playwright.sync_api import Page
import os, time, json

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:3000")
API_URL = os.environ.get("E2E_API_URL", "http://localhost:5001")
SEED_DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "seed_docs")
# Timeouts tuned per operation type
TIMEOUT_SHORT = 10_000        # 10s — page loads, UI interactions
TIMEOUT_MEDIUM = 60_000       # 60s — ontology generation, profile gen
TIMEOUT_LONG = 300_000        # 5min — graph build, simulation, report gen
TIMEOUT_PIPELINE = 900_000    # 15min — full end-to-end pipeline
# Real-world reference: 1427-agent, 15-round pipeline took 4h10m total.
# With max_agents=10, max_rounds=3: expect ~15-20 min for full pipeline.


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def api_url():
    return API_URL


@pytest.fixture
def home_page(page: Page, base_url):
    """Navigate to home and wait for app mount."""
    page.goto(base_url, wait_until="networkidle")
    page.wait_for_selector(".home-container", timeout=TIMEOUT_SHORT)
    return page


@pytest.fixture
def seed_docs():
    """Return list of absolute paths to seed document files."""
    docs = sorted([
        os.path.join(SEED_DOCS_DIR, f)
        for f in os.listdir(SEED_DOCS_DIR)
        if f.endswith(('.md', '.txt', '.pdf'))
    ])
    assert len(docs) >= 1, f"No seed docs found in {SEED_DOCS_DIR}"
    return docs
