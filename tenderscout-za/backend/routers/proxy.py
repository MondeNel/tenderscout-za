from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import urllib.parse
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_DOMAINS = [
    "ekurhuleni.gov.za",
    "buffalocity.gov.za",
    "nelsonmandelabay.gov.za",
    "siyathemba.gov.za",
    "northern-cape.gov.za",
    "sa-tenders.co.za",
    "tenderbulletins.co.za",
    "durban.gov.za",
    "capetown.gov.za",
    "joburg.org.za",
    "tshwane.gov.za",
    "mangaung.co.za",
]


def is_allowed(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        return any(host.endswith(d) for d in ALLOWED_DOMAINS)
    except Exception:
        return False


def get_filename(url: str, disposition: str) -> str:
    if "filename=" in disposition:
        name = disposition.split("filename=")[-1].strip().strip('"').strip("'")
        if name:
            return name
    path = urllib.parse.unquote(url.split("?")[0].split("/")[-1])
    if path and "." in path:
        return path
    return "tender-document.pdf"


@router.get("/proxy/pdf")
async def proxy_pdf(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="url parameter required")
    if not is_allowed(url):
        raise HTTPException(status_code=403, detail="Domain not in allowlist")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/pdf,application/octet-stream,*/*",
    }

    try:
        async with httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            verify=True,  # Always verify SSL certificates
            headers=headers,
        ) as client:
            response = await client.get(url)

        content_type = response.headers.get("content-type", "application/pdf")
        disposition = response.headers.get("content-disposition", "")
        filename = get_filename(url, disposition)

        logger.info(
            f"[PROXY] {url} -> {response.status_code} "
            f"| content-type: {content_type} "
            f"| filename: {filename}"
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Remote server returned {response.status_code}",
            )

        if "text/html" in content_type:
            logger.warning(f"[PROXY] Got HTML instead of PDF for {url}")
            raise HTTPException(
                status_code=422, detail="URL points to an HTML page, not a document"
            )

        # Stream the response without loading entire file into memory
        return StreamingResponse(
            response.aiter_bytes(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Cache-Control": "public, max-age=3600",
            },
        )

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception as e:
        logger.error(f"[PROXY] Error fetching {url}: {e}")
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")