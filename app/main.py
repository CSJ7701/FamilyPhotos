
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.core.config import settings

app = FastAPI(title="Family Hub")
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
async def startup_event():
    print("=== Settings Validation ===")
    print(f"Database URL: {settings.database_url}")
    print(f"Immich URL: {settings.immich_api_url}")
    key_status = "LOADED" if settings.immich_api_key else "MISSING"
    print(f"Immich API Key: {key_status}")
    print("=== === === === === === ===")

@app.get("/", response_class=HTMLResponse)
async def read_home(request: Request):
    """Public Landing Page"""
    return templates.TemplateResponse(request=request, name="index.html", context={"title": "Home"})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Authentication Gate"""
    return templates.TemplateResponse(request=request, name="login.html", context={"title": "Login"})

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin Management Interface"""
    return templates.TemplateResponse(request=request, name="admin.html", context={"title": "Admin"})

