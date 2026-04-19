"""
scraper/sites/etenders.py
--------------------------
Scraper for https://www.etenders.gov.za/Home/opportunities?id=1

Uses async_playwright (not sync_playwright) to work inside FastAPI's event loop on Windows.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from scraper.utils import (
    make_content_hash, detect_industry, detect_province,
    detect_municipality, detect_town, clean_text,
)

logger = logging.getLogger(__name__)

ETENDERS_URL  = "https://www.etenders.gov.za/Home/opportunities?id=1"
ETENDERS_BASE = "https://www.etenders.gov.za"
SOURCE_SITE   = "etenders.gov.za"
MAX_PAGES     = 20
ROWS_PER_PAGE = 100

_MODAL_JS = """
() => {
    document.querySelectorAll('.modal').forEach(m => {
        m.classList.remove('show');
        m.style.display = 'none';
        m.setAttribute('aria-hidden', 'true');
        m.removeAttribute('aria-modal');
    });
    document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
    document.body.classList.remove('modal-open');
    document.body.style.overflow = '';
    document.body.style.paddingRight = '';
    if (window.jQuery) { try { jQuery.fn.modal = function() { return this; }; } catch(e) {} }
    if (window.bootstrap && window.bootstrap.Modal) {
        window.bootstrap.Modal.prototype.show = function() {};
    }
}
"""


def _parse_date(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    m = re.search(
        r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+(\d{4})', text, re.IGNORECASE
    )
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y").strftime("%d/%m/%Y")
        except Exception:
            pass
    m2 = re.search(r'(\d{2}/\d{2}/\d{4})', text)
    if m2:
        return m2.group(1)
    m3 = re.search(r'in\s+(\d+)\s+day', text.lower())
    if m3:
        return (datetime.today() + timedelta(days=int(m3.group(1)))).strftime("%d/%m/%Y")
    if "today" in text.lower():
        return datetime.today().strftime("%d/%m/%Y")
    return text


def _parse_detail(html: str) -> Dict:
    soup = BeautifulSoup(html, "lxml")
    data: Dict = {}
    for row in soup.select("tr"):
        cells = row.select("td")
        if len(cells) < 2:
            continue
        label = clean_text(cells[0].get_text()).rstrip(":").lower()
        value = clean_text(cells[1].get_text())
        if not value:
            continue
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
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if any(x in href.lower() for x in [".pdf", "getfile", "download", "document", "attachment"]):
            doc_url = href if href.startswith("http") else urljoin(ETENDERS_BASE, href)
            data.setdefault("document_url", doc_url)
    return data


def _build_tender(title: str, category: str, detail: Dict, closing_fallback: str) -> Optional[Dict]:
    title = clean_text(title)
    if not title or len(title) < 8:
        return None
    if re.match(r'^\d{2}/\d{2}/\d{4}$', title.strip()):
        return None

    organ    = detail.get("organ_of_state", "")
    prov_raw = detail.get("province", "")
    location = detail.get("location", "")
    closing  = detail.get("closing_date") or closing_fallback

    province     = prov_raw if prov_raw else detect_province(f"{title} {organ} {location}")
    municipality = detect_municipality(f"{organ} {location} {title}", province)
    town         = detect_town(f"{organ} {location} {title}", province)
    contact_info = " | ".join(filter(None, [
        detail.get("contact_person"), detail.get("email"), detail.get("phone")
    ]))

    return {
        "title":             title,
        "description":       f"Tender Type: {detail.get('tender_type','')}. Organ: {organ}. Location: {location}.".strip(),
        "issuing_body":      organ or "National Government (eTenders)",
        "province":          province,
        "municipality":      municipality,
        "town":              town,
        "industry_category": detect_industry(f"{title} {category} {organ}"),
        "closing_date":      closing,
        "posted_date":       detail.get("posted_date", ""),
        "source_url":        ETENDERS_URL,
        "document_url":      detail.get("document_url"),
        "source_site":       SOURCE_SITE,
        "reference_number":  detail.get("tender_number", ""),
        "contact_info":      contact_info,
        "content_hash":      make_content_hash(title, detail.get("tender_number") or title),
    }


def _detect_cols(soup: BeautifulSoup) -> Dict[str, int]:
    for tbl in soup.select("table"):
        for row in tbl.select("tr")[:5]:
            cells = row.select("th, td")
            texts = [c.get_text().strip().lower() for c in cells]
            if any("description" in t for t in texts):
                col = {}
                for i, t in enumerate(texts):
                    if len(t) < 2:
                        continue
                    if "category" in t:
                        col.setdefault("category", i)
                    if "description" in t:
                        col.setdefault("description", i)
                    if "advertised" in t:
                        col.setdefault("advertised", i)
                    if "closing" in t:
                        col.setdefault("closing", i)
                if "description" in col:
                    logger.info(f"[ETENDERS] Columns: {col}")
                    return col
    return {}


async def scrape_etenders() -> List[Dict]:
    """Async Playwright scraper — works inside FastAPI's event loop."""
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.error("[ETENDERS] Playwright not installed")
        return []

    results: List[Dict] = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--ignore-certificate-errors", "--disable-web-security",
                      "--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                ignore_https_errors=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900},
            )
            page = await context.new_page()

            logger.info(f"[ETENDERS] Loading {ETENDERS_URL}")
            await page.goto(ETENDERS_URL, wait_until="networkidle", timeout=90000)
            await page.wait_for_timeout(2000)

            # Kill modal permanently
            await page.evaluate(_MODAL_JS)
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
            logger.info("[ETENDERS] Modal dismissed")

            # Try set page size to 100
            try:
                sel_el = await page.query_selector("select[name$='_length']")
                if sel_el:
                    await sel_el.select_option(value="100")
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    await page.evaluate(_MODAL_JS)
            except Exception:
                pass

            # Detect columns
            soup0 = BeautifulSoup(await page.content(), "lxml")
            col = _detect_cols(soup0)
            if "description" not in col:
                logger.error("[ETENDERS] Cannot find description column")
                await browser.close()
                return []

            seen: set = set()
            page_num = 0

            while page_num < MAX_PAGES:
                page_num += 1
                await page.evaluate(_MODAL_JS)

                all_rows = await page.query_selector_all("table tbody tr")
                # Skip header rows
                data_start = 0
                for i, row_el in enumerate(all_rows[:5]):
                    txt = (await row_el.inner_text() or "").lower()
                    if "tender description" in txt or ("category" in txt and "closing" in txt):
                        data_start = i + 1
                        break

                data_rows = all_rows[data_start:]
                logger.info(f"[ETENDERS] Page {page_num}: {len(data_rows)} data rows")

                if not data_rows:
                    break

                processed = 0
                for row_el in data_rows[:ROWS_PER_PAGE]:
                    try:
                        row_html  = await row_el.inner_html()
                        row_soup  = BeautifulSoup(f"<tr>{row_html}</tr>", "lxml")
                        cells     = row_soup.select("td")

                        def c(idx: int) -> str:
                            return clean_text(cells[idx].get_text()) if idx < len(cells) else ""

                        title        = c(col.get("description", 2))
                        category     = c(col.get("category", 1))
                        closing_raw  = c(col.get("closing", 5))
                        closing_fb   = _parse_date(closing_raw)

                        if not title or len(title) < 8:
                            continue
                        if re.match(r'^\d{2}/\d{2}/\d{4}$', title.strip()):
                            continue
                        if title.lower() in seen:
                            continue

                        # Expand row
                        first_td = await row_el.query_selector("td:first-child")
                        if first_td:
                            await first_td.click()
                            await page.wait_for_timeout(600)

                        # Parse detail panel
                        updated = BeautifulSoup(await page.content(), "lxml")
                        detail_html = ""
                        for el in updated.select("tr, div"):
                            if "organ of state" in el.get_text().lower():
                                detail_html = str(el)
                                break

                        detail = _parse_detail(detail_html) if detail_html else {}
                        if not detail.get("closing_date"):
                            detail["closing_date"] = closing_fb

                        tender = _build_tender(title, category, detail, closing_fb)
                        if tender:
                            seen.add(title.lower())
                            results.append(tender)
                            processed += 1

                        # Collapse
                        if first_td:
                            try:
                                await first_td.click()
                                await page.wait_for_timeout(300)
                            except Exception:
                                pass

                    except Exception as e:
                        logger.debug(f"[ETENDERS] Row error: {e}")

                logger.info(f"[ETENDERS] Page {page_num}: {processed} tenders (total {len(results)})")

                # Next page
                await page.evaluate(_MODAL_JS)
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

            await browser.close()

    except Exception as e:
        logger.exception(f"[ETENDERS] Scrape failed: {e}")

    logger.info(f"[ETENDERS] Final: {len(results)} tenders")
    return results


async def scrape() -> List[Dict]:
    return await scrape_etenders()