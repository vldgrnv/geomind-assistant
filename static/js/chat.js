const API = '';
const token = localStorage.getItem('token');
if (!token) window.location.href = '/static/login.html';

const headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + token,
};

let currentChatId = null;
let lastAssistantText = '';

if (typeof marked !== 'undefined' && marked.use) {
    marked.use({ gfm: true, breaks: true });
}

/** Разрывает «стену текста», когда модель не поставила переносы перед заголовками и шагами. */
function normalizeAssistantMarkdown(raw) {
    if (!raw || typeof raw !== 'string') return '';
    let t = raw.replace(/\r\n/g, '\n').trim();
    t = t.replace(/([^\n#])(#{1,6}\s)/g, '$1\n\n$2');
    t = t.replace(/([.!?;»])\s*(\d{1,2}\.\s)/g, '$1\n\n$2');
    t = t.replace(/([а-яёА-ЯЁa-zA-Z)\]”—])\s*(\d{1,2}\.\s+)/g, '$1\n\n$2');
    return t;
}

function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function renderAssistantHtml(text) {
    const normalized = normalizeAssistantMarkdown(text);
    let html;
    if (typeof marked !== 'undefined' && marked.parse) {
        html = marked.parse(normalized);
    } else {
        html = '<p>' + escapeHtml(normalized).replace(/\n{2,}/g, '</p><p>').replace(/\n/g, '<br>') + '</p>';
    }
    if (typeof DOMPurify !== 'undefined' && DOMPurify.sanitize) {
        return DOMPurify.sanitize(html, {
            ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'b', 'i', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'code', 'pre', 'blockquote', 'a', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td'],
            ALLOWED_ATTR: ['href', 'title', 'colspan', 'rowspan'],
        });
    }
    return escapeHtml(normalized).replace(/\n/g, '<br>');
}

// ---------- DOM Elements ----------
const chatList = document.getElementById('chat-list');
const messagesDiv = document.getElementById('messages');
const emptyState = document.getElementById('empty-state');
const queryInput = document.getElementById('query-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const logoutBtn = document.getElementById('logout-btn');
const exportDocxBtn = document.getElementById('export-docx-btn');
const exportPdfBtn = document.getElementById('export-pdf-btn');

function updateExportButtons() {
    const disabled = !lastAssistantText.trim();
    if (exportDocxBtn) exportDocxBtn.disabled = disabled;
    if (exportPdfBtn) exportPdfBtn.disabled = disabled;
}

function setLastAssistantText(text) {
    lastAssistantText = typeof text === 'string' ? text : '';
    updateExportButtons();
}

function getLastAssistantMessage(msgs) {
    for (let i = msgs.length - 1; i >= 0; i -= 1) {
        if (msgs[i].role === 'assistant' && typeof msgs[i].text === 'string') {
            return msgs[i].text;
        }
    }
    return '';
}

function buildExportFileName(ext) {
    const now = new Date();
    const pad = (v) => String(v).padStart(2, '0');
    const stamp = [
        now.getFullYear(),
        pad(now.getMonth() + 1),
        pad(now.getDate()),
    ].join('-') + '_' + [pad(now.getHours()), pad(now.getMinutes())].join('-');
    return `geomind-last-answer-${stamp}.${ext}`;
}

function markdownToPlainLines(text) {
    return normalizeAssistantMarkdown(text)
        .replace(/\r\n/g, '\n')
        .split('\n')
        .map((line) => line.replace(/\s+$/g, ''));
}

async function exportLastAnswerDocx() {
    if (!lastAssistantText.trim() || typeof docx === 'undefined' || typeof saveAs === 'undefined') return;

    const paragraphs = markdownToPlainLines(lastAssistantText).map((line) => {
        const trimmed = line.trim();
        if (!trimmed) {
            return new docx.Paragraph({ text: '' });
        }

        const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
        if (headingMatch) {
            const levelMap = {
                1: docx.HeadingLevel.HEADING_1,
                2: docx.HeadingLevel.HEADING_2,
                3: docx.HeadingLevel.HEADING_3,
                4: docx.HeadingLevel.HEADING_4,
                5: docx.HeadingLevel.HEADING_5,
                6: docx.HeadingLevel.HEADING_6,
            };
            return new docx.Paragraph({
                text: headingMatch[2],
                heading: levelMap[headingMatch[1].length],
                spacing: { after: 120 },
            });
        }

        return new docx.Paragraph({
            text: trimmed.replace(/^[-*]\s+/, '• ').replace(/^\d+\.\s+/, (m) => m),
            spacing: { after: 120 },
        });
    });

    const documentFile = new docx.Document({
        sections: [{
            properties: {},
            children: paragraphs,
        }],
    });

    const blob = await docx.Packer.toBlob(documentFile);
    saveAs(blob, buildExportFileName('docx'));
}

function exportLastAnswerPdf() {
    if (!lastAssistantText.trim() || typeof pdfMake === 'undefined') return;

    const content = markdownToPlainLines(lastAssistantText).map((line) => {
        const trimmed = line.trim();
        if (!trimmed) {
            return { text: ' ', margin: [0, 0, 0, 8] };
        }

        const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
        if (headingMatch) {
            const fontSizeMap = { 1: 18, 2: 16, 3: 15, 4: 14, 5: 13, 6: 12 };
            return {
                text: headingMatch[2],
                bold: true,
                fontSize: fontSizeMap[headingMatch[1].length],
                margin: [0, 8, 0, 6],
            };
        }

        return {
            text: trimmed.replace(/^[-*]\s+/, '• '),
            fontSize: 12,
            margin: [0, 0, 0, 6],
        };
    });

    pdfMake.createPdf({
        pageSize: 'A4',
        pageMargins: [40, 48, 40, 48],
        defaultStyle: {
            font: 'Roboto',
            fontSize: 12,
        },
        content,
    }).download(buildExportFileName('pdf'));
}

// ---------- Stats ----------
async function loadStats() {
    const res = await fetch(API + '/api/stats', { headers });
    if (res.status === 401) { logout(); return; }
    const s = await res.json();

    document.getElementById('stat-today').textContent = s.today;
    document.getElementById('stat-week').textContent = s.week;
    document.getElementById('stat-month').textContent = s.month;

    const rem = document.getElementById('stat-remaining');
    rem.textContent = s.remaining;
    rem.className = 'value' + (s.remaining <= 2 ? ' danger' : s.remaining <= 5 ? ' warn' : '');

    const badge = document.getElementById('plan-badge');
    badge.textContent = s.plan.charAt(0).toUpperCase() + s.plan.slice(1);
    badge.className = 'plan-badge ' + s.plan;

    document.getElementById('user-email').textContent = localStorage.getItem('email') || '—';
}

// ---------- Chats ----------
async function loadChats() {
    const res = await fetch(API + '/api/chats', { headers });
    const chats = await res.json();
    chatList.innerHTML = '';
    chats.forEach(c => {
        const div = document.createElement('div');
        div.className = 'chat-item' + (c.id === currentChatId ? ' active' : '');
        div.addEventListener('click', (e) => {
            if (e.target.closest('.chat-actions')) return;
            openChat(c.id);
        });

        const title = document.createElement('span');
        title.className = 'chat-title';
        title.textContent = c.title;

        const actions = document.createElement('span');
        actions.className = 'chat-actions';

        const ren = document.createElement('button');
        ren.type = 'button';
        ren.className = 'chat-rename';
        ren.textContent = '✎';
        ren.title = 'Переименовать';
        ren.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            renameChat(c.id, c.title);
        });

        const del = document.createElement('button');
        del.type = 'button';
        del.className = 'chat-delete';
        del.textContent = '✕';
        del.title = 'Удалить чат';
        del.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            deleteChat(c.id);
        });

        actions.appendChild(ren);
        actions.appendChild(del);
        div.appendChild(title);
        div.appendChild(actions);
        chatList.appendChild(div);
    });
}

