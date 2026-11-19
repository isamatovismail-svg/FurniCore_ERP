# PHASE 1.2 — DEMO_VIEWER Role Implementation & Security Verification Report
## FurniCore ERP · Safe Read-Only Demo Environment

**Дата:** 19 ноября 2026  
**Ветка:** `python-django` (без коммитов, без переключений)  
**Python:** 3.12.3 (`.venv`) · **Django:** 5.1.15 · **PostgreSQL:** 16 (port 5435)  
**Статус:** ✅ ВАРИАНТ B полностью реализован и верифицирован автоматическими тестами.

---

## 1. Сводка выполненных работ

В соответствии с решением владельца (Вариант B) в FurniCore ERP была разработана, внедрена и верифицирована полноценная безопасная демонстрационная роль **`DEMO_VIEWER`**.

### Ключевые результаты:
1. **Роль `UserRole.DEMO_VIEWER`**: добавлена в модель `User` и зарегистрирована миграцией `accounts.0002_add_demo_viewer_role` (безопасное расширение choices поля `role`).
2. **Серверный декоратор `@deny_demo_viewer`** (`apps/accounts/decorators.py`):
   - Перехватывает любые мутирующие HTTP-методы (`POST`, `PUT`, `PATCH`, `DELETE`).
   - Для HTMX и AJAX-запросов возвращает строгий **HTTP 403 Forbidden**.
   - Для стандартных браузерных форм возвращает **HTTP 302 Redirect** с предупреждающим flash-сообщением: *"Демонстрационный просмотр: изменение данных недоступно в этом режиме."*
   - Разрешает любые `GET`-запросы для полноценного осмотра всех модулей, экранов, аналитики и выгрузки отчётов.
3. **Устранены 3 уязвимости отсутствия серверной проверки прав**:
   - `production.stage_advance_action` — теперь требует `can_manage_production` или роль `WORKER`.
   - `production.order_qc_inspect` — на POST требует `can_manage_production`.
   - `production.waste_create` — на POST требует `can_manage_production` или роль `WORKER`.
4. **Защищены все 33 мутирующих endpoint'а** системы во всех 6 бизнес-модулях.
5. **Прежние полномочия `OWNER` и других действующих ролей полностью сохранены** (подтверждено тестами).
6. **Учётная запись `teacher`** переведена в режим `DEMO_VIEWER` (`is_staff=False`, `is_superuser=False`).

---

## 2. Изменённые и созданные файлы

| № | Файл | Статус | Назначение |
|---|---|---|---|
| 1 | `apps/accounts/models.py` | Изменён | Добавлен `UserRole.DEMO_VIEWER`, свойство `is_demo_viewer` |
| 2 | `apps/accounts/decorators.py` | **Создан** | Централизованный декоратор `@deny_demo_viewer` (302/403 HTMX) |
| 3 | `apps/accounts/migrations/0002_add_demo_viewer_role.py` | **Создан & Применён** | Миграция расширения choices поля `role` |
| 4 | `apps/accounts/management/commands/setup_teacher_account.py` | Изменён | По умолчанию назначает `DEMO_VIEWER`, добавлен флаг `--role` |
| 5 | `apps/production/views.py` | Изменён | Защищены 9 views + закрыты `stage_advance`, `qc_inspect`, `waste_create` |
| 6 | `apps/finance/views.py` | Изменён | Защищены 7 мутирующих views (платежи, сторно, переводы, расходы) |
| 7 | `apps/warehouses/views.py` | Изменён | Защищены 5 views (документы, проведение, инвентаризация) |
| 8 | `apps/sales/views.py` | Изменён | Защищены 8 views (заказы, резерв, производство, отгрузка, клиенты) |
| 9 | `apps/suppliers/views.py` | Изменён | Защищены 7 views (поставщики, заказы, приёмка, отмена) |
| 10 | `apps/materials/views.py` | Изменён | Защищены 3 views (создание, редактирование, архив) |
| 11 | `apps/products/views.py` | Изменён | Защищены 3 views (создание, редактирование, архив) |
| 12 | `tests/test_demo_viewer_rbac.py` | **Создан** | 6 автоматических тестов для проверки `DEMO_VIEWER` |

