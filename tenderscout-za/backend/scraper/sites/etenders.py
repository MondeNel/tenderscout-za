"""
scraper/sites/etenders.py — eTenders Portal National Scraper
==============================================================
Scrapes the official South African government tender portal:
https://www.etenders.gov.za

This is a JavaScript-heavy site that requires Playwright for rendering.
The scraper:
    1. Navigates to the opportunities page
    2. Dismisses Bootstrap modals that block interaction
    3. Detects table column positions dynamically
    4. Clicks each row to expand detail panels
    5. Extracts full tender information
    6. Paginates through up to 20 pages

Architecture:
    - _MODAL_JS: JavaScript injection to disable modal overlays
    - _parse_date(): Converts various date formats to DD/MM/YYYY
    - _parse_detail(): Extracts fields from the expanded detail panel
    - _get_col_map(): Discovers table column indices
    - _build_tender(): Constructs standardized tender dict
    - scrape_etenders(): Main async entry point
"""
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from scraper.utils import (
    make_content_hash,      # Creates unique hash for deduplication
    detect_industry,        # Classifies tender by industry category
    detect_province,        # Extracts province from text
    detect_municipality,    # Extracts municipality name
    detect_town,            # Extracts town/city name
    clean_text,             # Normalizes whitespace and removes junk
)

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS
# =============================================================================

# Main opportunities listing page (id=1 shows all open tenders)
ETENDERS_URL  = "https://www.etenders.gov.za/Home/opportunities?id=1"
ETENDERS_BASE = "https://www.etenders.gov.za"
SOURCE_SITE   = "etenders.gov.za"
MAX_PAGES     = 20  # Safety limit to prevent infinite loops

# =============================================================================
# JAVASCRIPT INJECTION FOR MODAL DISMISSAL
# =============================================================================
# eTenders uses Bootstrap modals that overlay the page and block clicks.
# This script:
#   1. Removes all modal elements from the DOM
#   2. Removes modal backdrop overlays
#   3. Restores body scrolling
#   4. Disables Bootstrap/jQuery modal functions to prevent re-creation
# =============================================================================

_MODAL_JS = """
() => {
    // Remove all visible modals
    document.querySelectorAll('.modal').forEach(m => {
        m.classList.remove('show');
        m.style.display = 'none';
        m.setAttribute('aria-hidden', 'true');
        m.removeAttribute('aria-modal');
    });
    
    // Remove modal backdrop overlays (the gray semi-transparent layer)
    document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
    
    // Restore body scrolling
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    
    // Override jQuery modal function if jQuery exists
    if (window.jQuery) { 
        try { 
            jQuery.fn.modal = function() { return this; }; 
        } catch(e) {} 
    }
    
    // Override Bootstrap 5 modal show method
    if (window.bootstrap && window.bootstrap.Modal) {
        window.bootstrap.Modal.prototype.show = function() {};
    }
}
"""


# =============================================================================
# DATE PARSING HELPER
# =============================================================================

def _parse_date(text: str) -> str:
    """
    Convert various date formats found on eTenders to standard DD/MM/YYYY.
    
    Handles:
        - "15 January 2026" → "15/01/2026"
        - "15/01/2026" → "15/01/2026"
        - "in 7 days" → calculates future date
        - "today" → current date
    
    Args:
        text: Raw date string from the page
        
    Returns:
        Standardized date string in DD/MM/YYYY format, or original text if unparseable
    """
    if not text:
        return ""
        
    text = text.strip()
    
    # -------------------------------------------------------------------------
    # Pattern 1: "15 January 2026" (day month year)
    # -------------------------------------------------------------------------
    m = re.search(
        r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+(\d{4})', 
        text, 
        re.IGNORECASE
    )
    if m:
        try:
            return datetime.strptime(
                f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y"
            ).strftime("%d/%m/%Y")
        except Exception:
            pass
    
    # -------------------------------------------------------------------------
    # Pattern 2: "15/01/2026" (already in correct format)
    # -------------------------------------------------------------------------
    m2 = re.search(r'(\d{2}/\d{2}/\d{4})', text)
    if m2:
        return m2.group(1)
    
    # -------------------------------------------------------------------------
    # Pattern 3: "in 7 days" (relative date)
    # -------------------------------------------------------------------------
    m3 = re.search(r'in\s+(\d+)\s+day', text.lower())
    if m3:
        return (datetime.today() + timedelta(days=int(m3.group(1)))).strftime("%d/%m/%Y")
    
    # -------------------------------------------------------------------------
    # Pattern 4: "today"
    # -------------------------------------------------------------------------
    if "today" in text.lower():
        return datetime.today().strftime("%d/%m/%Y")
    
    # Return original if no patterns match
    return text