async function deleteChat(chatId) {
    const confirmed = await showConfirm('Удалить этот чат?');
    if (!confirmed) return;
    await fetch(API + '/api/chats/' + chatId, { method: 'DELETE', headers });
    if (currentChatId === chatId) {
        currentChatId = null;
        setLastAssistantText('');
        messagesDiv.innerHTML = `
            <div class="empty-state">
                <div class="icon">🗺️</div>
                <div>Задайте вопрос по ГИС-алгоритмам</div>
                <div style="font-size:13px">Например: «Как построить буферную зону вокруг дороги?»</div>
            </div>`;
    }
    loadChats();
}

function showConfirm(message) {
    return new Promise(resolve => {
        const overlay = document.createElement('div');
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999;';
        const box = document.createElement('div');
        box.style.cssText = 'background:var(--bg-secondary);border:1px solid var(--border);border-radius:12px;padding:24px;max-width:340px;width:90%;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.4);';
        box.innerHTML = `
            <div style="font-size:15px;color:var(--text-primary);margin-bottom:20px;">${message}</div>
            <div style="display:flex;gap:10px;justify-content:center;">
                <button id="confirm-cancel" style="padding:8px 20px;border-radius:8px;border:1px solid var(--border);background:var(--bg-primary);color:var(--text-secondary);cursor:pointer;font-size:14px;">Отмена</button>
                <button id="confirm-ok" style="padding:8px 20px;border-radius:8px;border:none;background:var(--danger);color:#fff;cursor:pointer;font-size:14px;font-weight:600;">Удалить</button>
            </div>`;
        overlay.appendChild(box);
        document.body.appendChild(overlay);
        box.querySelector('#confirm-ok').focus();
        box.querySelector('#confirm-ok').addEventListener('click', () => { overlay.remove(); resolve(true); });
        box.querySelector('#confirm-cancel').addEventListener('click', () => { overlay.remove(); resolve(false); });
        overlay.addEventListener('click', (e) => { if (e.target === overlay) { overlay.remove(); resolve(false); } });
    });
}

