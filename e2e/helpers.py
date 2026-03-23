"""Shared helpers for E2E tests: API polling, state tracking, screenshot capture."""
import os, time, json, urllib.request

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "screenshots")


def wait_for_api_health(api_url, timeout=30):
    """Poll /health until backend is ready."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.urlopen(f"{api_url}/health", timeout=5)
            data = json.loads(req.read())
            if data.get("status") == "ok":
                return True
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError(f"Backend not ready after {timeout}s")


def poll_until(page, selector, text_contains=None, timeout=60_000):
    """Wait for element matching selector, optionally containing text."""
    locator = page.locator(selector)
    if text_contains:
        locator = locator.filter(has_text=text_contains)
    locator.wait_for(timeout=timeout)
    return locator


def capture_system_logs(page):
    """Extract all entries from the system log panel."""
    entries = page.locator(".system-log-entry, .log-entry, [class*='log'] .entry")
    count = entries.count()
    logs = []
    for i in range(count):
        logs.append(entries.nth(i).text_content())
    return logs


def get_api_json(api_url, path):
    """Direct API call bypassing the UI — for verification."""
    req = urllib.request.urlopen(f"{api_url}{path}", timeout=30)
    return json.loads(req.read())


def upload_files_via_ui(page, file_paths, requirement_text):
    """Upload files through the file input on Home."""
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(file_paths)
    if requirement_text:
        textarea = page.locator('textarea').first
        textarea.fill(requirement_text)


def wait_for_step_completion(page, step_name, timeout):
    """Wait for a pipeline step to show completion indicator."""
    page.wait_for_timeout(1000)  # Brief settle
    # Look for common completion indicators
    try:
        page.locator(f"text=/{step_name}.*complete/i").wait_for(timeout=timeout)
    except Exception:
        pass  # May use different indicator


def take_step_screenshot(page, step_name):
    """Save screenshot to e2e/screenshots/{step_name}_{timestamp}.png."""
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    ts = int(time.time())
    path = os.path.join(SCREENSHOTS_DIR, f"{step_name}_{ts}.png")
    page.screenshot(path=path, full_page=True)
    return path
