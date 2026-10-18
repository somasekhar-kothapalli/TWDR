from contextlib import contextmanager
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

log = logging.getLogger("twdr.te_scraper")

RELOAD_RETRIES = 2


@contextmanager
def browser_session(channel=None, new_tab=False, timezone_id=None, headless=False):
    """Launch one browser window + page (visible unless `headless`), reusable across multiple .goto() calls.

    Use this instead of render_page/render_html when a scrape needs several page loads
    (e.g. paginated lists) — spinning up a fresh browser per page is wasteful.

    headless is the caller's choice (a scraper's `headless` attribute): visible by default, as investing.com and the
    other sites we scrape do not cope with a headless browser.
    channel="chrome" drives the installed Google Chrome instead of Playwright's bundled Chromium (falls back to the
    bundled one, with a warning, when Chrome is not installed). investing.com's CDN answers the bundled Chromium
    with 403 for its scripts and styles, so the page never hydrates (no "Show More"); real Chrome gets them.
    new_tab=True opens the window's first tab on about:blank and scrapes in a second, new tab.
    timezone_id (e.g. "UTC") fixes the zone the page's own scripts display times in.
    """
    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    with sync_playwright() as pw:
        launch = dict(headless=headless, slow_mo=150,
                      args=["--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"])
        try:
            browser = pw.chromium.launch(channel=channel, **launch) if channel else pw.chromium.launch(**launch)
        except Exception as exc:  # noqa: BLE001 - Chrome not installed: use the bundled browser
            log.warning("browser channel %s unavailable (%s): using the bundled Chromium", channel, str(exc).splitlines()[0])
            browser, channel = pw.chromium.launch(**launch), None
        context = dict(viewport={"width": 1366, "height": 768}, locale="en-US")
        if channel is None:
            context["user_agent"] = _UA  # real Chrome keeps its own user agent
        if timezone_id:
            context["timezone_id"] = timezone_id
        ctx = browser.new_context(**context)
        if new_tab:
            ctx.new_page().goto("about:blank")  # the window's first tab; the scrape gets a new one
        page = ctx.new_page()
        if new_tab:
            page.bring_to_front()
        log.debug("Browser opened")
        try:
            yield page
        finally:
            browser.close()


def goto(page, url: str, wait_selector: str | None = None, timeout_ms: int = 20000, required: bool = True) -> None:
    """Navigate an existing page to url and let JS run.

    Uses domcontentloaded rather than networkidle: sites with ads/analytics/trackers
    often never go fully network-idle, and wait_selector is the real readiness signal.
    If wait_selector is given and required=False, a missing selector (e.g. a paginated
    list page past the last real page) is tolerated instead of raising.
    """
    response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    # investing.com answers a fresh session with 403 and lets a reload through.
    for _ in range(RELOAD_RETRIES):
        if response is None or response.status < 400:
            break
        page.wait_for_timeout(5000)
        response = page.reload(wait_until="domcontentloaded", timeout=timeout_ms)
    if response is not None and response.status >= 400:
        raise RuntimeError(f"{url} returned HTTP {response.status} (blocked or rate-limited)")
    if wait_selector:
        try:
            page.wait_for_selector(wait_selector, timeout=timeout_ms)
        except PlaywrightTimeoutError:
            if required:
                raise


@contextmanager
def render_page(url: str, wait_selector: str | None = None, timeout_ms: int = 20000):
    """Load url in headless chromium, let JS run, yield the Playwright page."""
    with browser_session() as page:
        goto(page, url, wait_selector, timeout_ms)
        yield page


def render_html(url: str, wait_selector: str | None = None, timeout_ms: int = 20000) -> str:
    with render_page(url, wait_selector, timeout_ms) as page:
        return page.content()