function renameChat(chatId, oldTitle) {
    // Находим элемент чата и заменяем title на input
    const items = chatList.querySelectorAll('.chat-item');
    for (const item of items) {
        const titleEl = item.querySelector('.chat-title');
        if (titleEl && titleEl.textContent === oldTitle) {
            const input = document.createElement('input');
            input.type = 'text';
            input.value = oldTitle;
            input.className = 'chat-rename-input';
            input.style.cssText = 'flex:1;background:var(--bg-primary);color:var(--text-primary);border:1px solid var(--accent);border-radius:4px;padding:2px 6px;font-size:13px;outline:none;min-width:0;';
            titleEl.replaceWith(input);
            input.focus();
            input.select();

            const save = async () => {
                const newTitle = input.value.trim();
                if (newTitle && newTitle !== oldTitle) {
                    await fetch(API + '/api/chats/' + chatId, {
                        method: 'PATCH', headers,
                        body: JSON.stringify({ title: newTitle }),
                    });
                }
                loadChats();
            };

            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') { e.preventDefault(); save(); }
                if (e.key === 'Escape') { loadChats(); }
            });
            input.addEventListener('blur', save);
            break;
        }
    }
}

async function openChat(chatId) {
    currentChatId = chatId;
    loadChats();
    const res = await fetch(API + '/api/chats/' + chatId + '/messages', { headers });
    const msgs = await res.json();
    renderMessages(msgs);
}

function renderMessages(msgs) {
    messagesDiv.innerHTML = '';
    if (!msgs.length) {
        messagesDiv.innerHTML = emptyState.outerHTML;
        setLastAssistantText('');
        return;
    }
    msgs.forEach(m => addMessageBubble(m.role, m.text));
    setLastAssistantText(getLastAssistantMessage(msgs));
}

function addMessageBubble(role, text) {
    if (emptyState && messagesDiv.contains(emptyState)) {
        messagesDiv.innerHTML = '';
    }
    const div = document.createElement('div');
    div.className = 'message ' + role;
    if (role === 'assistant') {
        const inner = document.createElement('div');
        inner.className = 'message-content';
        inner.innerHTML = renderAssistantHtml(text);
        div.appendChild(inner);
    } else {
        div.textContent = text;
    }
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    if (role === 'assistant') {
        setLastAssistantText(text);
    }
}

function showTyping() {
    const div = document.createElement('div');
    div.className = 'typing-indicator';
    div.id = 'typing';
    div.innerHTML = '<span></span><span></span><span></span>';
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function hideTyping() {
    const t = document.getElementById('typing');
    if (t) t.remove();
}

// ---------- Send ----------
async function send() {
    const query = queryInput.value.trim();
    if (!query) return;

    queryInput.value = '';
    addMessageBubble('user', query);
    showTyping();
    sendBtn.disabled = true;

    try {
        const res = await fetch(API + '/api/ask', {
            method: 'POST', headers,
            body: JSON.stringify({ query, chat_id: currentChatId }),
        });
        hideTyping();

        if (res.status === 403) {
            addMessageBubble('assistant', 'Лимит запросов исчерпан. Обновите тариф.');
            return;
        }

        const data = await res.json();
        currentChatId = data.chat_id;
        addMessageBubble('assistant', data.answer);
        loadChats();
        loadStats();
    } catch (e) {
        hideTyping();
        addMessageBubble('assistant', 'Ошибка соединения с сервером');
    } finally {
        sendBtn.disabled = false;
    }
}

sendBtn.addEventListener('click', send);
queryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') send();
});

// ---------- New Chat ----------
newChatBtn.addEventListener('click', () => {
    currentChatId = null;
    setLastAssistantText('');
    messagesDiv.innerHTML = `
        <div class="empty-state">
            <div class="icon">🗺️</div>
            <div>Задайте вопрос по ГИС-алгоритмам</div>
            <div style="font-size:13px">Например: «Как построить буферную зону вокруг дороги?»</div>
        </div>`;
    loadChats();
});
if (exportDocxBtn) exportDocxBtn.addEventListener('click', exportLastAnswerDocx);
if (exportPdfBtn) exportPdfBtn.addEventListener('click', exportLastAnswerPdf);

// ---------- Logout ----------
function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('email');
    window.location.href = '/static/login.html';
}
logoutBtn.addEventListener('click', logout);

// ---------- Init ----------
loadStats();
loadChats();
updateExportButtons();
