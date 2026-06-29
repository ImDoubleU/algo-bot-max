# MAX-бот и miniapp Алгоритмики

Черновой рабочий проект MAX-бота, backend API и miniapp для входа по Contact ID, магазина подарков, заказов, складов, загрузки товаров и начисления астрокоинов.

## Что уже работает

- MAX long polling-бот с inline-кнопками.
- Вход по CRM `Contact ID`.
- Выбор роли: родитель или ученик.
- FastAPI backend с tenant-изоляцией.
- CRM XLSX import.
- Miniapp:
  - обзор;
  - магазин;
  - корзина с выбором склада и количества;
  - оформление заказа с резервом склада;
  - история астрокоинов;
  - начисления в виде таблицы учеников;
  - админская загрузка товаров CSV/XLSX.

## Локальный запуск

Создать `.env` на основе `.env.example`, затем:

```powershell
max_bot_venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Miniapp для локальной проверки:

```text
http://127.0.0.1:8000/miniapp?demo=1
```

Запуск MAX-бота:

```powershell
$env:MAX_BOT_TOKEN = "..."
$env:MAX_BACKEND_API_BASE = "http://127.0.0.1:8000/api/v1"
$env:DEFAULT_TENANT_SLUG = "nizhniy-novgorod-partner-a"
$env:MAX_MINIAPP_URL = "http://127.0.0.1:8000/miniapp"
max_bot_venv\Scripts\python.exe main_bot.py
```

Для телефона в MAX `MAX_MINIAPP_URL` нужно заменить на публичный HTTPS-адрес.

## Проверки

```powershell
max_bot_venv\Scripts\python.exe -m ruff check app tests
max_bot_venv\Scripts\python.exe -m pytest
max_bot_venv\Scripts\python.exe -m compileall -q app main_bot.py
node --check app\web\static\miniapp\app.js
```

## Форматы данных

CRM и Google Sheets описаны в `DATA_INTEGRATION_DRAFT_RU.md`.

Технические команды и состояние backend описаны в `DEVELOPMENT.md`.