# =============================================================================
# DETAIL PANEL PARSER
# =============================================================================

def _parse_detail(html: str) -> Dict:
    """
    Parse the expanded detail panel HTML to extract tender metadata.
    
    The detail panel is a table with label/value pairs like:
        Tender Number: ABC123/2026
        Organ of State: Department of Public Works
        Province: Gauteng
        Closing Date: 15 January 2026
    
    Also extracts document download links (PDF attachments).
    
    Args:
        html: HTML string of the detail panel section
        
    Returns:
        Dictionary with extracted fields (tender_number, organ_of_state, etc.)
    """
    soup = BeautifulSoup(html, "lxml")
    data: Dict = {}
    
    # -------------------------------------------------------------------------
    # Extract label/value pairs from table rows
    # -------------------------------------------------------------------------
    for row in soup.select("tr"):
        cells = row.select("td")
        if len(cells) < 2:
            continue
            
        label = clean_text(cells[0].get_text()).rstrip(":").lower()
        value = clean_text(cells[1].get_text())
        
        if not value:
            continue
            
        # Map common label variations to standardized field names
        if "tender number" in label or "bid number" in label:
            data["tender_number"] = value
        elif "organ of state" in label or "institution" in label:
            data["organ_of_state"] = value
        elif "tender type" in label:
            data["tender_type"] = value
        elif label.strip() == "province":
            data["province"] = value
        elif "closing date" in label:
            data["closing_date"] = _parse_date(value)
        elif "date published" in label or "advertised" in label:
            data["posted_date"] = _parse_date(value)
        elif "contact person" in label:
            data["contact_person"] = value
        elif "email" in label:
            data["email"] = value
        elif "telephone" in label or "phone" in label:
            data["phone"] = value
        elif "place where" in label or "venue" in label:
            data["location"] = value
        elif "description" in label or "scope of work" in label:
            data["description"] = value
        elif "category" in label:
            data["category"] = value
    
    # -------------------------------------------------------------------------
    # Extract document download links (PDF attachments)
    # -------------------------------------------------------------------------
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        # Look for PDF links or download/document endpoints
        if any(x in href.lower() for x in [".pdf", "getfile", "download", "document", "attachment"]):
            doc_url = href if href.startswith("http") else urljoin(ETENDERS_BASE, href)
            data.setdefault("document_url", doc_url)
            
    return data


# =============================================================================
# COLUMN MAPPING DETECTOR
# =============================================================================

def _get_col_map(page_html: str) -> Dict[str, int]:
    """
    Dynamically discover the column indices for the tender table.
    
    The eTenders table structure can change, so we scan the header row
    to find which column contains what data.
    
    Expected columns:
        - Category
        - Tender Description (title)
        - Advertised (posted date)
        - Closing (closing date)
    
    Args:
        page_html: Full HTML of the current page
        
    Returns:
        Dictionary mapping field names to column indices, e.g.:
        {"category": 1, "description": 2, "advertised": 4, "closing": 5}
    """
    soup = BeautifulSoup(page_html, "lxml")
    col: Dict[str, int] = {}
    
    # Scan the first few rows of each table for a header row
    for tbl in soup.select("table"):
        for row in tbl.select("tr")[:6]:
            cells = row.select("th, td")
            texts = [c.get_text().strip().lower() for c in cells]
            
            logger.debug(f"[ETENDERS] Row texts: {texts[:8]}")
            
            # Check if this row contains header labels
            if any("description" in t or "tender description" in t for t in texts):
                for i, t in enumerate(texts):
                    if len(t) < 2:
                        continue
                    if "category" in t and "category" not in col:
                        col["category"] = i
                    if "description" in t and "description" not in col:
                        col["description"] = i
                    if "advertised" in t and "advertised" not in col:
                        col["advertised"] = i
                    if "closing" in t and "closing" not in col:
                        col["closing"] = i
                        
                if "description" in col:
                    logger.info(f"[ETENDERS] Column map: {col}")
                    return col
                    
    return col


