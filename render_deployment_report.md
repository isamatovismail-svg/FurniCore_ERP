# FurniCore ERP — Render Free Deployment Report

**Дата отчёта:** 22 ноября 2026 г.  
**Проект:** FurniCore ERP (Модульная ERP-система мебельного производства)  
**Репозиторий:** [https://github.com/isamatovismail-svg/FurniCore_ERP](https://github.com/isamatovismail-svg/FurniCore_ERP)  
**Ветка:** `python-django`  
**Commit SHA:** `228ef05b4ee689fb8f5eeb72f62cb96229c9dfa5`  
**Целевая платформа:** Render.com (Web Service — Free Tier)  
**Статус готовности:** ✅ **100% готов к безопасному подключению в Render**

---

## 1. Что было проверено и настроено

1. **WSGI-модуль проекта:**
   - Подтверждён реальный путь точки входа: `config.wsgi:application`.
2. **База данных PostgreSQL:**
   - Внедрена универсальная поддержка переменной `DATABASE_URL` через библиотеку `dj-database-url`.
   - Сохранена полная обратная совместимость: если `DATABASE_URL` не задана, Django использует раздельные переменные `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.
   - Включена опция проверки жизнеспособности соединений (`conn_health_checks=True`) и пулинг соединений (`CONN_MAX_AGE=600`).
3. **Раздача статических файлов в Production:**
   - Добавлен и протестирован модуль `whitenoise` (v6.12.0) с `CompressedStaticFilesStorage`.
   - Внедрён middleware `whitenoise.middleware.WhiteNoiseMiddleware` сразу после `SecurityMiddleware`.
   - Проверена сборка статики через `collectstatic`: сжаты и оптимизированы 145 файлов (Gzip / Brotli) без ошибок.
4. **Безопасность хостов и CSRF:**
   - В `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS` автоматически включены домены `.onrender.com` и `https://*.onrender.com`.
   - Добавлена поддержка системной переменной Render `RENDER_EXTERNAL_HOSTNAME`, динамически разрешающей индивидуальный адрес сервиса вида `<app-name>.onrender.com`.
5. **HTTPS и Reverse Proxy:**
   - Проверена настройка `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')`, исключающая бесконечные циклы перенаправлений за SSL-терминатором Render.
   - В режиме `DEBUG=False` включены флаги `SESSION_COOKIE_SECURE=True` и `CSRF_COOKIE_SECURE=True`.
6. **Health Check Endpoint:**
   - Для мониторинга доступности в Render задействован реальный эндпоинт `/health/`, проверяющий статус подключения к PostgreSQL (`SELECT 1;`) и возвращающий HTTP 200 JSON.

---

## 2. Добавленные и изменённые файлы

| Файл | Статус | Назначение изменений |
|---|:---:|---|
| `build.sh` | **Создан** | Скрипт сборки: обновление pip, установка зависимостей, сборка статики (`collectstatic`), применение миграций (`migrate`) и опциональный сид данных. Скрипт исполняемый (`chmod +x`). |
| `render.yaml` | **Создан** | Декларативный Blueprint для Render. Описывает **исключительно бесплатный** Web Service (`plan: free`, `runtime: python`) без автоматического подключения платных ресурсов. |
| `config/settings.py` | **Изменён** | Поддержка `DATABASE_URL` через `dj_database_url`, WhiteNoise middleware и storage, динамический `RENDER_EXTERNAL_HOSTNAME`, домены `.onrender.com`. |
| `requirements.txt` | **Изменён** | Добавлены `whitenoise>=6.6.0` и `dj-database-url>=2.1.0`. |
| `.env.example` | **Изменён** | Документирован формат `DATABASE_URL` для облачных БД (Render Postgres, Neon, Supabase) и домены `.onrender.com`. |
| `render_deployment_report.md` | **Создан** | Настоящий отчёт с пошаговой инструкцией и аудитом. |

---

## 3. Точные команды Build и Start

### Build Command
```bash
./build.sh
```
*Что делает `build.sh`:*
```bash
pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
```

### Start Command
```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

---

## 4. Переменные окружения для Render Dashboard

При создании Web Service в панели [dashboard.render.com](https://dashboard.render.com) задайте следующие переменные окружения (Environment Variables):

| Переменная | Значение / Источник | Обязательность | Назначение |
|---|---|:---:|---|
| **`PYTHON_VERSION`** | `3.12.9` | Обязательно | Фиксация версии Python на Render |
| **`DEBUG`** | `False` | Обязательно | Отключение отладочного режима в production |
| **`SECRET_KEY`** | *(Сгенерировать случайный ключ)* | Обязательно | Криптографический ключ Django (при использовании `render.yaml` генерируется автоматически) |
| **`DATABASE_URL`** | `postgresql://user:pass@host:5432/dbname?sslmode=require` | Обязательно | Строка подключения к PostgreSQL (Render Free Postgres, Neon.tech, Supabase) |
| **`ALLOWED_HOSTS`** | `.onrender.com` | Рекомендуется | Дополнительные разрешённые хосты |
| **`CSRF_TRUSTED_ORIGINS`** | `https://*.onrender.com` | Рекомендуется | Доверенные адреса для CSRF-защиты |
| **`SECURE_SSL_REDIRECT`** | `True` | Рекомендуется | Принудительное перенаправление HTTP на HTTPS |
| **`DB_CONN_MAX_AGE`** | `600` | Опционально | Время жизни постоянных соединений с БД (сек) |
| **`LOG_LEVEL`** | `INFO` | Опционально | Уровень логирования Django |
| **`SEED_DEMO`** | `false` (или `true` при первом запуске) | Опционально | Наполнение базы тестовыми складами и товарами при первом развёртывании |

---

## 5. Результаты локальных проверок

Все проверки перед отправкой в репозиторий выполнены в реальном окружении Python 3.12:

```bash
# 1. Системная проверка Django
python manage.py check
# Результат: System check identified no issues (0 silenced). ✅

# 2. Проверка состояния миграций
python manage.py makemigrations --check --dry-run
# Результат: No changes detected ✅

# 3. Полный стандартный тестовый набор pytest
pytest -q
# Результат: 88 passed in 29.61s (100% PASS, 0 failures, 0 errors) ✅

# 4. Проверка синтаксиса bash-скрипта сборки
bash -n build.sh
# Результат: Код возврата 0 (ошибок нет) ✅

# 5. Проверка сборки статических файлов WhiteNoise
python manage.py collectstatic --noinput
# Результат: 145 post-processed (Brotli + Gzip сжатие успешно) ✅
```

---

## 6. Известные ограничения бесплатного тарифа (Render Free Tier)

1. **Спящий режим (Spin-down on idle):**
   - На бесплатном тарифе Render Web Service засыпает после 15 минут отсутствия входящих HTTP-запросов.
   - Первый запрос после простоя «пробуждает» контейнер в течение 30–50 секунд (Cold Start). Это нормальное поведение бесплатного хостинга.
2. **Лимит оперативной памяти (RAM):**
   - Лимит Free Tier составляет 512 МБ RAM.
   - Команда запуска настроена на `--workers 2` с таймаутом `120` сек, что обеспечивает минимальное потребление памяти (~120–160 МБ) и предотвращает Out-Of-Memory (OOM).
3. **Бесплатный PostgreSQL на Render:**
   - Бесплатный инстанс PostgreSQL на Render удаляется через 30 дней после создания.
   - **Рекомендация:** Для постоянной демонстрации рекомендуется использовать бесплатный постоянный пул PostgreSQL от [Neon.tech](https://neon.tech) (0.5 ГБ бесплатно навсегда) или [Supabase](https://supabase.com), вставив предоставленный ими `DATABASE_URL` в переменные окружения Render.
4. **Фоновые задачи Celery / Redis:**
   - Фоновый воркер Celery требует отдельного процесса. Для учебной демонстрации на Free тарифе все критические операции (проводки, печать PDF, калькуляция) выполняются синхронно и надёжно в основном потоке Django.
