# MAX-бот и miniapp Алгоритмики

Рабочий проект MAX-бота, backend API и miniapp для входа по Contact ID, магазина подарков, преподавательского расписания, обратных связей, заказов, складов и астрокоинов.

Production-развертывание на российском VPS: [DEPLOYMENT_RU.md](DEPLOYMENT_RU.md).

## Что уже работает

- MAX-бот с inline-кнопками: long polling локально, webhook в production.
- Компактные меню под роли ученика, родителя, преподавателя, куратора, администратора,
  директора и суперадминистратора.
- Первый вход нового пользователя: выбор роли родителя или ученика, затем вход по CRM `Contact ID`.
- FastAPI backend с tenant-изоляцией и проверкой подписанных данных запуска MAX WebApp.
- База знаний старого бота с рабочими документами, учебными ресурсами и контактами.
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
  - сохраняемая корзина с выбором количества без показа складов покупателю;
  - подтверждение заказа со сводкой перед списанием AC;
  - карточки заказов с составом, суммой, складом, историей статусов и staff-действиями;
  - административная сводка с быстрыми переходами к выдаче, товарам и остаткам;
  - карточки связей доступа и сотрудников с отзывом, восстановлением и выдачей ролей;
  - карточки начисления AC ученикам и отдельное начисление выбранной группе;
  - CRM XLSX-импорт учеников и групп администратором или директором с предпросмотром;
  - преподавательское расписание с добавлением групп, выбором курса, даты, времени и номера урока;
  - автоматическая генерация ОС по расписанию в mini-app;
  - ручной inline-мастер ОС в MAX-боте по материалам 21 курса и 736 уроков;
  - история готовых ОС, учет отсутствующих учеников и повторения темы;
  - ручная отправка готовой ОС связанным MAX-аккаунтам родителей;
  - отдельная настройка автоматической доставки родителям для каждой группы;
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

`seed_store` автоматически импортирует `data/courses.json`. Повторный ручной импорт:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.import_courses
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

Быстрая offline-проверка самого бота без backend и без pytest:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke
```

После запуска backend можно проверить меню и обратную связь:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke --with-backend --user-id 1 --profile ops
```

Для точечной проверки можно передать `/start` и актуальные callbacks:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.bot_smoke --command "/start" --callback "help"
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

В local-режиме mini-app откроется по адресу
`http://127.0.0.1:8000/miniapp?max_user_id=1`.
В production прямой URL не дает доступ к данным: кабинет нужно открывать кнопкой MAX-бота.
Backend получает `MAX user_id` только из подписанных данных запуска MAX WebApp, поэтому пересылка
ссылки другому пользователю не передает ему чужую роль.
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
http://127.0.0.1:8000/miniapp?demo=1&demo_role=student
http://127.0.0.1:8000/miniapp?demo=1&demo_role=parent
http://127.0.0.1:8000/miniapp?demo=1&demo_role=teacher
http://127.0.0.1:8000/miniapp?demo=1&demo_role=curator
http://127.0.0.1:8000/miniapp?demo=1&demo_role=admin
http://127.0.0.1:8000/miniapp?demo=1&demo_role=partner_director
http://127.0.0.1:8000/miniapp?demo=1&demo_role=superadmin
```

Матрица разделов miniapp:

- ученик: обзор своего профиля, магазин, корзина, свои заказы и история AC;
- родитель: семейный обзор, магазин, корзина, заказы и история AC привязанных детей;
- преподаватель: свои ученики и группы, их заказы, история AC, начисления и расписание;
- куратор: ученики, заказы, начисления, расписание и обратная связь по филиалу;
- администратор/директор: весь tenant, заказы, AC, начисления, расписание и операции с товарами,
  остатками, складами, импортом CRM, связями и сотрудниками.

Преподаватель не видит магазин, корзину, чужие группы и чужие заказы. Ученик и родитель не
видят начисления, расписание и административные операции.

Запуск MAX-бота:

```powershell
$env:MAX_BOT_TOKEN = "..."
$env:MAX_BOT_USERNAME = "your_bot_username"
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

