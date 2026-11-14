# FurniCore ERP — Руководство по развёртыванию в продакшене (Production Deployment Guide)

**Версия документа:** 1.0.0  
**Дата актуализации:** 14 ноября 2026 г.  
**Целевая платформа:** Ubuntu 24.04 LTS (x86_64)  
**Технологический стек:** Python 3.12, Django 5.1.15, PostgreSQL 16, Gunicorn 23.x, Nginx 1.24+, systemd  

---

## 1. Введение и архитектура решения

FurniCore ERP спроектирован для высоконадёжной работы на современных дистрибутивах Linux (рекомендуется **Ubuntu 24.04 LTS**). Архитектура развёртывания построена по классической многоуровневой схеме:

```
[ Интернет / Клиенты (Браузеры) ]
             │  (HTTPS : 443 / HTTP : 80 с автоматическим редиректом)
             ▼
      [ Nginx 1.24+ ]
      ├─► Статика: /var/www/furnicore/staticfiles/
      ├─► Медиа:   /var/www/furnicore/media/
      └─► Проксирование: http://127.0.0.1:8000 (UNIX socket или TCP)
             │
             ▼
  [ Gunicorn 23.x (WSGI) ]
      ├─ Управляется через systemd (furnicore.service)
      ├─ Воркеры: (2 * CPU_CORES) + 1 (режим sync/gthread)
      ├─ Пул соединений к БД (CONN_MAX_AGE=600)
             │
             ▼
   [ PostgreSQL 16 ]
      └─ База: furnicore_db (локальный сокет или 127.0.0.1:5432)
```

---

## 2. Минимальные и рекомендуемые требования к серверу (VPS / Bare Metal)

| Параметр | Минимальные требования (до 50 польз.) | Рекомендуемые требования (50–300 польз.) |
|---|---|---|
| **Процессор (vCPU)** | 2 ядра | 4–8 ядер |
| **Оперативная память (RAM)** | 4 GB | 8–16 GB |
| **Накопитель (NVMe / SSD)** | 40 GB NVMe | 100+ GB NVMe |
| **ОС** | Ubuntu 22.04 / 24.04 LTS x86_64 | Ubuntu 24.04 LTS x86_64 |
| **Сеть** | 100 Мбит/с, статический публичный IPv4 | 1 Гбит/с, статический публичный IPv4 |

---

## 3. Подготовка операционной системы

### 3.1. Обновление пакетов
```bash
sudo apt update && sudo apt upgrade -y
```

### 3.2. Установка системных зависимостей
```bash
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    build-essential \
    libpq-dev \
    postgresql-16 \
    postgresql-client-16 \
    nginx \
    certbot \
    python3-certbot-nginx \
    git \
    curl \
    ufw
```

### 3.3. Настройка межсетевого экрана (UFW)
Разрешите только необходимые порты:
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status verbose
```
> [!IMPORTANT]
> Порты 5432 (PostgreSQL) и 8000 (Gunicorn) **не должны** быть открыты во внешнюю сеть. Доступ к ним осуществляется только локально (127.0.0.1).

---

## 4. Создание системного пользователя и каталогов

Для изоляции процесса веб-приложения создаётся выделенный системный пользователь `furnicore` без прав входа по паролю (shell: `/bin/bash`):

```bash
# Создание системного пользователя и группы
sudo adduser --system --group --home /var/www/furnicore furnicore

# Создание структуры каталогов
sudo mkdir -p /var/www/furnicore/{app,staticfiles,media,logs,backups}

# Назначение владельца и прав
sudo chown -R furnicore:furnicore /var/www/furnicore
sudo chmod 750 /var/www/furnicore
sudo chmod 770 /var/www/furnicore/logs
sudo chmod 700 /var/www/furnicore/backups
```

---

## 5. Настройка базы данных PostgreSQL 16

### 5.1. Создание пользователя и базы данных
Переключитесь под пользователя `postgres` и выполните команды в psql:

```bash
sudo -u postgres psql
```

В консоли PostgreSQL:
```sql
-- Создание выделенного пользователя БД
CREATE USER furnicore_user WITH PASSWORD 'CHANGE_THIS_TO_A_VERY_STRONG_DB_PASSWORD_123';

-- Создание производственной базы данных
CREATE DATABASE furnicore_db OWNER furnicore_user;

