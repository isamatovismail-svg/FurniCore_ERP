# PHASE 1.2 — Implementation Plan: DEMO_VIEWER Role
## FurniCore ERP · Дата: 2026-11-19

> **Статус:** Ожидает подтверждения владельца. Код не изменён.

---

## Часть 1. Полный аудит endpoint'ов (исходный код)

### 1.1 Метод аудита

Каждый `def view(request, ...)` в каждом `views.py` проанализирован скриптом:
- Определён HTTP-метод (GET, POST или оба)
- Определены декораторы (`@login_required`, `@require_POST`)
- Определено наличие `can_manage_*` или `can_user_*` проверки
- Определено: изменяет ли данные при POST

### 1.2 Итоговая таблица всех 33 мутирующих endpoint'ов

#### Финансы (`apps/finance/views.py`) — гейтер: `can_manage_finance` = OWNER, ADMIN, ACCOUNTANT

| View | Метод | `@require_POST` | Role-check | Изменяет данные | Допустимо для DEMO_VIEWER |
|---|---|---|---|---|---|
| `customer_payment_create` | GET+POST | ❌ | ✅ `can_manage_finance` | ✅ ДА — создаёт платёж | ❌ Запретить POST |
| `customer_payment_storno` | GET+POST | ❌ | ✅ `can_manage_finance` | ✅ ДА — сторно платежа | ❌ Запретить POST |
| `customer_payment_pdf` | GET | ❌ | ✅ `can_manage_finance` | ❌ Нет | ✅ Разрешить |
| `supplier_payment_create` | GET+POST | ❌ | ✅ `can_manage_finance` | ✅ ДА | ❌ Запретить POST |
| `supplier_payment_storno` | GET+POST | ❌ | ✅ `can_manage_finance` | ✅ ДА | ❌ Запретить POST |
| `supplier_payment_pdf` | GET | ❌ | ✅ `can_manage_finance` | ❌ Нет | ✅ Разрешить |
| `account_transfer` | GET+POST | ❌ | ✅ `can_manage_finance` | ✅ ДА | ❌ Запретить POST |
| `expense_create` | GET+POST | ❌ | ✅ `can_manage_finance` | ✅ ДА | ❌ Запретить POST |
| `expense_storno` | GET+POST | ❌ | ✅ `can_manage_finance` | ✅ ДА | ❌ Запретить POST |
| `export_excel` | GET | ❌ | `@login_required` only | ❌ Нет | ✅ Разрешить |
| `index`, `customer_payment_list`, `supplier_payment_list`, `account_list`, `expense_list`, `receivables_list`, `payables_list`, `cost_accounting_view` | GET | ❌ | `@login_required` | ❌ Нет | ✅ Разрешить |

#### Склады (`apps/warehouses/views.py`) — гейтеры: `can_user_manage_warehouses`, `can_user_post_doc`

| View | Метод | `@require_POST` | Role-check | Изменяет данные | Допустимо для DEMO_VIEWER |
|---|---|---|---|---|---|
| `document_create` | GET+POST | ❌ | ✅ `can_user_manage_warehouses` | ✅ ДА | ❌ Запретить POST |
| `document_post` | POST only | ✅ | ✅ `can_user_post_doc` | ✅ ДА — проводит документ | ❌ Запретить |
| `document_cancel` | POST only | ✅ | ✅ `can_user_post_doc` | ✅ ДА — отменяет документ | ❌ Запретить |
| `inventory_create` | GET+POST | ❌ | `@login_required` only | ✅ ДА | ❌ Запретить POST |
| `inventory_detail` | GET+POST | ❌ | `@login_required` only | ✅ ДА (reconcile) | ❌ Запретить POST |
| `index`, `wh1_view`, `wh2_view`, `document_list`, `document_detail`, `document_pdf`, `inventory_list`, `qr_image_view`, `item_label_pdf_view`, `scanner_view`, `scanner_lookup` | GET | — | `@login_required` | ❌ Нет | ✅ Разрешить |

#### Производство (`apps/production/views.py`) — гейтер: `can_manage_production` = OWNER, ADMIN, PRODUCTION_MANAGER

