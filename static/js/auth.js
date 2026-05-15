const API = '';
let isLogin = true;

const form = document.getElementById('auth-form');
const emailInput = document.getElementById('email');
const passwordInput = document.getElementById('password');
const submitBtn = document.getElementById('submit-btn');
const errorDiv = document.getElementById('error');
const toggleLink = document.getElementById('toggle-link');
const toggleText = document.getElementById('toggle-text');
const subtitle = document.getElementById('auth-subtitle');

const params = new URLSearchParams(window.location.search);
const pendingPlan = params.get('plan');
const nextPath = params.get('next');

function getSafeNextPath() {
    if (!nextPath || !nextPath.startsWith('/') || nextPath.startsWith('//')) {
        return '/static/dashboard.html';
    }
    return nextPath;
}

if (localStorage.getItem('token')) {
    if (pendingPlan) {
        activatePlan(pendingPlan);
    } else {
        window.location.href = getSafeNextPath();
    }
}

async function activatePlan(plan) {
    const token = localStorage.getItem('token');
    await fetch(API + '/api/plan', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token,
        },
        body: JSON.stringify({ plan }),
    });
    window.location.href = '/static/dashboard.html';
}

toggleLink.addEventListener('click', (e) => {
    e.preventDefault();
    isLogin = !isLogin;
    submitBtn.textContent = isLogin ? 'Войти' : 'Зарегистрироваться';
    toggleText.textContent = isLogin ? 'Нет аккаунта?' : 'Уже есть аккаунт?';
    toggleLink.textContent = isLogin ? 'Зарегистрироваться' : 'Войти';
    subtitle.textContent = isLogin ? 'Войдите в личный кабинет' : 'Создайте аккаунт';
    errorDiv.style.display = 'none';
});

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorDiv.style.display = 'none';
    submitBtn.disabled = true;
    submitBtn.textContent = 'Загрузка...';

    const endpoint = isLogin ? '/auth/login' : '/auth/register';
    try {
        const res = await fetch(API + endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: emailInput.value, password: passwordInput.value }),
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'Ошибка');
        }
        localStorage.setItem('token', data.token);
        localStorage.setItem('email', emailInput.value);

        if (pendingPlan) {
            await activatePlan(pendingPlan);
        } else {
            window.location.href = getSafeNextPath();
        }
    } catch (err) {
        errorDiv.textContent = err.message;
        errorDiv.style.display = 'block';
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = isLogin ? 'Войти' : 'Зарегистрироваться';
    }
});
