# PHASE 1.1 — Security Verification Report (v2 — Full Audit)
## FurniCore ERP · Public Demo Readiness Audit

**Дата первого отчёта:** 2026-11-18  
**Дата актуализации:** 2026-11-19  
**Ветка:** `python-django` (без коммитов)  
**Python:** 3.12.3 (`.venv`) · **Django:** 5.1.15 · **PostgreSQL:** 16 (port 5435)  
**Аудитор:** Antigravity Agent  
**Статус коммитов:** ❌ Коммиты не выполнялись — только чтение и анализ исходного кода

---

> [!IMPORTANT]
> В этом отчёте каждый факт помечен источником:
> - **[src]** — подтверждено чтением исходного кода
> - **[test]** — подтверждено тестовым логом
> - **[prev]** — сообщено предыдущим запуском, но не верифицировано в этом сеансе
> - **[?]** — не проверено / требует решения владельца

---

## 1. Анализ Cloudflare Proxy и `--forwarded-allow-ips`

### 1.1 Как работает цепочка Trust

```
Браузер → (HTTPS) → Cloudflare Edge → (HTTP) → cloudflared (локально) → Gunicorn (127.0.0.1:8000) → Django
```

Cloudflare Tunnel (cloudflared) устанавливает **исходящее соединение** с серверами Cloudflare,
а входящие HTTP-запросы к Gunicorn приходят **с loopback-адреса** (`127.0.0.1`).

Заголовок `X-Forwarded-Proto: https` добавляется **самим cloudflared** перед передачей запроса Gunicorn.

### 1.2 Значение `--forwarded-allow-ips`

Параметр Gunicorn `--forwarded-allow-ips` определяет, **каким IP-адресам Gunicorn доверяет** как
легитимным reverse-proxy. Только с доверенных IP заголовок `X-Forwarded-Proto` принимается в
расчёт при установке `REMOTE_ADDR` и `wsgi.url_scheme`.

**Gunicorn по умолчанию:** `--forwarded-allow-ips="127.0.0.1,::1"` [src — gunicorn --help]

### 1.3 Вывод: `"127.0.0.1"` БЕЗОПАСНЕЕ, чем `"*"`

| Вариант | Поведение | Риск |
|---|---|---|
| `--forwarded-allow-ips="*"` | Доверяет заголовкам **от любого IP** | ⚠️ Злоумышленник, отправивший запрос напрямую на 127.0.0.1:8000, мог бы подделать `X-Forwarded-Proto: https` |
| `--forwarded-allow-ips="127.0.0.1"` | Доверяет только loopback | ✅ Безопасно: cloudflared соединяется именно с 127.0.0.1 |
| (default, не задан) | Те же `127.0.0.1,::1` | ✅ Безопасно, совпадает с вариантом выше |

**Рекомендация:** Использовать `--forwarded-allow-ips="127.0.0.1"` или вовсе **не указывать флаг** —
Gunicorn по умолчанию уже доверяет 127.0.0.1, что точно соответствует поведению cloudflared.
Флаг `"*"` в предыдущем отчёте был избыточным и менее безопасным. **Исправление не требует изменений кода.**

### 1.4 Проверка Django-настроек для Cloudflare [src]

```python
# config/settings.py (строки 185, 191)
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True')   # True при DEBUG=False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')     # Активен при DEBUG=False
```

**Механизм защиты от redirect-loop:**

1. Cloudflared добавляет `X-Forwarded-Proto: https` → Gunicorn (127.0.0.1) передаёт в Django
2. Django видит `HTTP_X_FORWARDED_PROTO = 'https'` → считает соединение HTTPS
3. `SECURE_SSL_REDIRECT` проверяет: "запрос уже HTTPS?" → ДА → редирект не происходит
4. **Loop невозможен** при корректной цепочке

**CSRF-защита:** `CSRF_TRUSTED_ORIGINS = ['https://*.trycloudflare.com']` [src] — все POST-запросы
с Cloudflare-домена пройдут CSRF-проверку.

