"""
scraper/sites/js_scraper.py — JavaScript-Heavy Tender Sites Scraper
====================================================================
Scrapes tender sites that absolutely require a real browser (Playwright)
because they render content client-side with React, Vue, Angular, etc.

This module is specifically for sites that:
    - Don't work with httpx + BeautifulSoup at all
    - Have province-specific sub-pages
    - Require JavaScript execution to show any content

Source names match the test scripts exactly (test_all_scrapers.py, test_js_scrapers.py).

Architecture:
    - JS_SOURCES: Configuration registry with province_urls mapping
    - _parse_items(): HTML parser using CSS selectors
    - scrape_js_source(): Launches Playwright per province URL
    - scrape_all_js_sources(): Main entry point with deduplication
    - scrape_js_source_by_name(): Single-source scraper for testing

NOTE: There is overlap with sa_tenders.py. This module should be used for
the definitive JS scraping, and sa_tenders.py should delegate to it.
"""
import logging
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional

from scraper.utils import (
    make_content_hash,      # Creates unique hash for deduplication
    detect_industry,        # Classifies tender by industry category
    detect_province,        # Extracts province from text
    detect_municipality,    # Extracts municipality name
    detect_town,            # Extracts town/city name
    clean_text,             # Normalizes whitespace and removes junk
    is_closing_date_expired, # Checks if a date string is in the past
)

logger = logging.getLogger(__name__)

# =============================================================================
# JAVASCRIPT SOURCES REGISTRY
# =============================================================================
# Each entry defines a JS-heavy site with province-specific URLs.
#
# Fields:
#   - name: Display name (must match test script expectations)
#   - base_url: Base URL for resolving relative links
#   - province_urls: Dict mapping province name to URL (or single "url" for simple case)
#   - item_sel: CSS selector for individual tender items
#   - title_sel: CSS selector for tender title
#   - link_sel: CSS selector for detail page link
#   - closing_sel: CSS selector for closing date
#   - body_sel: CSS selector for issuing body/department
#   - max_scrolls: Number of scroll attempts for infinite-scroll sites
# =============================================================================

JS_SOURCES = [
    # -------------------------------------------------------------------------
    # EasyTenders — Nationwide (all provinces)
    # This is your most reliable JS aggregator (52 tenders in test)
    # -------------------------------------------------------------------------
    {
        "name":     "EasyTenders",
        "base_url": "https://easytenders.co.za",
        # For backward compatibility with test scripts that expect "url"
        "url":      "https://easytenders.co.za/tenders",
        "province_urls": {
            "Eastern Cape":  "https://easytenders.co.za/tenders-in/eastern-cape",
            "Free State":    "https://easytenders.co.za/tenders-in/free-state",
            "Gauteng":       "https://easytenders.co.za/tenders-in/gauteng",
            "KwaZulu-Natal": "https://easytenders.co.za/tenders-in/kwazulu-natal",
            "Limpopo":       "https://easytenders.co.za/tenders-in/limpopo",
            "Mpumalanga":    "https://easytenders.co.za/tenders-in/mpumalanga",
            "North West":    "https://easytenders.co.za/tenders-in/north-west",
            "Northern Cape": "https://easytenders.co.za/tenders-in/northern-cape",
            "Western Cape":  "https://easytenders.co.za/tenders-in/western-cape",
        },
        "item_sel":    ".tender-item, article.tender, div.listing-item, .tender-card, .card, [class*='tender']",
        "title_sel":   "h2, h3, h4, .tender-title, .title, a",
        "link_sel":    "a[href]",
        "closing_sel": ".closing-date, .date, time, .deadline, [class*='closing']",
        "body_sel":    ".issuer, .department, .authority, .tender-body, .organization",
        "max_scrolls": 3,
    },
    
    # -------------------------------------------------------------------------
    # EasyTenders (Northern Cape only) — For targeted scraping
    # This is the one that returned 52 tenders in your test
    # -------------------------------------------------------------------------
    {
        "name":     "EasyTenders (Northern Cape)",
        "base_url": "https://easytenders.co.za",
        "url":      "https://easytenders.co.za/tenders-in/northern-cape",  # Added to fix KeyError
        "province_urls": {
            "Northern Cape": "https://easytenders.co.za/tenders-in/northern-cape",
        },
        "item_sel":    ".tender-item, article.tender, div.listing-item, .tender-card, .card, [class*='tender']",
        "title_sel":   "h2, h3, h4, .tender-title, .title, a",
        "link_sel":    "a[href]",
        "closing_sel": ".closing-date, .date, time, .deadline, [class*='closing']",
        "body_sel":    ".issuer, .department, .authority, .organization",
        "max_scrolls": 3,
    },
    
    # -------------------------------------------------------------------------
    # OnlineTenders (Northern Cape) — Currently returns 0 results
    # NOTE: Site may have changed — needs investigation
    # -------------------------------------------------------------------------
    {
        "name":     "OnlineTenders (Northern Cape)",
        "base_url": "https://www.onlinetenders.co.za",
        "url":      "https://www.onlinetenders.co.za/tenders/northern-cape",  # Added to fix KeyError
        "province_urls": {
            "Northern Cape": "https://www.onlinetenders.co.za/tenders/northern-cape",
        },
        "item_sel":    "div.tender-item, div.listing-item, article, tr, .tender-row, .result-item",
        "title_sel":   "h2, h3, .tender-title, a, .result-title",
        "link_sel":    "a[href]",
        "closing_sel": ".date, .closing-date, time, .result-date",
        "body_sel":    ".issuer, .authority, .department, .result-authority",
        "max_scrolls": 2,
    },
    
    # -------------------------------------------------------------------------
    # SA-Tenders — Nationwide aggregator (currently returns 0 results)
    # NOTE: May require interaction or different selectors
    # -------------------------------------------------------------------------
    {
        "name":     "sa-tenders.co.za",
        "base_url": "https://sa-tenders.co.za",
        "url":      "https://sa-tenders.co.za/tenders",  # Added for completeness
        "province_urls": {
            "National": "https://sa-tenders.co.za/tenders",
        },
        "item_sel":    ".tender-item, article.tender, div[class*='tender'], .listing-item, .card",
        "title_sel":   "h2, h3, .tender-title, .title, a",
        "link_sel":    "a[href]",
        "closing_sel": ".closing-date, .date, .deadline, [class*='closing']",
        "body_sel":    ".department, .issuer, .authority, .organization",
        "max_scrolls": 5,  # This site may use infinite scroll
    },
]

