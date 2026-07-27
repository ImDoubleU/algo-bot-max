# Развертывание MAX-бота и mini-app в России

Production-схема проекта:

`MAX -> HTTPS/Nginx -> FastAPI webhook -> PostgreSQL`

FastAPI одновременно отдает mini-app и backend API. Отдельный worker готовит обратные связи.
Long polling в production не запускается.

## 1. Что нужно подготовить

- VPS в российском дата-центре: Ubuntu 24.04, 2 vCPU, 4 ГБ RAM, 40-60 ГБ SSD.
- Публичный IPv4.
- Домен или поддомен, например `bot.example.ru`.
- Токен созданного MAX-бота.
- Ваш MAX user ID для первой роли superadmin.
- CRM XLSX-файлы для повторного импорта учеников в production-базу.

Подойдут Selectel, Timeweb Cloud, VK Cloud или другой российский VPS с публичным IP.

## 2. Настроить домен

В DNS создайте запись:

```text
Тип: A
Имя: bot
Значение: ПУБЛИЧНЫЙ_IP_VPS
TTL: 300
```

Проверьте с компьютера:

```powershell
Resolve-DnsName bot.example.ru
```

## 3. Подготовить Ubuntu

Подключитесь к серверу:

```bash
ssh root@ПУБЛИЧНЫЙ_IP_VPS
```

Установите системные пакеты:

```bash
apt update && apt upgrade -y
apt install -y git curl nginx postgresql postgresql-client redis-server \
  python3 python3-venv python3-pip certbot python3-certbot-nginx
systemctl enable --now postgresql redis-server nginx
```

Если на VPS используется UFW, откройте только SSH и веб-порты:

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
```

Создайте пользователя и каталог приложения:

```bash
useradd --system --create-home --home-dir /home/algomax --shell /bin/bash algomax
install -d -o algomax -g algomax -m 0750 /opt/algo-max
```

## 4. Загрузить проект

Через Git:

```bash
sudo -u algomax git clone ВАШ_URL_РЕПОЗИТОРИЯ /opt/algo-max
cd /opt/algo-max
```

Если репозиторий закрытый, сначала добавьте deploy key или передайте архив проекта по SCP.
Локальный `.env`, SQLite и CRM-выгрузки в Git не входят.

Создайте виртуальное окружение:

```bash
bash deploy/scripts/install_russian_ca.sh
sudo -u algomax python3 -m venv /opt/algo-max/.venv
sudo -u algomax /opt/algo-max/.venv/bin/pip install --upgrade pip
sudo -u algomax /opt/algo-max/.venv/bin/pip install -r /opt/algo-max/requirements-prod.txt
```

## 5. Создать PostgreSQL

Сгенерируйте пароль без пробелов:

```bash
openssl rand -hex 24
```

Создайте пользователя и базу, подставив пароль:

```bash
sudo -u postgres psql <<'SQL'
CREATE USER algomax WITH PASSWORD 'ВСТАВЬТЕ_ПАРОЛЬ';
CREATE DATABASE algo_bot_max OWNER algomax;
SQL
```

## 6. Заполнить production-конфигурацию

Установите серверные шаблоны, подставив свой домен:

```bash
cd /opt/algo-max
bash deploy/scripts/install_server_files.sh bot.example.ru
nano /etc/algo-max/algo-max.env
```

Скрипт сам создает `/etc/algo-max/algo-max.env` при первом запуске и сразу
подставляет домен. При повторном запуске существующий env не перезаписывается.

Обязательно замените:

- `APP_SECRET_KEY`: результат `openssl rand -hex 32`.
- `MAX_BOT_TOKEN`: токен MAX.
- `MAX_WEBHOOK_SECRET`: результат `openssl rand -hex 32`.
- `MINIAPP_TOKEN_TTL_SECONDS`: срок подписанной ссылки mini-app; штатное значение `2592000`.
- `bot.example.ru`: реальный домен во всех URL.
- `CHANGE_DB_PASSWORD`: пароль PostgreSQL; спецсимволы должны быть URL-кодированы.
- `DEFAULT_TENANT_SLUG`: slug импортированного филиала.
- `INITIAL_SUPERADMIN_MAX_USER_ID`: ваш числовой MAX user ID.

Проверьте конфигурацию:

```bash
cd /opt/algo-max
set -a
source /etc/algo-max/algo-max.env
set +a
sudo -u algomax --preserve-env /opt/algo-max/.venv/bin/python main_bot.py --config-check
sudo -u algomax --preserve-env /opt/algo-max/.venv/bin/python -m app.cli.doctor \
  --production --skip-db
```

## 7. Создать таблицы и загрузить данные

```bash
cd /opt/algo-max
set -a
source /etc/algo-max/algo-max.env
set +a
sudo -u algomax --preserve-env /opt/algo-max/.venv/bin/python -m alembic upgrade head
```

Создайте закрытый каталог импорта:

```bash
install -d -o algomax -g algomax -m 0750 /opt/algo-max/import
```

Передайте CRM-файл с компьютера и выдайте права `algomax`:

```powershell
scp ".\актинвые стадии воронка контроль оплат.xlsx" `
  root@ПУБЛИЧНЫЙ_IP_VPS:/opt/algo-max/import/active.xlsx
ssh root@ПУБЛИЧНЫЙ_IP_VPS "chown algomax:algomax /opt/algo-max/import/active.xlsx"
```

Сначала выполните просмотр, затем импорт:

