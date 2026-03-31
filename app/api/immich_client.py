
import httpx
from typing import Optional, Dict, Any, List
from app.core.config import get_settings

class ImmichClient:
    def __init__(self, timeout: float = 10.0):
        self.settings = get_settings()
        self.base_url = self.settings.IMMICH_URL.rstrip("/")
        self.api_key = self.settings.IMMICH_API_KEY
        self.timeout = timeout
        self._headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None):
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout = self.timeout) as client:
            resp = await client.get(url, headers = self._headers, params=params)
            resp.raise_for_status()
            return resp.json()

    async def _post(self, endpoint: str, data: Any = None):
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=self._headers, json=data)
            resp.raise_for_status()
            return resp.json()

    async def _stream(self, endpoint: str, params: Optional[Dict[str, Any]] = None):
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("GET", url, headers=self._headers, params=params) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

    # ================= Immich API Wrappers =====================

    async def list_albums(self):
        return await self._get("/api/albums")

    # This method returns an indexed list of assets under "assets"
    async def get_album(self, album_id: str):
        return await self._get(f"/api/albums/{album_id}")

    async def get_asset(self, asset_id: str):
        return await self._get(f"/api/assets/{asset_id}")

    def asset_download_url(self, asset_id: str, variant: str="original"):
        return f"{self.base_url}/api/assets/{asset_id}/original"
