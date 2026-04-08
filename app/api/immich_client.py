
import httpx
import time
from datetime import datetime
from app.core.config import settings

class ImmichClient:
    def __init__(self):
        self.base_url = f"{settings.immich_api_url.rstrip('/')}/api"
        self.headers = {
            "x-api-key": settings.immich_api_key,
            "Accept": "application/json",
        }

    async def get_all_albums(self):
        """Fetch all shared or public albums."""
        async with httpx.AsyncClient(headers=self.headers) as client:
            response = await client.get(f"{self.base_url}/albums")
            response.raise_for_status()
            return response.json()

    async def get_album_info(self, album_id: str):
        """Fetch assets from a specific album ID for the carousel."""
        async with httpx.AsyncClient(headers=self.headers) as client:
            response = await client.get(f"{self.base_url}/albums/{album_id}")
            response.raise_for_status()
            # Immich returns the album object with an 'assets' list.
            # Will need to access that from this response.
            return response.json()

    async def get_thumbnail_url(self, asset_id: str):
        """Returns the internal URL to fetch a specific photo thumbnail or full image."""
        # This is used by the backend to proxy the image, so that API keys stay hidden.
        return f"{self.base_url}/assets/{asset_id}/thumbnail?size=preview"

    async def download_thumb(self, asset_id: str):
        """Streams the thumbnail file data."""
        url = await self.get_thumbnail_url(asset_id)
        async with httpx.AsyncClient(headers=self.headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def download_asset(self, asset_id: str):
        """Streams the actual file data for the 'Download' feature."""
        async with httpx.AsyncClient(headers=self.headers) as client:
            response = await client.get(f"{self.base_url}/assets/{asset_id}/original")
            response.raise_for_status()
            return response.content

    async def upload_asset(self, file_bytes: bytes, file_name: str):
        """Uploads a single asset to Immich."""
        async with httpx.AsyncClient(headers=self.headers) as client:
            files = {"assetData": (file_name, file_bytes)}
            # Immich requires deviceId and deviceAssetId for tracking
            data = {
                "deviceId": "family-hub-server",
                "deviceAssetId": f"{file_name}-{int(time.time())}",
                "fileCreatedAt": datetime.now().isoformat(),
                "fileModifiedAt": datetime.now().isoformat(),
            }
            response = await client.post(f"{self.base_url}/assets", files=files, data=data)
            response.raise_for_status()
            return response.json()

    async def add_assets_to_album(self, album_id: str, asset_ids: list):
        """Adds a list of asset IDs to a specific album."""
        if not asset_ids:
            return {"success": False, "message": "No assets to add"}
        async with httpx.AsyncClient(headers=self.headers) as client:
            payload = {"assetIds": asset_ids, "albumIds": [album_id]}
            response = await client.put(f"{self.base_url}/albums/assets", json=payload)
            response.raise_for_status()
            return response.json()

    async def get_storage_info(self):
        """Fetch server storage stats."""
        async with httpx.AsyncClient(headers=self.headers) as client:
            response = await client.get(f"{self.base_url}/server/storage")
            response.raise_for_status()
            return response.json()

immich_client = ImmichClient()        
