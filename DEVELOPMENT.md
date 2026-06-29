# Development

## Current Access Decision

- Parent/student entry key is CRM `contact_id`, not `student_id`.
- MAX deep link payload format is `cid_<CONTACT_ID>`.
- Deep link format: `https://max.ru/<botName>?start=cid_<CONTACT_ID>`.
- Test command in `main_bot.py`: `/link <Contact ID>` or `/code <Contact ID>`.
- CRM sync creates `contacts` and `contact_student_links`.
- One contact can be linked to multiple students; one student can be linked to multiple contacts.
- `student_access_links` are created per MAX account, tenant, student and selected role.
- Legacy `sid_...` payloads are parsed only for temporary compatibility.

## Clean UX Draft

- Local preview route: `GET /miniapp`.
- Static assets route: `/miniapp/static/*`.
- First screen is the actual working mini app shell, not a landing page.
- MVP sections:
  - overview with linked students and operational tasks;
  - store with categories, search, favorites and cart;
  - cart with quantity controls and order placement transition;
  - orders with status and warehouse signal;
  - astrocoin ledger;
  - admin operations for warehouses, inventory and Contact ID links.
- Role switch is explicit: student, parent, teacher, admin.
- Tenant switch is explicit: city plus partner.
- UX keeps `tenant = city + partner` visible because data isolation is a core rule.
- Admin UX treats warehouses as first-class objects, not as a product field.
- Current miniapp uses backend API in normal mode and demo data only for local preview via `?demo=1`.
- Store, cart, orders, product import and astrocoin accrual flows are wired to backend services.

## Стартовый Контекст

Backend живет в `app/`. `main_bot.py` оставлен как тонкая точка входа для long polling-бота и импортирует реализацию из `app.bot.max_long_polling`.

## Локальная Проверка

```powershell
max_bot_venv\Scripts\python.exe -m pytest
max_bot_venv\Scripts\python.exe -m ruff check app tests alembic
node --check app\web\static\miniapp\app.js
max_bot_venv\Scripts\python.exe -m alembic upgrade head --sql
```

## Запуск API

```powershell
max_bot_venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

После запуска healthcheck:

```text
http://127.0.0.1:8000/api/v1/health
```

Локальная miniapp:

```text
http://127.0.0.1:8000/miniapp?demo=1
```

Без `?demo=1` miniapp ожидает параметры из MAX:

```text
http://127.0.0.1:8000/miniapp?max_user_id=<MAX_USER_ID>&tenant_slug=nizhniy-novgorod-partner-a
```

## Запуск MAX-Бота

```powershell
$env:MAX_BOT_TOKEN = "..."
$env:MAX_BACKEND_API_BASE = "http://127.0.0.1:8000/api/v1"
$env:DEFAULT_TENANT_SLUG = "nizhniy-novgorod-partner-a"
$env:MAX_MINIAPP_URL = "http://127.0.0.1:8000/miniapp"
max_bot_venv\Scripts\python.exe main_bot.py
```

Для открытия miniapp из MAX на телефоне `MAX_MINIAPP_URL` должен быть публичным HTTPS-адресом.

## Миграции

Применить миграции к PostgreSQL:

```powershell
max_bot_venv\Scripts\python.exe -m alembic upgrade head
```

Создать новую миграцию после изменения моделей:

```powershell
max_bot_venv\Scripts\python.exe -m alembic revision --autogenerate -m "message"
```

## Нужно Заполнить В `.env`

Создать `.env` на основе `.env.example` и заполнить:

- `MAX_BOT_TOKEN` - токен MAX-бота.
- `APP_SECRET_KEY` - длинная случайная строка для внутренних hash/signature.
- `INITIAL_SUPERADMIN_MAX_USER_ID` - MAX user_id суперадмина.
- `DATABASE_URL` - async URL PostgreSQL.
- `DATABASE_SYNC_URL` - sync URL PostgreSQL для Alembic.
- `REDIS_URL` - Redis для будущих очередей и production rate limit.
- `CRM_ACTIVE_EXPORT_PATH` - путь к активной CRM XLSX-выгрузке.
- `CRM_DEPARTED_EXPORT_PATH` - путь к XLSX-выгрузке выбывших.
- `GOOGLE_SERVICE_ACCOUNT_FILE` - путь к JSON service account.
- `GOOGLE_SHEETS_ORDERS_SPREADSHEET_ID` - ID таблицы заказов.
- `MAX_BACKEND_API_BASE` - base URL backend API для long polling-бота.
- `DEFAULT_TENANT_SLUG` - tenant по умолчанию.
- `MAX_MINIAPP_URL` - URL miniapp для inline-кнопки.

## Текущие Реализованные Блоки

- FastAPI app factory.
- Pydantic settings с `.env`.
- SQLAlchemy async session.
- Alembic migrations.
- City/partner/tenant/account/student/access/audit/wallet/ledger models.
- Store/order/warehouse/inventory/stock movement models.
- Access API:
  - `POST /api/v1/access/resolve-student`
  - `POST /api/v1/access/links`
- MAX deep links для входа по `Contact ID`:
  - payload format: `cid_<Contact ID>`;
  - link format: `https://max.ru/<botName>?start=cid_<Contact ID>`;
  - тестовая команда в `main_bot.py`: `/link <Contact ID>` или `/code <Contact ID>`.
- Inline-кнопки выбора роли: `Я родитель`, `Я ученик`.
- Inline-кнопка открытия miniapp, если задан `MAX_MINIAPP_URL`.
- Rate limit для ввода `ID ученика` в локальной MVP-реализации.
- Audit log для попыток входа и связок.
- CRM XLSX parser для листа `Сделки`.
- DB-backed CRM import: создание/обновление учеников, контактов и связок.
- Miniapp backend:
  - `GET /api/v1/miniapp/session`;
  - `GET /api/v1/miniapp/catalog`;
  - `POST /api/v1/miniapp/orders`;
  - `POST /api/v1/miniapp/products/import`;
  - `POST /api/v1/miniapp/coins/accrue`.
- Miniapp frontend:
  - обзор;
  - магазин;
  - корзина с выбором склада и количества;
  - заказы;
  - история астрокоинов;
  - начисления по ученикам с фильтром ФИО/группа;
  - админская загрузка товаров CSV/XLSX.

## Текущая Модель Tenant И Складов

- `tenant` = независимый контур конкретного партнера в конкретном городе.
- Один город может иметь несколько партнеров, каждый партнер в городе получает отдельный tenant.
- Склады принадлежат tenant и могут быть общими, привязанными к площадке, партнерскими или внешними.
- Остатки хранятся в `warehouse_inventory`, а не напрямую у товара.
- Все складские операции должны писать `stock_movements` и `audit_logs`.

## Следующие Блоки

- Redis-backed rate limit.
- Staff role permissions middleware.
- Admin API для tenant, городов, партнеров, площадок, складов, сотрудников, связок, товаров и заказов.
- Google Sheets export.
- Production-публикация miniapp на публичный HTTPS-домен.
- Расширение жизненного цикла заказа: отмена, выдача, возврат, возврат астрокоинов.
