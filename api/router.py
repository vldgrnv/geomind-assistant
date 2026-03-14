from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from auth.jwt import get_current_user_id
from database.models import (
    get_stats, create_chat, get_chats,
    add_message, get_messages, count_requests, get_user_by_id,
    update_plan, PLAN_LIMITS, delete_chat, rename_chat,
)
from AI_service.main import handle

router = APIRouter(prefix="/api", tags=["api"])


class AskRequest(BaseModel):
    query: str
    chat_id: Optional[int] = None


class AskResponse(BaseModel):
    answer: str
    chat_id: int


class PlanRequest(BaseModel):
    plan: str


@router.post("/ask", response_model=AskResponse)
def ask_endpoint(req: AskRequest, user_id: int = Depends(get_current_user_id)):
    user = get_user_by_id(user_id)
    month_count = count_requests(user_id, 30)
    if month_count >= user["requests_limit"]:
        raise HTTPException(403, "Лимит запросов исчерпан. Обновите тариф.")

    chat_id = req.chat_id or create_chat(user_id)
    add_message(chat_id, "user", req.query)

    answer = handle(req.query)
    add_message(chat_id, "assistant", answer)

    return AskResponse(answer=answer, chat_id=chat_id)


@router.post("/plan")
def plan_endpoint(req: PlanRequest, user_id: int = Depends(get_current_user_id)):
    if req.plan not in PLAN_LIMITS:
        raise HTTPException(400, "Неизвестный план")
    update_plan(user_id, req.plan)
    return {"ok": True, "plan": req.plan}


@router.get("/chats")
def chats_endpoint(user_id: int = Depends(get_current_user_id)):
    return get_chats(user_id)


@router.get("/chats/{chat_id}/messages")
def messages_endpoint(chat_id: int, user_id: int = Depends(get_current_user_id)):
    return get_messages(chat_id)


@router.delete("/chats/{chat_id}")
def delete_chat_endpoint(chat_id: int, user_id: int = Depends(get_current_user_id)):
    ok = delete_chat(chat_id, user_id)
    if not ok:
        raise HTTPException(404, "Чат не найден")
    return {"ok": True}


class RenameRequest(BaseModel):
    title: str


@router.patch("/chats/{chat_id}")
def rename_chat_endpoint(chat_id: int, req: RenameRequest, user_id: int = Depends(get_current_user_id)):
    ok = rename_chat(chat_id, user_id, req.title)
    if not ok:
        raise HTTPException(404, "Чат не найден")
    return {"ok": True}


@router.get("/stats")
def stats_endpoint(user_id: int = Depends(get_current_user_id)):
    return get_stats(user_id)