### 1.5 Проблема с IP-адресами в AuditLog [src]

```python
# apps/accounts/views.py строки 39-40
ip_address=request.META.get('REMOTE_ADDR'),
```

При работе через Cloudflare Tunnel `REMOTE_ADDR` будет `127.0.0.1` (адрес cloudflared),
а не реальный IP пользователя. Для демо это **некритично**, но AuditLog будет содержать `127.0.0.1`
вместо реального IP преподавателя.

Реальный IP доступен в заголовке `CF-Connecting-IP` от Cloudflare, но его нет в коде. [?] — Решение на усмотрение владельца.

### 1.6 Итоговая команда запуска (скорректированная)

```bash
# Вместо --forwarded-allow-ips="*" используем безопасный вариант:
SERVE_STATIC=True DEBUG=False \
.venv/bin/gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 2 \
  --timeout 60 \
  --access-logfile -
# --forwarded-allow-ips не нужен — Gunicorn по умолчанию уже доверяет 127.0.0.1
```

---

## 2. Полный аудит TEACHER / OWNER прав

### 2.1 Модель пользователя [src]

```python
# apps/accounts/models.py
class UserRole(models.TextChoices):
    OWNER = 'OWNER'
    ADMIN = 'ADMIN'
    ACCOUNTANT = 'ACCOUNTANT'
    PRODUCTION_MANAGER = 'PRODUCTION_MANAGER'
    WAREHOUSE_MANAGER = 'WAREHOUSE_MANAGER'
    SALES_MANAGER = 'SALES_MANAGER'
    WORKER = 'WORKER'
    # DEMO_VIEWER — отсутствует
```

Свойства модели `User`: `is_owner`, `is_production_manager`, `is_warehouse_manager`,
`is_accountant`, `is_sales_manager` — все возвращают `True` для `OWNER`. [src]

### 2.2 Учётная запись `teacher` [prev — создана в предыдущем сеансе]

| Параметр | Значение | Источник |
|---|---|---|
| `username` | `teacher` | [prev] |
| `role` | `UserRole.OWNER` | [prev] |
| `is_staff` | `False` | [prev] |
| `is_superuser` | `False` | [prev] |
| `is_active` | `True` | [prev] |
| `password` | `TeacherPass2026!` (хэшировано в БД) | [prev] |

### 2.3 Матрица действий: OWNER vs серверная защита [src]

Каждое действие верифицировано чтением соответствующего view-файла.

#### Финансовый модуль (`apps/finance/views.py`)

Функция-гейтер: `can_manage_finance(user)` = `role in [OWNER, ADMIN, ACCOUNTANT] or is_superuser`

| Действие | URL | OWNER | Серверная защита | Результат |
|---|---|---|---|---|
| Просмотр финансового дашборда | `GET /finance/` | ✅ | `@login_required` | ✅ Допустимо |
| Создание платежа клиента | `POST /finance/payments/customers/create/` | ✅ | `can_manage_finance` | ⚠️ Write-доступ |
| Сторнирование платежа клиента | `POST /finance/payments/customers/<pk>/storno/` | ✅ | `can_manage_finance` | ⚠️ Write-доступ |
| Создание платежа поставщику | `POST /finance/payments/suppliers/create/` | ✅ | `can_manage_finance` | ⚠️ Write-доступ |
| Сторнирование платежа поставщику | `POST /finance/payments/suppliers/<pk>/storno/` | ✅ | `can_manage_finance` | ⚠️ Write-доступ |
| Перевод между счетами | `POST /finance/accounts/transfer/` | ✅ | `can_manage_finance` | ⚠️ Write-доступ |
| Создание расхода | `POST /finance/expenses/create/` | ✅ | `can_manage_finance` | ⚠️ Write-доступ |
| Сторнирование расхода | `POST /finance/expenses/<pk>/storno/` | ✅ | `can_manage_finance` | ⚠️ Write-доступ |
| Скачать PDF платежа | `GET /finance/payments/*/pdf/` | ✅ | `can_manage_finance` | ✅ Только просмотр |
| Скачать Excel экспорт | `GET /finance/export/excel/` | ✅ | `@login_required` | ✅ Только просмотр |

