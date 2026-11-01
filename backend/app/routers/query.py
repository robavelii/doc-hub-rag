import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import KIND_PUBLISHABLE_KEY, Principal, get_query_principal
from app.middleware.rate_limiter import rate_limit
from app.models.conversation import ConversationMessage
from app.routers.conversations import get_owned_conversation, persist_conversation_messages
from app.services.query_service import complete_rag_query, run_rag_query, stream_rag_query
from app.services.usage_service import check_query_limit

router = APIRouter(prefix="/query", tags=["query"])

HISTORY_MESSAGE_LIMIT = 20


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


def _keeps_conversations(principal: Principal) -> bool:
    # Widget visitors are anonymous: nothing is read from or written to stored conversations.
    return principal.kind != KIND_PUBLISHABLE_KEY


async def _load_conversation_history(
    db: AsyncSession, principal: Principal, conversation_id: str | None
) -> list[dict]:
    if not _keeps_conversations(principal):
        return []
    convo = await get_owned_conversation(db, principal, conversation_id)
    if not convo:
        return []
    # Most recent N messages, returned oldest first.
    result = await db.execute(
        select(ConversationMessage)
        .where(
            ConversationMessage.tenant_id == principal.tenant.id,
            ConversationMessage.conversation_id == convo.id,
        )
        .order_by(ConversationMessage.created_at.desc())
        .limit(HISTORY_MESSAGE_LIMIT)
    )
    messages = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in messages]


def _metrics(payload: dict) -> dict:
    return {
        "confidence": payload.get("confidence"),
        "tokens_total": payload.get("tokens_total"),
        "latency_ms": payload.get("latency_ms"),
    }


@router.post("")
async def query(
    body: QueryRequest,
    principal: Principal = Depends(get_query_principal),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit("query")),
):
    tenant = principal.tenant
    await check_query_limit(tenant, db)
    history = await _load_conversation_history(db, principal, body.conversation_id)
    context = await run_rag_query(body.question, str(tenant.id), db, history)
    result = await complete_rag_query(context, str(tenant.id), db)

    convo_id = None
    if _keeps_conversations(principal):
        convo_id = await persist_conversation_messages(
            db,
            principal,
            body.conversation_id,
            body.question,
            result.get("answer", ""),
            result.get("sources", []),
            _metrics(result),
            result.get("query_log_id"),
        )
    result["conversation_id"] = convo_id
    return result


@router.post("/stream")
async def query_stream(
    body: QueryRequest,
    principal: Principal = Depends(get_query_principal),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit("query")),
):
    tenant = principal.tenant
    await check_query_limit(tenant, db)
    history = await _load_conversation_history(db, principal, body.conversation_id)

    async def event_generator():
        full_answer = ""
        async for chunk in stream_rag_query(body.question, str(tenant.id), db, history):
            if not chunk.startswith("data: "):
                yield chunk
                continue
            data = json.loads(chunk[6:].strip())
            if data.get("type") == "chunk":
                full_answer += data.get("content", "")
                yield chunk
            elif data.get("type") == "done":
                convo_id = None
                if _keeps_conversations(principal):
                    convo_id = await persist_conversation_messages(
                        db,
                        principal,
                        body.conversation_id,
                        body.question,
                        full_answer,
                        data.get("sources", []),
                        _metrics(data),
                        data.get("query_log_id"),
                    )
                data["conversation_id"] = convo_id
                yield f"data: {json.dumps(data)}\n\n"
            else:
                yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
