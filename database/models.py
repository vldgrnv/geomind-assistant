import os
from database.db import get_db

ROLLING_WINDOW_DAYS = 30

PLAN_LIMITS = {
    "free": int(os.environ.get("PLAN_LIMIT_FREE", 10)),
    "basic": int(os.environ.get("PLAN_LIMIT_BASIC", 100)),
    "pro": int(os.environ.get("PLAN_LIMIT_PRO", 999999)),
}


def _fetchone(query, params=(), conn=None):
    if conn is not None:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None
    with get_db() as local_conn:
        row = local_conn.execute(query, params).fetchone()
    return dict(row) if row else None


def _fetchall(query, params=(), conn=None):
    if conn is not None:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    with get_db() as local_conn:
        rows = local_conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def _execute(query, params=(), conn=None):
    if conn is not None:
        conn.execute(query, params)
        return
    with get_db() as local_conn:
        local_conn.execute(query, params)


def update_plan(user_id, plan, conn=None):
    limit = PLAN_LIMITS.get(plan, 10)
    _execute(
        "UPDATE users SET plan = ?, requests_limit = ? WHERE id = ?",
        (plan, limit, user_id),
        conn=conn,
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

def create_user(email, password_hash, conn=None):
    if conn is not None:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash),
        )
        return cur.lastrowid
    with get_db() as local_conn:
        cur = local_conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash),
        )
        return cur.lastrowid


def get_user_by_email(email, conn=None):
    return _fetchone("SELECT * FROM users WHERE email = ?", (email,), conn=conn)


def get_user_by_id(user_id, conn=None):
    return _fetchone("SELECT * FROM users WHERE id = ?", (user_id,), conn=conn)


def is_admin_user(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return False
    admin_emails = {
        email.strip().lower()
        for email in os.environ.get("ADMIN_EMAILS", "").split(",")
        if email.strip()
    }
    return bool(admin_emails) and user["email"].strip().lower() in admin_emails


def update_user_password_hash(user_id, password_hash, conn=None):
    _execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (password_hash, user_id),
        conn=conn,
    )


# ---------- Чаты ----------

def create_chat(user_id, title="Новый чат", conn=None):
    if conn is not None:
        cur = conn.execute(
            "INSERT INTO chats (user_id, title) VALUES (?, ?)",
            (user_id, title),
        )
        return cur.lastrowid
    with get_db() as local_conn:
        cur = local_conn.execute(
            "INSERT INTO chats (user_id, title) VALUES (?, ?)",
            (user_id, title),
        )
        return cur.lastrowid


def get_chats(user_id, conn=None):
    return _fetchall(
        "SELECT id, title, created_at FROM chats WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
        conn=conn,
    )


def get_chat_for_user(chat_id, user_id, conn=None):
    return _fetchone(
        "SELECT id, user_id, title, created_at FROM chats WHERE id = ? AND user_id = ?",
        (chat_id, user_id),
        conn=conn,
    )


def rename_chat(chat_id, user_id, title, conn=None):
    if not get_chat_for_user(chat_id, user_id, conn=conn):
        return False
    _execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id), conn=conn)
    return True


# ---------- Сообщения ----------

def add_message(chat_id, role, text, conn=None):
    _execute(
        "INSERT INTO messages (chat_id, role, text) VALUES (?, ?, ?)",
        (chat_id, role, text),
        conn=conn,
    )


def create_bug_report(user_id, text, chat_id=None, page_url=None, user_agent=None):
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO bug_reports (user_id, chat_id, text, page_url, user_agent)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, chat_id, text, page_url, user_agent),
        )
        return cur.lastrowid