```bash
sudo -u algomax --preserve-env /opt/algo-max/.venv/bin/python -m app.cli.import_crm \
  --path /opt/algo-max/import/active.xlsx \
  --tenant-slug n-novgorod \
  --partner-slug n-novgorod \
  --partner-name "Нижний Новгород" \
  --dry-run

sudo -u algomax --preserve-env /opt/algo-max/.venv/bin/python -m app.cli.import_crm \
  --path /opt/algo-max/import/active.xlsx \
  --tenant-slug n-novgorod \
  --partner-slug n-novgorod \
  --partner-name "Нижний Новгород"
```

`--tenant-slug` фиксирует импорт в одном филиале. Повторный запуск обновляет
учеников в этом tenant и не создает tenant-ы с повторяющимися slug.

Если есть отдельная выгрузка выбывших, сначала импортируйте ее с
`--student-status departed`, затем повторите команды для `active.xlsx` без этого
параметра. Активная выгрузка выполняется последней и остается источником актуального
статуса при пересечениях.

Затем загрузите курсы в созданный tenant и назначьте первый superadmin:

```bash
sudo -u algomax --preserve-env /opt/algo-max/.venv/bin/python -m app.cli.import_courses \
  --tenant-slug n-novgorod
sudo -u algomax --preserve-env /opt/algo-max/.venv/bin/python -m app.cli.bootstrap_superadmin \
  --tenant-slug n-novgorod \
  --max-user-id "$INITIAL_SUPERADMIN_MAX_USER_ID"
```

После импорта удалите XLSX с VPS или перенесите его в закрытое хранилище.

Первичный импорт выполняется на сервере, потому что tenant и первая роль еще не созданы.
После назначения `partner_director` или `admin` последующие CRM XLSX загружаются в mini-app:
`Операции -> Импорт CRM -> Состав выгрузки -> Проверить файл -> Импортировать`.

## 8. Запустить API и получить HTTPS

```bash
systemctl enable --now algo-max-api algo-max-feedback algo-max-backup.timer
systemctl status algo-max-api --no-pager
curl http://127.0.0.1:8000/api/v1/health
curl --fail http://127.0.0.1:8000/api/v1/ready
```

Получите публичный сертификат:

```bash
certbot --nginx -d bot.example.ru --redirect
certbot renew --dry-run
curl https://bot.example.ru/api/v1/health
curl https://bot.example.ru/api/v1/ready
```

Для автоматического завершения после обновления DNS можно выполнить:

```bash
bash deploy/scripts/finish_domain_setup.sh bot.example.ru ПУБЛИЧНЫЙ_IP_VPS
```

Mini-app должна открыться по адресу `https://bot.example.ru/miniapp`.

## 9. Подключить MAX webhook

С активированным окружением зарегистрируйте подписку:

```bash
cd /opt/algo-max
set -a
source /etc/algo-max/algo-max.env
set +a
sudo -u algomax --preserve-env /opt/algo-max/.venv/bin/python -m app.cli.configure_webhook
sudo -u algomax --preserve-env /opt/algo-max/.venv/bin/python -m app.cli.configure_webhook --list
```

Webhook: `https://bot.example.ru/api/v1/max/webhook`.
Mini-app URL: `https://bot.example.ru/miniapp`.

Укажите URL mini-app в настройках приложения MAX. Затем откройте диалог с ботом,
запустите его штатной кнопкой MAX и проверьте ролевое inline-меню, рабочий кабинет
и раздел «Обратная связь».

## 10. Проверить рабочий сценарий

1. Войти своим MAX-аккаунтом и открыть mini-app.
2. Убедиться, что superadmin видит операции и сотрудников.
3. Выдать преподавателю роль через раздел сотрудников.
4. Открыть mini-app преподавателя и проверить только его группы.
5. Добавить расписание группы и сформировать тестовую обратную связь.
6. Привязать тестового ученика по Contact ID.
7. Начислить AC, оформить тестовый заказ и отменить его.
8. В разделе операций создать реальный склад и загрузить CSV/XLSX каталога товаров.

Логи при ошибках:

```bash
journalctl -u algo-max-api -f
journalctl -u algo-max-feedback -f
tail -f /var/log/nginx/error.log
```

## 11. Резервные копии и обновления

Backup запускается каждый день около 03:20 и хранит дампы 14 дней:

```bash
systemctl list-timers algo-max-backup.timer
systemctl start algo-max-backup.service
ls -lh /var/backups/algo-max
```

Восстановление в пустую базу:

```bash
systemctl stop algo-max-api algo-max-feedback
pg_restore --clean --if-exists --no-owner \
  --dbname 'postgresql://algomax:ПАРОЛЬ@127.0.0.1:5432/algo_bot_max' \
  /var/backups/algo-max/algo_bot_max_YYYYMMDDTHHMMSSZ.dump
systemctl start algo-max-api algo-max-feedback
```

Обновление после публикации нового коммита:

```bash
cd /opt/algo-max
bash deploy/scripts/update_app.sh
curl https://bot.example.ru/api/v1/ready
```

`update_app.sh` сам устанавливает зависимости, применяет миграции, запускает
production doctor, перезапускает процессы и проверяет локальный health endpoint.

## Что остается ручным

- Купить VPS и домен.
- Создать MAX-бота и получить токен.
- Подставить production-секреты и ваш MAX user ID.
- Передать CRM XLSX и выполнить production-импорт.
- Создать склад и загрузить реальный каталог товаров.
- Указать HTTPS URL mini-app в кабинете MAX.
- Провести один полный сценарий преподавателя и ученика на реальных аккаунтах.

Обычное первичное развертывание занимает 1-2 часа после получения VPS, домена и токена.
DNS и выпуск сертификата иногда добавляют еще до нескольких часов ожидания.