-- Оптимальные параметры сессии для Django
ALTER ROLE furnicore_user SET client_encoding TO 'utf8';
ALTER ROLE furnicore_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE furnicore_user SET timezone TO 'Asia/Almaty';

-- Предоставление полных прав на базу
GRANT ALL PRIVILEGES ON DATABASE furnicore_db TO furnicore_user;
\q
```

---

## 6. Развёртывание приложения FurniCore ERP

### 6.1. Клонирование репозитория
Выполняйте команды от пользователя `furnicore`:

```bash
sudo -u furnicore -i
cd /var/www/furnicore

# Клонирование репозитория в каталог app
git clone -b python-django https://github.com/your-org/furnicore-erp.git app
cd /var/www/furnicore/app
```

### 6.2. Создание виртуального окружения Python
```bash
python3.12 -m venv /var/www/furnicore/venv
source /var/www/furnicore/venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install --no-cache-dir -r requirements.txt
```

### 6.3. Настройка файла конфигурации `.env`
Создайте рабочий файл `.env` на основе шаблона `.env.example`:

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Заполните критические параметры:
```ini
DEBUG=False
# Сгенерируйте надёжный ключ: python -c "import secrets; print(secrets.token_urlsafe(50))"
SECRET_KEY=wX8_yZ_FurniCore_Production_Secret_Key_Change_Me_Now_2026_Secure!

ALLOWED_HOSTS=erp.furnicore.kz,www.erp.furnicore.kz,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://erp.furnicore.kz,https://www.erp.furnicore.kz

DB_ENGINE=django.db.backends.postgresql
DB_NAME=furnicore_db
DB_USER=furnicore_user
DB_PASSWORD=CHANGE_THIS_TO_A_VERY_STRONG_DB_PASSWORD_123
DB_HOST=127.0.0.1
DB_PORT=5432
DB_CONN_MAX_AGE=600

SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

LOG_LEVEL=INFO
COMPANY_NAME="FurniCore ERP"
CURRENCY_CODE=KZT
CURRENCY_SYMBOL=₸
TIME_ZONE=Asia/Almaty
LANGUAGE_CODE=ru-ru
```

### 6.4. Применение миграций и сбор статики
```bash
# Проверка конфигурации развёртывания
python manage.py check --deploy

# Применение миграций схемы данных
python manage.py migrate --noinput

# Сборка статических файлов в STATIC_ROOT (/var/www/furnicore/staticfiles)
python manage.py collectstatic --noinput

# Создание администратора (или загрузка демонстрационных данных)
python manage.py createsuperuser
# или
# python manage.py seed_demo

exit  # выход из сессии furnicore
```

---

## 7. Настройка сервера приложений Gunicorn и systemd

В репозитории уже подготовлен производственный файл конфигурации Gunicorn: `config/gunicorn_conf.py`.

### 7.1. Установка systemd unit-файла
Скопируйте подготовленный файл службы в каталог systemd:

```bash
sudo cp /var/www/furnicore/app/deployment/systemd/furnicore.service /etc/systemd/system/furnicore.service
sudo systemctl daemon-reload
```

Содержимое `/etc/systemd/system/furnicore.service`:
```ini
[Unit]
Description=FurniCore ERP Application Server (Gunicorn)
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=notify
User=furnicore
Group=furnicore
WorkingDirectory=/var/www/furnicore/app
EnvironmentFile=/var/www/furnicore/app/.env
ExecStart=/var/www/furnicore/venv/bin/gunicorn --config config/gunicorn_conf.py config.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=30
PrivateTmp=true
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 7.2. Запуск и активация службы
```bash
sudo systemctl enable --now furnicore
sudo systemctl status furnicore
```

### 7.3. Проверка эндпоинта здоровья (Health Check)
Проверьте доступность локального сервера:
```bash
curl -i http://127.0.0.1:8000/health/
```
Ожидаемый ответ:
```json
HTTP/1.1 200 OK
Content-Type: application/json

{"status": "ok", "database": "connected", "version": "1.0.0"}
```

---

## 8. Настройка веб-сервера Nginx и SSL (Let's Encrypt)

В репозитории подготовлена производственная конфигурация Nginx: `deployment/nginx/furnicore.conf`.