#### Складской модуль (`apps/warehouses/views.py`)

Функции-гейтеры: `can_user_manage_warehouses`, `can_user_post_doc`

| Действие | URL | OWNER | Серверная защита | Результат |
|---|---|---|---|---|
| Просмотр WH-1, WH-2, документов | `GET /warehouses/*` | ✅ | `@login_required` | ✅ Допустимо |
| Создание складского документа | `POST /warehouses/documents/create/` | ✅ | `can_user_manage_warehouses` | ⚠️ Write-доступ |
| Проведение документа | `POST /warehouses/documents/<pk>/post/` | ✅ | `can_user_post_doc` + `@require_POST` | ⚠️ Write-доступ |
| Отмена документа | `POST /warehouses/documents/<pk>/cancel/` | ✅ | `can_user_post_doc` + `@require_POST` | ⚠️ Write-доступ |
| Создание инвентаризации | `POST /warehouses/inventory/create/` | ✅ | `@login_required` | ⚠️ Write-доступ |
| QR-код и этикетки (PDF) | `GET /warehouses/qr/<sku>/`, `/label/` | ✅ | `@login_required` | ✅ Только просмотр |
| Поиск по сканеру | `GET /warehouses/scan/lookup/` | ✅ | `@login_required` | ✅ Только просмотр |

#### Производственный модуль (`apps/production/views.py`)

Функция-гейтер: `can_manage_production(user)` = `role in [OWNER, ADMIN, PRODUCTION_MANAGER]`

| Действие | URL | OWNER | Серверная защита | Результат |
|---|---|---|---|---|
| Создание производственного заказа | `POST /production/create/` | ✅ | `can_manage_production` | ⚠️ Write-доступ |
| Редактирование заказа | `POST /production/<pk>/edit/` | ✅ | `can_manage_production` | ⚠️ Write-доступ |
| Списание материалов | `POST /production/<pk>/issue-materials/` | ✅ | `can_manage_production` + `@require_POST` | ⚠️ Write-доступ |
| Запуск в производство | `POST /production/<pk>/launch/` | ✅ | `can_manage_production` + `@require_POST` | ⚠️ Write-доступ |
| Перевод этапа | `POST /production/stage/<id>/advance/` | ✅ | `@require_POST` (нет role-check!) | ⚠️ **Пропущен role-check** |
| Контроль качества (ОТК) | `POST /production/<pk>/qc/` | ✅ | `@login_required` (нет role-check!) | ⚠️ **Пропущен role-check** |
| Передача на WH-2 | `POST /production/<pk>/transfer-wh2/` | ✅ | `can_manage_production` + `@require_POST` | ⚠️ Write-доступ |
| Создание BOM | `POST /production/boms/create/` | ✅ | `can_manage_production` | ⚠️ Write-доступ |
| Регистрация отходов | `POST /production/<pk>/waste/create/` | ✅ | `@login_required` (нет role-check!) | ⚠️ **Пропущен role-check** |

#### Продажи (`apps/sales/views.py`)

Функция-гейтер: `can_manage_sales(user)` = `role in [OWNER, ADMIN, SALES_MANAGER, PRODUCTION_MANAGER, ACCOUNTANT]`