| View | Метод | `@require_POST` | Role-check | Изменяет данные | Допустимо для DEMO_VIEWER |
|---|---|---|---|---|---|
| `order_create` | GET+POST | ❌ | ✅ `can_manage_production` | ✅ ДА | ❌ Запретить POST |
| `order_edit` | GET+POST | ❌ | ✅ `can_manage_production` | ✅ ДА | ❌ Запретить POST |
| `order_issue_materials` | POST only | ✅ | ✅ `can_manage_production` | ✅ ДА | ❌ Запретить |
| `order_launch` | POST only | ✅ | ✅ `can_manage_production` | ✅ ДА | ❌ Запретить |
| `stage_advance_action` | POST only | ✅ | ❌ **Нет role-check!** | ✅ ДА | ❌ Запретить |
| `order_qc_inspect` | GET+POST | ❌ | ❌ **Нет role-check!** | ✅ ДА (POST) | ❌ Запретить POST; GET — разрешить просмотр |
| `order_transfer_wh2` | POST only | ✅ | ✅ `can_manage_production` | ✅ ДА | ❌ Запретить |
| `bom_create` | GET+POST | ❌ | ✅ `can_manage_production` | ✅ ДА | ❌ Запретить POST |
| `waste_create` | GET+POST | ❌ | ❌ **Нет role-check!** | ✅ ДА (POST) | ❌ Запретить POST; GET — разрешить просмотр |
| `index`, `detail`, `kanban_board`, `my_tasks`, `boms_list`, `bom_detail`, `routes_list`, `waste_list` | GET | — | `@login_required` | ❌ Нет | ✅ Разрешить |

#### Продажи (`apps/sales/views.py`) — гейтер: `can_manage_sales` = OWNER, ADMIN, SALES_MANAGER, PRODUCTION_MANAGER, ACCOUNTANT

| View | Метод | `@require_POST` | Role-check | Изменяет данные | Допустимо для DEMO_VIEWER |
|---|---|---|---|---|---|
| `order_create` | GET+POST | ❌ | ✅ `can_manage_sales` | ✅ ДА | ❌ Запретить POST |
| `order_reserve` | GET+POST | ❌ | ✅ `can_manage_sales` | ✅ ДА | ❌ Запретить |
| `order_create_production` | GET+POST | ❌ | ✅ `can_manage_sales` | ✅ ДА | ❌ Запретить |
| `order_ship` | GET+POST | ❌ | ✅ `can_manage_sales` | ✅ ДА (POST) | ❌ Запретить POST |
| `order_cancel` | GET+POST | ❌ | ✅ `can_manage_sales` | ✅ ДА | ❌ Запретить |
| `customer_create` | GET+POST | ❌ | ✅ `can_manage_sales` | ✅ ДА | ❌ Запретить POST |
| `customer_edit` | GET+POST | ❌ | ✅ `can_manage_sales` | ✅ ДА | ❌ Запретить POST |
| `customer_archive` | GET+POST | ❌ | ✅ `can_manage_sales` | ✅ ДА | ❌ Запретить |
| `index`, `order_detail`, `order_pdf`, `customers_list` | GET | — | `@login_required` | ❌ Нет | ✅ Разрешить |

#### Закупки (`apps/suppliers/views.py`) — гейтер: `can_manage_procurement` = OWNER, ADMIN, PRODUCTION_MANAGER, WAREHOUSE_MANAGER, ACCOUNTANT

| View | Метод | `@require_POST` | Role-check | Изменяет данные | Допустимо для DEMO_VIEWER |
|---|---|---|---|---|---|
| `supplier_create` | GET+POST | ❌ | ✅ `can_manage_procurement` | ✅ ДА | ❌ Запретить POST |
| `supplier_edit` | GET+POST | ❌ | ✅ `can_manage_procurement` | ✅ ДА | ❌ Запретить POST |
| `supplier_archive` | GET+POST | ❌ | ✅ `can_manage_procurement` | ✅ ДА | ❌ Запретить |
| `order_create` | GET+POST | ❌ | ✅ `can_manage_procurement` | ✅ ДА | ❌ Запретить POST |
| `order_send` | GET+POST | ❌ | ✅ `can_manage_procurement` | ✅ ДА | ❌ Запретить |
| `order_receive` | GET+POST | ❌ | ✅ `can_manage_procurement` | ✅ ДА | ❌ Запретить |
| `order_cancel` | GET+POST | ❌ | ✅ `can_manage_procurement` | ✅ ДА | ❌ Запретить |
| `index`, `order_list`, `order_detail`, `order_pdf` | GET | — | `@login_required` | ❌ Нет | ✅ Разрешить |

#### Справочники и остальные модули

