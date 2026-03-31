
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.immich_client import ImmichClient

templates = Jinja2Templates(directory="app/templates")

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/albums/{album_id}")
async def album_view(request: Request, album_id: str):
    client = ImmichClient()
    data = await client.get_album(album_id)

    # Immich returns assets list under "assets"
    assets = data.get("assets", [])

    # Build display data
    processed = [
        {
            "url": client.asset_download_url(a["id"]),
            "alt": a.get("originalFileName", "")
        }
        for a in assets
    ]

    return templates.TemplateResponse(
        "temp_albums.html",
        {"request": request, "assets": processed, "album": data}
    )