def create_contact_request(email, text, page_url=None, user_agent=None):
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO contact_requests (email, text, page_url, user_agent)
            VALUES (?, ?, ?, ?)
            """,
            (email, text, page_url, user_agent),
        )
        return cur.lastrowid


def get_messages_for_user(chat_id, user_id, conn=None):
    if not get_chat_for_user(chat_id, user_id, conn=conn):
        return None
    return _fetchall(
        "SELECT role, text, created_at FROM messages WHERE chat_id = ? ORDER BY created_at",
        (chat_id,),
        conn=conn,
    )


# ---------- Статистика запросов ----------

def get_usage_snapshot(user_id, conn=None):
    row = _fetchone(
        """
        SELECT
            u.id,
            u.plan,
            u.requests_limit,
            COALESCE(COUNT(m.id), 0) AS requests_30d
        FROM users u
        LEFT JOIN chats c ON c.user_id = u.id
        LEFT JOIN messages m
            ON m.chat_id = c.id
           AND m.role = 'user'
           AND m.created_at >= datetime('now', ?)
        WHERE u.id = ?
        GROUP BY u.id, u.plan, u.requests_limit
        """,
        (f"-{ROLLING_WINDOW_DAYS} days", user_id),
        conn=conn,
    )
    if not row:
        return None
    requests_30d = row["requests_30d"]
    return {
        "plan": row["plan"],
        "limit": row["requests_limit"],
        "requests_30d": requests_30d,
        "remaining": max(0, row["requests_limit"] - requests_30d),
    }


def get_stats(user_id, conn=None):
    snapshot = get_usage_snapshot(user_id, conn=conn)
    if not snapshot:
        return None
    return {
        "window_days": ROLLING_WINDOW_DAYS,
        "requests_30d": snapshot["requests_30d"],
        "limit": snapshot["limit"],
        "remaining": snapshot["remaining"],
        "plan": snapshot["plan"],
    }


def get_admin_overview():
    with get_db() as conn:
        users_total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        chats_total = conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
        messages_total = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE role = 'user'"
        ).fetchone()[0]
        bug_reports_total = conn.execute("SELECT COUNT(*) FROM bug_reports").fetchone()[0]
        contact_requests_total = conn.execute("SELECT COUNT(*) FROM contact_requests").fetchone()[0]
        requests_today = conn.execute(
            """
            SELECT COUNT(*) FROM messages
            WHERE role = 'assistant' AND created_at >= datetime('now', '-1 day')
            """
        ).fetchone()[0]
        requests_month = conn.execute(
            """
            SELECT COUNT(*) FROM messages
            WHERE role = 'assistant' AND created_at >= datetime('now', '-30 days')
            """
        ).fetchone()[0]
        active_users_month = conn.execute(
            """
            SELECT COUNT(DISTINCT c.user_id)
            FROM messages m
            JOIN chats c ON c.id = m.chat_id
            WHERE m.role = 'user' AND m.created_at >= datetime('now', '-30 days')
            """
        ).fetchone()[0]
    return {
        "users_total": users_total,
        "chats_total": chats_total,
        "messages_total": messages_total,
        "bug_reports_total": bug_reports_total,
        "contact_requests_total": contact_requests_total,
        "requests_today": requests_today,
        "requests_30d": requests_month,
        "active_users_30d": active_users_month,
    }


def get_admin_users():
    return _fetchall(
        """
        WITH user_stats AS (
            SELECT
                u.id,
                u.email,
                u.plan,
                u.requests_limit,
                u.created_at,
                COUNT(DISTINCT c.id) AS chats_count,
                COUNT(DISTINCT m.id) AS messages_count,
                COUNT(DISTINCT CASE
                    WHEN m.role = 'user'
                     AND m.created_at >= datetime('now', '-30 days')
                    THEN m.id
                END) AS requests_30d,
                COUNT(DISTINCT br.id) AS bug_reports_count,
                MAX(m.created_at) AS last_message_at
            FROM users u
            LEFT JOIN chats c ON c.user_id = u.id
            LEFT JOIN messages m ON m.chat_id = c.id
            LEFT JOIN bug_reports br ON br.user_id = u.id
            GROUP BY u.id, u.email, u.plan, u.requests_limit, u.created_at
        )
        SELECT
            *,
            CASE
                WHEN requests_limit - requests_30d < 0 THEN 0
                ELSE requests_limit - requests_30d
            END AS requests_remaining
        FROM user_stats
        ORDER BY requests_30d DESC, messages_count DESC, created_at DESC
        """
    )


def get_admin_bug_reports(limit=100):
    return _fetchall(
        """
        SELECT
            br.id,
            br.user_id,
            u.email,
            br.chat_id,
            br.text,
            br.page_url,
            br.user_agent,
            br.created_at
        FROM bug_reports br
        JOIN users u ON u.id = br.user_id
        ORDER BY br.created_at DESC
        LIMIT ?
        """,
        (limit,),
    )


def get_admin_contact_requests(limit=100):
    return _fetchall(
        """
        SELECT id, email, text, page_url, user_agent, created_at
        FROM contact_requests
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )


def get_admin_recent_chats(limit=100):
    return _fetchall(
        """
        SELECT
            c.id,
            c.user_id,
            u.email,
            c.title,
            c.created_at,
            COUNT(CASE WHEN m.role = 'user' THEN m.id END) AS messages_count
        FROM chats c
        JOIN users u ON u.id = c.user_id
        LEFT JOIN messages m ON m.chat_id = c.id
        GROUP BY c.id, c.user_id, u.email, c.title, c.created_at
        ORDER BY c.created_at DESC
        LIMIT ?
        """,
        (limit,),
    )


def get_admin_recent_messages(limit=100):
    return _fetchall(
        """
        SELECT
            m.id,
            m.chat_id,
            c.user_id,
            u.email,
            c.title AS chat_title,
            m.role,
            m.text,
            m.created_at
        FROM messages m
        JOIN chats c ON c.id = m.chat_id
        JOIN users u ON u.id = c.user_id
        ORDER BY m.created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
