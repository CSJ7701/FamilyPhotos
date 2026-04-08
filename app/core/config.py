
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import DirectoryPath
from typing import Optional

class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/family_hub.db"

    immich_api_url: str
    immich_api_key: str # Loaded from .env via Docker
    secret_key: str

    # Photo Settings (Carousel and Photo page)
    immich_showcase_album: str
    immich_showcase_limit: int
    immich_showcase_cache_cleanup_interval: int
    immich_allowed_albums: str
    immich_upload_album: str
    disk_usage_perc_cutoff: int

    announcements_path: str = "./data/announcements.md"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # General Settings
    family_name: str
    webmaster_name: str
    webmaster_email: str
settings = Settings()    
