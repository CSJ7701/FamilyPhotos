
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import DirectoryPath
from typing import Optional

class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/family_hub.db"

    immich_api_url: str
    immich_api_key: str # Loaded from .env via Docker

    # Album names ...

    announcements_path: str = "./data/announcements.md"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()    