| Действие | URL | OWNER | Серверная защита | Результат |
|---|---|---|---|---|
| Создание заказа | `POST /sales/create/` | ✅ | `can_manage_sales` | ⚠️ Write-доступ |
| Резервирование | `POST /sales/<pk>/reserve/` | ✅ | `can_manage_sales` | ⚠️ Write-доступ |
| Запуск производства по заказу | `POST /sales/<pk>/create-production/` | ✅ | `can_manage_sales` | ⚠️ Write-доступ |
| Отгрузка клиенту | `POST /sales/<pk>/ship/` | ✅ | `can_manage_sales` | ⚠️ Write-доступ |
| Отмена заказа | `POST /sales/<pk>/cancel/` | ✅ | `can_manage_sales` | ⚠️ Write-доступ |
| Создание/редактирование клиента | `POST /sales/customers/create/` | ✅ | `can_manage_sales` | ⚠️ Write-доступ |
| Архивирование клиента | `POST /sales/customers/<pk>/archive/` | ✅ | `can_manage_sales` | ⚠️ Write-доступ |

#### Закупки (`apps/suppliers/views.py`)

Функция-гейтер: `can_manage_procurement(user)` = `role in [OWNER, ADMIN, PRODUCTION_MANAGER, WAREHOUSE_MANAGER, ACCOUNTANT]`

| Действие | URL | OWNER | Серверная защита | Результат |
|---|---|---|---|---|
| Создание поставщика | `POST /suppliers/create/` | ✅ | `can_manage_procurement` | ⚠️ Write-доступ |
| Редактирование поставщика | `POST /suppliers/<pk>/edit/` | ✅ | `can_manage_procurement` | ⚠️ Write-доступ |
| Создание закупочного заказа | `POST /suppliers/orders/create/` | ✅ | `can_manage_procurement` | ⚠️ Write-доступ |
| Отправка, приёмка, отмена ЗЗ | `POST /suppliers/orders/<pk>/send/receive/cancel/` | ✅ | `can_manage_procurement` | ⚠️ Write-доступ |

#### Справочники: Материалы, Продукты [src]

| Модуль | Роли с write-доступом | OWNER |
|---|---|---|
| Материалы | OWNER, ADMIN, PRODUCTION_MANAGER, WAREHOUSE_MANAGER | ✅ |
| Продукты | OWNER, ADMIN, PRODUCTION_MANAGER, SALES_MANAGER, WAREHOUSE_MANAGER | ✅ |

#### Не-ролевые модули (только `@login_required`) [src]

| Модуль | URL | OWNER | Комментарий |
|---|---|---|---|
| Дашборд | `GET /` | ✅ | Просмотр — OK |
| Аналитика | `GET /analytics/`, `/analytics/map/` | ✅ | Просмотр — OK |
| AI Assistant | `GET/POST /ai/` | ✅ | Только query к AI — OK |
| Уведомления | `GET/POST /notifications/*` | ✅ | Только свои уведомления |
| Сотрудники | `GET /employees/` | ✅ | Просмотр — OK |
| ОТК (quality) | `GET /quality/` | ✅ | Просмотр — OK |

### 2.4 Критические находки в RBAC [src]

#### Находка 1: `stage_advance_action` без role-check

```python
# apps/production/views.py строка 393
@login_required
@require_POST
def stage_advance_action(request, stage_id):
    # Нет проверки can_manage_production(request.user)!
```

**Любой аутентифицированный пользователь** (включая WORKER, SALES_MANAGER) может переводить
технологические этапы производственного заказа на следующий статус.

#### Находка 2: `order_qc_inspect` без role-check

```python
# apps/production/views.py строка 420
@login_required
def order_qc_inspect(request, pk):
    # Нет проверки can_manage_production(request.user)!
```

Любой авторизованный пользователь может заполнить форму ОТК и изменить результат проверки.

#### Находка 3: `waste_create` без role-check

```python
# apps/production/views.py строка 742
@login_required
def waste_create(request, pk):
    # Нет проверки can_manage_production(request.user)!
```

Любой авторизованный пользователь может регистрировать производственные отходы.

#### Находка 4: `order_ship` принимает GET-запрос

```python
# apps/sales/views.py строка 224
@login_required
def order_ship(request, pk):
    if not can_manage_sales(request.user): ...
    if request.method == 'POST':  # ← только POST выполняет отгрузку
        ...
    return redirect(...)  # ← GET-запрос тихо редиректит без действия
```

