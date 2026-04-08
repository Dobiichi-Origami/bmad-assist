"""E2E test configuration - skip tests if Playwright not installed."""

import pytest


def _check_playwright():
    """Check if Playwright is installed and browsers are available."""
    try:
        from playwright.sync_api import sync_playwright

        # Try to actually start playwright to verify browsers are installed
        with sync_playwright() as p:
            # Check if chromium browser is installed
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


# Check once at import time
_PLAYWRIGHT_AVAILABLE = None


def pytest_configure(config):
    """Configure pytest - check playwright availability."""
    global _PLAYWRIGHT_AVAILABLE
    _PLAYWRIGHT_AVAILABLE = _check_playwright()


def pytest_collection_modifyitems(config, items):
    """Skip E2E tests if Playwright not available."""
    if not _PLAYWRIGHT_AVAILABLE:
        skip_playwright = pytest.mark.skip(
            reason="Playwright not installed or browsers not available. Run: playwright install"
        )
        for item in items:
            # Only skip Playwright-dependent tests (e2e/dashboard), not mock_loop tests
            fspath = str(item.fspath)
            if ("/e2e/" in fspath or "\\e2e\\" in fspath) and "/mock_loop/" not in fspath and "\\mock_loop\\" not in fspath:
                item.add_marker(skip_playwright)