# =============================================================================
# TENDER BUILDER
# =============================================================================

def _build_tender(
    title: str, 
    category: str, 
    detail: Dict, 
    closing_fallback: str
) -> Optional[Dict]:
    """
    Construct a standardized tender dictionary from extracted data.
    
    Args:
        title: Tender title from the main table row
        category: Category from the main table row
        detail: Dictionary of fields extracted from the detail panel
        closing_fallback: Closing date from the table row (used if detail missing)
        
    Returns:
        Standardized tender dict, or None if invalid/filtered out
    """
    # -------------------------------------------------------------------------
    # Validate title
    # -------------------------------------------------------------------------
    title = clean_text(title)
    if not title or len(title) < 8:
        return None
        
    # Skip rows that are just dates (common false positive)
    if re.match(r'^\d{2}/\d{2}/\d{4}$', title.strip()):
        return None

    # -------------------------------------------------------------------------
    # Extract and combine fields for geographic detection
    # -------------------------------------------------------------------------
    organ    = detail.get("organ_of_state", "")
    prov_raw = detail.get("province", "")
    location = detail.get("location", "")
    closing  = detail.get("closing_date") or closing_fallback
    
    # Build detection text for province/municipality/town
    detection_text = f"{title} {organ} {location} {detail.get('description', '')}"

    # -------------------------------------------------------------------------
    # Geographic detection
    # -------------------------------------------------------------------------
    # Province: Use explicit province from detail if available, else detect
    province = prov_raw if prov_raw else detect_province(detection_text)
    
    # Municipality: Detect from organ name and location
    municipality = detect_municipality(f"{organ} {location} {title}", province)
    
    # Town: Detect from location field or full text
    town = detect_town(f"{organ} {location} {title}", province)

    # -------------------------------------------------------------------------
    # Build contact info string
    # -------------------------------------------------------------------------
    contact_info = " | ".join(filter(None, [
        detail.get("contact_person"),
        detail.get("email"),
        detail.get("phone"),
    ]))

    # -------------------------------------------------------------------------
    # Build description (combine category, organ, and detail description)
    # -------------------------------------------------------------------------
    description_parts = []
    if category:
        description_parts.append(f"Category: {category}")
    if organ:
        description_parts.append(f"Organ: {organ}")
    if location:
        description_parts.append(f"Location: {location}")
    if detail.get("description"):
        description_parts.append(detail["description"])
    if detail.get("tender_type"):
        description_parts.append(f"Type: {detail['tender_type']}")
        
    description = ". ".join(description_parts).strip()

    # -------------------------------------------------------------------------
    # Industry detection
    # -------------------------------------------------------------------------
    industry_text = f"{title} {category} {organ} {detail.get('description', '')}"
    industry_category = detect_industry(industry_text)

    # -------------------------------------------------------------------------
    # Build final tender dictionary
    # -------------------------------------------------------------------------
    return {
        "title":             title,
        "description":       description,
        "issuing_body":      organ or "National Government (eTenders)",
        "province":          province,
        "municipality":      municipality,
        "town":              town,
        "industry_category": industry_category,
        "closing_date":      closing,
        "posted_date":       detail.get("posted_date", ""),
        "source_url":        ETENDERS_URL,
        "document_url":      detail.get("document_url"),
        "source_site":       SOURCE_SITE,
        "reference_number":  detail.get("tender_number", ""),
        "contact_info":      contact_info,
        "content_hash":      make_content_hash(title, detail.get("tender_number") or title),
    }


# =============================================================================
# MAIN ASYNC SCRAPER
# =============================================================================

