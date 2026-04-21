"""
scraper/sites/tender_bulletins.py — Tender Bulletin Aggregator Scraper
=======================================================================
Scrapes tender bulletin websites that aggregate tender notices from
government gazettes and various public sector sources.

Sites:
    - tenderbulletins.co.za (may have anti-bot protection)
    - tendersbulletins.co.za (possibly defunct — DNS fails)

These sites often have strict anti-bot measures. The scraper includes:
    - Realistic browser headers to avoid 403 blocks
    - Retry logic with exponential backoff
    - Fallback to Playwright if static scraping fails

Architecture:
    - SOURCES: Configuration registry with selectors per site
    - _parse_row(): Extracts tender data from a single row/item
    - scrape_page(): Fetches and parses a single page
    - scrape_source(): Handles pagination with retry logic
    - scrape(): Main entry point for orchestrator
"""
import httpx
import asyncio
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional
import logging

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
# SOURCE CONFIGURATION
# =============================================================================
# Each entry defines a tender bulletin site to scrape.
#
# Fields:
#   - name: Display name for logging
#   - url: Starting URL for the tender listings
#   - province_hint: Default province if not detected (None = detect from text)
#   - requires_js: True if site needs Playwright (for sites with anti-bot protection)
#   - selectors: CSS selectors for extracting data
#       - row: Selector for individual tender rows/items
#       - title: Selector for tender title
#       - link: Selector for detail page link
#       - description: Selector for description text
#       - closing_date: Selector for closing date
#       - issuing_body: Selector for issuing organization
#       - doc_link: Selector for document download links
# =============================================================================

SOURCES = [
    {
        "name":          "tenderbulletins.co.za",
        "url":           "https://tenderbulletins.co.za",
        "province_hint": None,
        "requires_js":   True,  # Try static first, fallback to JS if 403
        "selectors": {
            "row":          "table tbody tr, div.tender-row, article.post, .tender-listing-item",
            "title":        "h2, h3, .title, a, .tender-title",
            "link":         "a[href]",
            "description":  "td:nth-child(2), .description, .tender-description",
            "closing_date": "td:last-child, .closing-date, .date, .deadline",
            "issuing_body": "td:first-child, .issuer, .department, .authority",
            "doc_link":     "a[href*='.pdf'], a[href*='.doc'], a[href*='.docx']",
        },
    },
]


# =============================================================================
# ENHANCED HEADERS FOR ANTI-BOT SITES
# =============================================================================

