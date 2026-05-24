import logging
import re
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from auth.jwt import get_current_user_id
from database.models import (
    get_stats, create_chat, get_chats,
    add_message, get_user_by_id, get_chat_for_user, get_usage_snapshot,
    update_plan, PLAN_LIMITS, delete_chat, rename_chat, get_messages_for_user,
    create_bug_report, create_contact_request,
    is_admin_user, get_admin_overview, get_admin_users, get_admin_bug_reports,
    get_admin_contact_requests, get_admin_recent_chats, get_admin_recent_messages,
)
from database.db import get_db
from AI_service.main import handle
from conversion.options import build_options_payload

router = APIRouter(prefix="/api", tags=["api"])
logger = logging.getLogger("geomind.api")


class AskRequest(BaseModel):
    query: str
    chat_id: Optional[int] = None


class AskResponse(BaseModel):
    answer: str
    chat_id: int


class PlanRequest(BaseModel):
    plan: str


class BugReportRequest(BaseModel):
    text: str
    chat_id: Optional[int] = None
    page_url: Optional[str] = None


class ContactRequest(BaseModel):
    email: str
    text: str
    page_url: Optional[str] = None


def require_admin(user_id: int):
    if not is_admin_user(user_id):
        raise HTTPException(403, "Недостаточно прав")


@router.post("/ask", response_model=AskResponse)
def ask_endpoint(req: AskRequest, user_id: int = Depends(get_current_user_id)):
    started_at = time.perf_counter()
    with get_db() as conn:
        user = get_user_by_id(user_id, conn=conn)
        if not user:
            raise HTTPException(401, "Пользователь не найден")

        usage = get_usage_snapshot(user_id, conn=conn)
        if usage and usage["requests_30d"] >= user["requests_limit"]:
            raise HTTPException(403, "Лимит запросов исчерпан. Обновите тариф.")

        if req.chat_id is not None:
            chat = get_chat_for_user(req.chat_id, user_id, conn=conn)
            if not chat:
                raise HTTPException(404, "Чат не найден")
            chat_id = req.chat_id
        else:
            chat_id = create_chat(user_id, conn=conn)
        add_message(chat_id, "user", req.query, conn=conn)

    try:
        ai_started_at = time.perf_counter()
        answer = handle(req.query)
        ai_duration_ms = (time.perf_counter() - ai_started_at) * 1000
    except RuntimeError:
        ai_duration_ms = (time.perf_counter() - ai_started_at) * 1000
        answer = (
            "Сервис генерации ответа временно недоступен. "
            "Попробуйте повторить запрос чуть позже."
        )
    except Exception as exc:
        raise HTTPException(500, "Внутренняя ошибка обработки запроса") from exc

    with get_db() as conn:
        add_message(chat_id, "assistant", answer, conn=conn)

    total_duration_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "ask_completed user_id=%s chat_id=%s query_len=%s ai_duration_ms=%.2f total_duration_ms=%.2f",
        user_id,
        chat_id,
        len(req.query),
        ai_duration_ms,
        total_duration_ms,
    )
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


@router.get("/bootstrap")
def bootstrap_endpoint(user_id: int = Depends(get_current_user_id)):
    with get_db() as conn:
        user = get_user_by_id(user_id, conn=conn)
        if not user:
            raise HTTPException(404, "Пользователь не найден")

        stats = get_stats(user_id, conn=conn)
        if not stats:
            raise HTTPException(404, "Пользователь не найден")

        chats = get_chats(user_id, conn=conn)

    return {
        "me": {
            "id": user["id"],
            "email": user["email"],
            "plan": user["plan"],
            "is_admin": is_admin_user(user_id),
        },
        "stats": stats,
        "chats": chats,
        "convert_options": build_options_payload(),
    }


@router.get("/chats/{chat_id}/messages")
def messages_endpoint(chat_id: int, user_id: int = Depends(get_current_user_id)):
    messages = get_messages_for_user(chat_id, user_id)
    if messages is None:
        raise HTTPException(404, "Чат не найден")
    return messages


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


@router.post("/bug-reports")
def bug_reports_endpoint(
    req: BugReportRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
):
    text = req.text.strip()
    if len(text) < 5:
        raise HTTPException(400, "Опишите проблему чуть подробнее")
    if len(text) > 2000:
        raise HTTPException(400, "Сообщение слишком длинное")

    if req.chat_id is not None and not get_chat_for_user(req.chat_id, user_id):
        raise HTTPException(404, "Чат не найден")

    report_id = create_bug_report(
        user_id=user_id,
        chat_id=req.chat_id,
        text=text,
        page_url=(req.page_url or "")[:1000] or None,
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
    )
    return {"ok": True, "id": report_id}


@router.post("/contact-requests")
def contact_requests_endpoint(req: ContactRequest, request: Request):
    email = req.email.strip()
    text = req.text.strip()

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(400, "Укажите корректную электронную почту")
    if len(email) > 254:
        raise HTTPException(400, "Электронная почта слишком длинная")
    if len(text) < 5:
        raise HTTPException(400, "Опишите запрос чуть подробнее")
    if len(text) > 3000:
        raise HTTPException(400, "Сообщение слишком длинное")

    request_id = create_contact_request(
        email=email,
        text=text,
        page_url=(req.page_url or "")[:1000] or None,
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
    )
    logger.info("contact_request_created id=%s email=%s text_len=%s", request_id, email, len(text))
    return {"ok": True, "id": request_id}


@router.get("/me")
def me_endpoint(user_id: int = Depends(get_current_user_id)):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    return {
        "id": user["id"],
        "email": user["email"],
        "plan": user["plan"],
        "is_admin": is_admin_user(user_id),
    }


@router.get("/admin/dashboard")
def admin_dashboard_endpoint(user_id: int = Depends(get_current_user_id)):
    require_admin(user_id)
    return {
        "overview": get_admin_overview(),
        "users": get_admin_users(),
        "bug_reports": get_admin_bug_reports(),
        "contact_requests": get_admin_contact_requests(),
        "recent_chats": get_admin_recent_chats(),
        "recent_messages": get_admin_recent_messages(),
    }


@router.get("/stats")
def stats_endpoint(user_id: int = Depends(get_current_user_id)):
    stats = get_stats(user_id)
    if not stats:
        raise HTTPException(404, "Пользователь не найден")
    return stats
