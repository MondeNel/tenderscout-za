"""
scraper/sites/sa_tenders.py — Aggregator Tender Portals Scraper
================================================================
Scrapes third-party tender aggregator websites that compile tenders
from multiple sources across South Africa.

Key aggregators:
    - easytenders.co.za      (JavaScript-rendered)
    - sa-tenders.co.za       (JavaScript-rendered)
    - onlinetenders.co.za    (static HTML)
    - tenderalerts.co.za     (static HTML)

These sites provide nationwide coverage and are more efficient than
scraping individual municipal sites one by one.

Architecture:
    - AGGREGATORS: Configuration registry with selectors per site
    - _parse_items(): Generic HTML parser using CSS selectors
    - _scrape_with_playwright(): JavaScript rendering via Playwright
    - scrape_aggregator(): Dispatcher with pagination support
    - scrape(): Main entry point for orchestrator
"""
import logging
import httpx
import asyncio
import re
from datetime import datetime
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
    get_headers,            # Returns browser-like HTTP headers
    is_closing_date_expired, # Checks if a date string is in the past
)

logger = logging.getLogger(__name__)

# =============================================================================
# AGGREGATOR CONFIGURATION
# =============================================================================
# Each entry defines an aggregator website to scrape.
#
# Fields:
#   - name: Display name for logging
#   - url: Starting URL for the tender listings
#   - province_hint: Default province if not detected (None = detect from text)
#   - js_required: True = use Playwright, False = use httpx
#   - item_sel: CSS selector for individual tender items/rows
#   - title_sel: CSS selector for tender title within item
#   - link_sel: CSS selector for detail page link
#   - closing_sel: CSS selector for closing date
#   - body_sel: CSS selector for issuing body/department
#   - next_sel: CSS selector for "next page" link (for static sites)
# =============================================================================

