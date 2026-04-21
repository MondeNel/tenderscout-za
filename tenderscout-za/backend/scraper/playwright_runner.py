"""
scraper/playwright_runner.py
-----------------------------
Async-native Playwright helpers.

COMPATIBILITY: run_sync() is provided as an async shim so existing callers
(`await run_sync(fn)`) continue to import without error.

Root cause of the original Windows NotImplementedError:
  sync_playwright() inside ThreadPoolExecutor → ProactorEventLoop
  cannot spawn subprocesses from threads.
Fix: async_playwright() runs in the same event loop — no threads needed.
"""
import asyncio
import logging
import sys
from typing import Callable, Any

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    try:
        policy = asyncio.get_event_loop_policy()
        if not isinstance(policy, asyncio.WindowsSelectorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            logger.info("[PLAYWRIGHT_RUNNER] Set WindowsSelectorEventLoopPolicy")
    except AttributeError:
        pass


# ---------------------------------------------------------------------------
# Compatibility shim
# ---------------------------------------------------------------------------

async def run_sync(fn: Callable) -> Any:
    """
    Legacy shim. Old scrapers called: return await run_sync(_sync_fn)
    where _sync_fn took a sync playwright object.

    We now call fn as an async coroutine if possible. Scrapers that still
    use the sync playwright API inside _sync_fn must be rewritten — see
    etenders.py for the async rewrite pattern.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[PLAYWRIGHT] Not installed. Run: pip install playwright && playwright install chromium")
        return []

    try:
        async with async_playwright() as pw:
            if asyncio.iscoroutinefunction(fn):
                return await fn(pw)
            # Sync function: cannot safely run on Windows — log and return empty
            logger.error(
                "[PLAYWRIGHT] run_sync received a non-async function. "
                "Please rewrite it as 'async def _scrape(pw):' using async_playwright API."
            )
            return []
    except Exception as e:
        logger.error(f"[PLAYWRIGHT] run_sync failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Primary async API
# ---------------------------------------------------------------------------

async def get_page_content(
    url: str,
    wait_for: str = "networkidle",
    timeout: int = 30000,
    js_eval: str = "",
) -> str:
    """Navigate to url, return rendered HTML. Returns '' on failure."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[PLAYWRIGHT] Not installed")
        return ""
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--ignore-certificate-errors", "--no-sandbox", "--disable-dev-shm-usage"],
            )
            ctx = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,
            )
            page = await ctx.new_page()
            await page.goto(url, wait_until=wait_for, timeout=timeout)
            if js_eval:
                await page.evaluate(js_eval)
            content = await page.content()
            await browser.close()
            return content
    except Exception as e:
        logger.error(f"[PLAYWRIGHT] get_page_content failed [{url}]: {e}")
        return ""


async def get_multiple_pages(urls: list, wait_for: str = "networkidle", timeout: int = 30000) -> dict:
    """Load multiple URLs concurrently. Returns {url: html}."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {u: "" for u in urls}
    results = {}
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--ignore-certificate-errors", "--no-sandbox", "--disable-dev-shm-usage"],
            )
            ctx = await browser.new_context(ignore_https_errors=True)

            async def _load(url):
                try:
                    pg = await ctx.new_page()
                    await pg.goto(url, wait_until=wait_for, timeout=timeout)
                    html = await pg.content()
                    await pg.close()
                    return url, html
                except Exception as e:
                    logger.warning(f"[PLAYWRIGHT] {url}: {e}")
                    return url, ""

            pairs = await asyncio.gather(*[_load(u) for u in urls])
            await browser.close()
            results = dict(pairs)
    except Exception as e:
        logger.error(f"[PLAYWRIGHT] get_multiple_pages failed: {e}")
        results = {u: "" for u in urls}
    return results


async def interact_and_scrape(url: str, actions: list, timeout: int = 90000) -> str:
    """
    Load a page, run interaction steps, return final HTML.
    actions: list of dicts with keys: type, ms, js, selector, value
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return ""
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--ignore-certificate-errors", "--no-sandbox", "--disable-dev-shm-usage"],
            )
            ctx = await browser.new_context(ignore_https_errors=True,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ))
            page = await ctx.new_page()
            await page.goto(url, wait_until="networkidle", timeout=timeout)
            for act in actions:
                try:
                    t = act.get("type")
                    if t == "wait":       await page.wait_for_timeout(act.get("ms", 1000))
                    elif t == "eval":     await page.evaluate(act["js"])
                    elif t == "select":   await page.select_option(act["selector"], value=act["value"])
                    elif t == "click":    await page.click(act["selector"])
                    elif t == "waitnet":  await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception as e:
                    logger.debug(f"[PLAYWRIGHT] action {act.get('type')} failed: {e}")
            content = await page.content()
            await browser.close()
            return content
    except Exception as e:
        logger.error(f"[PLAYWRIGHT] interact_and_scrape failed: {e}")
        return ""