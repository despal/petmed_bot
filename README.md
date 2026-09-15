# petmed — ядро, бот, HTTP API, Mini App

Ядро ухода за животными, Telegram-бот (`tick`, due, «Сделано», `/start` + invite), FastAPI для Mini App, фронт в [`miniapp/`](./miniapp/).

Документы: [`docs/TZ_PLAN.md`](./docs/TZ_PLAN.md), поставка HTTP — [`docs/TZ_04_HTTP.md`](./docs/TZ_04_HTTP.md).

## Требования

- Python 3.10+
- Node.js 18+ (для Mini App)
- SQLite

## Установка Python

```powershell
cd "D:\Личные проекты\petmed_bot"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Скопируйте [`.env.example`](./.env.example). Секреты в git не класть.

## Переменные

| Имя | Кто | Смысл |
|---|---|---|
| `BOT_TOKEN` | бот + API (подпись initData) | токен BotFather |
| `DATABASE_URL` | бот + API + скрипт | одна БД, по умолчанию `sqlite:///petmed.db` |
| `WEBAPP_URL` | бот | HTTPS URL Mini App; пусто → кнопка «Скоро» |
| `BOT_USERNAME` | скрипт invite | имя бота без `@` |
| `DEV_TELEGRAM_ID` | API | обход initData **только для локальной отладки** |

Auth API: заголовок `Authorization: tma <initData>`.

## Два процесса

### API

```powershell
$env:DATABASE_URL="sqlite:///petmed.db"
$env:BOT_TOKEN="..."          # для прод-проверки initData
# $env:DEV_TELEGRAM_ID="1001" # только локально
python -m petmed_api
```

Слушает `http://127.0.0.1:8000`. Health: `GET /api/health`.

### Бот

```powershell
$env:BOT_TOKEN="..."
$env:DATABASE_URL="sqlite:///petmed.db"
$env:WEBAPP_URL="https://your-host.example/"   # после деплоя
python -m petmed_bot.runner
```

- `/start` — текст + кнопка приложения  
- `/start <token>` — `accept_invite` («Добро пожаловать» / «Ты внутри» / ошибка)  
- без `WEBAPP_URL` кнопка остаётся заглушкой «Скоро»

### Скрипт приглашения

```powershell
$env:DATABASE_URL="sqlite:///petmed.db"
$env:BOT_USERNAME="YourBot"
python -m petmed_api.create_invite
```

Печатает `token` и `https://t.me/<BOT_USERNAME>?start=<token>`.

## Mini App

- Моки (вёрстка): `VITE_USE_MOCKS=true npm run dev` в `miniapp/`  
- Live: `npm run dev` + API; vite проксирует `/api` → `:8000`  
- Сборка: `npm run build` → `miniapp/dist`  
- Пример nginx: [`deploy/nginx.example.conf`](./deploy/nginx.example.conf) (статика + `/api` → uvicorn). Снаружи только HTTPS.

## Тесты

```powershell
pytest
```

На Windows: `py -3.12 -m pytest`.

Приёмка API: `tests/test_api.py`. Регрессия ядра/бота не должна ломаться.

## Ручной контур (когда есть HTTPS)

1. Скрипт invite → ссылка → `/start` в Telegram.  
2. `WEBAPP_URL` на ваш HTTPS → кнопка открывает Mini App.  
3. Пояс → дом → животное → назначение → отметка.  
4. Без invite новый человек в Mini App видит «нет доступа».

## Ядро (кратко)

Пользователя с `telegram_id` создаёт **invite** (`/start` или скрипт), не Mini App.  
`tick` — только у бота. Mini App `tick` не вызывает.
