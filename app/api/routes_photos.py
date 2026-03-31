from fastapi import APIRouter, Depends, HTTPException
from .immich_client import ImmichClient

def get_immich():
    return ImmichClient()

router = APIRouter(prefix="/immich", tags=["immich"])

@router.get("/albums")
async def list_albums(client: ImmichClient = Depends(get_immich)):
    try:
        return await client.list_albums()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/albums/{album_id}")
async def get_album(album_id: str, client: ImmichClient = Depends(get_immich)):
    try:
        return await client.get_album(album_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/assets/{asset_id}")
async def get_asset(asset_id: str, client: ImmichClient = Depends(get_immich)):
    try:
        return await client.get_asset(asset_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
