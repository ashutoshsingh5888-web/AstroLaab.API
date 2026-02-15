import os
import secrets
from fastapi import Header, HTTPException
from starlette.status import HTTP_401_UNAUTHORIZED

API_KEY = os.getenv("API_KEY")

async def verify_api_key(x_api_key: str = Header(...)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured")

    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
