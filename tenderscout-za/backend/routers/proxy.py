from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import httpx, urllib.parse, logging

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_DOMAINS = [
    "ekurhuleni.gov.za","buffalocity.gov.za","nelsonmandelabay.gov.za",
    "durban.gov.za","capetown.gov.za","joburg.org.za","tshwane.gov.za","mangaung.co.za",
    "ncgov.co.za","northern-cape.gov.za","solplaatje.org.za","dikgatlong.gov.za",
    "magareng.gov.za","phokwane.gov.za","francesbaarddc.gov.za","dawidkruiper.gov.za",
    "kaigarib.gov.za","kharahais.gov.za","kheis.gov.za","tsantsabane.gov.za",
    "zfmgcawudc.gov.za","richtersveld.gov.za","namakhoi.gov.za","kamiesberg.gov.za",
    "hantam.gov.za","karoohoogland.gov.za","khai-ma.gov.za","namakwadc.gov.za",
    "siyathemba.gov.za","ubuntu.gov.za","umsobomvu.gov.za","emthanjeni.gov.za",
    "kareeberg.gov.za","renosterberg.gov.za","thembelihle.gov.za","siyancuma.gov.za",
    "pixleydc.gov.za","joemorolog.gov.za","gamagara.gov.za","ga-segonyana.gov.za",
    "johntaologaetsewedc.gov.za","sa-tenders.co.za","etenders.gov.za",
    "easytenders.co.za","municipalities.co.za",
]

def _is_allowed(url):
    try:
        host = urllib.parse.urlparse(url).netloc.lower().replace("www.","")
        return any(host.endswith(d) for d in ALLOWED_DOMAINS)
    except:
        return False

def _filename(url, disposition):
    if "filename=" in disposition:
        name = disposition.split("filename=")[-1].strip().strip('"\'')
        if name: return name
    path = urllib.parse.unquote(url.split("?")[0].split("/")[-1])
    return path if "." in path else "tender-document.pdf"

@router.get("/proxy/pdf")
async def proxy_pdf(url: str):
    if not url: raise HTTPException(400, "url required")
    if not _is_allowed(url): raise HTTPException(403, "Domain not allowed")
    headers = {"User-Agent":"Mozilla/5.0","Accept":"application/pdf,*/*","Accept-Encoding":"identity"}
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True, verify=False, headers=headers) as client:
            r = await client.get(url)
        if r.status_code != 200: raise HTTPException(r.status_code, f"Remote returned {r.status_code}")
        ct = r.headers.get("content-type","")
        if "text/html" in ct: raise HTTPException(422, "URL is HTML not a document")
        filename = _filename(url, r.headers.get("content-disposition",""))
        return StreamingResponse(iter([r.content]), media_type="application/octet-stream",
            headers={"Content-Disposition":f'attachment; filename="{filename}"',
                     "Content-Length":str(len(r.content)),"Cache-Control":"no-cache"})
    except HTTPException: raise
    except httpx.TimeoutException: raise HTTPException(504,"Timeout")
    except Exception as e: raise HTTPException(500, str(e))