# Quick lookup by name for single-source scraping
JS_SOURCES_BY_NAME: Dict[str, Dict] = {s["name"]: s for s in JS_SOURCES}


# =============================================================================
# HELPER: GET FIRST URL FOR A SOURCE (for test compatibility)
# =============================================================================

def _get_first_url(source: Dict) -> str:
    """
    Get the first available URL from a source configuration.
    
    Handles both:
        - Simple case: source["url"] (added for test compatibility)
        - Province case: first value from source["province_urls"]
    
    Args:
        source: Source configuration dictionary
        
    Returns:
        First available URL string
    """
    # Check for direct url field (added for test compatibility)
    if "url" in source:
        return source["url"]
    
    # Otherwise get first province URL
    urls = source.get("province_urls", {})
    if urls:
        return list(urls.values())[0]
    
    # Fallback to base_url
    return source.get("base_url", "")


# =============================================================================
# HTML PARSER
# =============================================================================

def _parse_items(
    html: str, 
    source: Dict, 
    page_url: str, 
    province_hint: Optional[str] = None
) -> List[Dict]:
    """
    Parse tender items from rendered HTML using configured CSS selectors.
    
    Args:
        html: Full HTML content after JavaScript rendering
        source: Source configuration dictionary
        page_url: URL of the page being parsed (for building absolute URLs)
        province_hint: Province to assign if detection fails
        
    Returns:
        List of standardized tender dictionaries
    """
    if not html:
        return []
        
    results = []
    soup = BeautifulSoup(html, "lxml")
    
    # -------------------------------------------------------------------------
    # Find all tender items
    # -------------------------------------------------------------------------
    items = soup.select(source["item_sel"])
    
    # Fallback: if no items found, try scanning links
    if not items:
        logger.debug(f"[JS_SCRAPER] No items with '{source['item_sel']}' — falling back to link scan")
        items = [a.parent for a in soup.select("a[href]") if a.parent]

    base = source["base_url"]
    seen_titles = set()  # Track seen titles to avoid duplicates

    for item in items:
        try:
            # -----------------------------------------------------------------
            # Extract title
            # -----------------------------------------------------------------
            title_el = item.select_one(source.get("title_sel", "a")) if source.get("title_sel") else item
            if not title_el:
                continue
                
            title = clean_text(title_el.get_text())
            if not title or len(title) < 8:
                continue
                
            # Skip duplicates within this page
            title_lower = title.lower()
            if title_lower in seen_titles:
                continue
            seen_titles.add(title_lower)

            # -----------------------------------------------------------------
            # Extract detail page link
            # -----------------------------------------------------------------
            link_el = item.select_one(source.get("link_sel", "a[href]")) if source.get("link_sel") else None
            href = link_el.get("href", page_url) if link_el else page_url
            if href and not href.startswith("http"):
                href = urljoin(base, href)

            # -----------------------------------------------------------------
            # Extract closing date
            # -----------------------------------------------------------------
            closing_el = item.select_one(source.get("closing_sel", "")) if source.get("closing_sel") else None
            closing_date = clean_text(closing_el.get_text()) if closing_el else ""

            # -----------------------------------------------------------------
            # Extract issuing body
            # -----------------------------------------------------------------
            body_el = item.select_one(source.get("body_sel", "")) if source.get("body_sel") else None
            issuing_body = clean_text(body_el.get_text()) if body_el else ""

            # -----------------------------------------------------------------
            # Skip expired tenders
            # -----------------------------------------------------------------
            if closing_date and is_closing_date_expired(closing_date):
                logger.debug(f"[JS_SCRAPER] Skipping expired: {title[:50]}")
                continue

            # -----------------------------------------------------------------
            # Build detection text for geographic/industry classification
            # -----------------------------------------------------------------
            full_text = f"{title} {issuing_body}"
            
            # Also include surrounding text for better detection
            item_text = clean_text(item.get_text())
            if len(item_text) > len(full_text):
                full_text = item_text[:500]

            # -----------------------------------------------------------------
            # Geographic detection
            # -----------------------------------------------------------------
            province = province_hint or detect_province(full_text)
            municipality = detect_municipality(full_text, province)
            town = detect_town(full_text, province)

            # -----------------------------------------------------------------
            # Extract source site domain
            # -----------------------------------------------------------------
            parsed = urlparse(base)
            source_site = parsed.netloc.replace("www.", "")

            # -----------------------------------------------------------------
            # Build result
            # -----------------------------------------------------------------
            results.append({
                "title":             title,
                "description":       issuing_body or f"Tender from {source['name']}",
                "issuing_body":      issuing_body,
                "province":          province,
                "municipality":      municipality,
                "town":              town,
                "industry_category": detect_industry(full_text),
                "closing_date":      closing_date,
                "posted_date":       "",
                "source_url":        href or page_url,
                "document_url":      None,  # Would require scraping detail page
                "source_site":       source_site,
                "reference_number":  "",
                "contact_info":      "",
                "content_hash":      make_content_hash(title, href or page_url),
            })
            
        except Exception as e:
            logger.debug(f"[JS_SCRAPER] Item parse error: {e}")

    return results