| View | Метод | Изменяет данные | Допустимо для DEMO_VIEWER |
|---|---|---|---|
| `materials.material_create/edit/archive` | POST | ✅ ДА | ❌ Запретить POST |
| `products.product_create/edit/archive` | POST | ✅ ДА | ❌ Запретить POST |
| `dashboard.index` | GET | ❌ | ✅ |
| `analytics.index`, `logistics_map` | GET | ❌ | ✅ |
| `notifications.*` | GET/POST | Только свои | ✅ Разрешить (безвредно) |
| `ai_assistant.index` | GET/POST | Только запросы к AI | ✅ Разрешить (только query) |
| `employees.index`, `quality.index` | GET | ❌ | ✅ |
| `accounts.profile` | GET | ❌ | ✅ |

---

## Часть 2. Проектирование роли `DEMO_VIEWER`

### 2.1 Принципы

1. **Серверная защита первична** — все проверки на уровне view, не только в шаблонах
2. **Метод-ориентированная блокировка** — DEMO_VIEWER может делать GET на любую страницу (просмотр), но любой POST, изменяющий данные, должен возвращать HTTP 403
3. **Нулевая миграция** — `DEMO_VIEWER` = 11 символов, `max_length=30`, **новая миграция нужна** (добавление choices, но поле VARCHAR не меняется — миграция безопасная)
4. **OWNER не затрагивается** — все существующие `can_manage_*` функции остаются без изменений

### 2.2 Определение разрешений `DEMO_VIEWER`

```
DEMO_VIEWER может:
  ✅ GET на все страницы (дашборд, аналитика, отчёты, PDF)
  ✅ Просмотр любых списков (заказы, платежи, склад, производство)
  ✅ Скачать PDF документов (счета, накладные, платёжки)
  ✅ Скачать Excel отчёты
  ✅ Просмотр карты логистики
  ✅ Просмотр AI Assistant (только чтение чата)
  ✅ Просмотр ОТК-формы (GET /production/<pk>/qc/)
  ✅ Просмотр формы отходов (GET /production/<pk>/waste/create/)

DEMO_VIEWER НЕ МОЖЕТ:
  ❌ POST /finance/payments/*/create/ — создание платежей
  ❌ POST /finance/payments/*/storno/ — сторно
  ❌ POST /finance/accounts/transfer/ — переводы
  ❌ POST /finance/expenses/create/ — расходы
  ❌ POST /finance/expenses/*/storno/ — сторно расходов
  ❌ POST /warehouses/documents/create/ — создание документов
  ❌ POST /warehouses/documents/*/post/ — проведение
  ❌ POST /warehouses/documents/*/cancel/ — отмена
  ❌ POST /warehouses/inventory/create/ — инвентаризация
  ❌ POST /warehouses/inventory/*/ — подтверждение инвентаризации
  ❌ POST /production/create/ — создание заказа
  ❌ POST /production/*/edit/ — редактирование
  ❌ POST /production/*/issue-materials/ — списание
  ❌ POST /production/*/launch/ — запуск
  ❌ POST /production/stage/*/advance/ — переход этапа
  ❌ POST /production/*/qc/ — результат ОТК
  ❌ POST /production/*/transfer-wh2/ — передача на склад
  ❌ POST /production/boms/create/ — создание BOM
  ❌ POST /production/*/waste/create/ — регистрация отходов
  ❌ POST /sales/create/ — создание заказа
  ❌ POST /sales/*/reserve/ — резервирование
  ❌ POST /sales/*/create-production/ — запуск производства
  ❌ POST /sales/*/ship/ — отгрузка
  ❌ POST /sales/*/cancel/ — отмена
  ❌ POST /sales/customers/create/ и edit/, archive/ — управление клиентами
  ❌ POST /suppliers/create/ и edit/, archive/ — поставщики
  ❌ POST /suppliers/orders/create/, send/, receive/, cancel/ — закупки
  ❌ POST /materials/create/, edit/, archive/ — материалы
  ❌ POST /products/create/, edit/, archive/ — продукты
```

### 2.3 Вспомогательная функция-утилита

```python
# apps/accounts/models.py — добавить в UserRole:
DEMO_VIEWER = 'DEMO_VIEWER', _('Демонстрационный просмотр')

# apps/accounts/models.py — добавить в класс User:
@property
def is_demo_viewer(self) -> bool:
    return self.role == UserRole.DEMO_VIEWER
```

### 2.4 Центральный декоратор `@deny_demo_viewer`