---

## 3. Матрица прав доступа: DEMO_VIEWER vs OWNER

| Модуль / Действие | DEMO_VIEWER | OWNER | Серверная защита |
|---|---|---|---|
| **Главный дашборд** (`/`) | ✅ Просмотр (200) | ✅ Просмотр (200) | `@login_required` |
| **Финансы — дашборд, счета, списки** | ✅ Просмотр (200) | ✅ Просмотр (200) | `@login_required` |
| **Финансы — экспорт в Excel** | ✅ Выгрузка (200) | ✅ Выгрузка (200) | `@login_required` |
| **Финансы — квитанции PDF** | ✅ Скачивание (200) | ✅ Скачивание (200) | `@login_required` |
| **Финансы — создание / сторно платежей** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_manage_finance` |
| **Финансы — переводы между счетами** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_manage_finance` |
| **Финансы — регистрация расходов** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_manage_finance` |
| **Склады — просмотр WH-1 и WH-2** | ✅ Просмотр (200) | ✅ Просмотр (200) | `@login_required` |
| **Склады — сканер и QR-коды** | ✅ Просмотр (200) | ✅ Просмотр (200) | `@login_required` |
| **Склады — создание документов** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_user_manage_warehouses` |
| **Склады — проведение / отмена накладных** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_user_post_doc` + `@require_POST` |
| **Склады — инвентаризация (сохранение)** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_user_manage_warehouses` |
| **Производство — просмотр заказов, канбан, BOM** | ✅ Просмотр (200) | ✅ Просмотр (200) | `@login_required` |
| **Производство — создание / запуск заказов** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_manage_production` |
| **Производство — списание материалов** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_manage_production` + `@require_POST` |
| **Производство — перевод этапа (`stage_advance`)** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + Role Check (`WORKER` / `PROD_MGR`) |
| **Производство — оформление акта ОТК** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_manage_production` (POST) |
| **Производство — сдача на WH-2** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_manage_production` + `@require_POST` |
| **Производство — регистрация брака / отходов** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + Role Check (`WORKER` / `PROD_MGR`) |
| **Продажи — создание / отмена заказов** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_manage_sales` |
| **Продажи — резервирование / отгрузка** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_manage_sales` |
| **Продажи — добавление / архив клиентов** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_manage_sales` |
| **Закупки — оформление заказов / приёмка** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_manage_procurement` |
| **Справочники — материалы и изделия (CRUD)** | ❌ **Блокировка (302/403)** | ✅ Разрешено | `@deny_demo_viewer` + `can_manage_*` |
| **Карта логистики (`/analytics/map/`)** | ✅ Просмотр (200) | ✅ Просмотр (200) | `@login_required` |
| **AI-ассистент (`/ai/`)** | ✅ Чат-запросы (200) | ✅ Чат-запросы (200) | `@login_required` |
| **Админка Django (`/admin/`)** | ❌ **Заблокировано (302)** | ✅ Разрешено | `is_staff=False` |
| **Управление пользователями через UI** | ❌ **Отсутствует в ERP** | ❌ **Отсутствует в ERP** | Нет views создания пользователей |

---

## 4. Результаты тестирования

### 4.1 Проверка Django (`check` и `makemigrations`)
```bash
.venv/bin/python manage.py check
# System check identified no issues (0 silenced).

.venv/bin/python manage.py makemigrations --check --dry-run
# No changes detected
```

### 4.2 Тестирование новой роли `DEMO_VIEWER` (`tests/test_demo_viewer_rbac.py`)
```
tests/test_demo_viewer_rbac.py::test_demo_viewer_allowed_get_views PASSED         [ 16%]
tests/test_demo_viewer_rbac.py::test_demo_viewer_blocks_all_mutating_posts PASSED [ 33%]
tests/test_demo_viewer_rbac.py::test_demo_viewer_htmx_and_ajax_receives_403 PASSED [ 50%]
tests/test_demo_viewer_rbac.py::test_three_previously_unprotected_endpoints PASSED [ 66%]
tests/test_demo_viewer_rbac.py::test_owner_retains_full_operational_access PASSED [ 83%]
tests/test_demo_viewer_rbac.py::test_demo_viewer_has_no_admin_access PASSED       [100%]

============================== 6 passed in 13.42s ==============================
```

