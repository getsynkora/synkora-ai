"""Newsletter Templates Controller

REST endpoints for managing custom newsletter templates.

  POST /api/newsletter/templates  — upload a custom HTML template
  GET  /api/newsletter/templates  — list built-in + tenant custom templates
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from src.middleware.auth_middleware import get_current_account, get_current_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/newsletter/templates", tags=["newsletter-templates"])

_BUILTIN_TEMPLATE_DIR = Path(__file__).parent.parent / "services" / "newsletter" / "templates"
_BUILTIN_NAMES = ["editorial", "minimal", "micromobility"]
_MAX_TEMPLATE_SIZE = 512 * 1024  # 512 KB


class TemplateUploadResponse(BaseModel):
    name: str
    s3_key: str
    size: int


class TemplateListResponse(BaseModel):
    built_in: list[str]
    custom: list[str]


@router.post("", response_model=TemplateUploadResponse)
async def upload_template(
    file: UploadFile,
    name: str | None = None,
    tenant_id: str = Depends(get_current_tenant_id),
    _account=Depends(get_current_account),
):
    """Upload a custom Jinja2 HTML newsletter template.

    The template is stored under ``newsletter-templates/{tenant_id}/{name}.html``
    in the configured S3 bucket.  Use ``{{ date }}``, ``{{ lead_headline }}``,
    etc. — the same variables as the built-in editorial template.
    """
    if not file.filename or not file.filename.endswith(".html"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Template file must be a .html file",
        )

    content = await file.read()
    if len(content) > _MAX_TEMPLATE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Template file exceeds 512 KB limit",
        )

    # Derive name from upload parameter or filename
    template_name = name or Path(file.filename).stem
    if not template_name or template_name in _BUILTIN_NAMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Template name '{template_name}' is reserved or invalid",
        )

    s3_key = f"newsletter-templates/{tenant_id}/{template_name}.html"

    try:
        from src.services.storage.s3_storage import get_s3_storage

        s3 = get_s3_storage()
        s3.upload_file(file_content=content, key=s3_key, content_type="text/html; charset=utf-8")
    except Exception as exc:
        logger.exception(f"Failed to upload newsletter template to S3: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service unavailable",
        ) from exc

    logger.info(f"Uploaded newsletter template: tenant={tenant_id} name={template_name} size={len(content)}")

    return TemplateUploadResponse(name=template_name, s3_key=s3_key, size=len(content))


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    tenant_id: str = Depends(get_current_tenant_id),
    _account=Depends(get_current_account),
):
    """List available newsletter templates.

    Returns both the built-in templates and any custom templates the tenant
    has uploaded to S3.
    """
    custom: list[str] = []

    try:
        from src.services.storage.s3_storage import get_s3_storage

        s3 = get_s3_storage()
        prefix = f"newsletter-templates/{tenant_id}/"
        # Use list_objects if available; gracefully degrade
        objs = s3.list_files(prefix=prefix) if hasattr(s3, "list_files") else []
        for obj in objs:
            key: str = obj.get("key", obj) if isinstance(obj, dict) else obj
            filename = key.removeprefix(prefix)
            if filename.endswith(".html"):
                custom.append(filename[:-5])  # strip .html
    except Exception as exc:
        logger.debug(f"Could not list custom newsletter templates from S3: {exc}")

    return TemplateListResponse(built_in=_BUILTIN_NAMES, custom=custom)
