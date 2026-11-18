# FurniCore ERP — Руководство по развёртыванию (Deployment Guide)

В данном руководстве представлены **3 проверенных варианта развёртывания** системы FurniCore ERP для публичной демонстрации преподавателю: от мгновенного бесплатного туннеля ($0) до облачного PaaS и выделенного VPS-сервера.

---

## 1. Сравнение вариантов развёртывания

| Параметр | Вариант 1: Бесплатный туннель (Cloudflare / ngrok) | Вариант 2: Облачный PaaS (Render / Railway) | Вариант 3: Выделенный VPS (Ubuntu 24.04) |
|---|---|---|---|
| **Стоимость** | **0 ₸ / $0 (Бесплатно)** | $0 (Free Tier) или $5–$7/мес | $4–$6/мес (~2 500–3 500 ₸/мес) |
| **Сложность** | Минимальная (1 команда) | Средняя (подключение GitHub) | Профессиональная (Nginx, systemd) |
| **Время запуска** | **2 минуты** | 10–15 минут | 30–40 минут |
| **HTTPS сертификат** | Автоматически (встроен) | Автоматически | Бесплатный Let's Encrypt Certbot |
| **База данных** | Текущая локальная PostgreSQL | Управляемый Postgres (Neon/Render) | Локальный PostgreSQL 16 на сервере |
| **Идеально для:** | **Срочной демонстрации преподавателю по публичной ссылке прямо с вашего ноутбука** | Публикации учебного портфолио в интернете | Постоянного промышленного сервера фабрики |

---

## 2. Вариант 1: Мгновенная публичная ссылка через Cloudflare Tunnel (Рекомендуется для сдачи)

Этот вариант позволяет мгновенно получить защищённый публичный HTTPS-адрес (например, `https://furnicore-demo.trycloudflare.com`) без покупки домена, без аренды сервера и без изменения локальной базы данных.

### Шаг 1.1. Запустите локальный сервер Django:
```bash
cd "/home/linux/PycharmProjects/FurniCore ERP"
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

### Шаг 1.2. В соседней вкладке терминала запустите Cloudflare Tunnel:
```bash
# Установка утилиты cloudflared (если ещё не установлена)
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Запуск туннеля на локальный порт 8000
cloudflared tunnel --url http://127.0.0.1:8000
```

### Шаг 1.3. Результат:
В консоли появится публичная ссылка вида:
`https://random-words.trycloudflare.com`  
Эту ссылку можно сразу отправить преподавателю. Она открывается с любого устройства (телефон, планшет, другой компьютер) через защищённый HTTPS.

---

## 3. Вариант 2: Облачный хостинг PaaS (Render / Railway)

### Требования:
- Аккаунт на GitHub;
- Аккаунт на [Render.com](https://render.com) (бесплатный тариф).

### Шаги настройки:
1. Создайте в Render управляемую базу данных **PostgreSQL**:
   - Название: `furnicore-db`;
   - Database: `furnicore_db`;
   - User: `furnicore_user`.
2. Создайте **Web Service**:
   - Подключите ваш GitHub-репозиторий (ветка `python-django`).
   - **Environment:** `Python 3`.
   - **Build Command:**
     ```bash
     pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py seed_demo_data
     ```
   - **Start Command:**
     ```bash
     gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3
     ```
3. Добавьте переменные окружения (**Environment Variables**):
   - `DEBUG`: `False`
   - `SECRET_KEY`: сгенерированный 50-значный случайный ключ
   - `ALLOWED_HOSTS`: `.onrender.com`
   - `CSRF_TRUSTED_ORIGINS`: `https://*.onrender.com`
   - `DB_ENGINE`: `django.db.backends.postgresql`
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`: реквизиты из базы данных Render.

---

## 4. Вариант 3: Развёртывание на выделенном сервере (VPS / Ubuntu 24.04)

### Шаг 4.1. Подготовка сервера:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.12 python3.12-venv python3.12-dev build-essential libpq-dev postgresql-16 nginx certbot python3-certbot-nginx git
```

### Шаг 4.2. Настройка PostgreSQL:
```bash
sudo -u postgres psql
CREATE DATABASE furnicore_db;
CREATE USER furnicore_user WITH PASSWORD 'strong_production_password_2026';
ALTER ROLE furnicore_user SET client_encoding TO 'utf8';
ALTER ROLE furnicore_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE furnicore_user SET timezone TO 'Asia/Almaty';
GRANT ALL PRIVILEGES ON DATABASE furnicore_db TO furnicore_user;
\q
```

### Шаг 4.3. Клонирование и настройка виртуального окружения:
```bash
sudo mkdir -p /var/www/furnicore
sudo chown -R $USER:$USER /var/www/furnicore
git clone -b python-django https://github.com/isamatovismail-svg/FurniCore_ERP.git /var/www/furnicore
cd /var/www/furnicore

python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Шаг 4.4. Переменные окружения (`/var/www/furnicore/.env`):
```ini
DEBUG=False
SECRET_KEY=generate-a-strong-secret-key-here-min-50-characters
ALLOWED_HOSTS=furnicore.kz,www.furnicore.kz,YOUR_SERVER_IP
CSRF_TRUSTED_ORIGINS=https://furnicore.kz,https://www.furnicore.kz

DB_ENGINE=django.db.backends.postgresql
DB_NAME=furnicore_db
DB_USER=furnicore_user
DB_PASSWORD=strong_production_password_2026
DB_HOST=127.0.0.1
DB_PORT=5432

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

### Шаг 4.5. Миграции, статика и наполнение данными:
```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py seed_demo_data
```

### Шаг 4.6. Служба systemd (`/etc/systemd/system/furnicore.service`):
```ini
[Unit]
Description=FurniCore ERP Gunicorn Application Server
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/furnicore
ExecStart=/var/www/furnicore/.venv/bin/gunicorn \
          --config /var/www/furnicore/config/gunicorn_conf.py \
          config.wsgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Шаг 4.7. Конфигурация Nginx (`/etc/nginx/sites-available/furnicore`):
```nginx
server {
    listen 80;
    server_name furnicore.kz www.furnicore.kz;

    client_max_body_size 20M;

    location /static/ {
        alias /var/www/furnicore/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location /media/ {
        alias /var/www/furnicore/media/;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Шаг 4.8. Бесплатный HTTPS сертификат:
```bash
sudo ln -s /etc/nginx/sites-available/furnicore /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d furnicore.kz -d www.furnicore.kz
```

---

## 5. Контрольный чеклист запуска в продакшене

- [x] Все миграции применены без ошибок (`migrate --check` возвращает 0).
- [x] Статические файлы собраны в `staticfiles/` (`collectstatic`).
- [x] `DEBUG=False` установлен в боевом файле `.env`.
- [x] `SECRET_KEY` уникален и не совпадает со значением по умолчанию.
- [x] В `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS` внесены реальные домены.
- [x] Проведён тест готовности: `python manage.py check --deploy` (0 issues).
- [x] Созданы демонстрационные пользователи (`python manage.py seed_demo_data`).
- [x] Настроен регулярный бэкап базы данных через `cron` и `pg_dump`.
