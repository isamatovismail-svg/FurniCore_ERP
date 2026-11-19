# HOTFIX REPORT — Production Order Creation NameError

**Дата:** 2026-11-19  
**Версия:** FurniCore ERP (ветка `python-django`)  
**Статус:** ✅ ИСПРАВЛЕНО И ПОДТВЕРЖДЕНО ТЕСТАМИ

---

## 1. Описание ошибки

| Поле | Значение |
|---|---|
| **Тип ошибки** | `NameError: name 'initialize_order_stages' is not defined` |
| **Файл** | `apps/production/views.py`, строка 250 |
| **Функция** | `order_create` |
| **URL** | `/production/create/` |
| **HTTP метод** | `POST` |
| **Критичность** | Высокая — полностью блокирует создание производственных заказов |

---

## 2. Корневая причина

Ошибка была вызвана **неполной очисткой импортов** на этапе PHASE 1.4 (Safe Project Cleanup).

В рамках cleanup-а из секции импортов `apps/production/views.py` был удалён ряд «неиспользуемых» символов, в том числе `initialize_order_stages`. Однако функция **существовала и была нужна** — она вызывалась в строке 250 вью `order_create`.

### Git diff (commit HEAD vs предыдущий)

```diff
# apps/production/views.py
 from apps.production.services import (
     check_materials_availability,
     issue_materials_for_production,
     launch_production_order,
     advance_stage,
     register_waste_or_defect,
     submit_quality_check,
     complete_and_transfer_to_warehouse,
     recalculate_order_costs,
     ensure_default_routing_templates,
-    initialize_order_stages,       # УДАЛЁН ПО ОШИБКЕ
 )
```

### Почему статический анализ не поймал это раньше

Стандартный AST-анализ, применявшийся в PHASE 1.4, обнаруживал «неиспользуемые» символы только через `import` → вызов в функции. При этом `initialize_order_stages` фигурировало в `from apps.production.services import (...)`, но было удалено до записи в файл, поэтому повторная проверка не нашла его как «unused».

---

## 3. Анализ: функция `initialize_order_stages`

Функция определена в `apps/production/services.py` (строки 199–229).

**Бизнес-логика:**
1. Проверяет, есть ли уже у заказа этапы — если да, возвращает без изменений (**идемпотентна**).
2. Если у BOM заказа есть `routing_template` — использует этапы из него.
3. Иначе — берёт этапы из `DEFAULT_CATEGORY_ROUTES` по категории изделия.
4. Создаёт записи `ProductionStage` для каждого этапа, масштабируя `planned_hours` на объём партии.

Функция используется в трёх местах:
- `apps/production/views.py` → `order_create()` (строка 252) — **создание заказа через UI**
- `apps/production/services.py` → `launch_production_order()` (строка 350) — **запуск заказа в производство**
- `apps/sales/services.py` — **автоматическое создание производственного заказа при дефиците товара**

---

## 4. Исправление

### Файл 1: `apps/production/views.py`

**Изменение 1:** Добавлен отсутствующий импорт `initialize_order_stages`:

```python
from apps.production.services import (
    check_materials_availability,
    issue_materials_for_production,
    launch_production_order,
    advance_stage,
    register_waste_or_defect,
    submit_quality_check,
    complete_and_transfer_to_warehouse,
    recalculate_order_costs,
    ensure_default_routing_templates,
    initialize_order_stages,       # ВОССТАНОВЛЕН
)
```

**Изменение 2:** Добавлен импорт `transaction` и создание заказа обёрнуто в `transaction.atomic()`:

```python
with transaction.atomic():
    order.save()
    form.save_m2m()
    initialize_order_stages(order)
```

Это гарантирует, что если `initialize_order_stages` упадёт — заказ не будет сохранён в БД в неполном состоянии.

---

## 5. Новые тесты

Добавлены 3 новых теста в `tests/test_production_phase3.py`:

| # | Тест | Проверяет |
|---|---|---|
| `test_17` | `test_17_order_create_post_success_and_stages_initialization` | POST /production/create/ создаёт заказ, все этапы инициализируются, повторный вызов не дублирует этапы |
| `test_18` | `test_18_order_create_post_blocked_for_demo_viewer` | DEMO_VIEWER не может создать заказ (302 для обычного запроса, 403 для HTMX) |
| `test_19` | `test_19_order_create_post_blocked_for_unauthorized_roles` | WORKER получает редирект на `/production/` без создания заказа |

---

## 6. Результаты тестирования

### Django system check
```
System check identified no issues (0 silenced).
```

### Production-модуль (19/19 тестов)
```
19 passed in 26.52s
```

### Полный тестовый набор (77/77 тестов)
```
77 passed in 109.97s (0:01:49)
```

| Файл тестов | Пройдено |
|---|:---:|
| `test_all_routes.py` | 6/6 |
| `test_warehouse_phase2.py` | 11/11 |
| `test_production_phase3.py` | **19/19** (+3 новых) |
| `test_phase4_procurement_sales.py` | 10/10 |
| `test_phase5_finance_costing.py` | 11/11 |
| `test_phase5_5_acceptance.py` | 5/5 |
| `test_django_suite.py` | 4/4 |
| `test_demo_viewer_rbac.py` | 6/6 |
| **Итого** | **77/77 ✅** |

---

## 7. Инварианты бизнес-логики (подтверждено)

| Инвариант | Статус |
|---|:---:|
| Этапы создаются при POST /production/create/ | ✅ |
| Повторный вызов `initialize_order_stages` не дублирует этапы | ✅ |
| `planned_hours` масштабируется на объём партии | ✅ |
| DEMO_VIEWER не может создать заказ (browser + HTMX) | ✅ |
| WORKER перенаправляется с ошибкой прав | ✅ |
| OWNER и PRODUCTION_MANAGER имеют полный доступ | ✅ |
| Создание заказа транзакционно (atomic) | ✅ |
| 18-шаговый производственный бизнес-цикл не затронут | ✅ |

---

## 8. Затронутые файлы

| Файл | Тип изменения |
|---|---|
| `apps/production/views.py` | Добавлен импорт `initialize_order_stages` и `transaction`; `order_create` обёрнут в `transaction.atomic()` |
| `tests/test_production_phase3.py` | Добавлены тесты 17, 18, 19 |

**Не изменялись:** модели, миграции, бизнес-логика сервисов, RBAC, другие view-функции, база данных.
