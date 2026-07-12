# MAX-бот и miniapp Алгоритмики

Рабочий проект MAX-бота, backend API и miniapp для входа по Contact ID, магазина подарков, заказов, складов, загрузки товаров и начисления астрокоинов.

## Что уже работает

- MAX long polling-бот с inline-кнопками.
- Вход по CRM `Contact ID`.
- Выбор роли: родитель или ученик.
- FastAPI backend с tenant-изоляцией.
- CRM XLSX import.
- Настраиваемый rate limit входа: локальная память по умолчанию или Redis для production.
- MAX-уведомления о создании, отмене, выдаче и возврате заказов.
- Miniapp:
  - обзор с показателями под роль ученика, родителя, педагога или администратора;
  - магазин;
  - мобильная нижняя навигация и компактный интерфейс для MAX WebView;
  - персональный кошелек выбранного ученика со сводкой баланса, начислений, списаний и историей операций;
  - ролевые списки заказов: личные для ученика и общие рабочие для сотрудников;
  - прямое открытие нужного раздела из MAX-уведомлений;
  - ручное обновление профиля, баланса, заказов, каталога и операционной сводки без перезапуска WebView;
  - сохранение выбранного ученика, фильтров каталога и заказов между открытиями mini-app;
  - каталог с фотографиями, поиском, сохраняемым избранным и детальной карточкой товара;
  - сортировка каталога, фильтр наличия и быстрая панель корзины с суммой заказа;
  - корзина со сводкой баланса, будущего остатка и понятным сообщением при нехватке AC;
  - сохраняемая корзина с выбором склада и количества;
  - подтверждение заказа со сводкой перед резервом склада и списанием AC;
  - карточки заказов с составом, суммой, складом, историей статусов и staff-действиями;
  - административная сводка с быстрыми переходами к выдаче, товарам и остаткам;
  - карточки связей доступа и сотрудников с отзывом, восстановлением и выдачей ролей;
  - карточки начисления AC ученикам и отдельное начисление выбранной группе;
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

То же самое одной командой для локальной разработки:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --max-user-id 1
```

По умолчанию команда делает offline-smoke бота. Если backend уже запущен в другом терминале,
можно добавить проверку связки бот -> backend:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --max-user-id 1 --with-backend-smoke
```

Или дать bootstrap временно поднять backend только на время smoke:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --max-user-id 1 --start-backend-smoke --api-port 8010
```

Сначала можно посмотреть план без изменений файлов и БД:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --dry-run
```

Если нужно использовать SQLite-профиль без перезаписи текущего `.env`:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --env-file .env.sqlite.example --max-user-id 1
```

`dev_bootstrap` по умолчанию останавливается, если текущий `DATABASE_URL` не SQLite.
Для намеренного запуска на текущей БД используйте явный флаг `--allow-non-sqlite`.
Значения из `.env` передаются во все дочерние команды bootstrap и перекрывают внешнее окружение
только внутри этого запуска.
Внутри локального bootstrap `doctor` запускается с `--allow-missing-bot-token`, поэтому backend/SQLite
подготовка не требует реального MAX-токена.

После запуска backend можно проверить команду бота через API:

```powershell
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/me" --simulate-user-id 1
```

Быстрая offline-проверка самого бота без backend и без pytest:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke
```

После запуска backend можно проверить основные сценарии через backend API:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke --with-backend --user-id 1
```

Доступны read-only профили: `basic`, `store`, `ops`. `store` проходит каталог, категории,
карточку товара, расчет цены, доступность покупки, карточку последнего открытого заказа и экран подтверждения order action; `ops` проходит складские и операторские команды.

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke --with-backend --user-id 1 --profile store
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke --with-backend --user-id 1 --profile ops
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke --with-backend --user-id 1 --profile all
```

