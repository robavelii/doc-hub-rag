import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_tenant
from app.models.conversation import Conversation, ConversationMessage
from app.models.tenant import Tenant

router = APIRouter(prefix="/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    title: str | None = None


class UpdateConversationRequest(BaseModel):
    title: str


def _auto_title(first_message: str) -> str:
    title = first_message.strip()[:60]
    return title if title else "New conversation"


@router.get("")
async def list_conversations(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.tenant_id == tenant.id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    convos = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in convos
    ]


@router.post("")
async def create_conversation(
    body: CreateConversationRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    convo = Conversation(
        tenant_id=tenant.id,
        title=body.title or "New conversation",
    )
    db.add(convo)
    await db.commit()
    await db.refresh(convo)
    return {
        "id": str(convo.id),
        "title": convo.title,
        "created_at": convo.created_at.isoformat() if convo.created_at else None,
    }


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    convo = await db.get(Conversation, uuid.UUID(conversation_id))
    if not convo or str(convo.tenant_id) != str(tenant.id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == convo.id)
        .order_by(ConversationMessage.created_at)
    )
    messages = result.scalars().all()
    return {
        "id": str(convo.id),
        "title": convo.title,
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "sources": m.sources or [],
                "metrics": m.metrics or {},
                "query_log_id": str(m.query_log_id) if m.query_log_id else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    body: UpdateConversationRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    convo = await db.get(Conversation, uuid.UUID(conversation_id))
    if not convo or str(convo.tenant_id) != str(tenant.id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    convo.title = body.title.strip()[:120] or "New conversation"
    convo.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {
        "id": str(convo.id),
        "title": convo.title,
        "updated_at": convo.updated_at.isoformat() if convo.updated_at else None,
    }


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    convo = await db.get(Conversation, uuid.UUID(conversation_id))
    if not convo or str(convo.tenant_id) != str(tenant.id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(convo)
    await db.commit()
    return {"ok": True}


async def persist_conversation_messages(
    db: AsyncSession,
    tenant_id: str,
    conversation_id: str | None,
    question: str,
    answer: str,
    sources: list,
    metrics: dict,
    query_log_id: str | None,
) -> str:
    from app.database import set_tenant_rls

    await set_tenant_rls(db, tenant_id)
    convo_id: uuid.UUID
    if conversation_id:
        convo = await db.get(Conversation, uuid.UUID(conversation_id))
        if not convo or str(convo.tenant_id) != tenant_id:
            convo = None
        if convo:
            convo_id = convo.id
            count_result = await db.execute(
                select(func.count()).select_from(ConversationMessage).where(
                    ConversationMessage.conversation_id == convo_id
                )
            )
            if (count_result.scalar() or 0) == 0:
                convo.title = _auto_title(question)
            convo.updated_at = datetime.now(timezone.utc)
        else:
            convo = Conversation(tenant_id=uuid.UUID(tenant_id), title=_auto_title(question))
            db.add(convo)
            await db.flush()
            convo_id = convo.id
    else:
        convo = Conversation(tenant_id=uuid.UUID(tenant_id), title=_auto_title(question))
        db.add(convo)
        await db.flush()
        convo_id = convo.id

    user_msg = ConversationMessage(
        conversation_id=convo_id,
        tenant_id=uuid.UUID(tenant_id),
        role="user",
        content=question,
    )
    assistant_msg = ConversationMessage(
        conversation_id=convo_id,
        tenant_id=uuid.UUID(tenant_id),
        role="assistant",
        content=answer,
        sources=sources,
        metrics=metrics,
        query_log_id=uuid.UUID(query_log_id) if query_log_id else None,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.commit()
    return str(convo_id)
