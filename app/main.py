
from fastapi import FastAPI, Request, Response, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import os
import io
import time
from pathlib import Path
from typing import List
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
from apscheduler.schedulers.background import BackgroundScheduler

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from passlib.context import CryptContext

from app.core.config import settings
from app.core.database import engine, Base, get_db
from app.core.auth import get_current_user, get_current_admin, create_access_token
from app.core.utils import process_announcement_data
from app.core.logging import logger, LOG_FILE
from app.api.immich_client import immich_client
from app.models.user import User


app = FastAPI(title="Family Hub")
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

register_heif_opener()
CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

#@app.on_event("startup")
async def startup_validation():
    print("=== Settings Validation ===")
    print(f"Database URL: {settings.database_url}")
    print(f"Immich URL: {settings.immich_api_url}")
    key_status = "LOADED" if settings.immich_api_key else "MISSING"
    print(f"Immich API Key: {key_status}")
    print("=== === === === === === ===")
    try:
        albums = await immich_client.get_all_albums()
        print(f"Immich Connection: SUCCESS ({len(albums)} albums found)")
    except Exception as e:
        print(f"Immich Connection: FAILED - {e}")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)

def sync_carousel_cache():
    """Removed cached images that are no longer in the featured album."""
    if not settings.immich_showcase_album:
        return
    try:
        # Get Immich IDs
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        album_data = loop.run_until_complete(immich_client.get_album_info(settings.immich_showcase_album))
        current_ids = {asset["id"] for asset in album_data.get("assets", [])}
        loop.close()

        # Scan local cache
        for file in CACHE_DIR.glob("*.jpg"):
            asset_id = file.stem
            if asset_id not in current_ids:
                os.remove(file)
                logger.info(f"Cache Cleanup: Removed orphaned asset {asset_id}")
    except Exception as e:
        logger.error(f"Cache Sync Error: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(sync_carousel_cache, 'interval', minutes=settings.immich_showcase_cache_cleanup_interval)
scheduler.start()

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("app/static/favicon.ico")

async def is_first_run(db: AsyncSession):
    result = await db.execute(select(func.count(User.id)))
    return result.scalar() == 0

@app.get("/", response_class=HTMLResponse)
@limiter.limit("5/minute")
async def read_home(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Public Landing Page"""
    # Redirect to setup if there are no users
    if await is_first_run(db):
        logger.info("Running initial setup")
        return RedirectResponse(url="/initial-setup")

    content = process_announcement_data(limit_recent=True)
    # Fetch Immich Assets
    carousel_assets = []
    carousel_error = False
    if settings.immich_showcase_album:
        try:
            album_data = await immich_client.get_album_info(settings.immich_showcase_album)
            carousel_assets = album_data.get("assets", [])
            logger.debug(f"Found {len(carousel_assets)} carousel assets.")
        except Exception as e:
            logger.error(f"Carousel Error: {e}")
            carousel_error = True
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": "Home",
            "user": user,
            "settings": settings,
            "announcements": content["announcements"],
            "events": content["events"],
            "assets": carousel_assets[:settings.immich_showcase_limit],
            "carousel_error": carousel_error
        })

@app.get("/announcements", response_class=HTMLResponse)
@limiter.limit("5/minute")
async def announcements_page(request: Request, user: User = Depends(get_current_user)):
    content = process_announcement_data(limit_recent=False)
    logger.debug(f"Found {len(content['announcements'])} announcements.")
    logger.debug(f"Found {len(content['events'])} events.")
    return templates.TemplateResponse(
        request=request,
        name="announcements.html",
        context={
            "title": "Announcements and Events",
            "user": user,
            "settings": settings,
            "available_years": content["available_years"],
            "announcements": content["announcements"],
            "events": content["events"]
        })

@app.get("/proxy/image/{asset_id}")
@limiter.limit("5/minute")
async def proxy_image(request: Request, asset_id: str):
    """Fetch image from Immich, and download to server. Skip download if already present, and serve it to the browser securely."""
    cache_path = CACHE_DIR / f"{asset_id}.jpg"
    logger.info(f"Proxying image: {asset_id}")

    # Check if present
    if cache_path.exists():
        return FileResponse(
            cache_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=31536000"} # Tell browser to cache for 1 year
        )
    # If not, fetch from Immich
    try:
        content = await immich_client.download_asset(asset_id)
        img = Image.open(io.BytesIO(content))
        # Read EXIF rotation tag. Fixes rotation on vertical images
        img = ImageOps.exif_transpose(img)
        # Skip if it's a GIF or multi-frame image
        if getattr(img, "is_animated", False):
            return Response(status_code=400, content="Animated formats not supported.")

        # Convert to JPEG by removing transparency
        img = img.convert("RGB")
        img.save(cache_path, "JPEG", quality=85, optimize=True)
        return FileResponse(cache_path, media_type="image/jpeg")
    except Exception as e:
        logger.error(f"Image Conversion Error for {asset_id}: {e}")
        return Response(status_code=404)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: User = Depends(get_current_user)):
    """Authentication Gate"""
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "title": "Login",
            "user": user,
            "settings": settings})

@app.post("/login")
@limiter.limit("5/minute")
async def handle_login(request: Request, email: str = Form(...), password: str = Form(...), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not pwd_context.verify(password, user.hashed_password):
        logger.warning(f"Failed login attempt for email: {email}")
        return RedirectResponse(url="/login?error=invalid", status_code=303)

    if not user.is_active:
        logger.warning(f"Login attempt for inactive account: {email}")
        return RedirectResponse(url="/login?error=pending", status_code=303)

    token = create_access_token(data={"sub": user.email})
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="access_token", value=token, httponly=True, samesite="lax")
    logger.info(f"User logged in: {user.full_name} ({user.email})")
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    return response

@app.get("/request-account", response_class=HTMLResponse)
async def request_account_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        request=request,
        name="request_account.html",
        context={
            "title": "Request Account",
            "user": user,
            "settings": settings})

@app.post("/request-account")
async def handle_account_request(request: Request, full_name: str = Form(...), email: str = Form(...), password: str = Form(...), db: AsyncSession = Depends(get_db)):
    # Check if account exists
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        logger.warning(f"Account request for existing account: {full_name} ({email})")
        return RedirectResponse(url="/request-account?error=exists", status_code=303)
    # Hash password and save as inactive user
    hashed_password = pwd_context.hash(password)
    new_user = User(full_name=full_name, email=email, hashed_password=hashed_password, is_active=False)

    db.add(new_user)
    await db.commit()
    logger.info(f"New user request: {email}")

    return RedirectResponse(url="/request-confirmation", status_code=303)

@app.get("/request-confirmation", response_class=HTMLResponse)
async def request_confirmation_page(request: Request, user: User = Depends(get_current_user)):
    # TODO: sent email notification to all admins
    return templates.TemplateResponse(
        request=request,
        name="request_confirmation.html",
        context={
            "title": "Request Received",
            "user": user,
            "settings": settings})

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard_page(request: Request, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    """Admin Management Interface"""
    # Fetch all users
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    all_users = result.scalars().all()

    safe_settings = settings.model_dump()
    # Filter out sensitive info (api keys, secrets, etc)
    display_settings = {k: (v if "key" not in k.lower() and "secret" not in k.lower() else "*******")
                        for k, v in safe_settings.items()}
    display_settings["LOG_FILE_PATH"] = str(LOG_FILE.absolute())

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "user": admin,
            "users": all_users,
            "settings": settings,
            "settings_map": display_settings,
            "title": "Admin Dashboard"})

@app.post("/admin/approve/{user_id}")
async def approve_user(user_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.is_active = True
        await db.commit()
    logger.info(f"Admin {admin.email} approved user account for {user.email}")
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/deny/{user_id}")
async def deny_user(user_id: int, db: AsyncSession = Depends(get_db), admin: User = Depends(get_current_admin)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    # Admins can't delete themselves
    if user and user.id != admin.id:
        await db.delete(user)
        await db.commit()
    logger.info(f"Admin {admin.email} denied user account for {user.email}")
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/edit-user/{user_id}", response_class=HTMLResponse)
async def edit_user_page(
        user_id: int, 
        request: Request, 
        db: AsyncSession = Depends(get_db), 
        admin: User = Depends(get_current_admin)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning(f"Admin {admin.email} attempted to edit a non-existant user")
        raise HTTPException(status_code=404, detail="User not found")
    
    return templates.TemplateResponse(
        request=request, 
        name="edit_user.html", 
        context={
            "user": admin,
            "request": request,
            "settings": settings,
            "user": user,
            "title": f"Edit {user.full_name}"})

@app.post("/admin/edit-user/{user_id}")
async def handle_edit_user(
        user_id: int,
        full_name: str = Form(...),
        email: str = Form(...),
        is_admin: bool = Form(False),
        is_active: bool = Form(False),
        db: AsyncSession = Depends(get_db),
        admin: User = Depends(get_current_admin)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"Admin {admin.email} attempted to edit a non-existant user")        
        raise HTTPException(status_code=404, detail="User not found")

    # Safety Valve: Don't let the current admin demote or deactivate themselves
    if user.id == admin.id:
        user.full_name = full_name
        user.email = email
        # Ignore is_admin and is_active changes for self to prevent lockout
    else:
        user.full_name = full_name
        user.email = email
        user.is_admin = is_admin
        user.is_active = is_active

    await db.commit()
    logger.info(f"Admin {admin.email} edited settings for user {user.email}")
    return RedirectResponse(url="/admin", status_code=303)


@app.get("/initial-setup", response_class=HTMLResponse)
async def initial_setup_page(request: Request, db: AsyncSession = Depends(get_db)):
    # Prevent access if any user exists
    if not await is_first_run(db):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="initial_setup.html",
        context={"title": "Initial Setup", "settings": settings})

@app.post("/initial-setup")
async def handle_initial_setup(full_name: str=Form(...), email: str=Form(...), password: str=Form(...), db: AsyncSession = Depends(get_db)):
    # Prevent access if any user exists
    if not await is_first_run(db):
        return HTTPException(status_code=403, detail="Setup already completed.")

    hashed_password = pwd_context.hash(password)
    admin_user = User(full_name=full_name, email=email, hashed_password=hashed_password, is_active=True, is_admin=True)
    db.add(admin_user)
    await db.commit()
    await db.refresh(admin_user)

    token = create_access_token(data={"sub": admin_user.email})
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="access_token", value=token, httponly=True, samesite="lax")
    return response

# === Photos Page Logic

@app.get("/photos", response_class=HTMLResponse)
async def photos_page(
        request: Request,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    if not user:
        logger.warning("Unauthorized access attempt to photos page")
        return RedirectResponse(url="/login", status_code=303)
    
    upload_enabled = True
    upload_error = None
    try:
        storage = await immich_client.get_storage_info()
        usage_perc = storage.get("diskUsagePercentage", 0)
        cutoff = settings.disk_usage_perc_cutoff
        if cutoff == 0:
            upload_enabled = False
            upload_error = "Uploads are currently disabled by the administrator."
        elif cutoff != 100 and usage_perc >= cutoff:
            upload_enabled = False
            upload_error = "The server storage is currently full. Please contact a server administrator."
    except Exception as e:
        logger.error(f"Failed to check storage status: {e}")

    allowed_ids = [aid.strip() for aid in settings.immich_allowed_albums.split(",") if aid.strip()]
    if not allowed_ids:
        logger.info("No configured albums for photos page. Update 'IMMICH_ALLOWED_ALBUMS' in the docker-compose file.")
        return templates.TemplateResponse(request=request, name="photos.html", context={"albums": [], "title": "Photos"})

    all_albums = await immich_client.get_all_albums()
    filtered_albums = [a for a in all_albums if a["id"] in allowed_ids]

    return templates.TemplateResponse(
        request=request,
        name="photos.html",
        context={
            "user": user,
            "settings": settings,
            "albums": filtered_albums,
            "upload_enabled": upload_enabled,
            "upload_error": upload_error,
            "title": "Photo Albums"}
    )

@app.get("/photos/album/{album_id}", response_class=HTMLResponse)
async def album_detail(
        album_id: str,
        request: Request,
        user: User = Depends(get_current_user)
):
    if not user:
        logger.warning("Unauthorized access attempt to album page")
        return RedirectResponse(url="/login", status_code=303)

    allowed_ids = settings.immich_allowed_albums.split(",")
    if album_id not in allowed_ids:
        logger.warning(f"User {user.email} attempted to access unauthorized album {album_id}")
        raise HTTPException(status_code=403, detail="Access denied to this album.")

    assets = await immich_client.get_album_info(album_id)
    assets = assets["assets"]
    return templates.TemplateResponse(
        request=request,
        name="album_view.html",
        context={
            "user": user,
            "settings": settings,
            "assets": assets,
            "album_id": album_id,
            "title": "Album View"})

@app.get("/proxy/thumb/{asset_id}")
@limiter.limit("10/minute")
async def proxy_thumbnail(request: Request, asset_id: str, user: User = Depends(get_current_user)):
    if not user:
        logger.warning("Unauthorized access attempt to thumbnail api")
        return Response(status_code=401)

    thumb_cache = CACHE_DIR / "thumbs"
    thumb_cache.mkdir(parents=True, exist_ok=True)
    cache_path = thumb_cache / f"{asset_id}.jpg"

    if cache_path.exists():
        return FileResponse(cache_path, media_type="image/jpeg")

    try:
        content = await immich_client.download_thumb(asset_id)
        with open(cache_path, "wb") as f:
            f.write(content)
        return FileResponse(cache_path, media_type="image/jpeg")
    except Exception as e:
        logger.error(f"Thumbnail download error for {asset_id}: {e}")
        return Response(status_code=404)

def sync_thumb_cache():
    """Removes thumbnails that haven't been accessed in X days."""
    thumb_cache = CACHE_DIR / "thumbs"
    if not thumb_cache.exists():
        return

    # 30 days. Converted to seconds
    ttl_seconds = 30 * 24 * 60 * 60
    current_time = time.time()

    try:
        for file in thumb_cache.glob(".jpg"):
            file_age = current_time - file.stat().st_atime
            if file_age > ttl_seconds:
                os.remove(file)
                logger.info(f"Cache Cleanup: Purged old thumbnail {file.name}")
    except Exception as e:
        logger.error(f"Thumbnail Cache Sync Error: {e}")

scheduler.add_job(sync_thumb_cache, 'interval', hours=24)

@app.get("/proxy/download/{asset_id}")
async def proxy_download(request: Request, asset_id: str, user: User = Depends(get_current_user)):
    """Fetch the original file (photo or video) from Immich and stream it to the user."""
    if not user:
        logger.warning(f"Unauthorized access attempt to download file: {asset_id}")
        return Response(status_code=401)

    try:
        content = await immich_client.download_asset(asset_id)
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename=family-photos-download-{asset_id}"}
        )
    except Exception as e:
        logger.error(f"Download Error for {asset_id}: {e}")
        return Response(status_code=404)

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        request=request,
        name="upload.html",
        context={"user": user, "settings": settings, "title": "Upload Media"})

@app.post("/upload")
async def handle_upload(request: Request, files: List[UploadFile] = File(...), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    uploaded_ids = []
    album_id = settings.immich_upload_album

    for file in files:
        try:
            content = await file.read()
            result = await immich_client.upload_asset(content, file.filename)
            asset_id = result.get("id")
            uploaded_ids.append(asset_id)
            logger.info(f"Asset uploaded: {asset_id} by {user.email}")
        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            
    # Add all uploads to the designated album
    if uploaded_ids and album_id:
        await immich_client.add_assets_to_album(album_id, uploaded_ids)

    return RedirectResponse(url="/photos?status=success", status_code=303)