```python
# apps/accounts/decorators.py — НОВЫЙ ФАЙЛ
from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect

def deny_demo_viewer(view_func):
    """Запрещает POST/PUT/PATCH/DELETE для роли DEMO_VIEWER."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if (hasattr(request.user, 'role') and
                request.user.role == 'DEMO_VIEWER' and
                request.method in ('POST', 'PUT', 'PATCH', 'DELETE')):
            messages.warning(
                request,
                'Демонстрационный просмотр: изменение данных недоступно.'
            )
            return redirect(request.META.get('HTTP_REFERER', '/'))
        return view_func(request, *args, **kwargs)
    return _wrapped
```

---

## Часть 3. Файлы для изменения и точные правки

### 3.1 Перечень файлов (8 файлов + 1 новый)

| Файл | Тип изменения | Объём |
|---|---|---|
| `apps/accounts/models.py` | Добавить `DEMO_VIEWER` в `UserRole` + свойство `is_demo_viewer` | +3 строки |
| `apps/accounts/decorators.py` | **СОЗДАТЬ** — декоратор `@deny_demo_viewer` | ~15 строк |
| `apps/accounts/migrations/0002_add_demo_viewer_role.py` | **СОЗДАТЬ** — миграция изменения choices | ~25 строк |
| `apps/finance/views.py` | Добавить `@deny_demo_viewer` на 7 view | +7 строк |
| `apps/warehouses/views.py` | Добавить `@deny_demo_viewer` на 5 view + role-check на inventory | +6 строк |
| `apps/production/views.py` | Добавить `@deny_demo_viewer` на 8 view + исправить role-check на 3 (stage/qc/waste) | +11 строк |
| `apps/sales/views.py` | Добавить `@deny_demo_viewer` на 8 view | +8 строк |
| `apps/suppliers/views.py` | Добавить `@deny_demo_viewer` на 7 view | +7 строк |
| `apps/materials/views.py` | Добавить `@deny_demo_viewer` на 3 view | +3 строки |
| `apps/products/views.py` | Добавить `@deny_demo_viewer` на 3 view | +3 строки |

**Итого: ~83 строки изменений в существующих файлах + 2 новых файла (~40 строк)**

### 3.2 Детальные правки: `apps/accounts/models.py`

```python
# БЫЛО:
class UserRole(models.TextChoices):
    OWNER = 'OWNER', _('Владелец бизнеса')
    ...
    WORKER = 'WORKER', _('Мастер цеха / Станочник')

# СТАЛО (добавить одну строку в конец UserRole):
class UserRole(models.TextChoices):
    OWNER = 'OWNER', _('Владелец бизнеса')
    ...
    WORKER = 'WORKER', _('Мастер цеха / Станочник')
    DEMO_VIEWER = 'DEMO_VIEWER', _('Демонстрационный просмотр')  # +1

# В классе User — добавить свойство:
@property
def is_demo_viewer(self) -> bool:
    return self.role == UserRole.DEMO_VIEWER
```

### 3.3 Детальные правки: `apps/production/views.py`

Три view без role-check — исправить одновременно с добавлением `@deny_demo_viewer`:

```python
# stage_advance_action — БЫЛО:
@login_required
@require_POST
def stage_advance_action(request, stage_id):
    ...

# СТАЛО:
@login_required
@require_POST
@deny_demo_viewer
def stage_advance_action(request, stage_id):
    if not (can_manage_production(request.user) or
            request.user.role == UserRole.WORKER):
        messages.error(request, 'Недостаточно прав.')
        return redirect('production:index')
    ...

# order_qc_inspect — БЫЛО:
@login_required
def order_qc_inspect(request, pk):
    ...

# СТАЛО:
@login_required
@deny_demo_viewer
def order_qc_inspect(request, pk):
    if request.method == 'POST' and not can_manage_production(request.user):
        messages.error(request, 'Недостаточно прав для оформления ОТК.')
        return redirect('production:detail', pk=pk)
    ...

# waste_create — БЫЛО:
@login_required
def waste_create(request, pk):
    ...

# СТАЛО:
@login_required
@deny_demo_viewer
def waste_create(request, pk):
    if request.method == 'POST' and not can_manage_production(request.user):
        messages.error(request, 'Недостаточно прав для регистрации отходов.')
        return redirect('production:detail', pk=pk)
    ...
```

### 3.4 Пример правки для finance view (шаблон для остальных)

