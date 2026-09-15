# PetMed Mini App

## Режимы

| Режим | Как | Данные |
|---|---|---|
| **Моки** (вёрстка) | `VITE_USE_MOCKS=true npm run dev` | стенды сверху, без API |
| **Live** (по умолчанию) | `npm run dev` + FastAPI на `:8000` | `GET/POST /api…` через vite-proxy |

Auth в live: заголовок `Authorization: tma <initData>`.  
Локально без Telegram: на API задайте `DEV_TELEGRAM_ID=<ваш telegram id>` и заранее создайте User (скрипт invite + `/start` или тесты).

## Запуск (моки)

```powershell
cd miniapp
npm install
$env:VITE_USE_MOCKS="true"
npm run dev
```

## Запуск (live с API)

Терминал 1:

```powershell
cd "D:\Личные проекты\petmed_bot"
$env:DATABASE_URL="sqlite:///petmed.db"
$env:DEV_TELEGRAM_ID="1001"
# заранее: User с telegram_id=1001 в БД
python -m petmed_api
```

Терминал 2:

```powershell
cd miniapp
npm run dev
```

Откройте http://localhost:5173/ — запросы `/api` проксируются на `127.0.0.1:8000`.

## Сборка под nginx

```powershell
npm run build
```

Положите `dist/` как `root` сайта; `location /api/` → FastAPI.

## Чеклист моков (B5)

См. предыдущую поставку; при `VITE_USE_MOCKS=true` стенды на месте.
