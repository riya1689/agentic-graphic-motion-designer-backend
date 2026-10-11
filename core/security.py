# core/security.py
# উদ্দেশ্য: API Key অথেনটিকেশন ও অ্যাক্সেস কন্ট্রোল (FastAPI ডিপ্লয়মেন্টের জন্য)

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from core.config import APP_API_KEY

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    """
    প্রতিটি ইনকামিং HTTP রিকোয়েস্টের X-API-Key ভ্যালিডেট করে।
    """
    if not api_key or api_key != APP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing API Key"
        )
    return api_key