# MAX-бот и miniapp Алгоритмики

Черновой рабочий проект MAX-бота, backend API и miniapp для входа по Contact ID, магазина подарков, заказов, складов, загрузки товаров и начисления астрокоинов.

## Что уже работает

- MAX long polling-бот с inline-кнопками.
- Вход по CRM `Contact ID`.
- Выбор роли: родитель или ученик.
- FastAPI backend с tenant-изоляцией.
- CRM XLSX import.
- Настраиваемый rate limit входа: локальная память по умолчанию или Redis для production.
- Miniapp:
  - обзор;
  - магазин;
  - корзина с выбором склада и количества;
  - оформление заказа с резервом склада;
  - история астрокоинов;
  - начисления в виде таблицы учеников;
  - админская загрузка товаров CSV/XLSX.

## Локальный запуск

Создать `.env` на основе `.env.example`, затем подготовить Python-окружение:

```powershell
py -3.11 -m venv max_bot_venv
max_bot_venv\Scripts\python.exe -m pip install --upgrade pip
max_bot_venv\Scripts\python.exe -m pip install -r requirements.txt
```

Если установлен Node.js, `doctor` дополнительно проверит синтаксис miniapp через `node --check`.
Если `doctor` запущен до установки зависимостей, он выведет ошибку `python_dependencies`
с командой установки и все равно проверит доступные статические файлы miniapp.

Поднять локальную инфраструктуру:

```powershell
docker compose up -d postgres redis
```

Если Docker/PostgreSQL недоступны, можно запустить локальный smoke на SQLite:

```powershell
Copy-Item .env.sqlite.example .env
New-Item -ItemType Directory -Force tmp | Out-Null
max_bot_venv\Scripts\python.exe -m alembic upgrade head
max_bot_venv\Scripts\python.exe -m app.cli.seed_store --max-user-id 1
max_bot_venv\Scripts\python.exe -m app.cli.doctor
max_bot_venv\Scripts\python.exe -m app.cli.bootstrap_superadmin --max-user-id 1
```

После запуска backend можно проверить команду бота через API:

```powershell
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/me" --simulate-user-id 1
```

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.doctor --skip-db
max_bot_venv\Scripts\python.exe -m alembic upgrade head
max_bot_venv\Scripts\python.exe -m app.cli.seed_store --max-user-id <MAX_USER_ID>
max_bot_venv\Scripts\python.exe -m app.cli.bootstrap_superadmin --max-user-id <MAX_USER_ID>
max_bot_venv\Scripts\python.exe -m app.cli.doctor
```

После этого запустить backend:

```powershell
max_bot_venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Проверка backend:

```text
http://127.0.0.1:8000/api/v1/health
http://127.0.0.1:8000/api/v1/ready
```

`/ready` возвращает безопасный config report и блок `checks` с состоянием БД и базовых данных miniapp.

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

Основные команды в MAX:

- `/help` - сценарий входа по Contact ID и подсказки.
- `/me` - профиль из backend: связанные ученики, балансы, роли и открытые заказы.
- `/balance` - балансы астрокоинов по связанным ученикам.
- `/ledger` - последние начисления, списания и возвраты астрокоинов по связанным ученикам.
- `/students [поиск]` - список доступных учеников с ролями, группами, площадками и балансами.
- `/access` - обзор связей доступа и staff-ролей, доступных текущему MAX user_id.
- `/accrue <AC> <ученик> | <причина>` - начислить астрокоины одному найденному ученику; права staff/admin проверяет backend.
- `/catalog [поиск]` - активные товары магазина с ценами и остатками; поиск работает по названию, SKU и категории.
- `/orders` - открытые и последние заказы пользователя из backend.
- `/order <номер>` - детальная карточка заказа: статус, состав, сумма и доступные быстрые действия.
- `/stock [порог]` - проблемные остатки магазина для staff/admin; по умолчанию порог 5 штук.
- `/ops [порог]` - операционная сводка для staff/admin: статусы заказов, ближайшие открытые заказы и остатки ниже порога.
- `/cancel <номер>`, `/issue <номер>`, `/return <номер>` - отменить, выдать или принять возврат заказа; права и складские операции проверяет backend.
- `/miniapp` - персональная ссылка на miniapp с текущим tenant и MAX user_id.
- `/status` - текущий tenant, backend API, miniapp и marker polling.
- `/ready` - readiness backend API: config report, БД и наличие базовых данных miniapp.
- `/id` - диагностический MAX user_id/chat_id.
- `/tenant <slug>` - сменить tenant для текущего пользователя.
- `/link <Contact ID>` - создать deep link для входа по Contact ID.