# =============================================================================
# PLAYWRIGHT SCRAPER FOR A SINGLE SOURCE
# =============================================================================

async def scrape_js_source(source: Dict) -> List[Dict]:
    """
    Scrape a single JS source across all its province URLs using Playwright.
    
    Features:
        - Handles infinite scroll by scrolling down multiple times
        - Closes pages after use to manage memory
        - Continues to next province if one fails
    
    Args:
        source: Source configuration dictionary
        
    Returns:
        List of standardized tender dictionaries from all provinces
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error(f"[JS_SCRAPER] playwright not installed — skipping {source['name']}")
        return []

    all_results = []
    urls = source.get("province_urls", {})
    
    # If no province_urls but has "url" field, use that as a single URL
    if not urls and "url" in source:
        urls = {"National": source["url"]}

    if not urls:
        logger.warning(f"[JS_SCRAPER] No URLs configured for {source['name']}")
        return []

    try:
        async with async_playwright() as pw:
            # -----------------------------------------------------------------
            # Launch browser
            # -----------------------------------------------------------------
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--ignore-certificate-errors",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            
            # Shared context for all pages (more efficient)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,
                viewport={"width": 1440, "height": 2000},
            )

            for province, url in urls.items():
                try:
                    logger.info(f"[JS_SCRAPER] Loading: {source['name']} / {province}")
                    
                    page = await context.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    
                    # ---------------------------------------------------------
                    # Scroll to load lazy content (infinite scroll sites)
                    # ---------------------------------------------------------
                    max_scrolls = source.get("max_scrolls", 3)
                    for i in range(max_scrolls):
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await page.wait_for_timeout(1000)
                        
                        # Check for "Load More" button
                        try:
                            load_more = await page.query_selector(
                                "button:has-text('Load More'), button:has-text('Show More'), "
                                "a:has-text('Load More'), .load-more"
                            )
                            if load_more:
                                await load_more.click()
                                await page.wait_for_timeout(1500)
                                logger.debug(f"[JS_SCRAPER] Clicked 'Load More'")
                        except Exception:
                            pass
                    
                    # Scroll back to top (some content only loads when visible)
                    await page.evaluate("window.scrollTo(0, 0)")
                    await page.wait_for_timeout(500)
                    
                    # Get fully rendered HTML
                    html = await page.content()
                    await page.close()
                    
                    # Parse the HTML
                    province_hint = province if province != "National" else None
                    items = _parse_items(html, source, url, province_hint)
                    all_results.extend(items)
                    
                    logger.info(f"[JS_SCRAPER] {source['name']} / {province}: {len(items)} tenders")
                    
                except Exception as e:
                    logger.warning(f"[JS_SCRAPER] {source['name']} / {province} failed: {e}")
                    
            await browser.close()
            
    except Exception as e:
        logger.error(f"[JS_SCRAPER] {source['name']} browser session failed: {e}", exc_info=True)

    return all_results


# =============================================================================
# SCRAPE ALL JS SOURCES
# =============================================================================

async def scrape_all_js_sources() -> List[Dict]:
    """
    Scrape all registered JS sources with deduplication.
    
    Returns:
        Combined list of unique tenders from all JS sources
    """
    seen = set()
    all_results = []
    
    for source in JS_SOURCES:
        try:
            logger.info(f"[JS_SCRAPER] Starting: {source['name']}")
            results = await scrape_js_source(source)
            
            # Deduplicate by content_hash
            for r in results:
                h = r.get("content_hash")
                if h and h not in seen:
                    seen.add(h)
                    all_results.append(r)
                    
            logger.info(f"[JS_SCRAPER] Completed: {source['name']} — {len(results)} tenders")
            
        except Exception as e:
            logger.error(f"[JS_SCRAPER] {source['name']} error: {e}", exc_info=True)
            
    logger.info(f"[JS_SCRAPER] TOTAL: {len(all_results)} tenders from all JS sources")
    return all_results


# =============================================================================
# SINGLE SOURCE SCRAPER (FOR TESTING)
# =============================================================================

async def scrape_js_source_by_name(name: str) -> List[Dict]:
    """
    Scrape a single JS source by name — used by test scripts.
    
    Args:
        name: Source name (must match exactly what's in JS_SOURCES)
        
    Returns:
        List of standardized tender dictionaries from this source
    """
    source = JS_SOURCES_BY_NAME.get(name)
    if not source:
        available = list(JS_SOURCES_BY_NAME.keys())
        logger.error(f"[JS_SCRAPER] Source '{name}' not found. Available: {available}")
        return []
    
    return await scrape_js_source(source)


# =============================================================================
# PUBLIC ENTRY POINT (matches pattern expected by orchestrator)
# =============================================================================

async def scrape() -> List[Dict]:
    """
    Main entry point — matches the pattern expected by the scraper orchestrator.
    
    Returns:
        Combined list of all tenders from all JS sources
    """
    return await scrape_all_js_sources()


# =============================================================================
# DEBUGGING HELPER
# =============================================================================

async def debug_js_source(name: str) -> None:
    """
    Debug helper — test a single JS source and show what it returns.
    
    Usage:
        await debug_js_source("EasyTenders (Northern Cape)")
    """
    source = JS_SOURCES_BY_NAME.get(name)
    if not source:
        print(f"Source '{name}' not found. Available: {list(JS_SOURCES_BY_NAME.keys())}")
        return
        
    print(f"\n=== DEBUG: {name} ===\n")
    
    # Show configuration
    print(f"Base URL: {source.get('base_url')}")
    print(f"Province URLs: {source.get('province_urls', {})}")
    print(f"Selectors:")
    for sel in ["item_sel", "title_sel", "link_sel", "closing_sel", "body_sel"]:
        print(f"  {sel}: {source.get(sel, '(not set)')}")
    
    print("\nScraping...")
    results = await scrape_js_source(source)
    
    print(f"\nResults: {len(results)} tenders")
    for i, tender in enumerate(results[:5]):
        print(f"\n  Tender {i+1}:")
        print(f"    Title: {tender['title'][:80]}")
        print(f"    Province: {tender['province']}")
        print(f"    Closing: {tender['closing_date']}")
        print(f"    Issuing Body: {tender['issuing_body'][:60]}")