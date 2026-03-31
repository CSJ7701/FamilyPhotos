
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from app.core.config import get_settings

security_scheme = HTTPBearer(auto_error=False)

async def get_current_user(token: str = Depends(security_scheme)):
    # Placeholder for future auth logic
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    # TODO: Verify token, lookup user, etc
    return {"user": "placeholder"}
