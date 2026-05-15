"""
scraper/playwright_runner.py — Playwright Browser Utilities
============================================================
Provides reusable async functions for JS-rendered page scraping
using a shared Playwright browser instance.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_browser_sem: Optional[asyncio.Semaphore] = None

def _get_semaphore() -> asyncio.Semaphore:
    global _browser_sem
    if _browser_sem is None:
        _browser_sem = asyncio.Semaphore(3)
    return _browser_sem

@asynccontextmanager
async def _browser_context(ignore_https_errors: bool = False):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[PLAYWRIGHT] playwright not installed")
        raise

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--ignore-certificate-errors", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=ignore_https_errors,
        )
        try:
            yield ctx
        finally:
            await ctx.close()
            try:
                await asyncio.wait_for(browser.close(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("[PLAYWRIGHT] Browser close timed out")

async def get_page_content(url: str, wait_for: str = "networkidle", timeout: int = 30000,
                           js_eval: str = "", ignore_https_errors: bool = False) -> str:
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

async def get_multiple_pages(urls: List[str], wait_for: str = "networkidle", timeout: int = 30000,
                             ignore_https_errors: bool = False) -> Dict[str, str]:
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

async def interact_and_scrape(url: str, actions: List[Dict], timeout: int = 90000,
                              ignore_https_errors: bool = False) -> str:
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
                        except Exception as action_err:
                            logger.debug(f"[PLAYWRIGHT] Action {action_type!r} failed: {action_err}")
                    return await page.content()
                finally:
                    await page.close()
        except Exception as e:
            logger.error(f"[PLAYWRIGHT] interact_and_scrape failed at {url}: {e}")
            return ""

async def run_with_playwright(fn: Callable) -> Any:
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

# Deprecated alias
async def run_sync(fn: Callable) -> Any:
    logger.warning("[PLAYWRIGHT] run_sync() is deprecated — use run_with_playwright()")
    return await run_with_playwright(fn)