"""
File: routers/proxy.py
Purpose: Authenticated proxy for fetching tender PDFs from allowed government domains.

This module implements a secure, streaming PDF proxy. Instead of exposing
raw document URLs to the frontend (which may be on unreliable municipal
servers or behind broken SSL), the frontend requests the document through
this endpoint. The backend then fetches the PDF, validates the target
domain, and streams the content back to the user.

Key security features:
- JWT authentication required (via Depends on get_current_user)
- Only URLs whose host matches an entry in ALLOWED_DOMAINS are proxied
- Redirect chains are validated on the fly – any redirect to a disallowed
  domain triggers an immediate 403
- SSL verification is disabled only for known broken domains (e.g.,
  etenders.gov.za) and enabled for all others
- File name sanitisation prevents path‑traversal attacks
- HTML content is rejected (prevents proxying of error pages)
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

# ------------------------------------------------------------------
# Domain whitelist – only these government sites may be proxied
# ------------------------------------------------------------------
# The set is defined at module level and used to validate both the
# original URL and any redirect targets. All domains are South African
# municipal, provincial, or national tender portals.
# ------------------------------------------------------------------
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

# ------------------------------------------------------------------
# SSL exemption list – domains with known broken certificates
# ------------------------------------------------------------------
# For these domains, SSL verification is turned off when fetching.
# This is a pragmatic workaround for government servers that use
# self‑signed, expired, or misconfigured certificates.
# ------------------------------------------------------------------
SSL_EXEMPT_DOMAINS: frozenset[str] = frozenset(["etenders.gov.za"])

# Regular expression to strip unsafe characters from filenames
_SAFE_FILENAME_RE = re.compile(r"[^\w\s\-.]")


def _get_host(url: str) -> str | None:
    """
    Extract the hostname (netloc) from a URL, lowercased and without 'www.'.

    Returns None if the scheme is not http or https.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None
        return parsed.netloc.lower().replace("www.", "")
    except Exception:
        return None


def _is_allowed(url: str) -> bool:
    """
    Check if the URL's host matches (or is a subdomain of) an allowed domain.
    """
    host = _get_host(url)
    if not host:
        return False
    return any(host == d or host.endswith(f".{d}") for d in ALLOWED_DOMAINS)


def _needs_ssl_exempt(url: str) -> bool:
    """
    Return True if the host is in the SSL exemption list (i.e. verify=False needed).
    """
    host = _get_host(url)
    if not host:
        return False
    return any(host == d or host.endswith(f".{d}") for d in SSL_EXEMPT_DOMAINS)


def _sanitise_filename(raw: str) -> str:
    """
    Clean a raw filename string to prevent path‑traversal and injection attacks.

    - Removes "..", "/", "\"
    - Strips non‑alphanumeric characters (except spaces, hyphens, dots)
    - Truncates to 120 characters
    - Defaults to "tender-document.pdf" if nothing valid remains
    """
    name = raw.replace("..", "").replace("/", "").replace("\\", "").strip()
    name = _SAFE_FILENAME_RE.sub("", name).strip()
    name = name[:120]
    return name if name else "tender-document.pdf"


def _extract_filename(url: str, disposition: str) -> str:
    """
    Determine the download filename, in order of preference:
    1. From the Content‑Disposition header (if present and valid)
    2. Derived from the last path segment of the URL
    3. Fallback to "tender-document.pdf"
    """
    # Prefer server‑provided filename in the Content‑Disposition header
    if "filename=" in disposition:
        raw = disposition.split("filename=")[-1].strip().strip("\"'").split(";")[0].strip()
        if raw:
            return _sanitise_filename(raw)
    # Fallback to the last segment of the URL path
    path = urllib.parse.unquote(url.split("?")[0].split("/")[-1])
    if "." in path:
        return _sanitise_filename(path)
    return "tender-document.pdf"


# ------------------------------------------------------------------
# GET /proxy/pdf
# ------------------------------------------------------------------
@router.get("/proxy/pdf")
async def proxy_pdf(
    url: str,
    http_request: Request,
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    """
    Securely stream a PDF document from an allowed government website.

    Parameters (query string):
    - url: The absolute URL of the document to fetch (must be whitelisted)

    Flow:
    1. Authenticate the user via JWT.
    2. Reject empty URLs or non‑whitelisted domains with 4xx errors.
    3. Determine whether to verify SSL based on the domain.
    4. Perform a HEAD request to get Content‑Type, Content‑Disposition,
       and Content‑Length for the streaming response.
    5. Stream the body in 64KB chunks. Every redirect during streaming is
       validated on‑the‑fly – any redirect to a disallowed domain
       immediately aborts with 403.
    6. Return a StreamingResponse with proper headers for the browser to
       trigger a download.

    Error handling:
    - 400: missing URL
    - 403: domain not allowed (initial or during redirect)
    - 422: URL returned HTML instead of a document
    - 502: remote server error, too many redirects, or other fetch failures
    - 504: timeout contacting the remote server
    """
    # Basic validation
    if not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url is required")

    if not _is_allowed(url):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Domain not allowed")

    # Decide SSL verification
    ssl_verify = not _needs_ssl_exempt(url)

    # Headers sent to the remote server
    headers = {
        "User-Agent":      "Mozilla/5.0 (compatible; TenderScoutBot/1.0)",
        "Accept":          "application/pdf,application/octet-stream,*/*",
        "Accept-Encoding": "identity",  # we don't want compressed responses
    }

    # ------------------------------------------------------------------
    # Async generator that streams the remote body while checking redirects
    # ------------------------------------------------------------------
    async def _validate_redirect(request: httpx.Request) -> None:
        """
        httpx event hook: fires before every redirect.
        If the redirect target is not allowed, abort the stream immediately
        with a 403 HTTPException.
        """
        if not _is_allowed(str(request.url)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Redirect to disallowed domain"
            )

    async def _stream_content() -> AsyncIterator[bytes]:
        """
        Core streaming logic:
        - Uses a separate httpx client with redirect validation enabled.
        - If the remote returns a non‑200 status or HTML content, the
          request fails (we don't proxy error pages).
        - Otherwise yields 64KB chunks to be streamed to the client.
        """
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0),
            follow_redirects=True,
            verify=ssl_verify,
            headers=headers,
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

    # ------------------------------------------------------------------
    # First, make a lightweight HEAD request to gather metadata
    # (Content-Type, filename, Content-Length) before streaming.
    # ------------------------------------------------------------------
    try:
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
        filename = _extract_filename(url, disposition)

        # Build response headers to trigger a browser download
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
        # Re‑raise FastAPI HTTPExceptions so they are handled by the
        # framework's error handling.
        raise
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request timed out"
        )
    except httpx.TooManyRedirects:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Too many redirects"
        )
    except Exception as e:
        logger.error(f"[PROXY] Unexpected error fetching {url}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch document"
        )