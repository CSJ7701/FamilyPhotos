
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.core.logging import setup_logging
from app.core.config import get_settings
from app.routes.home import router as home_router
from app.routes.api import router as api_router
from app.api.routes_photos import router as immich_router

settings = get_settings()
logger = setup_logging()

app = FastAPI(debug=settings.DEBUG)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(home_router)
app.include_router(api_router)
app.include_router(immich_router)
