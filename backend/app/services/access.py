"""Which documents a caller may see, as a retrieval filter.

  owner/admin users, secret API keys     everything
  members                                General + tenant-visible collections
                                         + restricted collections granted to their groups
  publishable (widget) key, scoped       only its collection
  publishable (widget) key, unscoped     General + tenant-visible collections

The same scope filters retrieval, document listing and reads, and is part of
the answer-cache key so one user's cached answer never reaches someone who
cannot see its sources.
"""

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DOCUMENT_WRITER_ROLES, KIND_PUBLISHABLE_KEY, KIND_SECRET_KEY, Principal
from app.models.access import VISIBILITY_TENANT, Collection, CollectionAccess, GroupMember
from app.models.api_key import ApiKey


@dataclass(frozen=True)
class AccessScope:
    all_documents: bool
    include_general: bool = True
    collection_ids: frozenset[str] = frozenset()

    @classmethod
    def everything(cls) -> "AccessScope":
        return cls(all_documents=True)

    def can_see(self, collection_id) -> bool:
        if self.all_documents:
            return True
        if collection_id is None:
            return self.include_general
        return str(collection_id) in self.collection_ids

    def narrow(self, requested: list[str] | None) -> "AccessScope":
        """Restrict to collections the caller asked for (a "search only HR" filter)."""
        if not requested:
            return self
        wanted = {str(c) for c in requested}
        general = "general" in wanted
        wanted.discard("general")
        allowed = wanted if self.all_documents else wanted & set(self.collection_ids)
        return AccessScope(
            all_documents=False,
            include_general=general and (self.all_documents or self.include_general),
            collection_ids=frozenset(allowed),
        )

    def digest(self) -> str:
        if self.all_documents:
            return "all"
        raw = f"g{int(self.include_general)}|" + ",".join(sorted(self.collection_ids))
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def sql_filter(self, column: str = "collection_id") -> tuple[str, dict]:
        """SQL fragment + bind params. Only generated bind names are interpolated."""
        if self.all_documents:
            return "TRUE", {}
        clauses, params = [], {}
        if self.include_general:
            clauses.append(f"{column} IS NULL")
        for i, cid in enumerate(sorted(self.collection_ids)):
            params[f"scope_c{i}"] = cid
        if params:
            clauses.append(f"{column} IN ({', '.join(f'CAST(:{k} AS uuid)' for k in params)})")
        return ("(" + " OR ".join(clauses) + ")") if clauses else "FALSE", params

    def orm_filter(self, column):
        if self.all_documents:
            return True
        conditions = []
        if self.include_general:
            conditions.append(column.is_(None))
        if self.collection_ids:
            conditions.append(column.in_([uuid.UUID(c) for c in self.collection_ids]))
        return or_(*conditions) if conditions else False


async def _tenant_visible_collections(db: AsyncSession, tenant_id) -> set[str]:
    rows = await db.execute(
        select(Collection.id).where(Collection.tenant_id == tenant_id, Collection.visibility == VISIBILITY_TENANT)
    )
    return {str(r) for r in rows.scalars().all()}


async def resolve_scope(db: AsyncSession, principal: Principal) -> AccessScope:
    tenant_id = principal.tenant.id
    if principal.kind == KIND_SECRET_KEY:
        return AccessScope.everything()
    if principal.user is not None and principal.user.role in DOCUMENT_WRITER_ROLES:
        return AccessScope.everything()

    if principal.kind == KIND_PUBLISHABLE_KEY:
        key = await db.get(ApiKey, principal.api_key_id) if principal.api_key_id else None
        if key is not None and key.collection_id is not None:
            return AccessScope(all_documents=False, include_general=False, collection_ids=frozenset({str(key.collection_id)}))
        return AccessScope(all_documents=False, collection_ids=frozenset(await _tenant_visible_collections(db, tenant_id)))

    visible = await _tenant_visible_collections(db, tenant_id)
    granted = await db.execute(
        select(CollectionAccess.collection_id)
        .join(GroupMember, GroupMember.group_id == CollectionAccess.group_id)
        .where(GroupMember.user_id == principal.user_id, CollectionAccess.tenant_id == tenant_id)
    )
    visible |= {str(r) for r in granted.scalars().all()}
    return AccessScope(all_documents=False, collection_ids=frozenset(visible))