async def scrape_etenders() -> List[Dict]:
    """
    Main entry point — scrapes the eTenders portal using Playwright.
    
    Process:
        1. Launch headless Chromium browser
        2. Navigate to opportunities page
        3. Dismiss modals
        4. Set page size to 100 results per page
        5. For each page:
           a. Detect column positions
           b. For each row:
              - Click to expand detail panel
              - Wait for detail content to load
              - Extract tender data
              - Click to collapse
           c. Navigate to next page
        6. Return all scraped tenders
    
    Returns:
        List of standardized tender dictionaries
    """
    # -------------------------------------------------------------------------
    # Check Playwright installation
    # -------------------------------------------------------------------------
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[ETENDERS] playwright not installed. Run: pip install playwright && playwright install chromium")
        return []

    results: List[Dict] = []

    try:
        async with async_playwright() as pw:
            # -----------------------------------------------------------------
            # Launch browser with security-disabled flags (gov sites often have cert issues)
            # -----------------------------------------------------------------
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--ignore-certificate-errors",
                    "--disable-web-security",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            
            # -----------------------------------------------------------------
            # Create context with realistic viewport and user agent
            # -----------------------------------------------------------------
            context = await browser.new_context(
                ignore_https_errors=True,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1440, "height": 900},
            )
            page = await context.new_page()

            # -----------------------------------------------------------------
            # Navigate to opportunities page
            # -----------------------------------------------------------------
            logger.info(f"[ETENDERS] Loading {ETENDERS_URL}")
            await page.goto(ETENDERS_URL, wait_until="networkidle", timeout=90000)
            
            # Wait for initial JavaScript to settle
            await page.wait_for_timeout(2000)
            
            # Dismiss any modals that appeared on load
            await page.evaluate(_MODAL_JS)

            # -----------------------------------------------------------------
            # Set page size to 100 results (max available) to reduce pagination
            # -----------------------------------------------------------------
            try:
                sel_el = await page.query_selector("select[name$='_length']")
                if sel_el:
                    await sel_el.select_option(value="100")
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    await page.evaluate(_MODAL_JS)
                    logger.info("[ETENDERS] Page size set to 100")
            except Exception as e:
                logger.warning(f"[ETENDERS] Could not set page size: {e}")

            # -----------------------------------------------------------------
            # Detect column positions from current page HTML
            # -----------------------------------------------------------------
            col = _get_col_map(await page.content())
            if "description" not in col:
                logger.error("[ETENDERS] Cannot find description column — aborting")
                await browser.close()
                return []

            seen: set = set()   # Track seen titles to avoid duplicates
            page_num  = 0

            # -----------------------------------------------------------------
            # Main pagination loop
            # -----------------------------------------------------------------
            while page_num < MAX_PAGES:
                page_num += 1
                
                # Dismiss modals before interacting with page
                await page.evaluate(_MODAL_JS)

                # -------------------------------------------------------------
                # Find all table rows
                # -------------------------------------------------------------
                all_rows = await page.query_selector_all("table tbody tr")
                logger.info(f"[ETENDERS] Page {page_num}: {len(all_rows)} total tbody rows")

                # -------------------------------------------------------------
                # Identify header row (skip it when processing data)
                # -------------------------------------------------------------
                header_idx = -1
                for i, row_el in enumerate(all_rows[:6]):
                    txt = (await row_el.inner_text() or "").lower()
                    if "tender description" in txt or ("category" in txt and "closing" in txt):
                        header_idx = i
                        logger.info(f"[ETENDERS] Header row at index {i}")
                        break

                data_start = header_idx + 1 if header_idx >= 0 else 2
                data_rows  = all_rows[data_start:]
                logger.info(f"[ETENDERS] Page {page_num}: {len(data_rows)} data rows (start={data_start})")

                if not data_rows:
                    logger.info("[ETENDERS] No data rows — done")
                    break

                # -------------------------------------------------------------
                # Process each data row
                # -------------------------------------------------------------
                processed = 0
                for row_el in data_rows:
                    try:
                        # -----------------------------------------------------
                        # Extract visible cell data from the row
                        # -----------------------------------------------------
                        row_html = await row_el.inner_html()
                        row_soup = BeautifulSoup(f"<tr>{row_html}</tr>", "lxml")
                        cells    = row_soup.select("td")

                        def c(idx: int) -> str:
                            """Helper to safely get cell text by index."""
                            return clean_text(cells[idx].get_text()) if idx < len(cells) else ""

                        title       = c(col.get("description", 2))
                        category    = c(col.get("category", 1))
                        closing_raw = c(col.get("closing", 5))
                        closing_fb  = _parse_date(closing_raw)

                        # Skip invalid or already-seen titles
                        if not title or len(title) < 8:
                            continue
                        if re.match(r'^\d{2}/\d{2}/\d{4}$', title.strip()):
                            continue
                        if title.lower() in seen:
                            continue

                        # -----------------------------------------------------
                        # Click to expand the detail panel
                        # -----------------------------------------------------
                        first_td = await row_el.query_selector("td:first-child")
                        if first_td:
                            await first_td.click()
                            
                            # Wait for detail content to actually load
                            # This is more reliable than fixed timeout
                            try:
                                await page.wait_for_selector(
                                    "td:has-text('Organ of State'), tr:has-text('Organ of State')",
                                    timeout=3000
                                )
                            except Exception:
                                # Fallback to fixed wait if selector not found
                                await page.wait_for_timeout(1000)

                        # -----------------------------------------------------
                        # Parse the expanded detail panel
                        # -----------------------------------------------------
                        updated_html = await page.content()
                        updated_soup = BeautifulSoup(updated_html, "lxml")
                        
                        # Find the detail panel — look for a row containing "Organ of State"
                        # that is near the expanded row (usually immediately after)
                        detail_html = ""
                        for el in updated_soup.select("tr"):
                            text_lower = el.get_text().lower()
                            if "organ of state" in text_lower:
                                # Found a detail panel — grab its HTML
                                detail_html = str(el)
                                # Also try to include following rows that contain more fields
                                next_el = el.find_next_sibling("tr")
                                if next_el and any(x in next_el.get_text().lower() for x in ["closing", "contact", "email"]):
                                    detail_html += str(next_el)
                                break

                        detail = _parse_detail(detail_html) if detail_html else {}
                        
                        # -----------------------------------------------------
                        # Build and store the tender
                        # -----------------------------------------------------
                        tender = _build_tender(title, category, detail, closing_fb)
                        if tender:
                            seen.add(title.lower())
                            results.append(tender)
                            processed += 1

                        # -----------------------------------------------------
                        # Click to collapse the row (restore table state)
                        # -----------------------------------------------------
                        if first_td:
                            try:
                                await first_td.click()
                                await page.wait_for_timeout(300)
                            except Exception:
                                pass  # Collapse may not be necessary

                    except Exception as e:
                        logger.debug(f"[ETENDERS] Row error: {e}")

                logger.info(f"[ETENDERS] Page {page_num}: {processed} extracted (running total {len(results)})")

                # -------------------------------------------------------------
                # Navigate to next page
                # -------------------------------------------------------------
                await page.evaluate(_MODAL_JS)
                
                # Try multiple possible next button selectors
                next_btn = (
                    await page.query_selector("#DataTables_Table_0_next:not(.disabled)")
                    or await page.query_selector(".dataTables_paginate .next:not(.disabled)")
                    or await page.query_selector("a.paginate_button.next:not(.disabled)")
                    or await page.query_selector("li.next:not(.disabled) a")
                )
                
                if not next_btn:
                    logger.info("[ETENDERS] No next page — done")
                    break
                    
                try:
                    await next_btn.click()
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    await page.wait_for_timeout(800)
                except Exception as e:
                    logger.warning(f"[ETENDERS] Pagination error: {e}")
                    break

            # -----------------------------------------------------------------
            # Cleanup
            # -----------------------------------------------------------------
            await browser.close()

    except Exception as e:
        logger.error(f"[ETENDERS] Failed: {e}", exc_info=True)

    logger.info(f"[ETENDERS] Final: {len(results)} tenders")
    return results


# =============================================================================
# PUBLIC ENTRY POINT
# =============================================================================

async def scrape() -> List[Dict]:
    """
    Public entry point — matches the pattern expected by the scraper orchestrator.
    
    Returns:
        List of standardized tender dictionaries from eTenders portal
    """
    return await scrape_etenders()