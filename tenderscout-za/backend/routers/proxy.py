"""
routers/proxy.py

Authenticated proxy for fetching tender PDFs from allowed SA government domains.

Security model:
  - JWT required — prevents use as an open proxy
  - Domain allowlist checked before any outbound request
  - Redirect chain validated — each hop must stay within allowed domains
  - SSL verification enabled by default; per-domain override for known broken certs
  - Filename sanitised before Content-Disposition header
  - True streaming — document bytes never fully loaded into server RAM
"""

import logging
import re
import urllib.parse
from typing import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

import auth_utils, models

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Domain allowlist
# ---------------------------------------------------------------------------

ALLOWED_DOMAINS: frozenset[str] = frozenset([
    "ekurhuleni.gov.za", "buffalocity.gov.za", "nelsonmandelabay.gov.za",
    "durban.gov.za", "capetown.gov.za", "joburg.org.za", "tshwane.gov.za",
    "mangaung.co.za", "ncgov.co.za", "northern-cape.gov.za",
    "solplaatje.org.za", "dikgatlong.gov.za", "magareng.gov.za",
    "phokwane.gov.za", "francesbaarddc.gov.za", "dawidkruiper.gov.za",
    "kaigarib.gov.za", "kharahais.gov.za", "kheis.gov.za",
    "tsantsabane.gov.za", "zfmgcawudc.gov.za", "richtersveld.gov.za",
    "namakhoi.gov.za", "kamiesberg.gov.za", "hantam.gov.za",
    "karoohoogland.gov.za", "khai-ma.gov.za", "namakwadc.gov.za",
    "siyathemba.gov.za", "ubuntu.gov.za", "umsobomvu.gov.za",
    "emthanjeni.gov.za", "kareeberg.gov.za", "renosterberg.gov.za",
    "thembelihle.gov.za", "siyancuma.gov.za", "pixleydc.gov.za",
    "joemorolog.gov.za", "gamagara.gov.za", "ga-segonyana.gov.za",
    "johntaologaetsewedc.gov.za", "sa-tenders.co.za", "etenders.gov.za",
    "easytenders.co.za", "municipalities.co.za",
])

# Domains with known broken/expired SSL certs — exempt from verification
SSL_EXEMPT_DOMAINS: frozenset[str] = frozenset(["etenders.gov.za"])

_SAFE_FILENAME_RE = re.compile(r"[^\w\s\-.]")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _host(url: str) -> str | None:
    try:
        p = urllib.parse.urlparse(url)
        return p.netloc.lower().replace("www.", "") if p.scheme in ("http", "https") else None
    except Exception:
        return None


def _is_allowed(url: str) -> bool:
    h = _host(url)
    return bool(h and any(h == d or h.endswith(f".{d}") for d in ALLOWED_DOMAINS))


def _ssl_verify(url: str) -> bool:
    h = _host(url)
    return not (h and any(h == d or h.endswith(f".{d}") for d in SSL_EXEMPT_DOMAINS))


def _sanitise_filename(raw: str) -> str:
    name = raw.replace("..", "").replace("/", "").replace("\\", "").strip()
    name = _SAFE_FILENAME_RE.sub("", name).strip()[:120]
    return name or "tender-document.pdf"


def _extract_filename(url: str, disposition: str) -> str:
    if "filename=" in disposition:
        raw = disposition.split("filename=")[-1].strip().strip("\"'").split(";")[0].strip()
        if raw:
            return _sanitise_filename(raw)
    path = urllib.parse.unquote(url.split("?")[0].split("/")[-1])
    return _sanitise_filename(path) if "." in path else "tender-document.pdf"


async def _validate_redirect(request: httpx.Request) -> None:
    """httpx event hook — blocks redirects to non-allowed domains."""
    if not _is_allowed(str(request.url)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Redirect to disallowed domain: {request.url.host}",
        )

# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/proxy/pdf")
async def proxy_pdf(
    url:          str,
    http_request: Request,
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Stream a PDF or document from an allowed SA government domain.

    Previously made two HTTP calls (HEAD for metadata + GET for content).
    Now uses a single streaming GET — metadata is read from the response
    headers before the body is consumed, eliminating the extra round-trip.
    """
    if not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url is required")
    if not _is_allowed(url):
        logger.warning(f"[PROXY] Blocked: {url} user={current_user.id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Domain not allowed")

    logger.info(f"[PROXY] user={current_user.id} → {url}")

    _headers = {
        "User-Agent":      "Mozilla/5.0 (compatible; TenderScoutBot/1.0)",
        "Accept":          "application/pdf,application/octet-stream,*/*",
        "Accept-Encoding": "identity",  # keep Content-Length accurate
    }

    try:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0),
            follow_redirects=True,
            verify=_ssl_verify(url),
            headers=_headers,
            event_hooks={"request": [_validate_redirect]},
        )

        # Single streaming request — read headers from the response before
        # yielding the body, so we can set Content-Disposition correctly
        # without a separate HEAD round-trip.
        response = await client.send(
            client.build_request("GET", url),
            stream=True,
        )

        if response.status_code != 200:
            await response.aclose()
            await client.aclose()
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Remote returned {response.status_code}",
            )

        content_type = response.headers.get("content-type", "application/octet-stream")
        if "text/html" in content_type:
            await response.aclose()
            await client.aclose()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="URL returned HTML, not a document",
            )

        disposition    = response.headers.get("content-disposition", "")
        content_length = response.headers.get("content-length")
        filename       = _extract_filename(str(response.url), disposition)

        resp_headers = {"Content-Disposition": f'attachment; filename="{filename}"',
                        "Cache-Control": "private, max-age=3600"}
        if content_length:
            resp_headers["Content-Length"] = content_length

        async def _stream() -> AsyncIterator[bytes]:
            try:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        return StreamingResponse(_stream(), media_type=content_type, headers=resp_headers)

    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.warning(f"[PROXY] Timeout: {url}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Request timed out")
    except httpx.TooManyRedirects:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Too many redirects")
    except Exception as e:
        logger.error(f"[PROXY] Error fetching {url}: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch document")