Автоматическую подготовку и отправку ОС запустить отдельным процессом:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.feedback_worker
```

Для однократной обработки занятий используется `--once`. Интервал задается через
`FEEDBACK_WORKER_INTERVAL_SECONDS`, отключение - через `FEEDBACK_WORKER_ENABLED=false`.
Worker всегда готовит ОС преподавателю. Если в расписании группы включена доставка родителям,
он дополнительно находит активные родительские связи учеников этой группы и отправляет текст им.

`MAX_API_TIMEOUT_SECONDS` задает таймаут обычных запросов к MAX API, `MAX_POLL_TIMEOUT_SECONDS`
задает long polling timeout, `MAX_BACKEND_TIMEOUT_SECONDS` задает таймаут запросов бота к backend API.
`MAX_DROP_WEBHOOKS_ON_START=true` разрешает polling-боту удалять активные webhook-подписки при старте; разово то же делает `--drop-webhooks`.
`MAX_ORDER_NOTIFICATIONS_ENABLED=true` отправляет создателю заказа и связанным родителям/ученикам сообщения MAX при создании, отмене, выдаче и возврате заказа. Кнопка в сообщении сразу открывает вкладку заказов mini-app.
Для телефона в MAX `MAX_MINIAPP_URL` нужно заменить на публичный HTTPS-адрес.
`MAX_BOT_USERNAME` задаётся без `@`; он нужен нативной кнопке открытия mini-app.

Интерфейс MAX-бота:

- текстовые команды не используются; `/start` остается только системной точкой входа MAX;
- ученик получает кнопку личного кабинета;
- родитель получает кнопку семейного кабинета;
- преподаватель и куратор получают рабочий кабинет и раздел «Обратная связь»;
- директор tenant, superadmin и admin получают рабочий кабинет и раздел «Обратная связь»;
- преподаватель, куратор и управляющие роли получают раздел «База знаний»;
- магазин, баланс, заказы, группы, начисления, импорт и управление складами работают только
  в mini-app и не дублируются сообщениями бота;
- старые команды и кнопки безопасно возвращают пользователя в актуальное inline-меню.

При первом обращении аккаунта без действующих связей и staff-ролей бот обязательно показывает
выбор «Родитель»/«Ученик», затем просит CRM `Contact ID`. Staff-роли через этот сценарий не выдаются:
их назначает администратор в mini-app. Роль `superadmin` создается только явной командой
`app.cli.bootstrap_superadmin` и не назначается автоматически при первом входе.

Ручной сценарий обратной связи в MAX-боте полностью кнопочный и не требует расписания:

1. Сотрудник открывает раздел «Обратная связь».
2. Нажимает «Создать ОС вручную» и выбирает доступную CRM-группу.
3. Выбирает курс и конкретный урок.
4. Кнопками задает дату, формат занятия, отсутствующих и повторение прошлой темы.
5. Проверяет сформированный текст и отправляет его связанным родительским аккаунтам.

Ручные черновики сохраняются отдельно в backend и доступны только через раздел MAX-бота.
В mini-app настраиваются расписание, курсы, автоматическая подготовка ОС после занятия и
автоматическая доставка родителям. Права и список групп проверяются
для текущего tenant: преподаватель работает только со своими группами, куратор и управляющие
роли могут работать со всеми группами tenant.

`MAX_USER_ID` для первичного суперадмина можно узнать из события `bot_started`/webhook MAX
или в кабинете приложения MAX, после чего его нужно явно передать в `app.cli.bootstrap_superadmin`.
`app.cli.seed_store` создает demo tenant, каталог, склад, двух учеников, кошельки по 1000 AC и Contact ID `681`; если передать `--max-user-id`, команда сразу привяжет этот Contact ID к пользователю.
`app.cli.doctor` после подключения к БД предупреждает, если default tenant, ученики, товары или склады еще не заполнены.
В miniapp во вкладке «Операции» -> «Связи» staff/admin может отозвать или восстановить доступ родителя/ученика к конкретному ученику.
Во вкладке «Операции» -> «Сотрудники» superadmin/admin может выдавать и отзывать staff-роли по MAX user_id. Управляющие роли (`superadmin`, `partner_director`, `admin`) меняет только `superadmin`; `admin` может управлять операционными ролями `teacher` и `curator`.
Во вкладке «Операции» -> «Товары» admin может вручную создать или отредактировать цельную карточку товара: загрузить JPEG/PNG/WebP, проверить предпросмотр, заполнить SKU, название, категорию, цену, описание и статус, затем сохранить одной кнопкой. Массовая загрузка CSV/XLSX находится в отдельном сворачиваемом блоке. Статусы `hidden` и `archived` остаются видимыми в админском управлении, но не попадают в обычную витрину магазина.
Во вкладке «Операции» -> «Склады» admin может создать или отредактировать склад tenant: название, slug, тип и адрес.
Во вкладке «Операции» -> «Остатки» admin может корректировать фактический остаток товара на складе и перемещать свободный остаток между складами; backend пишет складские движения `adjustment`/`transfer` и не дает поставить факт ниже текущего резерва.

Сценарий магазина:

1. Ученик или родитель оформляет заказ в miniapp.
2. Backend списывает астрокоины и показывает покупателю статус «Зарезервировано».
3. Администратор или директор выбирает склад для каждой позиции; только после этого резервируется
   складской остаток.
4. Сотрудник выдает заказ через `POST /api/v1/miniapp/orders/{order_id}/issue`.
5. Отмена снимает созданный резерв, если склад уже назначен, и возвращает астрокоины.
6. Возврат выданного заказа возвращает товар на склад и зачисляет астрокоины.

Операционный контроль для staff/admin доступен в mini-app и через
`GET /api/v1/miniapp/ops/summary?max_user_id=<MAX_USER_ID>&low_stock_threshold=5`.

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

Быстрый smoke inline-меню без MAX API и backend:

```powershell
max_bot_venv\Scripts\python.exe main_bot.py --simulate-command "/start" --simulate-offline
max_bot_venv\Scripts\python.exe main_bot.py --simulate-callback "help" --simulate-offline
```

Когда `MAX_BOT_TOKEN` уже настоящий, можно проверить доступ к MAX API и активные webhook-подписки:

```powershell
max_bot_venv\Scripts\python.exe main_bot.py --check
```

## Проверки

```powershell
max_bot_venv\Scripts\ruff.exe check app alembic
max_bot_venv\Scripts\python.exe -m pytest tests --ignore=tests/test_main_bot.py -q
max_bot_venv\Scripts\python.exe -m compileall -q app main_bot.py
node --check app\web\static\miniapp\app.js
```

`tests/test_main_bot.py` проверяет удаленные текстовые команды прежнего интерфейса и пока
оставлен только как архив сценариев; актуальное меню проверяет `tests/test_bot_inline_feedback.py`.

## Форматы данных

CRM и Google Sheets описаны в `DATA_INTEGRATION_DRAFT_RU.md`.

Проверить CRM XLSX без записи в базу:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.import_crm `
  --path ".\актинвые стадии воронка контроль оплат.xlsx" `
  --tenant-slug n-novgorod `
  --partner-slug partner-a `
  --partner-name "Партнер А" `
  --dry-run