Отгрузка выполняется только при POST, но view не декорирован `@require_POST`.
На практике GET-запрос ничего не делает — функциональной уязвимости нет, но стиль нестрогий.

#### Находка 5: `order_reserve` принимает GET-запрос (аналогично отгрузке)

Та же ситуация: резервирование выполняется при любом методе без `@require_POST`.

#### Находка 6: AuditLog не охватывает finance-операции через views [src]

AuditLog создаётся в `finance/services.py` (подтверждено — 8 вызовов), однако не через views.
Это правильная архитектура: лог создаётся на уровне сервисного слоя.
Finance-операции **логируются** через services.py. ✅

#### Находка 7: `dev_login_view` заблокирован в production [src]

```python
# apps/accounts/views.py строка 11
if not settings.DEBUG:
    raise Http404("Available only in DEBUG mode")
```

При `DEBUG=False` эндпоинт `/accounts/dev-login/` возвращает HTTP 404. ✅ Безопасно.

### 2.5 Управление пользователями через UI [src]

**Нет ни одного view** для создания, редактирования или удаления пользователей в UI.
Единственный путь: Django `/admin/` (заблокирован для teacher) или `manage.py` shell.

Таблица недоступных операций для `teacher`:

| Операция | Доступность через UI | Комментарий |
|---|---|---|
| Создание нового пользователя | ❌ Нет view | Только через `manage.py` |
| Изменение пароля другого пользователя | ❌ Нет view | |
| Изменение роли пользователя | ❌ Нет view | |
| Удаление пользователя | ❌ Нет view | |
| Просмотр списка пользователей | ❌ Нет view | |
| Доступ к Django `/admin/` | ❌ `is_staff=False` | HTTP 302 → login |
| Доступ к AuditLog через `/admin/` | ❌ `is_staff=False` | |

### 2.6 Оценка рисков для демонстрации

**Вывод:** Роль OWNER для teacher принята как допустимая для учебного демо. Три находки
(stage_advance, qc_inspect, waste_create без role-check) существуют, но:

1. Это **внутренние** эндпоинты, защищённые хотя бы `@login_required`
2. Для демо teacher работает как "владелец", что отражает реалистичный бизнес-сценарий
3. RBAC-тест `test_rbac_server_side_enforcement` проходит со статусом PASS [test], т.к. тест
   проверяет основные критические операции (создание заказов, финансы), но не stage_advance/qc/waste

**Если требуется read-only роль:** необходимо добавить `UserRole.DEMO_VIEWER` и соответствующие
проверки во все 8 view-функций, которые сейчас используют только `@login_required`. [?] — Решение владельца.

---

## 3. Сквозной бизнес-цикл — подтверждение

### 3.1 Источник [test — task-415.log, подтверждён прямым чтением файла]

```
tests/test_phase5_5_acceptance.py::test_end_to_end_18_step_furniture_business_cycle PASSED
```

Файл лога: `.system_generated/tasks/task-415.log` — читался напрямую в этом сеансе.

### 3.2 Верификация покрытия сквозного цикла [src — test_phase5_5_acceptance.py]

