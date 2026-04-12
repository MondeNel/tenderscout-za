
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import urllib.parse

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

@router.get("/proxy/pdf")
async def proxy_pdf(url: str):
    """
    Proxies a PDF from a government site through the backend so the
    browser can download it without CORS restrictions.
    """
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
        "Accept": "application/pdf,*/*",
    }

    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            verify=False,
            headers=headers,
        ) as client:
            response = await client.get(url)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Remote returned {response.status_code}"
                )

            content_type = response.headers.get("content-type", "application/pdf")

            # Get filename from URL or Content-Disposition header
            disposition = response.headers.get("content-disposition", "")
            if "filename=" in disposition:
                filename = disposition.split("filename=")[-1].strip().strip('"')
            else:
                filename = urllib.parse.unquote(url.split("/")[-1].split("?")[0])
                if not filename.lower().endswith(".pdf"):
                    filename = filename + ".pdf"

            return StreamingResponse(
                iter([response.content]),
                media_type=content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Length": str(len(response.content)),
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")