```python
# БЫЛО:
@login_required
def customer_payment_create(request):
    if not can_manage_finance(request.user):
        ...

# СТАЛО (добавить только одну строку декоратора):
@login_required
@deny_demo_viewer
def customer_payment_create(request):
    if not can_manage_finance(request.user):
        ...
```

### 3.5 Скрипт создания аккаунта teacher с DEMO_VIEWER

```python
# apps/accounts/management/commands/setup_teacher_account.py
# Изменить role= с UserRole.OWNER на UserRole.DEMO_VIEWER:
user.role = UserRole.DEMO_VIEWER
```

---

## Часть 4. Совместимость с OWNER

### 4.1 Что НЕ меняется

| Компонент | Статус |
|---|---|
| `can_manage_finance()` — OWNER входит | ✅ Без изменений |
| `can_manage_production()` — OWNER входит | ✅ Без изменений |
| `can_manage_sales()` — OWNER входит | ✅ Без изменений |
| `can_manage_procurement()` — OWNER входит | ✅ Без изменений |
| `can_manage_materials()` — OWNER входит | ✅ Без изменений |
| `can_manage_products()` — OWNER входит | ✅ Без изменений |
| `can_user_manage_warehouses()` — OWNER входит | ✅ Без изменений |
| `can_user_post_doc()` — OWNER входит | ✅ Без изменений |
| Все существующие 8 demo-пользователей (owner, admin_sys, ...) | ✅ Без изменений |

### 4.2 Принцип совместимости

`@deny_demo_viewer` проверяется **до** `can_manage_*`. Для OWNER:
1. `request.user.role == 'DEMO_VIEWER'` → **False** → декоратор пропускается
2. Выполняется `can_manage_finance(user)` → True → операция разрешена

Нет конфликтов, нет регрессий.

---

## Часть 5. Защита от обхода ограничений

### 5.1 Прямые URL

Декоратор `@deny_demo_viewer` блокирует POST на уровне Django view **до** любой бизнес-логики.
Прямой HTTP-запрос `POST /finance/payments/customers/create/` от DEMO_VIEWER → HTTP 302 на referer
с сообщением об ошибке. CSRF-токен проверяется Django middleware **до** view, так что форма
без валидного CSRF-токена вернёт HTTP 403 ещё раньше.

### 5.2 API endpoints

В проекте **нет REST API endpoints** (DRF ViewSet, APIView) для бизнес-операций — подтверждено
аудитом `config/urls.py` и всех `apps/*/urls.py`. Единственный DRF — `rest_framework` для
browsable API (только dev-режим). Нет обходного пути через API.

### 5.3 Django Admin

`is_staff=False` → Django Admin недоступен. Не изменяется.

### 5.4 `dev_login`

При `DEBUG=False` эндпоинт возвращает HTTP 404. Не изменяется.

---

## Часть 6. Тесты, которые необходимо добавить

### 6.1 Новый тестовый файл: `tests/test_phase6_demo_viewer_rbac.py`

```python
# Тест-кейсы (псевдокод):

def test_demo_viewer_can_view_all_read_pages():
    """DEMO_VIEWER получает HTTP 200 на все GET-страницы."""
    # GET /, /finance/, /warehouses/, /production/, /sales/, /suppliers/
    # /materials/, /products/, /analytics/, /analytics/map/

def test_demo_viewer_blocked_finance_post():
    """DEMO_VIEWER не может создать платёж, расход, перевод."""
    # POST /finance/payments/customers/create/ → 302 (redirect, не 200)
    # POST /finance/expenses/create/ → 302

def test_demo_viewer_blocked_warehouse_post():
    """DEMO_VIEWER не может провести или создать складской документ."""
    # POST /warehouses/documents/create/ → 302
    # POST /warehouses/documents/<pk>/post/ → 302

def test_demo_viewer_blocked_production_post():
    """DEMO_VIEWER не может запустить производство, провести ОТК, зарегистрировать отходы."""
    # POST /production/create/ → 302
    # POST /production/stage/<id>/advance/ → 302
    # POST /production/<pk>/qc/ → 302
    # POST /production/<pk>/waste/create/ → 302

def test_demo_viewer_blocked_sales_post():
    """DEMO_VIEWER не может создать, зарезервировать, отгрузить или отменить заказ."""
    # POST /sales/create/ → 302
    # POST /sales/<pk>/reserve/ → 302
    # POST /sales/<pk>/ship/ → 302

def test_demo_viewer_can_download_pdf():
    """DEMO_VIEWER может скачать PDF документов."""
    # GET /finance/payments/customers/<pk>/pdf/ → 200
    # GET /sales/<pk>/pdf/ → 200

def test_owner_unaffected_by_demo_viewer_changes():
    """OWNER сохраняет полный доступ ко всем операциям."""
    # POST /finance/payments/customers/create/ с OWNER → 200 или redirect после успеха
    # POST /production/stage/<id>/advance/ с OWNER → успех

def test_stage_advance_now_has_role_check():
    """stage_advance_action теперь требует can_manage_production или WORKER."""
    # POST от SALES_MANAGER → 302 (blocked)
    # POST от PRODUCTION_MANAGER → 200 (allowed)
    # POST от WORKER → 200 (allowed)
```

