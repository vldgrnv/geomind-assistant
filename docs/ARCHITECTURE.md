# GeoMind Assistant — Архитектура проекта

## Структура файлов

```
geomind-assistant/
│
├── app.py                          ← Точка входа: FastAPI-сервер
├── requirements.txt                ← Зависимости проекта
├── .env                            ← Секреты (YANDEX_API_KEY, YANDEX_FOLDER_ID)
├── geomind.db                      ← SQLite база (создаётся автоматически)
│
├── auth/                           ← Пакет: авторизация
│   ├── __init__.py
│   ├── jwt.py                      ← Создание/проверка JWT-токенов
│   └── router.py                   ← POST /auth/register, /auth/login
│
├── api/                            ← Пакет: бизнес-эндпоинты
│   ├── __init__.py
│   └── router.py                   ← POST /api/ask, GET /api/chats, /api/stats
│
├── database/                       ← Пакет: данные
│   ├── __init__.py
│   ├── db.py                       ← Подключение SQLite, init_db()
│   └── models.py                   ← CRUD: users, chats, messages + статистика
│
├── AI_service/                     ← Пакет: логика ИИ
│   ├── __init__.py
│   ├── main.py                     ← handle(query) — главный pipeline
│   ├── search_algorithm.py         ← Поиск алгоритма (TF-IDF + BM25)
│   ├── classifier.py               ← «Второй шанс» — GPT-классификатор
│   ├── prompt.py                   ← Шаблон итогового промта
│   └── yandex_gpt.py               ← Обёртка над YandexGPT API
│
├── algorithms/                     ← База знаний: .md файлы алгоритмов
│   ├── buffer_analysis.md
│   ├── clip_analysis.md
│   ├── ...                         ← (12 файлов, расширяется)
│   └── update_analysis.md
│
├── static/                         ← Фронтенд (HTML + CSS + JS)
│   ├── css/
│   │   └── style.css               ← Дизайн-система (тёмная тема)
│   ├── js/
│   │   ├── auth.js                 ← Логика логина/регистрации
│   │   └── chat.js                 ← Логика чата, статистика
│   ├── index.html                  ← Landing page (главная)
│   ├── login.html                  ← Страница входа/регистрации
│   ├── dashboard.html              ← Личный кабинет (чат + панели)
│   └── plans.html                  ← Страница тарифов
│
├── deploy/                         ← Конфиги деплоя
│   ├── nginx.conf                  ← Nginx reverse proxy
│   ├── geomind.service             ← Systemd unit
│   └── setup.sh                    ← Скрипт установки на VPS
│
├── .env                            ← Настройки (локальные)
├── .env.production                 ← Шаблон настроек для продакшна
│
├── docs/                           ← Документация
│   └── ARCHITECTURE.md             ← Этот файл
│
└── venv/                           ← Виртуальное окружение
```

## Схема связей

```
┌──────────────────────────────────────────────────────────────────────┐
│  Клиент (curl / фронтенд)                                           │
│  POST /auth/register   {"email","password"}  → {token}              │
│  POST /auth/login      {"email","password"}  → {token}              │
│  POST /api/ask         {"query","chat_id?"}  → {answer, chat_id}    │
│  POST /api/plan        {"plan":"basic"}      → {message}            │
│  GET  /api/chats                             → [{id, title}]        │
│  GET  /api/chats/{id}/messages               → [{role, text}]       │
│  DELETE /api/chats/{id}                      → {ok}                 │
│  GET  /api/stats                             → {today,week,month,…} │
└──────────────────────┬───────────────────────────────────────────────┘
                       │  Authorization: Bearer <JWT>
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  app.py  (FastAPI)                                                   │
│  ├── auth/router.py   → register / login                            │
│  └── api/router.py    → ask / chats / messages / stats              │
│         │                     │                                     │
│         ▼                     ▼                                     │
│  auth/jwt.py            database/models.py                          │
│  (JWT create/verify)    (CRUD: users, chats, messages, stats)       │
│                               │                                     │
│                               ▼                                     │
│                         database/db.py                               │
│                         (SQLite connect + schema)                    │
└──────────────────────┬───────────────────────────────────────────────┘
                       │  (POST /api/ask only)
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  AI_service/main.py  —  handle(query)                                │
│                                                                      │
│  1. search_algorithm.search(query) → (path, score)                   │
│            score >= 0.45?                                            │
│             Да → читаем .md                                          │
│             Нет → classifier.classify_with_gpt(query)                │
│                    Найден → читаем .md                               │
│                    Не найден → "Error prompt"                        │
│  2. prompt.build_answer_prompt(query, text)                          │
│  3. yandex_gpt.ask(prompt) → ответ                                  │
└──────────────────────────────────────────────────────────────────────┘
```