Кнопки меню открывают те же быстрые сценарии: каталог, баланс, заказы, учеников, историю астрокоинов, статус и miniapp.
Дополнительные alias-команды: `/menu` и `/commands` открывают помощь, `/shop` открывает каталог, `/history` открывает историю астрокоинов. Неизвестная slash-команда возвращает подсказку по командам и не запускает вход по Contact ID.

`MAX_USER_ID` для первичного суперадмина можно узнать командой `/id` в боте.
`app.cli.seed_store` создает demo tenant, каталог, склад, двух учеников, кошельки по 1000 AC и Contact ID `681`; если передать `--max-user-id`, команда сразу привяжет этот Contact ID к пользователю.
`app.cli.doctor` после подключения к БД предупреждает, если default tenant, ученики, товары или склады еще не заполнены.
В miniapp во вкладке «Операции» -> «Связи» staff/admin может отозвать или восстановить доступ родителя/ученика к конкретному ученику.
Во вкладке «Операции» -> «Сотрудники» superadmin/admin может выдавать и отзывать staff-роли по MAX user_id. Управляющие роли (`superadmin`, `partner_director`, `admin`) меняет только `superadmin`; `admin` может управлять операционными ролями `teacher` и `curator`.
Во вкладке «Операции» -> «Товары» admin может загрузить CSV/XLSX или вручную создать/отредактировать карточку товара: SKU, название, категорию, цену, описание, фото и статус. Статусы `hidden` и `archived` остаются видимыми в админском управлении, но не попадают в обычную витрину магазина.
Во вкладке «Операции» -> «Склады» admin может создать или отредактировать склад tenant: название, slug, тип и адрес.
Во вкладке «Операции» -> «Остатки» admin может корректировать фактический остаток товара на складе и перемещать свободный остаток между складами; backend пишет складские движения `adjustment`/`transfer` и не дает поставить факт ниже текущего резерва.

Сценарий магазина:

1. Ученик или родитель оформляет заказ в miniapp.
2. Backend резервирует остаток на складе и списывает астрокоины.
3. Сотрудник выдает заказ через `POST /api/v1/miniapp/orders/{order_id}/issue`.
4. Если заказ отменен, `POST /api/v1/miniapp/orders/{order_id}/cancel` снимает резерв и возвращает астрокоины.
5. Если выданный заказ вернули, `POST /api/v1/miniapp/orders/{order_id}/return` возвращает товар на склад и зачисляет астрокоины.

Операционный контроль для staff/admin доступен через `GET /api/v1/miniapp/ops/summary?max_user_id=<MAX_USER_ID>&low_stock_threshold=5` и команду `/ops`.

В miniapp эти действия доступны в разделе «Заказы»: сотрудник может выдать или принять возврат, а доступный пользователю открытый заказ можно отменить.
Если `GOOGLE_SERVICE_ACCOUNT_FILE` и `GOOGLE_SHEETS_ORDERS_SPREADSHEET_ID` заданы, заказы и изменения статусов синхронизируются в лист `orders`.

Rate limit ввода Contact ID по умолчанию работает в памяти процесса. Для нескольких backend-инстансов включите Redis:

```env
RATE_LIMIT_BACKEND=redis
REDIS_URL=redis://localhost:6379/0
RATE_LIMIT_MAX_ATTEMPTS=8
RATE_LIMIT_WINDOW_SECONDS=900
```

Перед запуском polling можно проверить локальную конфигурацию без сетевых запросов:

```powershell
max_bot_venv\Scripts\python.exe main_bot.py --config-check
```

Быстрый smoke ответа бота без MAX API и без backend:

```powershell
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/help" --simulate-offline
```

Когда `MAX_BOT_TOKEN` уже настоящий, можно проверить доступ к MAX API и активные webhook-подписки:

```powershell
max_bot_venv\Scripts\python.exe main_bot.py --check
```

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