def get_enhanced_headers() -> Dict[str, str]:
    """
    Get enhanced browser headers to bypass basic anti-bot protection.
    
    Includes:
        - Realistic Accept-Language
        - Referer (makes request look like navigation)
        - Cache-Control
        - Sec-* headers that browsers send
    
    Returns:
        Dictionary of HTTP headers
    """
    base_headers = get_headers()
    
    # Add more realistic browser headers
    enhanced = {
        **base_headers,
        "Accept-Language": "en-US,en;q=0.9,af;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    return enhanced


# =============================================================================
# ROW PARSER
# =============================================================================

def _parse_row(row, base_url: str, source: Dict) -> Optional[Dict]:
    """
    Parse a single tender row/item into a standardized tender dictionary.
    
    Args:
        row: BeautifulSoup element representing a single tender row
        base_url: Base URL of the page (for resolving relative links)
        source: Source configuration dictionary with selectors
        
    Returns:
        Standardized tender dict, or None if invalid/filtered out
    """
    sel = source["selectors"]

    # -------------------------------------------------------------------------
    # Extract title (required)
    # -------------------------------------------------------------------------
    title_el = row.select_one(sel["title"])
    if not title_el:
        return None
        
    title = clean_text(title_el.get_text())
    if not title or len(title) < 8:
        return None

    # -------------------------------------------------------------------------
    # Extract detail page link
    # -------------------------------------------------------------------------
    link_el = row.select_one(sel["link"])
    if link_el and link_el.get("href"):
        detail_url = link_el["href"]
        if not detail_url.startswith("http"):
            detail_url = urljoin(base_url, detail_url)
    else:
        detail_url = base_url

    # -------------------------------------------------------------------------
    # Helper to safely extract text using a selector
    # -------------------------------------------------------------------------
    def _extract(selector: str) -> str:
        if not selector:
            return ""
        el = row.select_one(selector)
        return clean_text(el.get_text()) if el else ""

    # -------------------------------------------------------------------------
    # Extract other fields
    # -------------------------------------------------------------------------
    description  = _extract(sel.get("description", ""))
    closing_date = _extract(sel.get("closing_date", ""))
    issuing_body = _extract(sel.get("issuing_body", ""))

    # -------------------------------------------------------------------------
    # Extract document download link (PDF, DOC, etc.)
    # -------------------------------------------------------------------------
    doc_el = row.select_one(sel.get("doc_link", "")) if sel.get("doc_link") else None
    document_url = doc_el.get("href") if doc_el else None
    if document_url and not document_url.startswith("http"):
        document_url = urljoin(base_url, document_url)

    # -------------------------------------------------------------------------
    # Skip expired tenders
    # -------------------------------------------------------------------------
    if closing_date and is_closing_date_expired(closing_date):
        logger.debug(f"[BULLETINS] Skipping expired: {title[:50]}")
        return None

    # -------------------------------------------------------------------------
    # Geographic detection
    # -------------------------------------------------------------------------
    # Combine all text fields for better detection accuracy
    full_text = f"{title} {description} {issuing_body}"
    
    province = source.get("province_hint") or detect_province(full_text)
    municipality = detect_municipality(full_text, province)
    town = detect_town(full_text, province)

    # -------------------------------------------------------------------------
    # Extract source site domain
    # -------------------------------------------------------------------------
    parsed = urlparse(source["url"])
    source_site = parsed.netloc.replace("www.", "")

    # -------------------------------------------------------------------------
    # Build result
    # -------------------------------------------------------------------------
    return {
        "title":             title,
        "description":       description or f"Tender from {source['name']}",
        "issuing_body":      issuing_body,
        "province":          province,
        "municipality":      municipality,
        "town":              town,
        "industry_category": detect_industry(full_text),
        "closing_date":      closing_date,
        "posted_date":       "",  # Bulletin sites rarely show posted dates
        "source_url":        detail_url,
        "document_url":      document_url,
        "source_site":       source_site,
        "reference_number":  "",
        "contact_info":      "",
        "content_hash":      make_content_hash(title, detail_url),
    }


# =============================================================================
# PAGE SCRAPER (with retry logic)
# =============================================================================

async def scrape_page(
    client: httpx.AsyncClient, 
    url: str, 
    source: Dict,
    retry_count: int = 3
) -> List[Dict]:
    """
    Fetch and parse a single page, with retry logic for transient failures.
    
    Args:
        client: HTTPX async client
        url: Page URL to scrape
        source: Source configuration dictionary
        retry_count: Number of retry attempts (with exponential backoff)
        
    Returns:
        List of standardized tender dictionaries from this page
    """
    results = []
    
    for attempt in range(retry_count):
        try:
            # Use enhanced headers for anti-bot sites
            headers = get_enhanced_headers()
            headers["Referer"] = url  # Make request look like navigation
            
            response = await client.get(url, headers=headers)
            
            # Check for blocking
            if response.status_code == 403:
                logger.warning(f"{source['name']} returned 403 Forbidden (attempt {attempt + 1}/{retry_count})")
                if attempt < retry_count - 1:
                    # Exponential backoff with jitter
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"{source['name']} blocked after {retry_count} attempts")
                    return results
                    
            if response.status_code != 200:
                logger.warning(f"{source['name']} returned {response.status_code} for {url}")
                return results
                
            # Parse successful response
            soup = BeautifulSoup(response.text, "lxml")
            rows = soup.select(source["selectors"]["row"])
            
            if not rows:
                logger.debug(f"[BULLETINS] No rows found with selector: {source['selectors']['row']}")
                # Fallback: try to find any links that look like tenders
                rows = soup.select("a[href*='tender'], a[href*='bid'], a[href*='rfq']")
                
            for row in rows:
                try:
                    parsed = _parse_row(row, url, source)
                    if parsed:
                        results.append(parsed)
                except Exception as e:
                    logger.debug(f"{source['name']} row parse error: {e}")
                    
            # Success — break retry loop
            break
            
        except httpx.TimeoutException:
            logger.warning(f"{source['name']} timeout (attempt {attempt + 1}/{retry_count})")
            if attempt < retry_count - 1:
                await asyncio.sleep(2 ** attempt)
                continue
        except Exception as e:
            logger.error(f"{source['name']} page scrape failed [{url}]: {e}")
            break
            
    return results