| Шаг | Описание | Тест проверяет | Статус |
|---|---|---|---|
| 1 | Создание поставщика и материала | `supplier.pk`, `material.purchase_cost_kzt` | ✅ [src+test] |
| 2 | Закупочный заказ (20 листов МДФ) | `po.total_amount_kzt == 130000`, статус SENT | ✅ [src+test] |
| 3 | Приёмка на WH-1 | Документ POSTED, PO статус RECEIVED | ✅ [src+test] |
| 4 | Складские остатки WH-1 | `bal_mdf.current_stock == 20.000` | ✅ [src+test] |
| 5 | Клиент, продукт, BOM, заказ (2 стола) | `so.total_amount_kzt == 130000` | ✅ [src+test] |
| 6 | Дефицит на WH-2 | `is_fully_available == False`, deficit_qty == 2 | ✅ [src+test] |
| 7 | Создание производственного заказа | `len(prod_orders) == 1`, qty == 2, linked to SO | ✅ [src+test] |
| 8 | Проверка BOM и наличия материалов | `is_all_available == True` (нужно 4 листа, есть 20) | ✅ [src+test] |
| 9 | Списание материалов с WH-1 | `doc_type == PRODUCTION_ISSUE`, `bal_mdf == 15.800` (5% отход) | ✅ [src+test] |
| 10 | Запуск производства, этапы маршрута | `status == IN_PROGRESS`, `len(stages) >= 3` | ✅ [src+test] |
| 11 | Регистрация технологических отходов | `waste.cost_kzt == 3250.00` | ✅ [src+test] |
| 12 | ОТК — контроль качества PASS | `qc.is_passed == True`, `status == READY` | ✅ [src+test] |
| 13 | Передача готовой мебели на WH-2 | `bal_desk.current_stock == 2.00`, статус COMPLETED | ✅ [src+test] |
| 14 | Резервирование под заказ покупателя | `reserved_stock == 2.00`, статус READY | ✅ [src+test] |
| 15 | Отгрузка клиенту | `current_stock == 0`, `reserved_stock == 0`, статус SHIPPED | ✅ [src+test] |
| 16 | Оплата (частичная 50 000 + доплата 80 000) | `paid_amount == 130000`, `remaining_debt == 0`, статус PAID | ✅ [src+test] |
| 17 | Финансовая задолженность | `receivables_list` для клиента пуста | ✅ [src+test] |
| 18 | Себестоимость и рентабельность | `actual_materials_cost == 27300`, `gross_margin > 0` | ✅ [src+test] |

**Сквозной цикл охватывает 18 шагов** (не 13, как указано в задании — тест более полный).
**Все 18 шагов выполнены в изолированных тестовых данных** (pytest `@pytest.mark.django_db`
с автоматическим откатом транзакций). Основная БД не затронута. ✅

---

## 4. Верификация тестового отчёта

### 4.1 Оригинальный лог [task-415.log — читался напрямую в этом сеансе]

**Файл:** `/home/linux/.gemini/antigravity/brain/c7d4aa39-1da4-47bd-9366-c7f50d8e47f7/.system_generated/tasks/task-415.log`

**Команда запуска:**
```bash
.venv/bin/pytest tests/test_all_routes.py tests/test_warehouse_phase2.py \
  tests/test_production_phase3.py tests/test_phase4_procurement_sales.py \
  tests/test_phase5_finance_costing.py tests/test_phase5_5_acceptance.py \
  tests/test_django_suite.py -v --tb=short
```

**Результаты (из оригинального лога):**

| Метрика | Значение |
|---|---|
| ✅ PASSED | **68** |
| ❌ FAILED | **0** |
| 💥 ERROR | **0** |
| ⏱ Время | **32.59 сек** |
| Exit code | **0** |
| Дата запуска | 2026-11-18 ~23:00 (+05) |

**Последние строки лога (дословно):**
```
tests/test_django_suite.py::FurniCoreERPTestCase::test_unauthenticated_access PASSED [100%]

============================= 68 passed in 32.59s ==============================
```

> [!NOTE]
> Лог прочитан напрямую из файла задачи в этом сеансе. Данные **подтверждены независимо** [test].

### 4.2 Покрытие тестами по модулям

| Файл | Тестов | Статус | Охват |
|---|---|---|---|
| `test_all_routes.py` | 11 | ✅ PASS | HTTP-доступность, аутентификация |
| `test_warehouse_phase2.py` | 7 | ✅ PASS | WH-1, WH-2, документы, сканер, RBAC |
| `test_production_phase3.py` | 16 | ✅ PASS | BOM, заказы, этапы, ОТК, себестоимость, RBAC |
| `test_phase4_procurement_sales.py` | 10 | ✅ PASS | Закупки, продажи, резерв, отгрузка, отмена |
| `test_phase5_finance_costing.py` | 15 | ✅ PASS | Платежи, счета, расходы, PDF/Excel, RBAC |
| `test_phase5_5_acceptance.py` | 5 | ✅ PASS | 18-шаговый цикл, инварианты, RBAC, документы |
| `test_django_suite.py` | 4 | ✅ PASS | Маршруты, аутентификация |

