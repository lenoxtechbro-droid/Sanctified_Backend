"""Admin media uploads to Supabase Storage (returns URL)."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _sanitize_filename(name: str) -> str:
    base = os.path.basename(name or "upload")
    base = base.replace("\\", "_").replace("/", "_").strip()
    if not base:
        return "upload"
    return base


def _upload_to_supabase_storage_sync(
    *,
    bucket: str,
    path: str,
    content_type: str,
    data: bytes,
) -> dict[str, str]:
    """Use httpx only so we never touch gotrue/storage3 Client(proxy=)."""
    import httpx

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase is not configured")

    base = settings.supabase_url.rstrip("/")
    storage_base = f"{base}/storage/v1"
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "x-upsert": "true",
    }

    # Use only kwargs that httpx.Client accepts (no proxy=)
    with httpx.Client(
        base_url=storage_base,
        headers=headers,
        timeout=60.0,
        follow_redirects=True,
    ) as client:
        # Create bucket if missing (ignore 4xx e.g. already exists)
        try:
            client.post(
                "/bucket",
                json={
                    "id": bucket,
                    "name": bucket,
                    "public": settings.supabase_media_public,
                },
            )
            # Ignore 400/409 (bucket exists etc.)
        except Exception:
            pass

        # Upload: POST /object/{bucket}/{path} with multipart file
        obj_path = f"/object/{bucket}/{path}"
        files = {"file": (path.rsplit("/", 1)[-1], data, content_type)}
        resp = client.post(obj_path, files=files)
        resp.raise_for_status()

    if settings.supabase_media_public:
        url = f"{storage_base}/object/public/{bucket}/{path}"
    else:
        # Signed URL: POST /object/sign/{bucket}/{path} with expiresIn
        with httpx.Client(
            base_url=storage_base,
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            r = client.post(
                f"/object/sign/{bucket}/{path}",
                json={"expiresIn": settings.supabase_media_signed_url_ttl_seconds},
            )
            r.raise_for_status()
            url = r.json().get("signedURL") or r.json().get("signedUrl") or ""

    return {"bucket": bucket, "path": path, "url": url}


@router.post("/admin/media/upload")
async def admin_upload_media(
    file: UploadFile = File(...),
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
) -> dict[str, str]:
    """
    Upload a file to Supabase Storage using the service role key (server-side),
    then return a URL to access it (public or signed depending on settings).
    """
    settings = get_settings()

    if not settings.admin_api_key:
        raise HTTPException(status_code=501, detail="Admin uploads not configured")
    if not x_admin_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not settings.supabase_media_bucket:
        raise HTTPException(status_code=500, detail="Storage bucket not configured")

    content_type = file.content_type or "application/octet-stream"
    safe_name = _sanitize_filename(file.filename or "upload")
    date_prefix = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    object_path = f"admin/{date_prefix}/{uuid4().hex}_{safe_name}"

    try:
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="Empty file")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed reading upload: %s", e)
        raise HTTPException(status_code=400, detail="Invalid upload")

    try:
        result = await asyncio.to_thread(
            _upload_to_supabase_storage_sync,
            bucket=settings.supabase_media_bucket,
            path=object_path,
            content_type=content_type,
            data=data,
        )
        return result
    except Exception as e:
        logger.exception("Supabase upload failed: %s", e)
        detail = "Storage provider error"
        if settings.app_env.lower() != "production":
            detail = f"{detail}: {e}"
        raise HTTPException(status_code=502, detail=detail)

