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
Runtime-обвязка бота (`.env`, marker-файл, версия/revision и logging) вынесена в `app.bot.runtime`, чтобы `max_long_polling.py` оставался ближе к обработчикам команд.
Backend API client для long polling-бота вынесен в `app.bot.backend_client`; `max_long_polling.py` импортирует его и отвечает за MAX polling, routing и форматирование ответов.
MAX transport client и локальный simulation client вынесены в `app.bot.max_client`; long polling-обработчики больше не содержат HTTP-детали MAX API.
Общие модели ответа и pending Contact ID вынесены в `app.bot.models`, чтобы transport, smoke CLI и обработчики могли использовать один контракт ответа.
Парсинг аргументов команд вынесен в `app.bot.command_parsers`, чтобы сценарии long polling не смешивались с валидацией строкового ввода.
Callback payloads, кнопки и inline keyboards вынесены в `app.bot.keyboards`, чтобы UI-обвязка бота развивалась отдельно от обработчиков команд.

## Локальная Проверка

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.doctor --skip-db
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke --with-backend --user-id 1
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke --with-backend --user-id 1 --profile store
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke --with-backend --user-id 1 --profile ops
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke --with-backend --user-id 1 --profile all
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke --command "/version" --callback "orders:open"
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/help" --simulate-offline
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/help staff" --simulate-offline
max_bot_venv\Scripts\python.exe -m pytest
max_bot_venv\Scripts\python.exe -m ruff check app tests alembic
node --check app\web\static\miniapp\app.js
max_bot_venv\Scripts\python.exe -m alembic upgrade head --sql
```

## Запуск API

```powershell
docker compose up -d postgres redis
max_bot_venv\Scripts\python.exe -m alembic upgrade head
max_bot_venv\Scripts\python.exe -m app.cli.seed_store --max-user-id <MAX_USER_ID>
max_bot_venv\Scripts\python.exe -m app.cli.bootstrap_superadmin --max-user-id <MAX_USER_ID>
max_bot_venv\Scripts\python.exe -m app.cli.doctor
max_bot_venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Без Docker можно проверить backend на SQLite:

```powershell
Copy-Item .env.sqlite.example .env
New-Item -ItemType Directory -Force tmp | Out-Null
max_bot_venv\Scripts\python.exe -m alembic upgrade head
max_bot_venv\Scripts\python.exe -m app.cli.seed_store --max-user-id 1
max_bot_venv\Scripts\python.exe -m app.cli.doctor
max_bot_venv\Scripts\python.exe -m app.cli.bootstrap_superadmin --max-user-id 1
max_bot_venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Автоматизированный локальный bootstrap:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --dry-run
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --max-user-id 1
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --env-file .env.sqlite.example --max-user-id 1
max_bot_venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

`dev_bootstrap` защищает от случайного запуска миграций/seed на non-SQLite БД; для намеренного запуска на текущей БД нужен `--allow-non-sqlite`.
Значения из `.env` используются как окружение дочерних команд bootstrap; это делает `--force-env` предсказуемым даже при внешних переменных.
В bootstrap `doctor` запускается с `--allow-missing-bot-token`, чтобы локальная backend/SQLite проверка не требовала реального MAX-токена.

`dev_bootstrap` по умолчанию запускает offline smoke. Для проверки связки через уже запущенный API:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --max-user-id 1 --with-backend-smoke
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --max-user-id 1 --with-backend-smoke --backend-smoke-profile store
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --max-user-id 1 --with-backend-smoke --backend-smoke-profile all
```

