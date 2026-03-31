from fastapi import APIRouter, Depends
from app.core.security import get_current_user

router = APIRouter(prefix="/api")

@router.get("/me")
async def user_info(user=Depends(get_current_user)):
    return user
