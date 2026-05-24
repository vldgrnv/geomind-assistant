const cooperationForm = document.getElementById('cooperation-form');
const cooperationStatus = document.getElementById('cooperation-status');
const assistantPreview = document.querySelector('.assistant-preview');

function initAssistantPreviewAnimation() {
    if (!assistantPreview) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion || !('IntersectionObserver' in window)) {
        assistantPreview.classList.add('is-visible');
        return;
    }

    assistantPreview.classList.add('is-animated');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            assistantPreview.classList.add('is-visible');
            observer.disconnect();
        });
    }, {
        threshold: 0.34,
        rootMargin: '0px 0px -12% 0px',
    });

    observer.observe(assistantPreview);
}

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

initAssistantPreviewAnimation();
