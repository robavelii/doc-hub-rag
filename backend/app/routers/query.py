import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_tenant
from app.middleware.rate_limiter import rate_limit
from app.models.conversation import ConversationMessage
from app.models.tenant import Tenant
from app.routers.conversations import persist_conversation_messages
from app.services.query_service import complete_rag_query, run_rag_query, stream_rag_query
from app.services.usage_service import check_query_limit

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    question: str
    conversation_id: str | None = None


async def _load_conversation_history(
    db: AsyncSession, tenant_id: str, conversation_id: str | None
) -> list[dict]:
    if not conversation_id:
        return []
    result = await db.execute(
        select(ConversationMessage)
        .where(
            ConversationMessage.tenant_id == uuid.UUID(tenant_id),
            ConversationMessage.conversation_id == uuid.UUID(conversation_id),
        )
        .order_by(ConversationMessage.created_at)
        .limit(20)
    )
    messages = result.scalars().all()
    return [{"role": m.role, "content": m.content} for m in messages]


@router.post("")
async def query(
    body: QueryRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit("query")),
):
    await check_query_limit(tenant, db)
    history = await _load_conversation_history(db, str(tenant.id), body.conversation_id)
    context = await run_rag_query(body.question, str(tenant.id), db, history)
    result = await complete_rag_query(context, str(tenant.id), db)

    convo_id = await persist_conversation_messages(
        db,
        str(tenant.id),
        body.conversation_id,
        body.question,
        result.get("answer", ""),
        result.get("sources", []),
        {
            "confidence": result.get("confidence"),
            "tokens_total": result.get("tokens_total"),
            "latency_ms": result.get("latency_ms"),
        },
        result.get("query_log_id"),
    )
    result["conversation_id"] = convo_id
    return result


@router.post("/stream")
async def query_stream(
    body: QueryRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit("query")),
):
    await check_query_limit(tenant, db)
    history = await _load_conversation_history(db, str(tenant.id), body.conversation_id)

    async def event_generator():
        full_answer = ""
        async for chunk in stream_rag_query(
            body.question,
            str(tenant.id),
            db,
            history,
            conversation_id=body.conversation_id,
        ):
            if chunk.startswith("data: "):
                data = json.loads(chunk[6:].strip())
                if data.get("type") == "chunk":
                    full_answer += data.get("content", "")
                    yield chunk
                elif data.get("type") == "done":
                    convo_id = await persist_conversation_messages(
                        db,
                        str(tenant.id),
                        body.conversation_id,
                        body.question,
                        full_answer,
                        data.get("sources", []),
                        {
                            "confidence": data.get("confidence"),
                            "tokens_total": data.get("tokens_total"),
                            "latency_ms": data.get("latency_ms"),
                        },
                        data.get("query_log_id"),
                    )
                    data["conversation_id"] = convo_id
                    yield f"data: {json.dumps(data)}\n\n"
                else:
                    yield chunk
            else:
                yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
