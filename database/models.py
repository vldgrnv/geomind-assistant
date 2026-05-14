import os
from database.db import get_db

PLAN_LIMITS = {
    "free": int(os.environ.get("PLAN_LIMIT_FREE", 10)),
    "basic": int(os.environ.get("PLAN_LIMIT_BASIC", 100)),
    "pro": int(os.environ.get("PLAN_LIMIT_PRO", 999999)),
}


def _fetchone(query, params=()):
    with get_db() as conn:
        row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def _fetchall(query, params=()):
    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def _execute(query, params=()):
    with get_db() as conn:
        conn.execute(query, params)


def update_plan(user_id, plan):
    limit = PLAN_LIMITS.get(plan, 10)
    _execute(
        "UPDATE users SET plan = ?, requests_limit = ? WHERE id = ?",
        (plan, limit, user_id),
    )


def delete_chat(chat_id, user_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id)
        ).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        return True

def create_user(email, password_hash):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash),
        )
        return cur.lastrowid


def get_user_by_email(email):
    return _fetchone("SELECT * FROM users WHERE email = ?", (email,))


def get_user_by_id(user_id):
    return _fetchone("SELECT * FROM users WHERE id = ?", (user_id,))


def update_user_password_hash(user_id, password_hash):
    _execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (password_hash, user_id),
    )


# ---------- Чаты ----------

def create_chat(user_id, title="Новый чат"):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO chats (user_id, title) VALUES (?, ?)",
            (user_id, title),
        )
        return cur.lastrowid


def get_chats(user_id):
    return _fetchall(
        "SELECT id, title, created_at FROM chats WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )


def get_chat_for_user(chat_id, user_id):
    return _fetchone(
        "SELECT id, user_id, title, created_at FROM chats WHERE id = ? AND user_id = ?",
        (chat_id, user_id),
    )


def rename_chat(chat_id, user_id, title):
    if not get_chat_for_user(chat_id, user_id):
        return False
    _execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))
    return True


# ---------- Сообщения ----------

def add_message(chat_id, role, text):
    _execute(
        "INSERT INTO messages (chat_id, role, text) VALUES (?, ?, ?)",
        (chat_id, role, text),
    )


def get_messages_for_user(chat_id, user_id):
    if not get_chat_for_user(chat_id, user_id):
        return None
    return _fetchall(
        "SELECT role, text, created_at FROM messages WHERE chat_id = ? ORDER BY created_at",
        (chat_id,),
    )


# ---------- Статистика запросов ----------

def count_requests(user_id, days):
    row = _fetchone(
        """SELECT COUNT(*) as cnt FROM messages m
           JOIN chats c ON m.chat_id = c.id
           WHERE c.user_id = ? AND m.role = 'user'
             AND m.created_at >= datetime('now', ?)""",
        (user_id, f"-{days} days"),
    )
    return row["cnt"] if row else 0


def get_stats(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return None
    today = count_requests(user_id, 1)
    week = count_requests(user_id, 7)
    month = count_requests(user_id, 30)
    return {
        "today": today,
        "week": week,
        "month": month,
        "limit": user["requests_limit"],
        "remaining": max(0, user["requests_limit"] - month),
        "plan": user["plan"],
    }
