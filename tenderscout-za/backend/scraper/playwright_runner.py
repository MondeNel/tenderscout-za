"""
scraper/playwright_runner.py
-----------------------------
Windows-compatible Playwright runner.

On Windows, asyncio uses ProactorEventLoop which does NOT support
subprocess creation (needed by Playwright). The fix is to run Playwright
in a separate thread with its OWN event loop using SelectorEventLoop.

Usage:
    from scraper.playwright_runner import run_sync

    def my_scraper(playwright):
        browser = playwright.chromium.launch(headless=True)
        ...
        return results

    results = await run_sync(my_scraper)
"""

import asyncio
import sys
import threading
from typing import Callable, Any


def _run_in_thread(fn: Callable) -> Any:
    """
    Run fn(playwright) in a new thread with its own SelectorEventLoop.
    This bypasses Windows ProactorEventLoop subprocess limitation.
    """
    result = None
    error  = None

    def thread_target():
        nonlocal result, error
        # Force SelectorEventLoop on Windows
        if sys.platform == "win32":
            loop = asyncio.SelectorEventLoop()
            asyncio.set_event_loop(loop)
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                result = fn(pw)
        except Exception as e:
            error = e
        finally:
            loop.close()

    t = threading.Thread(target=thread_target, daemon=True)
    t.start()
    t.join(timeout=300)  # 5 min max per scraper

    if error:
        raise error
    return result


async def run_sync(fn: Callable) -> Any:
    """
    Async wrapper — runs a sync Playwright function in a thread pool.
    Call from async code: results = await run_sync(my_fn)
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_in_thread, fn)