AGGREGATORS = [
    # -------------------------------------------------------------------------
    # EasyTenders — JavaScript-rendered, reliable results in testing (52 tenders)
    # -------------------------------------------------------------------------
    {
        "name":          "EasyTenders (Northern Cape)",
        "url":           "https://easytenders.co.za/tenders-in/northern-cape",
        "province_hint": "Northern Cape",
        "js_required":   True,
        "item_sel":      ".tender-item, article.tender, div[class*='tender'], .listing-item, .card",
        "title_sel":     "h2, h3, h4, .tender-title, .title, a",
        "link_sel":      "a[href]",
        "closing_sel":   ".closing-date, .date, time, .deadline, [class*='closing']",
        "body_sel":      ".issuer, .department, .authority, .organization, [class*='issuer']",
        "next_sel":      "a.next, a[rel='next'], .pagination .next",
    },
    
    # -------------------------------------------------------------------------
    # OnlineTenders — Static HTML, but currently returns 0 results
    # NOTE: Site may have changed structure — needs investigation
    # -------------------------------------------------------------------------
    {
        "name":          "OnlineTenders (Northern Cape)",
        "url":           "https://www.onlinetenders.co.za/tenders/northern-cape",
        "province_hint": "Northern Cape",
        "js_required":   False,
        "item_sel":      "div.tender-item, div.listing-item, article.tender, table tbody tr, .tender-row",
        "title_sel":     "h2, h3, .tender-title, a, td:first-child a",
        "link_sel":      "a[href]",
        "closing_sel":   ".date, .closing-date, time, td:nth-child(3)",
        "body_sel":      ".issuer, .authority, .department, td:nth-child(2)",
        "next_sel":      "a.next, a[rel='next'], .pagination li.next a",
    },
    
    # -------------------------------------------------------------------------
    # SA-Tenders — JavaScript-rendered, currently returns 0 results
    # NOTE: May require interaction (clicking "Load More") or different selectors
    # -------------------------------------------------------------------------
    {
        "name":          "sa-tenders.co.za",
        "url":           "https://sa-tenders.co.za/tenders",
        "province_hint": None,  # Nationwide — detect from text
        "js_required":   True,
        "item_sel":      ".tender-item, article.tender, div[class*='tender'], .listing-item, .card",
        "title_sel":     "h2, h3, .tender-title, .title, a",
        "link_sel":      "a[href]",
        "closing_sel":   ".closing-date, .date, .deadline, [class*='closing']",
        "body_sel":      ".department, .issuer, .authority, .organization",
        "next_sel":      "a.next, a[rel='next'], button.load-more",
    },
    
    # -------------------------------------------------------------------------
    # TenderAlerts — Static HTML, currently returns 0 results
    # -------------------------------------------------------------------------
    {
        "name":          "TenderAlerts",
        "url":           "https://tenderalerts.co.za",
        "province_hint": None,
        "js_required":   False,
        "item_sel":      "div.tender-item, div.post, article, table tbody tr, .tender-listing",
        "title_sel":     "h2, h3, h4, .tender-title, a, .entry-title",
        "link_sel":      "a[href]",
        "closing_sel":   ".date, .closing, time, .deadline",
        "body_sel":      ".issuer, .department, .authority, .entry-meta",
        "next_sel":      "a.next, a[rel='next'], .nav-links .next",
    },
     # -------------------------------------------------------------------------
    # EasyTenders — WORKING (keep as is)
    # -------------------------------------------------------------------------
    {
        "name":          "EasyTenders (Northern Cape)",
        "url":           "https://easytenders.co.za/tenders-in/northern-cape",
        "province_hint": "Northern Cape",
        "js_required":   True,
        "item_sel":      "div.grid > div, article, .tender-item, [class*='tender']",
        "title_sel":     "h2, h3, .font-semibold, .tender-title, a",
        "link_sel":      "a[href]",
        "closing_sel":   ".closing-date, .date, time, .text-sm, [class*='closing']",
        "body_sel":      ".issuer, .department, .authority, .text-gray-600",
        "next_sel":      "a.next, a[rel='next'], button:has-text('Next')",
        "max_scrolls":   3,
    },
    
    # -------------------------------------------------------------------------
    # OnlineTenders — UPDATED SELECTORS
    # -------------------------------------------------------------------------
    {
        "name":          "OnlineTenders (Northern Cape)",
        "url":           "https://www.onlinetenders.co.za/tenders/northern-cape",
        "province_hint": "Northern Cape",
        "js_required":   True,  # Changed to True — site may use JS
        "item_sel":      "div.row > div, .tender-listing, .search-result, table tr",
        "title_sel":     "h4, h5, .tender-title, a strong, td:first-child a",
        "link_sel":      "a[href*='tender'], a[href*='/tenders/']",
        "closing_sel":   ".closing, .date, .deadline, td:nth-child(3), time",
        "body_sel":      ".issuer, .authority, .dept, td:nth-child(2)",
        "next_sel":      "a:has-text('Next'), .pagination .next, li.next a",
        "max_scrolls":   2,
    },
    
    # -------------------------------------------------------------------------
    # SA-Tenders — UPDATED SELECTORS
    # -------------------------------------------------------------------------
    {
        "name":          "sa-tenders.co.za",
        "url":           "https://sa-tenders.co.za/tenders",
        "province_hint": None,
        "js_required":   True,
        "item_sel":      "div.listing, article.post, div.tender-listing, .card",
        "title_sel":     "h2, h3, .entry-title, .listing-title, a",
        "link_sel":      "a[href*='tender'], a.listing-link, h2 a",
        "closing_sel":   ".closing-date, .deadline, .date, .posted-date",
        "body_sel":      ".issuer, .department, .authority, .listing-meta",
        "next_sel":      "a.next, .pagination a, .nav-links a",
        "max_scrolls":   5,
    },
    
    # -------------------------------------------------------------------------
    # TenderAlerts — UPDATED SELECTORS
    # -------------------------------------------------------------------------
    {
        "name":          "TenderAlerts",
        "url":           "https://tenderalerts.co.za",
        "province_hint": None,
        "js_required":   False,
        "item_sel":      "div.tender-item, div.alert-item, article, .listing-item",
        "title_sel":     "h3, h4, .alert-title, .title, a",
        "link_sel":      "a[href*='tender'], a.btn, .read-more",
        "closing_sel":   ".closing, .deadline, .date, .expiry",
        "body_sel":      ".issuer, .authority, .organization, .source",
        "next_sel":      "a.next, .pagination a",
        "max_scrolls":   2,
    },
]


# =============================================================================
# DATE PARSING HELPER
# =============================================================================