```

Выполнить импорт:

```powershell
max_bot_venv\Scripts\python.exe -m app.cli.import_crm `
  --path ".\актинвые стадии воронка контроль оплат.xlsx" `
  --tenant-slug n-novgorod `
  --partner-slug partner-a `
  --partner-name "Партнер А"
```

Для выгрузки выбывших добавьте `--student-status departed`. Если загружаются оба файла,
сначала импортируйте выбывших, затем активных: при пересечении последняя активная выгрузка
сохранит актуальный статус ученика.

Группа хранится в карточке ученика (`students.group_name`). Mini-app собирает список групп
из уникальных значений внутри текущего tenant. `--tenant-slug` фиксирует серверный импорт
в одном филиале; повторный импорт обновляет учеников по LMS ID, CRM UUID/ID сделки либо
Contact ID вместе с ФИО и не создает повторные кошельки.

После первичной настройки роли `superadmin`, `partner_director` и `admin` могут повторно
загружать CRM XLSX без доступа к серверу: `Операции -> Импорт CRM`. Сначала показывается
сводка файла без записи, затем отдельная кнопка подтверждает импорт в текущий tenant.
Перед проверкой файла нужно выбрать «Активные ученики» или «Выбывшие ученики».

Технические команды и состояние backend описаны в `DEVELOPMENT.md`.
