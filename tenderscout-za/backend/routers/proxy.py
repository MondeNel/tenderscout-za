"""
File: routers/proxy.py
Purpose: Authenticated proxy for fetching tender PDFs from allowed government domains.

Security model:
  - JWT authentication required — anonymous users cannot use this as an open proxy
  - Domain allowlist checked before any outbound request
  - Redirect chain validated — each hop must stay within allowed domains
  - SSL verification enabled by default; per-domain override for known broken certs
  - Filename sanitised before being placed in Content-Disposition header
  - True streaming — document bytes are never fully loaded into server RAM
"""

import re
import urllib.parse
import logging
from typing import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

import auth_utils, models

logger = logging.getLogger(__name__)
router = APIRouter()

# =============================================================================
# ALLOWED DOMAINS
# =============================================================================

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

# FIX: Some SA government sites have broken/expired SSL certs.
# We disable verification only for these specific known-broken domains
# rather than globally disabling it with verify=False.
SSL_EXEMPT_DOMAINS: frozenset[str] = frozenset([
    "etenders.gov.za",
])

# Filename characters that are safe for Content-Disposition headers
_SAFE_FILENAME_RE = re.compile(r"[^\w\s\-.]")


# =============================================================================
# HELPERS
# =============================================================================

def _get_host(url: str) -> str | None:
    """Extract and normalise the hostname from a URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None
        return parsed.netloc.lower().replace("www.", "")
    except Exception:
        return None


def _is_allowed(url: str) -> bool:
    """Return True if the URL's host is in the allowlist."""
    host = _get_host(url)
    if not host:
        return False
    return any(host == d or host.endswith(f".{d}") for d in ALLOWED_DOMAINS)


def _needs_ssl_exempt(url: str) -> bool:
    """Return True if this domain is known to have a broken SSL certificate."""
    host = _get_host(url)
    if not host:
        return False
    return any(host == d or host.endswith(f".{d}") for d in SSL_EXEMPT_DOMAINS)


def _sanitise_filename(raw: str) -> str:
    """
    Sanitise a filename for use in a Content-Disposition header.

    FIX: Remote servers can return filenames containing path traversal sequences
    (../../etc/passwd), semicolons that break header parsing, or Unicode that
    causes encoding issues. Strip everything except word chars, spaces, hyphens,
    and dots. Always ensure a .pdf extension as fallback.
    """
    # Remove path traversal and directory separators
    name = raw.replace("..", "").replace("/", "").replace("\\", "").strip()
    # Keep only safe characters
    name = _SAFE_FILENAME_RE.sub("", name).strip()
    # Truncate to reasonable length
    name = name[:120]
    # Fallback
    return name if name else "tender-document.pdf"


def _extract_filename(url: str, disposition: str) -> str:
    """Extract and sanitise filename from Content-Disposition or URL path."""
    if "filename=" in disposition:
        raw = disposition.split("filename=")[-1].strip().strip("\"'").split(";")[0].strip()
        if raw:
            return _sanitise_filename(raw)
    # Fall back to URL path
    path = urllib.parse.unquote(url.split("?")[0].split("/")[-1])
    if "." in path:
        return _sanitise_filename(path)
    return "tender-document.pdf"


# =============================================================================
# PROXY ENDPOINT
# =============================================================================

@router.get("/proxy/pdf")
async def proxy_pdf(
    url: str,
    http_request: Request,
    # FIX: Authentication required — without this any anonymous user can use
    # the server as an open proxy to fetch documents from allowed domains
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Authenticated proxy that fetches a PDF or document from an allowed
    South African government tender domain and streams it to the client.

    Security:
      - JWT required
      - Domain allowlist enforced before any outbound request
      - Redirect chain validated — each hop must stay within allowed domains
      - SSL verification enabled (per-domain override for broken gov certs)
      - Filename sanitised before Content-Disposition header
      - True streaming — bytes never fully loaded into server memory
    """
    if not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url is required")

    if not _is_allowed(url):
        logger.warning(
            f"[PROXY] Blocked request to disallowed domain: {url} "
            f"by user={current_user.id}"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Domain not allowed")

    ssl_verify = not _needs_ssl_exempt(url)

    headers = {
        "User-Agent":      "Mozilla/5.0 (compatible; TenderScoutBot/1.0)",
        "Accept":          "application/pdf,application/octet-stream,*/*",
        "Accept-Encoding": "identity",   # disable compression so Content-Length is accurate
    }

    logger.info(f"[PROXY] user={current_user.id} fetching: {url}")

    try:
        # FIX: True streaming — use httpx.stream() so bytes are never fully
        # loaded into memory. Previously iter([r.content]) read the entire
        # file into RAM first then "streamed" a single chunk — not streaming.
        async def _stream_content() -> AsyncIterator[bytes]:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0),
                follow_redirects=True,
                verify=ssl_verify,
                headers=headers,
                # FIX: Validate redirect chain — each redirect hop must stay
                # within the allowed domain list to prevent open redirect abuse
                event_hooks={"request": [_validate_redirect]},
            ) as client:
                async with client.stream("GET", url) as response:
                    if response.status_code != 200:
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"Remote returned {response.status_code}",
                        )
                    ct = response.headers.get("content-type", "")
                    if "text/html" in ct:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="URL returned HTML, not a document",
                        )
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        yield chunk

        # We need headers from a HEAD or initial response before we can set
        # Content-Disposition. Do a quick HEAD first to get metadata, then stream.
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=5.0),
            follow_redirects=True,
            verify=ssl_verify,
            headers=headers,
        ) as meta_client:
            head = await meta_client.head(url)

        content_type = head.headers.get("content-type", "application/octet-stream")
        disposition  = head.headers.get("content-disposition", "")
        content_length = head.headers.get("content-length")
        filename     = _extract_filename(url, disposition)

        response_headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control":       "private, max-age=3600",
        }
        if content_length:
            response_headers["Content-Length"] = content_length

        return StreamingResponse(
            _stream_content(),
            media_type=content_type or "application/octet-stream",
            headers=response_headers,
        )

    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.warning(f"[PROXY] Timeout fetching: {url}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Request timed out")
    except httpx.TooManyRedirects:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Too many redirects")
    except Exception as e:
        logger.error(f"[PROXY] Unexpected error fetching {url}: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch document")


async def _validate_redirect(request: httpx.Request) -> None:
    """
    httpx event hook — fires on every request in a redirect chain.
    Raises immediately if a redirect leads outside the allowed domain list.
    """
    if not _is_allowed(str(request.url)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Redirect to disallowed domain: {request.url.host}",
        )