def _parse_date_flexible(text: str) -> str:
    """
    Parse various date formats commonly found on aggregator sites.
    
    These sites use inconsistent date formats. This function handles:
        - "2026-01-15" → "15/01/2026"
        - "15 Jan 2026" → "15/01/2026"
        - "15/01/2026" → "15/01/2026"
        - "Closing: 15 January 2026" → "15/01/2026"
    
    Args:
        text: Raw date string from the page
        
    Returns:
        Standardized DD/MM/YYYY string, or empty string if unparseable
    """
    if not text:
        return ""
    
    text = clean_text(text)
    
    # ISO format: 2026-01-15
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    
    # "15 Jan 2026" or "15 January 2026"
    m = re.search(
        r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
        text, re.IGNORECASE
    )
    if m:
        try:
            month_map = {
                "jan": 1, "january": 1, "feb": 2, "february": 2,
                "mar": 3, "march": 3, "apr": 4, "april": 4,
                "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
                "aug": 8, "august": 8, "sep": 9, "september": 9,
                "oct": 10, "october": 10, "nov": 11, "november": 11,
                "dec": 12, "december": 12,
            }
            month_lower = m.group(2).lower()
            month_num = next((v for k, v in month_map.items() if k in month_lower), None)
            if month_num:
                return f"{int(m.group(1)):02d}/{month_num:02d}/{m.group(3)}"
        except Exception:
            pass
    
    # Already in DD/MM/YYYY format
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    
    return ""


# =============================================================================
# GENERIC HTML PARSER
# =============================================================================

