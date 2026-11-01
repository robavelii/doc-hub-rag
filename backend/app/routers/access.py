"""Groups and collections (owner/admin), plus the collections a caller can see."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import Principal, get_principal, require_owner
from app.models.access import Collection, CollectionAccess, Group, GroupMember
from app.models.document import Document
from app.models.tenant import Tenant
from app.models.user import User
from app.services.access import resolve_scope
from app.services.audit_service import log_audit
from app.services.cache_service import bump_corpus_version

router = APIRouter(tags=["access"])


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class MemberChange(BaseModel):
    user_id: str | None = None
    email: str | None = None


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    visibility: Literal["tenant", "restricted"] = "tenant"


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    visibility: Literal["tenant", "restricted"] | None = None
    group_ids: list[str] | None = None  # replaces the access list when given


async def _audit(db: AsyncSession, request: Request, tenant: Tenant, action: str, **details) -> None:
    user = getattr(request.state, "user", None)
    await log_audit(
        db, action, tenant_id=str(tenant.id), user_id=str(user.id) if user else None,
        details={k: v if isinstance(v, list | type(None)) else str(v) for k, v in details.items()},
    )


def _uuid_or_404(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"{what} not found") from exc


async def _owned(db: AsyncSession, model, obj_id: str, tenant: Tenant, what: str):
    obj = await db.get(model, _uuid_or_404(obj_id, what))
    if not obj or obj.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return obj


async def _commit_unique(db: AsyncSession, message: str) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=message) from exc


# --- groups -------------------------------------------------------------------


async def _group_out(db: AsyncSession, group: Group) -> dict:
    members = await db.execute(
        select(User.id, User.email).join(GroupMember, GroupMember.user_id == User.id).where(GroupMember.group_id == group.id)
    )
    return {
        "id": str(group.id),
        "name": group.name,
        "source": group.source,
        "members": [{"id": str(uid), "email": email} for uid, email in members.all()],
    }


@router.get("/groups")
async def list_groups(tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    groups = (await db.execute(select(Group).where(Group.tenant_id == tenant.id).order_by(Group.name))).scalars().all()
    return [await _group_out(db, g) for g in groups]


@router.post("/groups", status_code=201)
async def create_group(
    request: Request,
    body: GroupCreate, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    group = Group(tenant_id=tenant.id, name=body.name.strip())
    db.add(group)
    await _commit_unique(db, "A group with this name already exists")
    await _audit(db, request, tenant, "group_created", group_id=group.id, name=group.name)
    return await _group_out(db, group)


@router.delete("/groups/{group_id}")
async def delete_group(
    request: Request,
    group_id: str, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    group = await _owned(db, Group, group_id, tenant, "Group")
    if group.source == "scim":
        raise HTTPException(status_code=409, detail="This group is managed by your identity provider")
    await db.delete(group)
    await db.commit()
    await bump_corpus_version(str(tenant.id))
    await _audit(db, request, tenant, "group_deleted", group_id=group.id, name=group.name)
    return {"ok": True}


async def _member_user(db: AsyncSession, tenant: Tenant, body: MemberChange) -> User:
    if body.user_id:
        user = await db.get(User, _uuid_or_404(body.user_id, "User"))
    elif body.email:
        user = (
            await db.execute(select(User).where(User.tenant_id == tenant.id, func.lower(User.email) == body.email.lower()))
        ).scalar_one_or_none()
    else:
        raise HTTPException(status_code=422, detail="user_id or email is required")
    if not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/groups/{group_id}/members")
async def add_member(
    request: Request,
    group_id: str,
    body: MemberChange,
    tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)
):
    group = await _owned(db, Group, group_id, tenant, "Group")
    user = await _member_user(db, tenant, body)
    if not await db.get(GroupMember, (group.id, user.id)):
        db.add(GroupMember(group_id=group.id, user_id=user.id, tenant_id=tenant.id))
        await db.commit()
    await _audit(db, request, tenant, "group_member_added", group_id=group.id, user_id=user.id)
    return await _group_out(db, group)


@router.delete("/groups/{group_id}/members/{user_id}")
async def remove_member(
    request: Request,
    group_id: str, user_id: str, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)
):
    group = await _owned(db, Group, group_id, tenant, "Group")
    await db.execute(
        delete(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == _uuid_or_404(user_id, "User"))
    )
    await db.commit()
    await _audit(db, request, tenant, "group_member_removed", group_id=group.id, user_id=user_id)
    return await _group_out(db, group)


# --- collections --------------------------------------------------------------


async def _collection_out(db: AsyncSession, c: Collection, *, with_access: bool) -> dict:
    count = (await db.execute(select(func.count()).select_from(Document).where(Document.collection_id == c.id))).scalar()
    out = {
        "id": str(c.id),
        "name": c.name,
        "description": c.description,
        "visibility": c.visibility,
        "document_count": count or 0,
    }
    if with_access:
        rows = await db.execute(select(CollectionAccess.group_id).where(CollectionAccess.collection_id == c.id))
        out["group_ids"] = [str(g) for g in rows.scalars().all()]
    return out


@router.get("/collections")
async def list_collections(principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    """Collections the caller can see (owners/admins: all, with their access lists)."""
    scope = await resolve_scope(db, principal)
    rows = (
        await db.execute(
            select(Collection)
            .where(Collection.tenant_id == principal.tenant.id, scope.orm_filter(Collection.id))
            .order_by(Collection.name)
        )
    ).scalars().all()
    return [await _collection_out(db, c, with_access=scope.all_documents) for c in rows]


@router.post("/collections", status_code=201)
async def create_collection(
    request: Request,
    body: CollectionCreate, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)
):
    collection = Collection(
        tenant_id=tenant.id, name=body.name.strip(), description=body.description, visibility=body.visibility
    )
    db.add(collection)
    await _commit_unique(db, "A collection with this name already exists")
    await _audit(db, request, tenant, "collection_created", collection_id=collection.id, visibility=collection.visibility)
    return await _collection_out(db, collection, with_access=True)


@router.patch("/collections/{collection_id}")
async def update_collection(
    request: Request,
    collection_id: str, body: CollectionUpdate, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)
):
    collection = await _owned(db, Collection, collection_id, tenant, "Collection")
    if body.name is not None:
        collection.name = body.name.strip()
    if body.description is not None:
        collection.description = body.description
    if body.visibility is not None:
        collection.visibility = body.visibility
    if body.group_ids is not None:
        group_ids = [_uuid_or_404(g, "Group") for g in body.group_ids]
        found = (
            await db.execute(select(Group.id).where(Group.tenant_id == tenant.id, Group.id.in_(group_ids)))
        ).scalars().all()
        if len(set(found)) != len(set(group_ids)):
            raise HTTPException(status_code=404, detail="Group not found")
        await db.execute(delete(CollectionAccess).where(CollectionAccess.collection_id == collection.id))
        for gid in set(group_ids):
            db.add(CollectionAccess(collection_id=collection.id, group_id=gid, tenant_id=tenant.id))
    await _commit_unique(db, "A collection with this name already exists")
    await bump_corpus_version(str(tenant.id))  # visibility changes what cached answers may cite
    await _audit(db, request, tenant, "collection_updated", collection_id=collection.id, visibility=collection.visibility, group_ids=body.group_ids)
    return await _collection_out(db, collection, with_access=True)


@router.delete("/collections/{collection_id}")
async def delete_collection(
    request: Request,
    collection_id: str, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)
):
    """Only empty collections can be deleted: moving their documents to General
    automatically would make restricted documents visible to everyone."""
    collection = await _owned(db, Collection, collection_id, tenant, "Collection")
    remaining = (
        await db.execute(select(func.count()).select_from(Document).where(Document.collection_id == collection.id))
    ).scalar()
    if remaining:
        raise HTTPException(
            status_code=409, detail=f"Move or delete the {remaining} document(s) in this collection first"
        )
    await db.delete(collection)
    await db.commit()
    await bump_corpus_version(str(tenant.id))
    await _audit(db, request, tenant, "collection_deleted", collection_id=collection_id)
    return {"ok": True}
