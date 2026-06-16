import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_tenant, require_owner
from app.models.tenant import Tenant

router = APIRouter(prefix="/widget", tags=["widget"])

DOMAIN_RE = re.compile(r"^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")


class WidgetConfigUpdate(BaseModel):
    primary_color: str | None = None
    welcome_message: str | None = None
    allowed_domains: list[str] | None = None
    position: str | None = None
    icon: str | None = None


@router.get("/config")
async def widget_config(tenant: Tenant = Depends(get_current_tenant)):
    config = tenant.widget_config or {}
    return {
        "tenant_id": str(tenant.id),
        "tenant_name": tenant.name,
        "primary_color": config.get("primary_color", "#1D9E75"),
        "welcome_message": config.get("welcome_message", "Hi! How can I help you today?"),
        "allowed_domains": config.get("allowed_domains", []),
        "position": config.get("position", "bottom-right"),
        "icon": config.get("icon", "chat"),
    }


@router.put("/config")
async def update_widget_config(
    body: WidgetConfigUpdate,
    tenant: Tenant = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    config = dict(tenant.widget_config or {})
    if body.primary_color is not None:
        config["primary_color"] = body.primary_color
    if body.welcome_message is not None:
        config["welcome_message"] = body.welcome_message
    if body.allowed_domains is not None:
        for domain in body.allowed_domains:
            if domain and not DOMAIN_RE.match(domain.lstrip(".")):
                raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")
        config["allowed_domains"] = body.allowed_domains
    if body.position is not None:
        config["position"] = body.position
    if body.icon is not None:
        config["icon"] = body.icon
    tenant.widget_config = config
    await db.commit()
    return await widget_config(tenant)