def _parse_items(html: str, source: Dict, page_url: str) -> List[Dict]:
    """
    Parse tender items from HTML using the configured CSS selectors.
    
    This is the core extraction function that works for both static (httpx)
    and JavaScript-rendered (Playwright) pages.
    
    Args:
        html: Full HTML content of the page
        source: Aggregator configuration dictionary
        page_url: URL of the page being parsed (for building absolute URLs)
        
    Returns:
        List of standardized tender dictionaries
    """
    if not html:
        return []
        
    results = []
    soup = BeautifulSoup(html, "lxml")
    
    # -------------------------------------------------------------------------
    # Find all tender items using the configured selector
    # -------------------------------------------------------------------------
    items = soup.select(source["item_sel"])
    
    # Fallback: If no items found with selector, scan all links as a last resort
    if not items:
        logger.debug(f"[SA_TENDERS] No items found with '{source['item_sel']}' — falling back to link scan")
        items = soup.select("a[href]")
        
    if not items:
        logger.warning(f"[SA_TENDERS] No items found at all for {source['name']}")
        return []

    province_hint = source.get("province_hint")
    
    # Extract base URL for resolving relative links
    parsed = urlparse(page_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    seen_titles = set()  # Track seen titles to avoid duplicates within this page

    for item in items:
        try:
            # -----------------------------------------------------------------
            # Extract title
            # -----------------------------------------------------------------
            title_el = item.select_one(source["title_sel"]) if source.get("title_sel") else item
            if not title_el:
                continue
                
            title = clean_text(title_el.get_text())
            if not title or len(title) < 8:
                continue
                
            # Skip duplicates (common with overlapping selectors)
            title_lower = title.lower()
            if title_lower in seen_titles:
                continue
            seen_titles.add(title_lower)

            # -----------------------------------------------------------------
            # Extract link
            # -----------------------------------------------------------------
            link_el = item.select_one(source["link_sel"]) if source.get("link_sel") else item
            href = link_el.get("href", "") if link_el else ""
            
            # Build absolute URL
            if href and not href.startswith("http"):
                href = urljoin(base, href)
            detail_url = href if href else page_url

            # -----------------------------------------------------------------
            # Extract closing date
            # -----------------------------------------------------------------
            closing_el = item.select_one(source["closing_sel"]) if source.get("closing_sel") else None
            closing_raw = clean_text(closing_el.get_text()) if closing_el else ""
            closing_date = _parse_date_flexible(closing_raw)

            # Skip expired tenders
            if closing_date and is_closing_date_expired(closing_date):
                logger.debug(f"[SA_TENDERS] Skipping expired tender: {title[:50]}")
                continue

            # -----------------------------------------------------------------
            # Extract issuing body
            # -----------------------------------------------------------------
            body_el = item.select_one(source["body_sel"]) if source.get("body_sel") else None
            issuing_body = clean_text(body_el.get_text()) if body_el else ""

            # -----------------------------------------------------------------
            # Build detection text for geographic/industry classification
            # -----------------------------------------------------------------
            # Combine title and issuing body for better detection
            detection_text = f"{title} {issuing_body}"
            
            # Also try to get description text from the item
            item_text = clean_text(item.get_text())
            if len(item_text) > len(detection_text):
                detection_text = item_text[:500]  # Limit to first 500 chars

            # -----------------------------------------------------------------
            # Geographic detection
            # -----------------------------------------------------------------
            province = province_hint or detect_province(detection_text)
            municipality = detect_municipality(detection_text, province)
            town = detect_town(detection_text, province)

            # -----------------------------------------------------------------
            # Build result
            # -----------------------------------------------------------------
            results.append({
                "title":             title,
                "description":       issuing_body or f"Tender listed on {source['name']}",
                "issuing_body":      issuing_body,
                "province":          province,
                "municipality":      municipality,
                "town":              town,
                "industry_category": detect_industry(detection_text),
                "closing_date":      closing_date,
                "posted_date":       "",  # Aggregators rarely show posted dates
                "source_url":        detail_url,
                "document_url":      None,  # Would require scraping detail page
                "source_site":       parsed.netloc.replace("www.", ""),
                "reference_number":  "",
                "contact_info":      "",
                "content_hash":      make_content_hash(title, detail_url),
            })
            
        except Exception as e:
            logger.debug(f"[SA_TENDERS] Item parse error: {e}")

    return results


# =============================================================================
# PLAYWRIGHT SCRAPER (for JavaScript-rendered sites)
# =============================================================================

async def _scrape_with_playwright(source: Dict, max_scrolls: int = 5) -> List[Dict]:
    """
    Scrape a JavaScript-rendered aggregator page using Playwright.
    
    Features:
        - Handles infinite scroll by scrolling down multiple times
        - Waits for dynamic content to load
        - Handles cookie consent banners and modals
    
    Args:
        source: Aggregator configuration dictionary
        max_scrolls: Number of times to scroll down for infinite-scroll sites
        
    Returns:
        List of standardized tender dictionaries
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[SA_TENDERS] playwright not installed. Run: pip install playwright && playwright install chromium")
        return []

    results = []
    
    try:
        async with async_playwright() as pw:
            # -----------------------------------------------------------------
            # Launch browser with realistic viewport
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
            
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,
                viewport={"width": 1440, "height": 2000},
            )
            
            page = await context.new_page()
            
            # -----------------------------------------------------------------
            # Navigate to page
            # -----------------------------------------------------------------
            logger.info(f"[SA_TENDERS] Loading (JS): {source['url']}")
            await page.goto(source["url"], wait_until="domcontentloaded", timeout=60000)
            
            # -----------------------------------------------------------------
            # Handle common cookie consent banners
            # -----------------------------------------------------------------
            try:
                # Try to click "Accept" on cookie banners
                accept_btn = await page.query_selector(
                    "button:has-text('Accept'), button:has-text('OK'), button:has-text('Agree'), "
                    "button:has-text('Allow'), .cookie-accept, .cc-accept"
                )
                if accept_btn:
                    await accept_btn.click()
                    await page.wait_for_timeout(500)
            except Exception:
                pass

            # -----------------------------------------------------------------
            # Scroll to load lazy-loaded content (infinite scroll sites)
            # -----------------------------------------------------------------
            for i in range(max_scrolls):
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)
                
                # Check if new content loaded
                new_height = await page.evaluate("document.body.scrollHeight")
                logger.debug(f"[SA_TENDERS] Scroll {i+1}: height={new_height}")
                
            # Scroll back to top (some sites only render visible content)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(1000)

            # -----------------------------------------------------------------
            # Try to click "Load More" button if present
            # -----------------------------------------------------------------
            try:
                load_more = await page.query_selector(
                    "button:has-text('Load More'), button:has-text('Show More'), "
                    "a:has-text('Load More'), .load-more, .show-more"
                )
                if load_more:
                    await load_more.click()
                    await page.wait_for_timeout(2000)
                    logger.info("[SA_TENDERS] Clicked 'Load More' button")
            except Exception:
                pass

            # -----------------------------------------------------------------
            # Wait for content to stabilize
            # -----------------------------------------------------------------
            await page.wait_for_timeout(1000)
            
            # Get the fully-rendered HTML
            html = await page.content()
            
            await browser.close()
            
            # -----------------------------------------------------------------
            # Parse the HTML using the generic parser
            # -----------------------------------------------------------------
            results = _parse_items(html, source, source["url"])
            logger.info(f"[SA_TENDERS] {source['name']} (JS): {len(results)} tenders")
            
    except Exception as e:
        logger.error(f"[SA_TENDERS] {source['name']} playwright failed: {e}", exc_info=True)

    return results


# =============================================================================
# AGGREGATOR SCRAPER (Dispatcher with Pagination)
# =============================================================================

async def scrape_aggregator(
    client: httpx.AsyncClient, 
    source: Dict, 
    max_pages: int = 5
) -> List[Dict]:
    """
    Scrape a single aggregator source with pagination support.
    
    Routes to Playwright for JS sites, uses httpx for static sites.
    Handles following "next" links for multi-page results.
    
    Args:
        client: HTTPX async client (shared for efficiency)
        source: Aggregator configuration dictionary
        max_pages: Maximum number of pages to scrape (safety limit)
        
    Returns:
        List of standardized tender dictionaries from this aggregator
    """
    # -------------------------------------------------------------------------
    # JavaScript sites: delegate to Playwright (handles its own pagination)
    # -------------------------------------------------------------------------
    if source.get("js_required"):
        return await _scrape_with_playwright(source)

    # -------------------------------------------------------------------------
    # Static sites: use httpx with pagination
    # -------------------------------------------------------------------------
    all_results = []
    current_url = source["url"]
    pages_scraped = 0

    while pages_scraped < max_pages:
        try:
            logger.debug(f"[SA_TENDERS] Fetching page {pages_scraped + 1}: {current_url}")
            
            response = await client.get(current_url)
            if response.status_code != 200:
                logger.warning(f"{source['name']} returned {response.status_code} for {current_url}")
                break
                
            # Parse current page
            page_results = _parse_items(response.text, source, current_url)
            all_results.extend(page_results)
            pages_scraped += 1
            
            logger.debug(f"[SA_TENDERS] Page {pages_scraped}: {len(page_results)} tenders")

            # -----------------------------------------------------------------
            # Find next page link
            # -----------------------------------------------------------------
            soup = BeautifulSoup(response.text, "lxml")
            
            # Try multiple next-link selectors
            next_sel = source.get("next_sel", 'a.next, a[rel="next"], .pagination .next a, .nav-links .next')
            next_link = soup.select_one(next_sel)
            
            if next_link and next_link.get("href"):
                next_href = next_link["href"]
                # Skip if it's just "#" or javascript:
                if next_href.startswith("#") or next_href.startswith("javascript:"):
                    break
                    
                current_url = urljoin(current_url, next_href)
                await asyncio.sleep(1.0)  # Be polite — rate limiting
            else:
                logger.debug(f"[SA_TENDERS] No next page found for {source['name']}")
                break
                
        except Exception as e:
            logger.error(f"{source['name']} page {pages_scraped + 1} failed: {e}")
            break

    logger.info(f"[SA_TENDERS] {source['name']}: {len(all_results)} tenders ({pages_scraped} pages)")
    return all_results


# =============================================================================
# DETAIL PAGE SCRAPER (for future use)
# =============================================================================

async def scrape_detail(client: httpx.AsyncClient, url: str, source: Dict) -> List[Dict]:
    """
    Scrape a single detail/listing URL for additional information.
    
    Currently not used in main flow — could be implemented to extract
    full descriptions, document URLs, and contact info from detail pages.
    
    Args:
        client: HTTPX async client
        url: Detail page URL to scrape
        source: Aggregator configuration (for selectors)
        
    Returns:
        List containing single tender dict, or empty list on failure
    """
    try:
        response = await client.get(url)
        if response.status_code != 200:
            return []
        return _parse_items(response.text, source, url)
    except Exception as e:
        logger.error(f"[SA_TENDERS] detail scrape failed [{url}]: {e}")
        return []


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def scrape() -> List[Dict]:
    """
    Main entry point — scrapes all configured aggregator sources.
    
    Creates a shared HTTPX client, iterates through all aggregators,
    and combines results.
    
    Returns:
        Combined list of all tenders from all aggregators
    """
    all_results = []
    
    async with httpx.AsyncClient(
        timeout=30,              # Generous timeout for slower aggregator sites
        headers=get_headers(),   # Browser-like headers
        follow_redirects=True,   # Handle 301/302
        verify=False,            # Skip SSL verification (some sites have bad certs)
    ) as client:
        for source in AGGREGATORS:
            try:
                logger.info(f"[SA_TENDERS] Starting: {source['name']}")
                results = await scrape_aggregator(client, source)
                all_results.extend(results)
                logger.info(f"[SA_TENDERS] Completed: {source['name']} — {len(results)} tenders")
            except Exception as e:
                logger.error(f"[SA_TENDERS] {source['name']} failed: {e}", exc_info=True)
                
    logger.info(f"[SA_TENDERS] TOTAL: {len(all_results)} tenders from all aggregators")
    return all_results


# =============================================================================
# DEBUGGING HELPER — Test individual selectors
# =============================================================================

async def debug_selectors(source_name: str) -> None:
    """
    Debug helper — fetch a page and test the configured selectors.
    
    Usage:
        await debug_selectors("OnlineTenders (Northern Cape)")
    
    This helps identify why a site returns 0 results by showing:
        - What the page HTML actually contains
        - Which selectors are failing
    """
    source = next((s for s in AGGREGATORS if s["name"] == source_name), None)
    if not source:
        print(f"Source '{source_name}' not found")
        return
        
    print(f"\n=== DEBUG: {source['name']} ===\n")
    
    if source.get("js_required"):
        print("Using Playwright (JS rendering)...")
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(source["url"], wait_until="networkidle", timeout=30000)
                html = await page.content()
                await browser.close()
        except Exception as e:
            print(f"Playwright error: {e}")
            return
    else:
        print("Using httpx (static)...")
        async with httpx.AsyncClient(timeout=20, verify=False) as client:
            resp = await client.get(source["url"])
            html = resp.text
            
    soup = BeautifulSoup(html, "lxml")
    
    # Test each selector
    print(f"\nURL: {source['url']}")
    print(f"HTML length: {len(html)} characters")
    print(f"\n--- Selector Tests ---")
    
    for sel_name in ["item_sel", "title_sel", "link_sel", "closing_sel", "body_sel"]:
        selector = source.get(sel_name)
        if selector:
            matches = soup.select(selector)
            print(f"{sel_name}: '{selector}' → {len(matches)} matches")
            if matches and len(matches) <= 3:
                for m in matches[:3]:
                    print(f"   → {clean_text(m.get_text())[:80]}")
        else:
            print(f"{sel_name}: (not configured)")
            
    # Show first few links on page
    print(f"\n--- First 10 links on page ---")
    for i, link in enumerate(soup.select("a[href]")[:10]):
        text = clean_text(link.get_text())[:60]
        href = link.get("href", "")[:60]
        print(f"{i+1}. {text} → {href}")


# Add this debug function to sa_tenders.py or run separately:

async def debug_sa_tenders():
    """Debug sa-tenders.co.za specifically."""
    from playwright.async_api import async_playwright
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)  # Visible browser
        page = await browser.new_page()
        
        url = "https://sa-tenders.co.za/tenders"
        print(f"Loading: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        
        # Wait for content
        await page.wait_for_timeout(3000)
        
        # Take screenshot
        await page.screenshot(path="sa_tenders_debug.png", full_page=True)
        print("Screenshot saved to sa_tenders_debug.png")
        
        # Get HTML
        html = await page.content()
        
        # Save HTML for inspection
        with open("sa_tenders_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("HTML saved to sa_tenders_debug.html")
        
        # Check for common selectors
        selectors_to_test = [
            "a[href*='tender']",
            ".tender-item",
            "article",
            ".listing-item",
            ".card",
            "h2",
            "h3",
            ".title",
        ]
        
        print("\nSelector test results:")
        for sel in selectors_to_test:
            count = await page.locator(sel).count()
            if count > 0:
                print(f"  {sel}: {count} matches")
                # Show first match text
                first = await page.locator(sel).first.text_content()
                print(f"    → {first[:80]}...")
        
        await browser.close()