Для точечной проверки можно передать свои команды и callbacks:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke --command "/version" --callback "orders:open"
```

Если передан хотя бы один `--command` или `--callback`, smoke запускает только явно указанные проверки.

Для полного read-only backend smoke через bootstrap:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.dev_bootstrap --max-user-id 1 --start-backend-smoke --backend-smoke-profile all --api-port 8010
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

Mini-app откроется по адресу `http://127.0.0.1:8000/miniapp?max_user_id=1`.
Для просмотра интерфейса без MAX и backend-данных используйте demo-режим:
`http://127.0.0.1:8000/miniapp?demo=1`.

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
$env:MAX_API_TIMEOUT_SECONDS = "15"
$env:MAX_POLL_TIMEOUT_SECONDS = "30"
$env:MAX_BACKEND_API_BASE = "http://127.0.0.1:8000/api/v1"
$env:MAX_BACKEND_TIMEOUT_SECONDS = "15"
$env:DEFAULT_TENANT_SLUG = "nizhniy-novgorod-partner-a"
$env:MAX_MINIAPP_URL = "http://127.0.0.1:8000/miniapp"
$env:MAX_DROP_WEBHOOKS_ON_START = "false"
$env:MAX_ORDER_NOTIFICATIONS_ENABLED = "true"
max_bot_venv\Scripts\python.exe main_bot.py
```

`MAX_API_TIMEOUT_SECONDS` задает таймаут обычных запросов к MAX API, `MAX_POLL_TIMEOUT_SECONDS`
задает long polling timeout, `MAX_BACKEND_TIMEOUT_SECONDS` задает таймаут запросов бота к backend API.
`MAX_DROP_WEBHOOKS_ON_START=true` разрешает polling-боту удалять активные webhook-подписки при старте; разово то же делает `--drop-webhooks`.
`MAX_ORDER_NOTIFICATIONS_ENABLED=true` отправляет создателю заказа и связанным родителям/ученикам сообщения MAX при создании, отмене, выдаче и возврате заказа. Кнопка в сообщении сразу открывает вкладку заказов mini-app.
Для телефона в MAX `MAX_MINIAPP_URL` нужно заменить на публичный HTTPS-адрес.

Основные команды в MAX:

- `/help [shop|orders|students|staff|setup]` - сценарий входа по Contact ID, общие команды и короткие разделы помощи.
- `/me` - профиль из backend: связанные ученики, балансы, роли и открытые заказы; aliases: `/whoami`, `/profile`.
- `/search <текст>` - общий поиск по товарам, ученикам и заказам; alias: `/find`.
- `/balance [ученик]` - балансы астрокоинов по связанным ученикам; alias: `/wallet`.
- `/lowbalance [AC]` - ученики с балансом ниже порога; по умолчанию 200 AC; alias: `/lowwallets`.
- `/ledger [поиск]` - последние начисления, списания и возвраты; фильтр по ученику, причине, направлению или дате.
- `/students [поиск]` - список доступных учеников с ролями, группами, площадками и балансами.
- `/groups [поиск]` - сводка по группам: ученики, суммарный баланс, низкие балансы и открытые заказы; alias: `/classes`.
- `/leaderboard [поиск]` - топ учеников по балансу AC с фильтром по группе, площадке или преподавателю; aliases: `/top`, `/leaders`.
- `/student <поиск>` - карточка одного ученика: профиль, баланс, последние заказы и операции.
- `/access` - обзор связей доступа и staff-ролей, доступных текущему MAX user_id.
- `/accessoff <id>` и `/accesson <id>` - отозвать или восстановить связь доступа по ID из `/access`; права проверяет backend.
- `/staffrole <MAX_ID> <role> [active|revoked] [| имя]` - выдать или отозвать staff-роль; aliases: `/staffset`, `/staffoff`, `/staffon`.
- `/accrue <AC> <ученик> | <причина>` - начислить астрокоины одному найденному ученику; права staff/admin проверяет backend.
- `/catalog [поиск]` - активные товары магазина с ценами и остатками; поиск работает по названию, SKU и категории.
- `/categories` - разделы каталога с количеством товаров, общим остатком и готовыми поисковыми командами.
- `/product <SKU или товар>` - карточка товара: цена, описание, остатки по складам и быстрая команда покупки.
- `/quote <SKU> [шт.][, SKU шт.] [| <ученик>]` - рассчитать корзину, остатки и баланс без создания заказа и списания AC.
- `/canbuy <SKU> [шт.][, SKU шт.] [| фильтр]` - показать, каким ученикам хватает AC на корзину; alias: `/afford`.
- `/buy <SKU> [шт.][, SKU шт.] [| <ученик>]` - оформить заказ из чата; если связан один ученик, бот выберет его автоматически, иначе попросит уточнить ученика после `|`.
- `/orders [open|issued|cancelled|поиск]` - открытые, последние или найденные заказы пользователя из backend.
- `/myorders` - короткий alias для `/orders`; `/open` - короткий alias для `/orders open`.
- `/order <номер>` - детальная карточка заказа: статус, состав, сумма и кнопки быстрых действий.
- `/last [open|issued|cancelled]` - последняя карточка заказа или ближайший заказ с нужным статусом без поиска номера.
- `/sales [open|issued|cancelled|all]` - сумма заказов, разрез по статусам и топ товаров; alias: `/revenue`.
- `/repeat <номер>` - повторить заказ теми же товарами; backend заново проверит остатки, баланс и права.
- `/productset <SKU> | <название> | <цена> [| категория] [| статус] [| описание]` - создать или обновить товар; статус: `active`, `hidden`, `archived`.
- `/setprice <SKU или товар> <цена>` - быстро изменить цену существующего товара; alias: `/pricechange`.
- `/productstatus <SKU или товар> <active|hidden|archived>` - изменить видимость товара; aliases: `/hideproduct`, `/showproduct`, `/archiveproduct`.
- `/setphoto <SKU или товар> | <url>` - обновить фото товара; `/clearphoto <SKU или товар>` - удалить фото.
- `/stock [порог]` - проблемные остатки магазина для staff/admin; по умолчанию порог 5 штук; alias: `/lowstock`.
- `/inventory [порог]` - расширенный список остатков; без порога показывает позиции с остатком до 999 штук.
- `/warehouses` - склады tenant, slug, типы и суммарные остатки; alias: `/wh`.
- `/warehouse <slug> | <название> [| type] [| адрес]` - создать или обновить склад; type: `common`, `venue`, `partner`, `external`.
- `/setstock <SKU> <остаток> [| склад]` - установить фактический остаток товара на складе; права проверяет backend.
- `/transfer <SKU> <шт> | <откуда> -> <куда>` - переместить свободный остаток между складами; alias: `/move`.
- `/ops [порог]` - операционная сводка для staff/admin: статусы заказов, ближайшие открытые заказы и остатки ниже порога; aliases: `/dashboard`, `/overview`.
- `/todo [порог]` - компактный список ближайших заказов к выдаче и низких остатков для staff/admin.
- `/cancel <номер>`, `/issue <номер>`, `/return <номер>` - отменить, выдать или принять возврат заказа; права и складские операции проверяет backend. Staff aliases: `/void`, `/done`, `/refund`.
- Для `/repeat`, `/cancel`, `/issue`, `/return`, кнопок карточки заказа и staff aliases нужен точный номер заказа; слова `last`/`open` не выполняют действие. Сначала откройте `/last open` или `/orders open`, затем используйте номер. Кнопки карточки заказа перед изменением заказа показывают отдельное подтверждение.
- `/miniapp` - персональная ссылка на miniapp с текущим tenant и MAX user_id.
- `/status` - текущий/default tenant, MAX/backend/miniapp URL, marker polling и быстрые команды проверки.
- `/setup` - короткая справка по запуску, `.env`, readiness и диагностическим командам.
- `/version` или `/about` - версия приложения, revision, окружение и runtime-ссылки для быстрой диагностики.
- `/config` или `/doctor` - безопасный локальный config report без секретов.
- `/ready` - readiness backend API: config report, БД и наличие базовых данных miniapp.
- `/id` - диагностический MAX user_id/chat_id, текущий tenant, backend API и miniapp URL.
- `/tenant <slug|reset>` - сменить tenant для текущего пользователя или вернуть default; slug принимает латинские буквы, цифры, `-` и `_`.
- `/link <Contact ID>` - создать deep link для входа по Contact ID.

Кнопки меню открывают те же быстрые сценарии: каталог, баланс, все заказы, открытые заказы, учеников, группы, рейтинг AC, историю астрокоинов, staff-сводку, заказы к выдаче, проблемные остатки, статус и miniapp.
Обычный текст без `/` сначала проверяется как Contact ID; если backend не нашел такой Contact ID и текст похож на название/SKU товара, бот покажет поиск по каталогу.
Дополнительные alias-команды: `/menu` и `/commands` открывают помощь, `/shop` открывает каталог, `/history` открывает историю астрокоинов, `/myorders` открывает заказы, `/open` открывает открытые заказы, `/price` рассчитывает корзину как `/quote`. Неизвестная slash-команда возвращает подсказку по командам и не запускает вход по Contact ID.
В групповых чатах поддерживаются команды с упоминанием бота, например `/help@BotName shop`; команды, адресованные другому боту, игнорируются.

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

Для `APP_ENV` вне `local/dev/development/test` команда `doctor` считает placeholder
`APP_SECRET_KEY=replace_me` ошибкой, а не предупреждением.

Перед запуском polling можно проверить локальную конфигурацию без сетевых запросов:

```powershell
max_bot_venv\Scripts\python.exe main_bot.py --config-check
```

Быстрый smoke ответа бота без MAX API и без backend:

```powershell
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/help" --simulate-offline
max_bot_venv\Scripts\python.exe main_bot.py --simulate-callback "orders:open" --simulate-offline
max_bot_venv\Scripts\python.exe main_bot.py --simulate-callback "groups" --simulate-offline
max_bot_venv\Scripts\python.exe main_bot.py --simulate-callback "leaderboard" --simulate-offline
max_bot_venv\Scripts\python.exe main_bot.py --simulate-callback "todo" --simulate-offline
max_bot_venv\Scripts\python.exe main_bot.py --simulate-callback "stock" --simulate-offline
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
