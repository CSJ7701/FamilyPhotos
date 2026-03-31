
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    IMMICH_URL: str = ""
    IMMICH_API_KEY: str | None = None

    SECRET_KEY: str = "change-this-later"

    class Config:
        env_prefix = ""

@lru_cache()
def get_settings():
    return Settings()