# =============================================================================
# SOURCE SCRAPER (with pagination)
# =============================================================================

async def scrape_source(
    client: httpx.AsyncClient, 
    source: Dict, 
    max_pages: int = 3
) -> List[Dict]:
    """
    Scrape a single bulletin source with pagination support.
    
    Follows "next" links up to max_pages.
    
    Args:
        client: HTTPX async client
        source: Source configuration dictionary
        max_pages: Maximum number of pages to scrape (safety limit)
        
    Returns:
        List of standardized tender dictionaries from this source
    """
    all_results = []
    current_url = source["url"]
    pages_scraped = 0
    
    while pages_scraped < max_pages:
        logger.debug(f"[BULLETINS] Page {pages_scraped + 1}: {current_url}")
        
        # Scrape current page
        page_results = await scrape_page(client, current_url, source)
        all_results.extend(page_results)
        pages_scraped += 1
        
        if not page_results:
            logger.debug(f"[BULLETINS] No results on page {pages_scraped} — stopping")
            break
        
        # ---------------------------------------------------------------------
        # Find next page link
        # ---------------------------------------------------------------------
        try:
            response = await client.get(current_url, headers=get_enhanced_headers())
            if response.status_code != 200:
                break
                
            soup = BeautifulSoup(response.text, "lxml")
            
            # Try multiple next-link selectors
            next_link = soup.select_one(
                'a.next, a[rel="next"], .pagination .next a, '
                '.nav-links .next, .pagination li:last-child a, '
                'a:contains("Next"), a:contains("→")'
            )
            
            if next_link and next_link.get("href"):
                next_href = next_link["href"]
                # Skip if it's just "#" or javascript:
                if next_href.startswith("#") or next_href.startswith("javascript:"):
                    break
                    
                current_url = urljoin(current_url, next_href)
                await asyncio.sleep(1.5)  # Be polite — rate limiting
            else:
                logger.debug(f"[BULLETINS] No next page found")
                break
                
        except Exception as e:
            logger.debug(f"[BULLETINS] Pagination error: {e}")
            break
    
    logger.info(f"{source['name']}: {len(all_results)} tenders ({pages_scraped} pages)")
    return all_results


# =============================================================================
# PLAYWRIGHT FALLBACK (for sites with strong anti-bot protection)
# =============================================================================