### 8.1. Установка конфигурации Nginx
```bash
sudo cp /var/www/furnicore/app/deployment/nginx/furnicore.conf /etc/nginx/sites-available/furnicore.conf

# Активация виртуального хоста
sudo ln -sf /etc/nginx/sites-available/furnicore.conf /etc/nginx/sites-enabled/furnicore.conf
sudo rm -f /etc/nginx/sites-enabled/default

# Проверка синтаксиса
sudo nginx -t
sudo systemctl reload nginx
```

### 8.2. Выпуск бесплатного доверенного SSL-сертификата Let's Encrypt
```bash
sudo certbot --nginx -d erp.furnicore.kz -d www.erp.furnicore.kz
```
Certbot автоматически сконфигурирует параметры HTTPS и настроит автоматическое продление сертификата по cron/systemd таймеру (`certbot.timer`).

---

## 9. Автоматическое резервное копирование базы данных

Скрипт `scripts/backup_db.sh` создаёт сжатые дампы PostgreSQL (`.dump`), вычисляет контрольные суммы MD5 и автоматически ротирует архивы (по умолчанию сохраняет копии за последние 14 дней).

### 9.1. Настройка прав на запуск
```bash
sudo chmod +x /var/www/furnicore/app/scripts/backup_db.sh
sudo chmod +x /var/www/furnicore/app/scripts/restore_db.sh
```

### 9.2. Добавление задачи в crontab пользователя furnicore
```bash
sudo -u furnicore crontab -e
```
Добавьте строку для ежедневного ночного бэкапа в 02:00:
```cron
0 2 * * * /var/www/furnicore/app/scripts/backup_db.sh >> /var/www/furnicore/logs/backup.log 2>&1
```

Подробная инструкция по восстановлению описана в документе `DATABASE_BACKUP_RESTORE.md`.

---

## 10. Процедура обновления приложения (Zero-Downtime Deployment)

Для выпуска обновлений без остановки сервиса используйте следующий регламент:

```bash
#!/usr/bin/env bash
set -e

echo "==> Переход в каталог приложения..."
cd /var/www/furnicore/app

echo "==> Получение свежего кода из Git..."
sudo -u furnicore git pull origin python-django

echo "==> Обновление зависимостей..."
sudo -u furnicore /var/www/furnicore/venv/bin/pip install --no-cache-dir -r requirements.txt

echo "==> Применение миграций базы данных..."
sudo -u furnicore /var/www/furnicore/venv/bin/python manage.py migrate --noinput

echo "==> Сборка статических файлов..."
sudo -u furnicore /var/www/furnicore/venv/bin/python manage.py collectstatic --noinput

echo "==> Мягкий перезапуск воркеров Gunicorn (Zero Downtime)..."
sudo systemctl reload furnicore

echo "==> Проверка статуса приложения..."
curl -s http://127.0.0.1:8000/health/ | grep -q '"status": "ok"' && echo "УСПЕШНО: Приложение обновлено и работает!" || echo "ОШИБКА: Проверьте логи!"
```

---

## 11. Мониторинг и просмотр логов

| Лог | Команда для просмотра |
|---|---|
| **Системные логи службы (systemd)** | `sudo journalctl -u furnicore.service -f -n 100` |
| **Логи приложения FurniCore** | `tail -f /var/www/furnicore/logs/furnicore.log` |
| **Логи ошибок приложения** | `tail -f /var/www/furnicore/logs/furnicore_errors.log` |
| **Логи Nginx Access** | `tail -f /var/log/nginx/furnicore_access.log` |
| **Логи Nginx Error** | `tail -f /var/log/nginx/furnicore_error.log` |
| **Логи бэкапов** | `tail -f /var/www/furnicore/logs/backup.log` |

---

## 12. Экстренные меры (Disaster Recovery)

В случае аварии сервера или сбоя данных:
1. Остановите приложение: `sudo systemctl stop furnicore`.
2. Создайте аварийный снепшот текущей базы: `/var/www/furnicore/app/scripts/backup_db.sh`.
3. Восстановите базу из последнего проверенного дампа:
   ```bash
   /var/www/furnicore/app/scripts/restore_db.sh /var/www/furnicore/backups/furnicore_db_backup_YYYYMMDD_HHMMSS.dump --force-production
   ```
4. Запустите приложение: `sudo systemctl start furnicore`.
5. Проверьте работоспособность: `curl http://127.0.0.1:8000/health/`.
