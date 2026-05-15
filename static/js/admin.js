const API = '';
const token = localStorage.getItem('token');

if (!token) {
    window.location.href = '/static/login.html?next=/admin';
}

const headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + token,
};

const statsGrid = document.getElementById('admin-stats-grid');
const usersTableBody = document.querySelector('#admin-users-table tbody');
const chatsTableBody = document.querySelector('#admin-chats-table tbody');
const messagesTableBody = document.querySelector('#admin-messages-table tbody');
const bugReportsContainer = document.getElementById('admin-bug-reports');
const logoutBtn = document.getElementById('admin-logout-btn');

function escapeHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatDate(value) {
    if (!value) return '—';
    return value.replace('T', ' ').slice(0, 19);
}

function truncate(text, limit = 160) {
    const value = String(text ?? '');
    return value.length > limit ? value.slice(0, limit - 1) + '…' : value;
}

function renderOverview(overview) {
    const cards = [
        ['Пользователи', overview.users_total],
        ['Чаты', overview.chats_total],
        ['Сообщения', overview.messages_total],
        ['Ошибки', overview.bug_reports_total],
        ['Запросы за 30 дней', overview.requests_30d],
        ['Активные юзеры за 30 дней', overview.active_users_30d],
    ];

    statsGrid.innerHTML = cards.map(([label, value]) => `
        <article class="admin-stat-card">
            <div class="admin-stat-value">${escapeHtml(value)}</div>
            <div class="admin-stat-label">${escapeHtml(label)}</div>
        </article>
    `).join('');
}

function renderUsers(users) {
    usersTableBody.innerHTML = users.map((user) => `
        <tr>
            <td>${user.id}</td>
            <td>${escapeHtml(user.email)}</td>
            <td>${escapeHtml(user.plan)}</td>
            <td>${user.requests_remaining ?? Math.max(0, user.requests_limit - user.requests_30d)}</td>
            <td>${user.chats_count}</td>
            <td>${user.messages_count}</td>
            <td>${user.requests_30d}</td>
            <td>${user.bug_reports_count}</td>
            <td>${escapeHtml(formatDate(user.last_message_at))}</td>
            <td>${escapeHtml(formatDate(user.created_at))}</td>
        </tr>
    `).join('');
}

function renderChats(chats) {
    chatsTableBody.innerHTML = chats.map((chat) => `
        <tr>
            <td>${chat.id}</td>
            <td>${escapeHtml(chat.email)}</td>
            <td title="${escapeHtml(chat.title)}">${escapeHtml(truncate(chat.title, 40))}</td>
            <td>${chat.messages_count}</td>
            <td>${escapeHtml(formatDate(chat.created_at))}</td>
        </tr>
    `).join('');
}

function renderMessages(messages) {
    messagesTableBody.innerHTML = messages.map((message) => `
        <tr>
            <td>${message.id}</td>
            <td>${escapeHtml(message.email)}</td>
            <td title="${escapeHtml(message.chat_title || '')}">#${message.chat_id}</td>
            <td>${escapeHtml(message.role)}</td>
            <td title="${escapeHtml(message.text)}">${escapeHtml(truncate(message.text, 180))}</td>
            <td>${escapeHtml(formatDate(message.created_at))}</td>
        </tr>
    `).join('');
}

function renderBugReports(bugReports) {
    if (!bugReports.length) {
        bugReportsContainer.innerHTML = '<div class="admin-empty">Пока нет сообщений об ошибках.</div>';
        return;
    }

    bugReportsContainer.innerHTML = bugReports.map((report) => `
        <article class="admin-card">
            <div class="admin-card-meta">
                <strong>#${report.id}</strong>
                <span>${escapeHtml(report.email)}</span>
                <span>${escapeHtml(formatDate(report.created_at))}</span>
            </div>
            <div class="admin-card-text">${escapeHtml(report.text)}</div>
            <div class="admin-card-foot">
                <span>chat_id: ${report.chat_id ?? '—'}</span>
                <span title="${escapeHtml(report.page_url || '')}">${escapeHtml(truncate(report.page_url || '—', 60))}</span>
            </div>
        </article>
    `).join('');
}

async function loadAdminDashboard() {
    const meRes = await fetch(API + '/api/me', { headers });
    if (meRes.status === 401) {
        logout();
        return;
    }
    const me = await meRes.json();
    if (!me.is_admin) {
        document.body.innerHTML = '<div class="admin-denied">Недостаточно прав для доступа к админ-панели.</div>';
        return;
    }

    const res = await fetch(API + '/api/admin/dashboard', { headers });
    if (!res.ok) {
        document.body.innerHTML = '<div class="admin-denied">Не удалось загрузить админ-данные.</div>';
        return;
    }
    const data = await res.json();
    renderOverview(data.overview);
    renderUsers(data.users);
    renderChats(data.recent_chats);
    renderMessages(data.recent_messages);
    renderBugReports(data.bug_reports);
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('email');
    window.location.href = '/static/login.html?next=/admin';
}

logoutBtn.addEventListener('click', logout);
loadAdminDashboard();