async def scrape_source_with_playwright(source: Dict) -> List[Dict]:
    """
    Fallback scraper using Playwright for sites that block httpx requests.
    
    Use this when a site returns 403 Forbidden despite enhanced headers.
    
    Args:
        source: Source configuration dictionary
        
    Returns:
        List of standardized tender dictionaries
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[BULLETINS] playwright not installed")
        return []
        
    results = []
    
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--ignore-certificate-errors", "--no-sandbox"]
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,
                viewport={"width": 1440, "height": 900},
            )
            page = await context.new_page()
            
            logger.info(f"[BULLETINS] Loading with Playwright: {source['url']}")
            await page.goto(source["url"], wait_until="networkidle", timeout=45000)
            await page.wait_for_timeout(2000)
            
            html = await page.content()
            await browser.close()
            
            # Parse using the same logic
            soup = BeautifulSoup(html, "lxml")
            rows = soup.select(source["selectors"]["row"])
            
            for row in rows:
                try:
                    parsed = _parse_row(row, source["url"], source)
                    if parsed:
                        results.append(parsed)
                except Exception as e:
                    logger.debug(f"Row parse error: {e}")
                    
            logger.info(f"[BULLETINS] {source['name']} (Playwright): {len(results)} tenders")
            
    except Exception as e:
        logger.error(f"[BULLETINS] Playwright failed for {source['name']}: {e}")
        
    return results


# =============================================================================
# DETAIL PAGE SCRAPER
# =============================================================================

async def scrape_detail(client: httpx.AsyncClient, url: str, source: Dict) -> List[Dict]:
    """
    Scrape a single detail/listing URL for additional information.
    
    Args:
        client: HTTPX async client
        url: Detail page URL to scrape
        source: Source configuration (for selectors)
        
    Returns:
        List containing single tender dict, or empty list on failure
    """
    return await scrape_page(client, url, source)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

async def scrape() -> List[Dict]:
    """
    Main entry point — scrapes all configured bulletin sources.
    
    Attempts static scraping first. If a site returns 403 Forbidden,
    it falls back to Playwright for that specific source.
    
    Returns:
        Combined list of all tenders from all bulletin sources
    """
    all_results = []
    
    async with httpx.AsyncClient(
        timeout=30,                     # Generous timeout
        headers=get_enhanced_headers(), # Enhanced headers for anti-bot sites
        follow_redirects=True,          # Handle 301/302
        verify=False,                   # Skip SSL verification
    ) as client:
        for source in SOURCES:
            try:
                logger.info(f"[BULLETINS] Starting: {source['name']}")
                
                # Try static scraping first
                results = await scrape_source(client, source)
                
                # If no results and site might have anti-bot protection, try Playwright
                if not results:
                    logger.warning(f"[BULLETINS] No results for {source['name']} — trying Playwright fallback")
                    results = await scrape_source_with_playwright(source)
                
                all_results.extend(results)
                logger.info(f"[BULLETINS] Completed: {source['name']} — {len(results)} tenders")
                
            except Exception as e:
                logger.error(f"[BULLETINS] {source['name']} failed: {e}", exc_info=True)
                
    logger.info(f"[BULLETINS] TOTAL: {len(all_results)} tenders from all bulletins")
    return all_results


# =============================================================================
# DEBUGGING HELPER
# =============================================================================

async def debug_bulletin_source(source_name: str) -> None:
    """
    Debug helper — test a bulletin source and show what's being blocked.
    
    Usage:
        await debug_bulletin_source("tenderbulletins.co.za")
    """
    source = next((s for s in SOURCES if s["name"] == source_name), None)
    if not source:
        print(f"Source '{source_name}' not found")
        return
        
    print(f"\n=== DEBUG: {source['name']} ===\n")
    
    async with httpx.AsyncClient(timeout=20, verify=False) as client:
        # Test with default headers
        print("Testing with default headers...")
        resp1 = await client.get(source["url"], headers=get_headers())
        print(f"  Status: {resp1.status_code}")
        
        # Test with enhanced headers
        print("\nTesting with enhanced headers...")
        headers = get_enhanced_headers()
        headers["Referer"] = source["url"]
        resp2 = await client.get(source["url"], headers=headers)
        print(f"  Status: {resp2.status_code}")
        
        if resp2.status_code == 200:
            soup = BeautifulSoup(resp2.text, "lxml")
            rows = soup.select(source["selectors"]["row"])
            print(f"\n  Rows found: {len(rows)}")
            
            # Show first few rows
            for i, row in enumerate(rows[:3]):
                text = clean_text(row.get_text())[:100]
                print(f"  Row {i+1}: {text}...")
        else:
            print(f"\n  Response body preview: {resp2.text[:500]}")