Если отдельный `uvicorn` не запущен, bootstrap может временно поднять API для smoke:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --max-user-id 1 --start-backend-smoke --api-port 8010
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --max-user-id 1 --start-backend-smoke --backend-smoke-profile store --api-port 8010
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --max-user-id 1 --start-backend-smoke --backend-smoke-profile all --api-port 8010
```

После старта API можно в другом терминале проверить связку бот -> backend:

```powershell
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/id" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/version" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/setup" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/config" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/doctor" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/tenant reset" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/me" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/balance Алиса" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/lowbalance 200" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/groups" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/leaderboard" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/ledger Алиса" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/search ручка" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/student Алиса" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/access" --simulate-user-id 1
# После /access можно проверить управление связью, подставив реальный ID:
# max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/accessoff <access-link-id>" --simulate-user-id 1
# max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/accesson <access-link-id>" --simulate-user-id 1
# max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/staffrole <MAX_USER_ID> teacher | Имя" --simulate-user-id 1
# max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/staffoff <MAX_USER_ID> teacher" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/catalog ручка" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/categories" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/product PEN-LOGO" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "ручка" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/quote PEN-LOGO 2" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/canbuy PEN-LOGO 2" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/buy PEN-LOGO 2, BRACELET-SILICONE 1" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/orders" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/last open" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/last issued" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/sales all" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/orders open" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/open" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-callback "orders:open" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-callback "groups" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-callback "leaderboard" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/repeat 1" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/dashboard" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/todo" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-callback "todo" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-callback "stock" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/productset PEN-LOGO | Ручка Алгоритмики | 120 | Канцелярия" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/setprice PEN-LOGO 140" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/productstatus PEN-LOGO hidden" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/setphoto PEN-LOGO | https://example.com/pen.jpg" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/warehouses" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/warehouse nn-main | Основной склад | common" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/setstock PEN-LOGO 18" --simulate-user-id 1
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/transfer PEN-LOGO 3 | основной -> витрина" --simulate-user-id 1
```

Smoke полного заказа: создать заказ командой `/buy <SKU> [шт.][, SKU шт.] [| <ученик>]` или в miniapp, затем проверить `/orders`, `/order <номер>`,
кнопки карточки заказа и экран подтверждения, `/repeat <номер>`, `/cancel <номер>` или `/void <номер>` и убедиться, что баланс ученика и остаток товара вернулись к исходным значениям.

После запуска healthcheck:

```text
http://127.0.0.1:8000/api/v1/health
http://127.0.0.1:8000/api/v1/ready
```

`/ready` возвращает safe config report и `checks.database`/`checks.app_data`; пустой default tenant или незаполненный магазин дают warning, а не 500.

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
- `MAX_API_TIMEOUT_SECONDS` - таймаут обычных запросов к MAX API.
- `MAX_POLL_TIMEOUT_SECONDS` - long polling timeout для `/updates`.
- `APP_SECRET_KEY` - длинная случайная строка для внутренних hash/signature.
- `INITIAL_SUPERADMIN_MAX_USER_ID` - MAX user_id суперадмина.
- `DATABASE_URL` - async URL PostgreSQL.
- `DATABASE_SYNC_URL` - sync URL PostgreSQL для Alembic.
- `RATE_LIMIT_BACKEND` - `memory` локально или `redis` для нескольких backend-инстансов.
- `RATE_LIMIT_MAX_ATTEMPTS` - лимит попыток ввода Contact ID за окно.
- `RATE_LIMIT_WINDOW_SECONDS` - окно rate limit в секундах.
- `REDIS_URL` - Redis для production rate limit при `RATE_LIMIT_BACKEND=redis`.
- `CRM_ACTIVE_EXPORT_PATH` - путь к активной CRM XLSX-выгрузке.
- `CRM_DEPARTED_EXPORT_PATH` - путь к XLSX-выгрузке выбывших.
- `GOOGLE_SERVICE_ACCOUNT_FILE` - путь к JSON service account.
- `GOOGLE_SHEETS_ORDERS_SPREADSHEET_ID` - ID таблицы заказов.
- `MAX_BACKEND_API_BASE` - base URL backend API для long polling-бота.
- `MAX_BACKEND_TIMEOUT_SECONDS` - таймаут запросов бота к backend API.
- `DEFAULT_TENANT_SLUG` - tenant по умолчанию.
- `MAX_MINIAPP_URL` - URL miniapp для inline-кнопки.
- `MAX_DROP_WEBHOOKS_ON_START` - `true`, если long polling-боту нужно удалять активные MAX webhooks при старте.
- `MAX_ORDER_NOTIFICATIONS_ENABLED` - отправка MAX-уведомлений о создании и смене статуса заказа.

В production-like окружениях (`APP_ENV` не `local/dev/development/test`) placeholder
`APP_SECRET_KEY=replace_me` считается ошибкой `doctor`.

Первичная staff-роль создается командой:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.bootstrap_superadmin --max-user-id <MAX_USER_ID>
```

