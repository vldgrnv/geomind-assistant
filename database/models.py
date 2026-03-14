import os
from database.db import get_conn
from datetime import datetime, timedelta

PLAN_LIMITS = {
    "free": int(os.environ.get("PLAN_LIMIT_FREE", 10)),
    "basic": int(os.environ.get("PLAN_LIMIT_BASIC", 100)),
    "pro": int(os.environ.get("PLAN_LIMIT_PRO", 999999)),
}


def update_plan(user_id, plan):
    limit = PLAN_LIMITS.get(plan, 10)
    conn = get_conn()
    conn.execute(
        "UPDATE users SET plan = ?, requests_limit = ? WHERE id = ?",
        (plan, limit, user_id),
    )
    conn.commit()
    conn.close()


def delete_chat(chat_id, user_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id)
    ).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn.commit()
    conn.close()
    return True



def create_user(email, password_hash):
    conn = get_conn()
    conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        (email, password_hash),
    )
    conn.commit()
    user_id = conn.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()["id"]
    conn.close()
    return user_id


def get_user_by_email(email):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------- Чаты ----------

def create_chat(user_id, title="Новый чат"):
    conn = get_conn()
    conn.execute("INSERT INTO chats (user_id, title) VALUES (?, ?)", (user_id, title))
    conn.commit()
    chat_id = conn.execute(
        "SELECT last_insert_rowid() as id"
    ).fetchone()["id"]
    conn.close()
    return chat_id


def get_chats(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, title, created_at FROM chats WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def rename_chat(chat_id, user_id, title):
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id)
    ).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))
    conn.commit()
    conn.close()
    return True


# ---------- Сообщения ----------

def add_message(chat_id, role, text):
    conn = get_conn()
    conn.execute(
        "INSERT INTO messages (chat_id, role, text) VALUES (?, ?, ?)",
        (chat_id, role, text),
    )
    conn.commit()
    conn.close()


def get_messages(chat_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, text, created_at FROM messages WHERE chat_id = ? ORDER BY created_at",
        (chat_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Статистика запросов ----------

def count_requests(user_id, days):
    conn = get_conn()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM messages m
           JOIN chats c ON m.chat_id = c.id
           WHERE c.user_id = ? AND m.role = 'user' AND m.created_at >= ?""",
        (user_id, since),
    ).fetchone()
    conn.close()
    return row["cnt"]


def get_stats(user_id):
    user = get_user_by_id(user_id)
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
