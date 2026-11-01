"""Groups and collections (owner/admin), plus the collections a caller can see."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
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
async def create_group(body: GroupCreate, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    group = Group(tenant_id=tenant.id, name=body.name.strip())
    db.add(group)
    await _commit_unique(db, "A group with this name already exists")
    return await _group_out(db, group)


@router.delete("/groups/{group_id}")
async def delete_group(group_id: str, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)):
    group = await _owned(db, Group, group_id, tenant, "Group")
    if group.source == "scim":
        raise HTTPException(status_code=409, detail="This group is managed by your identity provider")
    await db.delete(group)
    await db.commit()
    await bump_corpus_version(str(tenant.id))
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
    group_id: str, body: MemberChange, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)
):
    group = await _owned(db, Group, group_id, tenant, "Group")
    user = await _member_user(db, tenant, body)
    if not await db.get(GroupMember, (group.id, user.id)):
        db.add(GroupMember(group_id=group.id, user_id=user.id, tenant_id=tenant.id))
        await db.commit()
    return await _group_out(db, group)


@router.delete("/groups/{group_id}/members/{user_id}")
async def remove_member(
    group_id: str, user_id: str, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)
):
    group = await _owned(db, Group, group_id, tenant, "Group")
    await db.execute(
        delete(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == _uuid_or_404(user_id, "User"))
    )
    await db.commit()
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
    body: CollectionCreate, tenant: Tenant = Depends(require_owner), db: AsyncSession = Depends(get_db)
):
    collection = Collection(
        tenant_id=tenant.id, name=body.name.strip(), description=body.description, visibility=body.visibility
    )
    db.add(collection)
    await _commit_unique(db, "A collection with this name already exists")
    return await _collection_out(db, collection, with_access=True)


@router.patch("/collections/{collection_id}")
async def update_collection(
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
    return await _collection_out(db, collection, with_access=True)


@router.delete("/collections/{collection_id}")
async def delete_collection(
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
    return {"ok": True}
