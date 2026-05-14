import asyncio
import logging
import sys
from typing import Callable, Any, Dict, List, Optional
from datetime import datetime

# Use loguru if installed, otherwise fallback to standard logging
try:
    from loguru import logger
except ImportError:
    logger = logging.getLogger(__name__)

# --- Windows Compatibility Fix ---
if sys.platform == "win32":
    try:
        policy = asyncio.get_event_loop_policy()
        if not isinstance(policy, asyncio.WindowsSelectorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            logger.info("[PLAYWRIGHT] Applied WindowsSelectorEventLoopPolicy")
    except AttributeError:
        pass

# Global limit for concurrent tabs to prevent memory spikes
BROWSER_SEMAPHORE = asyncio.Semaphore(3)

async def run_sync(fn: Callable) -> Any:
    """
    Legacy shim for older scrapers. 
    Attempts to run the provided function as an async coroutine.
    """
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            if asyncio.iscoroutinefunction(fn):
                return await fn(pw)
            
            logger.error("[PLAYWRIGHT] run_sync received a non-async function. Please refactor to async.")
            return []
    except Exception as e:
        logger.error(f"[PLAYWRIGHT] run_sync failed: {e}")
        return []

async def get_page_content(
    url: str,
    wait_for: str = "networkidle",
    timeout: int = 30000,
    js_eval: str = "",
) -> str:
    """
    Navigates to a URL and returns the fully rendered HTML.
    Includes anti-detection headers and SSL bypass.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[PLAYWRIGHT] Dependency missing.")
        return ""

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--ignore-certificate-errors", "--no-sandbox", "--disable-dev-shm-usage"]
            )
            
            # Context mimicking a real desktop browser
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True
            )
            
            page = await ctx.new_page()
            await page.goto(url, wait_until=wait_for, timeout=timeout)
            
            if js_eval:
                await page.evaluate(js_eval)
            
            content = await page.content()
            await browser.close()
            return content
            
    except Exception as e:
        logger.error(f"[PLAYWRIGHT] Error fetching {url}: {e}")
        return ""

async def get_multiple_pages(urls: List[str], wait_for: str = "networkidle", timeout: int = 30000) -> Dict[str, str]:
    """
    Loads multiple URLs concurrently with a concurrency limit (Semaphore).
    Returns a dictionary of {url: html_content}.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {u: "" for u in urls}

    results = {}
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = await browser.new_context(ignore_https_errors=True)

        async def _safe_load(url: str):
            async with BROWSER_SEMAPHORE:
                page = None
                try:
                    page = await ctx.new_page()
                    await page.goto(url, wait_until=wait_for, timeout=timeout)
                    html = await page.content()
                    return url, html
                except Exception as e:
                    logger.warning(f"[PLAYWRIGHT] Skipping {url} due to error: {e}")
                    return url, ""
                finally:
                    if page:
                        await page.close()

        # Orchestrate the concurrent loads
        tasks = [_safe_load(u) for u in urls]
        pairs = await asyncio.gather(*tasks)
        
        await browser.close()
        results = dict(pairs)
        
    return results

async def interact_and_scrape(url: str, actions: List[Dict], timeout: int = 90000) -> str:
    """
    Complex interaction (clicking, waiting, selecting) before scraping.
    Useful for 'Search' buttons on SA municipal portals.
    """
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
            ctx = await browser.new_context(ignore_https_errors=True)
            page = await ctx.new_page()
            
            await page.goto(url, wait_until="networkidle", timeout=timeout)
            
            for act in actions:
                try:
                    type_ = act.get("type")
                    if type_ == "wait":
                        await page.wait_for_timeout(act.get("ms", 1000))
                    elif type_ == "eval":
                        await page.evaluate(act["js"])
                    elif type_ == "select":
                        await page.select_option(act["selector"], value=act["value"])
                    elif type_ == "click":
                        await page.click(act["selector"])
                    elif type_ == "waitnet":
                        await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception as action_err:
                    logger.debug(f"[PLAYWRIGHT] Action {act.get('type')} failed: {action_err}")
            
            content = await page.content()
            await browser.close()
            return content
    except Exception as e:
        logger.error(f"[PLAYWRIGHT] Interaction failed at {url}: {e}")
        return ""