## Назначение файлов

| Файл | Назначение |
|---|---|
| **Корень** | |
| `app.py` | FastAPI-сервер. Инициализация БД, подключение роутеров, CORS |
| `.env` | Секреты: `YANDEX_API_KEY`, `YANDEX_FOLDER_ID` |
| **auth/** | |
| `auth/jwt.py` | `create_token(user_id)` и `get_current_user_id()` — FastAPI dependency |
| `auth/router.py` | `POST /auth/register`, `POST /auth/login` → возвращают JWT |
| **api/** | |
| `api/router.py` | `POST /api/ask` (защищён, с лимитами, сохраняет в чат), `GET /api/chats`, `GET /api/chats/{id}/messages`, `GET /api/stats` |
| **database/** | |
| `database/db.py` | `get_conn()`, `init_db()` — SQLite подключение и создание таблиц |
| `database/models.py` | CRUD-функции для users, chats, messages + `get_stats()` (день/неделя/месяц/остаток) |
| **AI_service/** | |
| `AI_service/main.py` | `handle(query)` — главный pipeline: поиск → классификатор → промт → GPT |
| `AI_service/search_algorithm.py` | Локальный поиск (TF-IDF + BM25, синонимы, лемматизация) |
| `AI_service/classifier.py` | Fallback: GPT определяет алгоритм по метаданным |
| `AI_service/prompt.py` | Шаблон промта для GPT |
| `AI_service/yandex_gpt.py` | HTTP-обёртка `ask(prompt) → str` |
| **algorithms/** | |
| `algorithms/*.md` | База знаний — .md файлы алгоритмов геообработки |

## API Эндпоинты

| Метод | URL | Auth | Описание |
|---|---|---|---|
| POST | `/auth/register` | ❌ | Регистрация, возвращает JWT |
| POST | `/auth/login` | ❌ | Логин, возвращает JWT |
| POST | `/api/ask` | ✅ | Вопрос чат-боту (проверяет лимит, сохраняет в чат) |
| POST | `/api/plan` | ✅ | Смена тарифа (заглушка) |
| GET | `/api/chats` | ✅ | Список чатов пользователя |
| GET | `/api/chats/{id}/messages` | ✅ | Сообщения чата |
| DELETE | `/api/chats/{id}` | ✅ | Удаление чата (каскадно с сообщениями) |
| GET | `/api/stats` | ✅ | Статистика: запросы за день/неделю/месяц, остаток, план |

## Схема БД

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│    users     │       │    chats     │       │   messages   │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ id (PK)      │──┐    │ id (PK)      │──┐    │ id (PK)      │
│ email        │  │    │ user_id (FK) │  │    │ chat_id (FK) │
│ password_hash│  └───▶│ title        │  └───▶│ role         │
│ plan         │       │ created_at   │       │ text         │
│ requests_limit│       └──────────────┘       │ created_at   │
│ created_at   │                               └──────────────┘
└──────────────┘
```

## Конфигурация (.env)

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `YANDEX_API_KEY` | Ключ API YandexGPT | — |
| `YANDEX_FOLDER_ID` | ID каталога Yandex Cloud | — |
| `JWT_SECRET` | Секрет для подписи JWT | `geomind-secret-...` |
| `JWT_EXPIRE_DAYS` | Срок жизни токена (дни) | `30` |
| `PLAN_LIMIT_FREE` | Лимит запросов Free | `10` |
| `PLAN_LIMIT_BASIC` | Лимит запросов Basic | `100` |
| `PLAN_LIMIT_PRO` | Лимит запросов Pro | `999999` |
| `APP_PORT` | Порт сервера | `8000` |
| `DEBUG` | Режим отладки | `true` |
| `DATABASE_URL` | Путь к БД | `geomind.db` |
| `YUKASSA_SHOP_ID` | ID магазина ЮKassa | — |
| `YUKASSA_SECRET` | Секрет ЮKassa | — |

## Локальный запуск

```bash
# 1. Установка
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Сервер
uvicorn app:app --reload --port 8000
# → http://localhost:8000

# 3. Тест регистрации
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"123456"}'

# 4. Тест запроса (подставить полученный токен)
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"query": "Как построить буферную зону вокруг дороги?"}'
```

## Проверка базы данных

```bash
# Открыть базу
sqlite3 geomind.db

# Полезные команды
.tables                                     -- список таблиц
SELECT * FROM users;                        -- все пользователи
SELECT email, plan, requests_limit FROM users;  -- планы
SELECT * FROM chats;                        -- чаты
SELECT * FROM messages;                     -- сообщения
.quit                                       -- выход

# Сброс базы (начать с нуля)
rm geomind.db
# При следующем запуске сервера база создастся автоматически
```

## Фронтенд (static/)

| Файл | Назначение |
|---|---|
| `static/css/style.css` | Дизайн-система: тёмная тема, компоненты, анимации, landing стили |
| `static/index.html` | Landing page: navbar, hero (CTA + glow), фичи, «как работает», тарифы, footer |
| `static/login.html` | Форма входа/регистрации с переключением режимов |
| `static/dashboard.html` | Личный кабинет: 3-колоночный layout (чаты / сообщения / профиль+статистика) |
| `static/plans.html` | Тарифы: Free (0₽) / Basic (490₽) / Pro (1490₽) |
| `static/js/auth.js` | Логин/регистрация → JWT → redirect в dashboard |
| `static/js/chat.js` | Чат: загрузка чатов/сообщений, отправка, typing indicator, статистика |

## Деплой (конфиги)

| Файл | Назначение |
|---|---|
| `deploy/nginx.conf` | Nginx reverse proxy → uvicorn:8000 + статика |
| `deploy/geomind.service` | Systemd unit: автозапуск, 2 воркера |
| `deploy/setup.sh` | Скрипт установки на VPS (Ubuntu 22.04+) |
| `.env.production` | Шаблон .env для продакшна |

### Быстрый деплой

```bash
# 1. Копировать проект на сервер
scp -r . user@server:/opt/geomind-assistant/

# 2. Запустить скрипт установки
ssh user@server 'sudo bash /opt/geomind-assistant/deploy/setup.sh'

# 3. Выпустить SSL
ssh user@server 'sudo certbot --nginx -d geomind.ru'
```

## Планируемые этапы расширения

| Этап | Описание | Статус |
|---|---|---|
| 1. FastAPI бэкенд | `POST /api/ask` — REST API чат-бота | ✅ |
| 2. БД + авторизация | Users, chats, messages, JWT, лимиты | ✅ |
| 3. Личный кабинет | Чат-интерфейс + боковые панели | ✅ |
| 4. Landing page | Главная страница продукта + тарифы | ✅ |
| 5. Оплата | ЮKassa, тарифные планы | ⏳ |
| 6. Деплой | VPS + nginx + HTTPS + домен | ✅ конфиги |
