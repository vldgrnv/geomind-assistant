const cooperationForm = document.getElementById('cooperation-form');
const cooperationStatus = document.getElementById('cooperation-status');

function setCooperationStatus(text, type = '') {
    if (!cooperationStatus) return;
    cooperationStatus.textContent = text;
    cooperationStatus.className = 'feedback-status' + (type ? ' ' + type : '');
}

async function submitCooperationForm(event) {
    event.preventDefault();
    if (!cooperationForm) return;

    const submitButton = cooperationForm.querySelector('button[type="submit"]');
    const formData = new FormData(cooperationForm);
    const email = String(formData.get('email') || '').trim();
    const message = String(formData.get('message') || '').trim();

    if (!email || !message) {
        setCooperationStatus('Заполните оба поля.', 'error');
        return;
    }

    if (submitButton) submitButton.disabled = true;
    setCooperationStatus('Отправляем...');

    try {
        const response = await fetch('/api/contact-requests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email,
                text: message,
                page_url: window.location.href,
            }),
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload.detail || 'Не удалось отправить сообщение');
        }

        cooperationForm.reset();
        setCooperationStatus('Спасибо, сообщение отправлено.', 'success');
    } catch (error) {
        setCooperationStatus(error.message || 'Не удалось отправить сообщение.', 'error');
    } finally {
        if (submitButton) submitButton.disabled = false;
    }
}

if (cooperationForm) {
    cooperationForm.addEventListener('submit', submitCooperationForm);
}