---

## 5. Настройки HTTPS и безопасность [src]

### 5.1 Всегда активные настройки (`config/settings.py`)

| Настройка | Значение | Статус |
|---|---|---|
| `SECURE_BROWSER_XSS_FILTER` | `True` | ✅ |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | ✅ |
| `X_FRAME_OPTIONS` | `'DENY'` | ✅ |
| `SESSION_COOKIE_HTTPONLY` | `True` | ✅ |
| `SESSION_COOKIE_AGE` | `86400 сек (24 ч)` | ✅ |
| `CSRF_COOKIE_HTTPONLY` | `False` | ⚠️ Допустимо (нужен JS-доступ) |
| `ALLOWED_HOSTS` | включает `.trycloudflare.com` | ✅ |
| `CSRF_TRUSTED_ORIGINS` | включает `https://*.trycloudflare.com` | ✅ |

### 5.2 Активные только при `DEBUG=False`

| Настройка | Значение | Статус |
|---|---|---|
| `SECURE_SSL_REDIRECT` | `True` (default) | ✅ при правильном Gunicorn |
| `SESSION_COOKIE_SECURE` | `True` | ✅ |
| `CSRF_COOKIE_SECURE` | `True` | ✅ |
| `SECURE_PROXY_SSL_HEADER` | `('HTTP_X_FORWARDED_PROTO', 'https')` | ✅ |
| `SECURE_HSTS_SECONDS` | `31536000` (1 год) | ⚠️ Долгий, но допустимо для demo |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` | ✅ |

### 5.3 `check --deploy` [prev — выполнялось в предыдущем сеансе]

```
System check identified no issues (0 silenced).
```

**Не повторялось в этом сеансе** — результат из предыдущего сеанса. [prev]

### 5.4 Static Files [src]

FurniCore UI полностью на CDN (Tailwind, Alpine.js, Chart.js, Lucide, Google Fonts).
`staticfiles/` содержит только `admin/` и `rest_framework/` — достаточно для работы.

**Зависимость от CDN:** При отсутствии интернет-соединения UI не загрузится. [?] — Допустимо для онлайн-демо.

---

## 6. Сводный список замечаний

### 🔴 Критические (требуют решения до публикации)

| № | Находка | Последствие | Безопасный план |
|---|---|---|---|
| **C-1** | `--forwarded-allow-ips="*"` в прошлом отчёте был неоптимален | Мог позволить подмену X-Forwarded-Proto при прямом доступе к порту | **Не использовать `"*"`** — достаточно дефолта Gunicorn (127.0.0.1). Изменений в коде не нужно |
| **C-2** | `SECURE_SSL_REDIRECT=True` требует корректного Gunicorn | Без доверия к X-Forwarded-Proto возможен redirect loop | Запускать Gunicorn без `--forwarded-allow-ips` или с `"127.0.0.1"` |

### 🟡 Некритические (допустимо для демо, рекомендуется исправить в продакшне)

| № | Находка | Последствие | Рекомендация |
|---|---|---|---|
| **N-1** | `stage_advance_action` без role-check | Любой пользователь может переводить производственные этапы | Добавить `can_manage_production` или `is_production_manager` проверку |
| **N-2** | `order_qc_inspect` без role-check | Любой пользователь может заполнить ОТК-форму | Добавить проверку роли |
| **N-3** | `waste_create` без role-check | Любой пользователь может регистрировать отходы | Добавить проверку роли |
| **N-4** | `order_reserve`, `order_ship` без `@require_POST` | GET-запрос тихо редиректит (не выполняет действие) | Добавить `@require_POST` |
| **N-5** | AuditLog логирует `REMOTE_ADDR` (127.0.0.1) при Cloudflare Tunnel | Реальный IP не записывается | Использовать `CF-Connecting-IP` или `X-Forwarded-For` |
| **N-6** | teacher/OWNER имеет полный write-доступ к бизнес-операциям | Преподаватель может изменять данные демо | Решение владельца: OK для демо или ввести DEMO_VIEWER |
| **N-7** | HSTS 1 год при `DEBUG=False` | После первого посещения браузер требует HTTPS 1 год | Допустимо для Demo; не подходит для частых смен домена |
| **N-8** | `CSRF_COOKIE_HTTPONLY=False` | JS может читать CSRF-токен | Допустимо если нет XSS; для демо приемлемо |

### ✅ Подтверждено безопасным [src]

| Аспект | Статус |
|---|---|
| Django `/admin/` недоступен для teacher | ✅ |
| Нет UI для управления пользователями | ✅ |
| `dev_login_view` заблокирован при `DEBUG=False` | ✅ |
| Нет `csrf_exempt` в production views | ✅ |
| Hard-delete (`obj.delete()`) не реализован ни в одном view | ✅ |
| Финансовые операции логируются через AuditLog в services.py | ✅ |
| CSRF-защита на всех POST-формах (Django middleware) | ✅ |
| `@require_POST` на критических складских операциях | ✅ |

---

## 7. Безопасный план исправления (требует подтверждения владельца)

> [!CAUTION]
> Все исправления ниже — **только предложения**. Код не изменялся в рамках этого аудита.
> Выполнять только после явного подтверждения владельца.

### Минимальный набор перед публичным запуском

**Исправление C-1 / C-2 (не требует изменения кода):**
```bash
# Правильная команда запуска Gunicorn — не использовать --forwarded-allow-ips="*":
SERVE_STATIC=True DEBUG=False \
.venv/bin/gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 2 \
  --timeout 60 \
  --access-logfile -
