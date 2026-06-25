"""
scraper/playwright_runner.py — Playwright Browser Utilities
============================================================
Provides reusable async functions for scraping JavaScript‑rendered pages
using a shared Playwright browser instance.

This module handles the complexity of:
- Launching and tearing down Chromium browser contexts safely.
- Limiting concurrency with a semaphore to avoid overloading the system
  (running too many browser instances simultaneously can crash or hang).
- Offering different access patterns:
    * get_page_content          – simple page fetch, returns HTML string.
    * get_multiple_pages        – parallel fetch of multiple URLs.
    * interact_and_scrape       – page interaction (click, select, evaluate)
                                  before returning HTML.
    * run_with_playwright       – execute an arbitrary async function inside
                                  a Playwright context.
- All functions handle timeouts, HTTPS certificate errors (via
  ignore_https_errors), and browser launch arguments for headless
  environments.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Concurrency control – how many Playwright contexts can be active
# simultaneously. This prevents spawning too many Chromium instances
# which would exhaust system memory.
# ------------------------------------------------------------------
_browser_sem: Optional[asyncio.Semaphore] = None

def _get_semaphore() -> asyncio.Semaphore:
    """
    Return a module‑level semaphore (max 3 concurrent browser contexts).
    Created lazily on first access.
    """
    global _browser_sem
    if _browser_sem is None:
        _browser_sem = asyncio.Semaphore(3)
    return _browser_sem


@asynccontextmanager
async def _browser_context(ignore_https_errors: bool = False):
    """
    Async context manager that yields a Playwright browser context.

    Lifecycle:
    1. Launch a headless Chromium browser with flags that bypass
       certificate errors and sandbox restrictions (for Docker/CI).
    2. Create a new browser context with a realistic viewport and
       user‑agent string.
    3. Yield the context to the caller.
    4. After the block exits, close the context and the browser.
       A timeout of 10 seconds is enforced for browser.close() to
       prevent hanging.

    Args:
        ignore_https_errors: if True, HTTPS certificate errors are
                             ignored for all pages in this context.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[PLAYWRIGHT] playwright not installed")
        raise

    async with async_playwright() as pw:
        # Launch Chromium headless; ignore certificate errors at process level
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--ignore-certificate-errors",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        # Create a new context (isolated cookie jar, storage, etc.)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=ignore_https_errors,
        )
        try:
            yield ctx
        finally:
            await ctx.close()
            try:
                # Wait up to 10 seconds for the browser process to shut down
                await asyncio.wait_for(browser.close(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("[PLAYWRIGHT] Browser close timed out")


async def get_page_content(
    url: str,
    wait_for: str = "networkidle",
    timeout: int = 30000,
    js_eval: str = "",
    ignore_https_errors: bool = False,
) -> str:
    """
    Fetch the full HTML content of a single URL using Playwright.

    The page is loaded and the script waits until the network is idle
    (or the specified wait condition). Optionally, a JavaScript snippet
    can be executed before capturing the HTML.

    Args:
        url:                 target URL to load.
        wait_for:            Playwright wait condition (e.g., "networkidle",
                             "domcontentloaded", "load").
        timeout:             max time (ms) to wait for the page to load.
        js_eval:             optional JavaScript to evaluate on the page
                             before retrieving content.
        ignore_https_errors: passed to the browser context.

    Returns:
        The page's HTML as a string, or an empty string on failure.
    """
    # Limit concurrent Playwright contexts
    async with _get_semaphore():
        try:
            async with _browser_context(ignore_https_errors=ignore_https_errors) as ctx:
                page = await ctx.new_page()
                try:
                    await page.goto(url, wait_until=wait_for, timeout=timeout)
                    if js_eval:
                        await page.evaluate(js_eval)
                    return await page.content()
                finally:
                    # Always close the page, even if an error occurred
                    await page.close()
        except Exception as e:
            logger.error(f"[PLAYWRIGHT] get_page_content failed for {url}: {e}")
            return ""


async def get_multiple_pages(
    urls: List[str],
    wait_for: str = "networkidle",
    timeout: int = 30000,
    ignore_https_errors: bool = False,
) -> Dict[str, str]:
    """
    Fetch multiple URLs in parallel using separate pages.

    Each URL is fetched concurrently, but the total number of parallel
    contexts is limited by the semaphore. Failures on individual URLs
    are caught and logged; they do not stop the whole batch.

    Args:
        urls:                list of URLs to fetch.
        wait_for:            Playwright wait condition.
        timeout:             max wait per page (ms).
        ignore_https_errors: passed to browser context.

    Returns:
        A dictionary mapping each URL to its HTML content (empty string
        if the fetch failed).
    """
    async def _fetch_one(url: str) -> tuple[str, str]:
        """Fetch a single URL with its own browser context."""
        async with _get_semaphore():
            try:
                async with _browser_context(ignore_https_errors=ignore_https_errors) as ctx:
                    page = await ctx.new_page()
                    try:
                        await page.goto(url, wait_until=wait_for, timeout=timeout)
                        html = await page.content()
                        return url, html
                    finally:
                        await page.close()
            except Exception as e:
                logger.warning(f"[PLAYWRIGHT] Skipping {url}: {e}")
                return url, ""

    # Run all fetches concurrently and collect into a dict
    pairs = await asyncio.gather(*[_fetch_one(u) for u in urls])
    return dict(pairs)


async def interact_and_scrape(
    url: str,
    actions: List[Dict],
    timeout: int = 90000,
    ignore_https_errors: bool = False,
) -> str:
    """
    Perform a sequence of interactions on a page, then return the HTML.

    This is intended for sites that require clicking through a form,
    selecting dropdowns, or waiting for dynamically loaded content
    before the tender information is visible.

    Supported action types (each dict should have a "type" key):
      - "wait"     : pause for a given number of milliseconds ("ms").
      - "eval"     : execute arbitrary JavaScript ("js").
      - "select"   : choose an option from a <select> element
                     ("selector", "value").
      - "click"    : click an element ("selector").
      - "waitnet"  : wait for the page to reach "networkidle" state
                     (with a 15s timeout).

    If an action fails, it is logged and the script continues to the
    next action (best‑effort).

    Args:
        url:                 starting URL.
        actions:             list of action dicts (see above).
        timeout:             total page load timeout (ms).
        ignore_https_errors: passed to browser context.

    Returns:
        The page's HTML after all actions, or empty string on failure.
    """
    async with _get_semaphore():
        try:
            async with _browser_context(ignore_https_errors=ignore_https_errors) as ctx:
                page = await ctx.new_page()
                try:
                    # Navigate to the starting URL
                    await page.goto(url, wait_until="networkidle", timeout=timeout)

                    # Execute each action sequentially
                    for act in actions:
                        action_type = act.get("type")
                        try:
                            if action_type == "wait":
                                await page.wait_for_timeout(act.get("ms", 1000))
                            elif action_type == "eval":
                                await page.evaluate(act["js"])
                            elif action_type == "select":
                                await page.select_option(
                                    act["selector"], value=act["value"]
                                )
                            elif action_type == "click":
                                await page.click(act["selector"])
                            elif action_type == "waitnet":
                                await page.wait_for_load_state(
                                    "networkidle", timeout=15000
                                )
                        except Exception as action_err:
                            # Log and continue – don't fail the whole scrape
                            logger.debug(
                                f"[PLAYWRIGHT] Action {action_type!r} failed: {action_err}"
                            )

                    # Return the final HTML
                    return await page.content()
                finally:
                    await page.close()
        except Exception as e:
            logger.error(f"[PLAYWRIGHT] interact_and_scrape failed at {url}: {e}")
            return ""


async def run_with_playwright(fn: Callable) -> Any:
    """
    Execute an async function inside a fresh Playwright context.

    The function must accept a single argument: the Playwright instance
    (from `playwright.async_api.async_playwright()`). The caller is
    responsible for launching browsers and creating contexts.

    Example usage:
        async def my_scraper(pw):
            browser = await pw.chromium.launch(...)
            ...

    Args:
        fn: an async callable that takes a Playwright object.

    Returns:
        Whatever `fn` returns, or an empty list if `fn` is not async
        or if an error occurs.
    """
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            if asyncio.iscoroutinefunction(fn):
                return await fn(pw)
            logger.error("[PLAYWRIGHT] run_with_playwright requires an async function")
            return []
    except Exception as e:
        logger.error(f"[PLAYWRIGHT] run_with_playwright failed: {e}")
        return []


# Deprecated alias – kept for backward compatibility
async def run_sync(fn: Callable) -> Any:
    """
    Deprecated: use run_with_playwright() instead.
    """
    logger.warning("[PLAYWRIGHT] run_sync() is deprecated — use run_with_playwright()")
    return await run_with_playwright(fn)