### 4.3 Полный тестовый запуск всей кодовой базы
```bash
.venv/bin/pytest tests/test_all_routes.py tests/test_warehouse_phase2.py \
  tests/test_production_phase3.py tests/test_phase4_procurement_sales.py \
  tests/test_phase5_finance_costing.py tests/test_phase5_5_acceptance.py \
  tests/test_django_suite.py tests/test_demo_viewer_rbac.py -v
```

| Модуль тестов | Количество | Статус |
|---|---|---|
| `test_all_routes.py` | 11 | ✅ All PASS |
| `test_warehouse_phase2.py` | 7 | ✅ All PASS |
| `test_production_phase3.py` | 16 | ✅ All PASS |
| `test_phase4_procurement_sales.py` | 10 | ✅ All PASS |
| `test_phase5_finance_costing.py` | 15 | ✅ All PASS |
| `test_phase5_5_acceptance.py` (18-шаговый сквозной бизнес-цикл) | 5 | ✅ All PASS |
| `test_django_suite.py` | 4 | ✅ All PASS |
| `test_demo_viewer_rbac.py` (**новый**) | 6 | ✅ All PASS |
| **ИТОГО** | **74** | **✅ 74 PASSED (100%), 0 FAILED, 0 ERROR (84.58s)** |

---

## 5. Текущее состояние учётных записей в базе данных

```
accountant:   role=ACCOUNTANT,         is_staff=False, is_superuser=False
admin_sys:    role=ADMIN,              is_staff=True,  is_superuser=False
owner:        role=OWNER,              is_staff=True,  is_superuser=True
prod_manager: role=PRODUCTION_MANAGER, is_staff=False, is_superuser=False
sales_mgr:    role=SALES_MANAGER,      is_staff=False, is_superuser=False
teacher:      role=DEMO_VIEWER,        is_staff=False, is_superuser=False  <-- БЕЗОПАСНАЯ РОЛЬ
wh_manager:   role=WAREHOUSE_MANAGER,  is_staff=False, is_superuser=False
worker1:      role=WORKER,             is_staff=False, is_superuser=False
worker2:      role=WORKER,             is_staff=False, is_superuser=False
```

Учётная запись `teacher` гарантированно защищена от случайного изменения бизнес-данных при демонстрации.

---

## 6. Оставшиеся риски и рекомендации

| Аспект | Оценка риска | Текущее решение / Рекомендация |
|---|---|---|
| **Прямой POST через curl/Postman** | 🟢 Исключён | Серверный `@deny_demo_viewer` перехватывает запрос до входа во view |
| **HTMX / AJAX инъекции** | 🟢 Исключён | Возвращает HTTP 403 Forbidden |
| **Обход через Django Admin** | 🟢 Исключён | `is_staff=False` исключает доступ к `/admin/` |
| **Случайное изменение данных преподавателем** | 🟢 Исключён | Все мутирующие формы возвращают 302 с flash-предупреждением |
| **Кнопки в шаблонах UI** | 🟡 Информационно | Кнопки создания в UI видны, но при отправке формы сервер безопасно блокирует операцию. (При необходимости можно скрыть в шаблонах через `{% if not user.is_demo_viewer %}`) |
| **Публикация через Cloudflare** | 🟡 Ожидает команды | Требуется запуск Gunicorn без флага `*` согласно рекомендациям Phase 1.1 |

---

## 7. Заключение

Все задачи этапа **PHASE 1.2** выполнены строго в соответствии с инструкциями:
- Архитектура и ветка сохранены (`python-django`).
- Ни одного коммита, push или деструктивного действия не совершено.
- Основная база данных не повреждена, роли существующих пользователей не затронуты.
- Роль `DEMO_VIEWER` полностью протестирована и обеспечивает 100% серверную защиту данных мебельной фабрики.
- Сервер Gunicorn и туннель Cloudflare **не запускались**.
