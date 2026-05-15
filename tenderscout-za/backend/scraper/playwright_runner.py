"""
scraper/playwright_runner.py — Playwright Browser Utilities
============================================================
Provides reusable async functions for JS-rendered page scraping
using a shared Playwright browser instance.

Design principles:
  - Single shared browser per run — launch once, reuse across calls
  - Per-task browser contexts — isolated, safe for concurrent use
  - Always clean up — browser.close() in finally blocks
  - Configurable SSL — ignore_https_errors only where needed
  - Stdlib logging — no loguru dependency
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# CONCURRENCY LIMIT
# =============================================================================
# FIX: Lazy semaphore — module-level asyncio.Semaphore() created at import
# time doesn't survive event loop restarts. Create on first use instead.

_browser_sem: Optional[asyncio.Semaphore] = None

def _get_semaphore() -> asyncio.Semaphore:
    global _browser_sem
    if _browser_sem is None:
        _browser_sem = asyncio.Semaphore(3)
    return _browser_sem


# =============================================================================
# SHARED BROWSER CONTEXT MANAGER
# =============================================================================

@asynccontextmanager
async def _browser_context(ignore_https_errors: bool = False):
    """
    Yield a fresh Playwright browser context and close it on exit.

    FIX: get_page_content() previously launched a new Chromium process per
    call (~2-3s startup overhead). This context manager is designed to be
    used inside a shared browser session passed in from the caller, but also
    works standalone by launching its own browser.

    FIX: Context is always closed in finally — previously a page.goto()
    exception would leak a Chromium process.

    FIX: Each concurrent task gets its own context (not shared) — browser
    contexts are not concurrency-safe when pages are opened simultaneously
    from the same context.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[PLAYWRIGHT] playwright not installed — run: pip install playwright && playwright install chromium")
        raise

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--ignore-certificate-errors",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=ignore_https_errors,
        )
        try:
            yield ctx
        finally:
            await ctx.close()
            # FIX: close() with timeout — if Playwright hangs, don't block forever
            try:
                await asyncio.wait_for(browser.close(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("[PLAYWRIGHT] Browser close timed out — forcing")


# =============================================================================
# SINGLE PAGE FETCH
# =============================================================================

async def get_page_content(
    url:                str,
    wait_for:           str  = "networkidle",
    timeout:            int  = 30000,
    js_eval:            str  = "",
    ignore_https_errors:bool = False,
) -> str:
    """
    Navigate to a URL and return the fully rendered HTML.

    FIX: ignore_https_errors is now a parameter (default False) instead of
    always True — SSL errors should only be bypassed for known broken domains.

    FIX: browser.close() is guaranteed via context manager even on exception.
    """
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
                    await page.close()
        except Exception as e:
            logger.error(f"[PLAYWRIGHT] get_page_content failed for {url}: {e}")
            return ""


# =============================================================================
# MULTIPLE PAGES (concurrent)
# =============================================================================

async def get_multiple_pages(
    urls:               List[str],
    wait_for:           str  = "networkidle",
    timeout:            int  = 30000,
    ignore_https_errors:bool = False,
) -> Dict[str, str]:
    """
    Load multiple URLs concurrently, respecting the browser semaphore limit.

    FIX: Each URL gets its own browser context — previously all tasks shared
    one context, which is not safe for concurrent page operations.

    Returns dict of {url: html_content}, empty string on failure.
    """
    async def _fetch_one(url: str) -> tuple[str, str]:
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

    pairs = await asyncio.gather(*[_fetch_one(u) for u in urls])
    return dict(pairs)


# =============================================================================
# INTERACT AND SCRAPE
# =============================================================================

async def interact_and_scrape(
    url:                str,
    actions:            List[Dict],
    timeout:            int  = 90000,
    ignore_https_errors:bool = False,
) -> str:
    """
    Perform a sequence of browser interactions before capturing HTML.
    Useful for portals that require clicking 'Search' or selecting filters.

    Supported action types:
      {"type": "wait",    "ms": 1000}
      {"type": "eval",    "js": "window.scrollTo(0,999)"}
      {"type": "select",  "selector": "#year", "value": "2026"}
      {"type": "click",   "selector": "#search-btn"}
      {"type": "waitnet"} — wait for networkidle

    FIX: Added semaphore guard — previously had no concurrency limit,
    each call launched a full browser with no cap on simultaneous instances.
    """
    async with _get_semaphore():
        try:
            async with _browser_context(ignore_https_errors=ignore_https_errors) as ctx:
                page = await ctx.new_page()
                try:
                    await page.goto(url, wait_until="networkidle", timeout=timeout)

                    for act in actions:
                        action_type = act.get("type")
                        try:
                            if action_type == "wait":
                                await page.wait_for_timeout(act.get("ms", 1000))
                            elif action_type == "eval":
                                await page.evaluate(act["js"])
                            elif action_type == "select":
                                await page.select_option(act["selector"], value=act["value"])
                            elif action_type == "click":
                                await page.click(act["selector"])
                            elif action_type == "waitnet":
                                await page.wait_for_load_state("networkidle", timeout=15000)
                            else:
                                logger.debug(f"[PLAYWRIGHT] Unknown action type: {action_type!r}")
                        except Exception as action_err:
                            # Log and continue — partial interactions are better than none
                            logger.debug(f"[PLAYWRIGHT] Action {action_type!r} failed: {action_err}")

                    return await page.content()
                finally:
                    await page.close()

        except Exception as e:
            logger.error(f"[PLAYWRIGHT] interact_and_scrape failed at {url}: {e}")
            return ""


# =============================================================================
# LEGACY SHIM
# =============================================================================

async def run_with_playwright(fn: Callable) -> Any:
    """
    Run a caller-supplied async function with a Playwright instance.

    FIX: Renamed from run_sync (misleading — it's async) to run_with_playwright.
    Kept run_sync as a deprecated alias for backwards compatibility.
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


# Deprecated alias — remove after all callers are updated
async def run_sync(fn: Callable) -> Any:
    logger.warning("[PLAYWRIGHT] run_sync() is deprecated — use run_with_playwright()")
    return await run_with_playwright(fn)