Команду нужно запускать после миграций и после того, как tenant уже создан импортом CRM или `app.cli.seed_store`.
Для локального smoke-сценария `app.cli.seed_store --max-user-id <MAX_USER_ID>` создает demo tenant, магазин, склад, двух учеников, Contact ID `681`, кошельки и access links для указанного MAX user_id.

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
- Inline-кнопки быстрых сценариев: каталог, баланс, заказы, ученики, группы, рейтинг AC, история астрокоинов и статус.
- Команды `/me`, `/balance`, `/wallet`, `/lowbalance`, `/lowwallets`, `/groups`, `/classes`, `/leaderboard`, `/top`, `/leaders`, `/ledger`, `/students`, `/student`, `/access`, `/accessoff`, `/accesson`, `/staffrole`, `/staffset`, `/staffoff`, `/staffon`, `/accrue`, `/catalog`, `/categories`, `/product`, `/productset`, `/setproduct`, `/setprice`, `/pricechange`, `/productstatus`, `/statusproduct`, `/hideproduct`, `/showproduct`, `/archiveproduct`, `/setphoto`, `/productphoto`, `/clearphoto`, `/quote`, `/price`, `/canbuy`, `/afford`, `/buy`, `/orders`, `/myorders`, `/open`, `/order`, `/last`, `/sales`, `/revenue`, `/repeat`, `/ops`, `/dashboard`, `/overview`, `/todo`, `/pending`, `/stock`, `/lowstock`, `/inventory`, `/warehouses`, `/wh`, `/warehouse`, `/upsertwarehouse`, `/setstock`, `/transfer`, `/move`, `/cancel`, `/issue`, `/return`, `/done`, `/void`, `/refund`, `/status`, `/setup`, `/version`, `/about`, `/ready` и `/miniapp` для проверки профиля, балансов, низких балансов, сводки групп, рейтинга учеников, истории астрокоинов, учеников, карточки ученика, просмотра и управления доступами/staff-ролями, начислений, каталога, категорий и карточки товара, управления товарами, ценами, фото и видимостью, безопасного расчета корзины, проверки кто может купить, создания и повтора заказов из чата, сводки продаж, staff-сводок и задач, проблемных и расширенных остатков, списка и управления складами, ручной корректировки и перемещения остатков, запуска, версии приложения, readiness, базовых order actions и открытия miniapp из MAX.
- Rate limit для ввода Contact ID: локальная память по умолчанию, Redis-backed режим для production.
- Audit log для попыток входа и связок.
- CRM XLSX parser для листа `Сделки`.
- DB-backed CRM import: создание/обновление учеников, контактов и связок.
- Idempotent demo bootstrap `app.cli.seed_store`: tenant, demo ученики, Contact ID `681`, кошельки, магазин, склад и опциональные access links.
- `app.cli.doctor` проверяет конфиг, miniapp assets, Redis/Google Sheets, подключение к БД и наличие базовых данных default tenant.
- Miniapp backend:
  - `GET /api/v1/miniapp/session`;
  - `GET /api/v1/miniapp/catalog`;
  - `POST /api/v1/miniapp/orders`;
  - `POST /api/v1/miniapp/products`;
  - `POST /api/v1/miniapp/orders/{order_id}/issue|cancel|return`;
  - `POST /api/v1/miniapp/products/import`;
  - `POST /api/v1/miniapp/warehouses`;
  - `POST /api/v1/miniapp/inventory/adjust`;
  - `POST /api/v1/miniapp/inventory/transfer`;
  - `POST /api/v1/miniapp/coins/accrue`;
  - `PATCH /api/v1/miniapp/access-links/{link_id}`;
  - `POST /api/v1/miniapp/staff/assignments`.
- Miniapp frontend:
  - обзор;
  - магазин;
  - корзина с выбором склада и количества;
  - заказы;
  - история астрокоинов;
  - начисления по ученикам с фильтром ФИО/группа;
  - админская загрузка товаров CSV/XLSX и ручное создание/редактирование карточек товаров, включая управление `active`/`hidden`/`archived`;
  - создание и редактирование складов tenant;
  - корректировка фактических остатков и перемещение свободных остатков между складами;
  - отзыв и восстановление связей доступа;
  - выдача и отзыв staff-ролей сотрудников.

## Текущая Модель Tenant И Складов

- `tenant` = независимый контур конкретного партнера в конкретном городе.
- Один город может иметь несколько партнеров, каждый партнер в городе получает отдельный tenant.
- Склады принадлежат tenant и могут быть общими, привязанными к площадке, партнерскими или внешними.
- Admin может создавать и редактировать склады из miniapp без seed-скрипта.
- Остатки хранятся в `warehouse_inventory`, а не напрямую у товара.
- Все складские операции должны писать `stock_movements` и `audit_logs`.
- Жизненный цикл заказа сейчас покрывает создание, резерв, выдачу ученику, отмену с возвратом астрокоинов и возврат выданного товара.
- Admin может создавать и редактировать карточки товаров из miniapp без CSV/XLSX; скрытые и архивные товары доступны в админском каталоге, но не отображаются в витрине и корзине.
- Если Google Sheets настроен через `.env`, создание/выдача/отмена заказа синхронизируются в лист `orders`.
- Корректировка и перемещение остатков из miniapp пишут `stock_movements` с типами `adjustment`/`transfer`; корректировка не позволяет опустить факт ниже резерва, перемещение использует только свободный остаток.
- Staff-ролями можно управлять из miniapp по MAX user_id. Операционные роли (`teacher`, `curator`) доступны admin/superadmin, управляющие роли (`admin`, `partner_director`, `superadmin`) меняет только superadmin.

## Следующие Блоки

- Staff role permissions middleware.
- Admin API для tenant, городов, партнеров, площадок, складов, сотрудников, связок, товаров и заказов.
- Production-публикация miniapp на публичный HTTPS-домен.
- Расширение жизненного цикла заказа: частичный возврат товара и частичный возврат астрокоинов.