### 6.2 Количество новых тест-кейсов: ~8 функций, ~25 assertion'ов

---

## Часть 7. Риски миграции

### 7.1 Технические риски

| Риск | Вероятность | Последствие | Митигация |
|---|---|---|---|
| `choices` в CharField — изменение приведёт к новой миграции | Гарантировано | Нужна `0002_add_demo_viewer_role.py` | Миграция не меняет тип колонки (VARCHAR(30)), только метаданные choices. Безопасна. |
| Существующие пользователи с `role='DEMO_VIEWER'` в БД | Невозможно | — | Роль новая, в БД её нет |
| `max_length=30` достаточен для `'DEMO_VIEWER'` (11 символов) | ✅ Подтверждено | — | Запас 19 символов |
| Тест `test_rbac_server_side_enforcement` — может сломаться если проверяет список ролей | Маловероятно | 1 тест FAIL | Проверить тест перед apply |

### 7.2 Функциональные риски

| Риск | Вероятность | Последствие | Митигация |
|---|---|---|---|
| `@deny_demo_viewer` добавлен не на все нужные views | Возможно | Частичный обход | Покрывается новыми тестами |
| Шаблоны показывают кнопки DEMO_VIEWER (UI не обновлён) | Высокий | Визуальный дискомфорт (кнопки ведут к 302) | Добавить `{% if not request.user.is_demo_viewer %}` вокруг write-кнопок |
| `order_reserve` и `order_create_production` принимают GET — DEMO_VIEWER может случайно активировать | Низкий (GET-ветка проверяет can_manage_sales) | Нет — действие выполняется только в POST-ветке | Дополнительно добавить `@require_POST` |

### 7.3 Демо-риски

| Риск | Последствие | Решение |
|---|---|---|
| Преподаватель видит кнопки, нажимает — получает "Доступ запрещён" без объяснения | Плохой UX | Вывести понятное сообщение "Демо-режим: только просмотр" |
| Преподаватель не понимает, что он в demo-режиме | Путаница | Добавить badge "DEMO MODE" в navbar |

---

## Часть 8. Альтернатива: оставить OWNER

Если реализация DEMO_VIEWER кажется избыточной для учебного проекта:

**Вариант A (текущий):** teacher = OWNER — полный доступ. Преподаватель может случайно изменить данные.  
**Риск:** Испорченные демо-данные в процессе показа.  
**Митигация:** Перед демо выполнить `python manage.py seed_demo_data` повторно (идемпотентен).

**Вариант B (рекомендуемый):** teacher = DEMO_VIEWER — только просмотр.  
**Плюсы:** Данные защищены, демо предсказуемо.  
**Минусы:** ~83 строки кода + миграция + тесты.

**Вариант C (компромисс):** Исправить только 3 критических gap'а (stage_advance, qc, waste),
оставить teacher = OWNER.  
**Объём:** ~6 строк кода, без новой роли, без миграции.

---

## Часть 9. Итог и решение владельца

> [!IMPORTANT]
> **Выберите один из вариантов:**

**Вариант A — ничего не менять:**
- teacher остаётся OWNER
- 3 gap'а (stage/qc/waste) не исправляются
- Объём: 0

**Вариант B — полная реализация DEMO_VIEWER:**
- Новая роль + декоратор + миграция + 8 view-файлов + тесты
- Объём: ~2 часа

**Вариант C — минимальные исправления (без новой роли):**
- Исправить role-check в stage_advance, qc_inspect, waste_create
- Добавить `@require_POST` на order_reserve, order_ship
- teacher остаётся OWNER
- Объём: ~20 минут

**После выбора — незамедлительно приступлю к реализации.**

---

*Код не изменялся. Ветка: `python-django`. Коммитов: 0.*  
*Все данные подтверждены чтением исходного кода.*