```

### Опциональные улучшения кода (N-1, N-2, N-3)

Добавить в три view в `apps/production/views.py`:
```python
# stage_advance_action, order_qc_inspect, waste_create
if not can_manage_production(request.user):
    messages.error(request, 'Недостаточно прав.')
    return redirect('production:index')
```

### Опционально: Роль DEMO_VIEWER для преподавателя

Если нужен read-only режим, потребуется:
1. Добавить `UserRole.DEMO_VIEWER = 'DEMO_VIEWER'` в модель (+ миграция)
2. Убрать DEMO_VIEWER из всех `can_manage_*` функций
3. Пересоздать аккаунт teacher с новой ролью

**Объём работы:** ~30 мин. **Нужно решение владельца.** [?]

---

## 8. Итоговый вердикт

| Критерий | Статус | Источник |
|---|---|---|
| 68/68 тестов PASS | ✅ | [test — task-415.log] |
| 18-шаговый бизнес-цикл PASS | ✅ | [test — task-415.log] |
| `check --deploy` — 0 issues | ✅ | [prev] |
| CSRF + Cloudflare совместимость | ✅ | [src] |
| SSL Redirect — не будет loop | ✅ | [src] |
| `--forwarded-allow-ips` скорректирован | ✅ | [src — анализ] |
| Django Admin заблокирован | ✅ | [src] |
| UI управления пользователями отсутствует | ✅ | [src] |
| `dev_login` заблокирован в prod | ✅ | [src] |
| stage_advance/qc/waste без role-check | ⚠️ N-1,2,3 | [src] |
| IP в AuditLog = 127.0.0.1 через tunnel | ⚠️ N-5 | [src] |
| **Готов к публичному демо при правильном запуске** | ✅ **ДА** | |

---

**⏸ Аудит завершён. Ожидаю решения владельца.**

*Ветка: `python-django` · Коммитов: 0 · Код не изменялся*
