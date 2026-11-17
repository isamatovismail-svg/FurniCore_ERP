# Отчёт об исправлении ошибок финансового модуля FurniCore ERP

## 1. Какие ошибки обнаружены

1. **Платежи клиентов (`/finance/payments/customers/`):**
   - **Причина:** В представлении `customer_payment_list` (а также `customer_payment_pdf`) использовался `select_related('created_by')`. Модель `CustomerPayment` содержит реальное поле внешнего ключа `recorded_by`, тогда как `created_by` является Python-property (`@property`), не поддерживаемым в ORM-оптимизации `select_related`.
   - **Ошибка шаблона:** В `templates/finance/payments/customer_payment_list.html` использовался фильтр `{{ p.payment_date|date:"d.m.Y H:i" }}` на поле `DateField` (без времени), что приводило к `TypeError: The format for date objects may not contain time-related format specifiers (found 'H')` при наличии записей.

2. **Оплаты поставщикам (`/finance/payments/suppliers/`):**
   - **Причина:** В представлении `supplier_payment_list` и `supplier_payment_pdf` также использовался ошибочный `select_related('created_by')`. Поле модели `SupplierPayment` называется `recorded_by`.
   - **Ошибка шаблона:** В `templates/finance/payments/supplier_payment_list.html` аналогично использовался фильтр `{{ p.payment_date|date:"d.m.Y H:i" }}` для `DateField`.

3. **Счета и кассы (`/finance/accounts/`):**
   - **Причина 1:** В функции `account_list` выполнялась сортировка `FinancialAccount.objects.all().order_by('type', 'name')`, тогда как поле типа счета называется `account_type`. Это вызывало `FieldError: Cannot resolve keyword 'type' into field`.
   - **Причина 2:** Запрос `AccountTransfer.objects.select_related('from_account', 'to_account', 'created_by')` также содержал ошибочное имя поля (в модели `AccountTransfer` внешним ключом является `recorded_by`).
   - **Причина 3:** Шаблон вызывал `{{ acc.get_type_display }}` (вместо автогенерируемого Django `get_account_type_display` или `type_label`).
   - **Ошибка шаблона:** В таблице истории переводов использовался `{{ tr.transfer_date|date:"d.m.Y H:i" }}` для `DateField`.

4. **Себестоимость производства (`/finance/costing/`):**
   - **Причина 1:** В шаблоне `templates/finance/costing/order_cost.html` была неверная ссылка на детальную страницу производственного заказа: `{% url 'production:order_detail' item.order.pk %}` вместо `{% url 'production:detail' item.order.pk %}`, что вызывало `NoReverseMatch`.
   - **Причина 2:** В шаблоне использовалось свойство `item.order.quantity`, отсутствовавшее в модели `ProductionOrder` (реальное поле — `quantity_planned`).
   - **Причина 3:** В экспорте отчёта себестоимости в Excel (`apps/finance/reports.py`) происходило обращение к `po.quantity`, вызывавшее `AttributeError: 'ProductionOrder' object has no attribute 'quantity'`.

5. **Экспорт отчётов в Excel (`/finance/export/excel/`):**
   - **P&L экспорт (`?type=pandl`):** Вставка Django lazy-translation объектов (`gettext_lazy` `cat['label']`) в openpyxl приводила к `ValueError: Cannot convert 'Фонд оплаты труда (ФОТ)' to Excel`.
   - **Costing экспорт (`?type=costing`):** `AttributeError` из-за `po.quantity` и отсутствие строкового преобразования lazy-статусов.

6. **Дебиторская и кредиторская задолженность (`/finance/receivables/`, `/finance/payables/`):**
   - В заголовках таблиц выводилось `{{ orders.count }}`, которое для списков Python (`list`) возвращало пустую строку вместо количества записей. Заменено на `{{ orders|length }}`.

7. **Безопасность и обработка пустых связей при сторнировании (`apps/finance/services.py`):**
   - При сторнировании авансового платежа клиента (без привязки к `sales_order`) или поставщика (без привязки к `purchase_order`) прямое обращение `pay.sales_order.order_number` и `pay.supplier.name` в `AuditLog` вызывало `AttributeError: 'NoneType' object has no attribute ...`.

8. **Каталог мебели и загрузка фотографий (`apps/products/`):**
   - Поле `Product.image` присутствовало в модели, но формы создания/редактирования не поддерживали `enctype="multipart/form-data"` и не содержали `<input type="file" name="image">`.
   - В `apps/products/views.py` в функциях `product_create` и `product_edit` отсутствовала обработка `request.FILES`.
   - В шаблонах каталога (`products/index.html`) и детальной карточки (`products/detail.html`) отображались только статические векторные заглушки, а реальное фото `p.image` не рендерилось.
   - Отсутствовали реальные фотографии мебели для базовых категорий.

---

## 2. Какие файлы изменены

### Финансовый модуль:
1. `apps/finance/views.py`:
   - Исправлены `select_related('recorded_by')` вместо `select_related('created_by')` для `CustomerPayment`, `SupplierPayment`, `AccountTransfer`.
   - Исправлена сортировка счетов `order_by('account_type', 'name')` вместо несуществующего поля `type`.
   - В функциях `customer_payment_create`, `supplier_payment_create`, `account_transfer` передается `recorded_by=request.user`.
2. `apps/finance/models.py`:
   - Для `FinancialAccount` добавлен метод `get_type_display()` и безопасный доступ к `created_by` через `getattr(self, 'recorded_by', None)`.
3. `apps/finance/services.py`:
   - Добавлены проверки на `None` в `storno_customer_payment` (`pay.sales_order.order_number if pay.sales_order else None`) и `storno_supplier_payment`.
4. `apps/finance/reports.py`:
   - Все `lazy`-переводы (`gettext_lazy`) приведены к `str()` перед передачей в `openpyxl`.
   - Обращение к количеству в заказе скорректировано на `float(po.quantity_planned)`.
5. `apps/production/models.py`:
   - Добавлено свойство `@property def quantity(self) -> Decimal: return self.quantity_planned` для обратной совместимости шаблонов и отчетов.

### Шаблоны финансов:
6. `templates/finance/payments/customer_payment_list.html`:
   - Исправлен формат даты `{{ p.payment_date|date:"d.m.Y" }}`.
7. `templates/finance/payments/supplier_payment_list.html`:
   - Исправлен формат даты `{{ p.payment_date|date:"d.m.Y" }}`.
8. `templates/finance/accounts/account_list.html`:
   - Исправлен формат даты `{{ tr.transfer_date|date:"d.m.Y" }}`.
9. `templates/finance/costing/order_cost.html`:
   - Исправлен URL `production:detail` вместо `production:order_detail`.
10. `templates/finance/debts/receivables.html`:
    - Исправлен подсчет элементов `{{ orders|length }}`.
11. `templates/finance/debts/payables.html`:
    - Исправлен подсчет элементов `{{ orders|length }}`.

### Модуль продукции и фотографий:
12. `apps/products/views.py`:
    - Добавлена обработка `image = request.FILES.get('image')` в `product_create` и обновление `product.image` в `product_edit`.
13. `templates/products/form.html`:
    - Добавлен `enctype="multipart/form-data"`, превью текущего изображения и поле выбора файла `image`.
14. `templates/products/index.html`:
    - Добавлено отображение `p.image.url` с масштабированием `object-cover` и сохранением SVG-заглушки при отсутствии фото.
15. `templates/products/detail.html`:
    - Добавлено отображение `product.image.url` в карточке товара с сохранением заглушки.

---

## 3. Какие миграции созданы

- Запуск `python manage.py makemigrations --check --dry-run` показал: **«No changes detected»**.
- Поле `image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name='Фото')` уже существовало в схеме базы данных (миграция `apps/products/migrations/0001_initial.py`).
- Новые миграции не потребовались, структура таблиц БД сохранена в строгом соответствии с существующей архитектурой.

---

## 4. Какие финансовые страницы теперь открываются

Все ключевые финансовые разделы и операции экспорта возвращают HTTP 200 OK:
- `/finance/` — Финансовый центр (дашборд, KPI начисления и ДДС, структура расходов, виджеты счетов, последние операции).
- `/finance/payments/customers/` — Реестр платежей покупателей (с фильтрацией, поиском и статусами).
- `/finance/payments/customers/create/` — Форма регистрации оплаты покупателя (с предзаполнением по заказам и суммам долга).
- `/finance/payments/customers/<uuid:pk>/pdf/` — Генерация PDF-квитанции об оплате покупателя.
- `/finance/payments/suppliers/` — Реестр оплат поставщикам.
- `/finance/payments/suppliers/create/` — Форма проведения выплаты поставщику (с привязкой к заказам закупки).
- `/finance/payments/suppliers/<uuid:pk>/pdf/` — Генерация PDF платёжного поручения.
- `/finance/accounts/` — Казначейство: счета и кассы, балансы, история межбанковских переводов.
- `/finance/accounts/transfer/` — Форма внутреннего перевода денежных средств между счетами и кассами.
- `/finance/expenses/` — Реестр операционных расходов предприятия.
- `/finance/expenses/create/` — Форма регистрации расхода со списанием со счёта.
- `/finance/receivables/` — Дебиторская задолженность покупателей по заказам.
- `/finance/payables/` — Кредиторская задолженность перед поставщиками по закупкам.
- `/finance/costing/` — Калькуляция фактической и плановой себестоимости заказов цеха с анализом отклонений.
- `/finance/export/excel/?type=pandl` — Экспорт отчёта о прибылях и убытках (P&L) в Excel (.xlsx).
- `/finance/export/excel/?type=cashflow` — Экспорт отчёта о движении денежных средств (ДДС) в Excel (.xlsx).
- `/finance/export/excel/?type=receivables` — Экспорт реестра дебиторской задолженности в Excel (.xlsx).
- `/finance/export/excel/?type=payables` — Экспорт реестра кредиторской задолженности в Excel (.xlsx).
- `/finance/export/excel/?type=costing` — Экспорт калькуляции себестоимости заказов в Excel (.xlsx).

---

## 5. Какие операции проверены

1. **Регистрация клиентских платежей:**
   - Полная оплата заказа покупателя с автоматическим закрытием задолженности.
   - Частичная оплата (аванс) с корректным пересчетом остатка долга (`remaining_debt_kzt`).
   - Зачисление на расчетный счет банка и Kaspi QR с мгновенным ростом баланса счета (`current_balance_kzt`).
   - Защита от переплаты (нельзя принять сумму, превышающую долг по заказу).
   - Защита от дублирования платежей в течение 10 секунд.
   - Сторнирование платежа покупателя с возвратом остатка на счете и восстановлением задолженности заказа.

2. **Выплаты поставщикам:**
   - Выплата по заказу на закупку (`PurchaseOrder`) с уменьшением остатка кредиторской задолженности.
   - Списание средств с расчетного счета фабрики с контролем доступного баланса.
   - Защита от отрицательного баланса (отказ в операции при нехватке денег на счете).
   - Сторнирование выплаты с возвратом денежных средств на счет фабрики и восстановлением долга перед поставщиком.

3. **Внутренние переводы между счетами:**
   - Перевод средств со счета банка в кассу (инкассация/пополнение): списание с одного счета и начисление на второй.
   - Защита от списания суммы больше текущего остатка счета (`current_balance_kzt < amount`).
   - Сортировка `id` счетов при блокировке `select_for_update` для предотвращения deadlocks.

4. **Операционные расходы:**
   - Регистрация расходов со списанием с кассы/счета.
   - Сторнирование расхода с восстановлением остатка на счете.

5. **Каталог мебели и медиа:**
   - Локально загружены и размещены в `media/products/` фотографии мебели высокого разрешения для 5 базовых категорий:
     - `products/wardrobe.jpg` — Шкафы
     - `products/kitchen.jpg` — Кухни
     - `products/bed.jpg` — Кровати
     - `products/table.jpg` — Столы
     - `products/sofa.jpg` — Диваны
   - Фотографии привязаны ко всем существующим товарам каталога.
   - Проверено создание товара с загрузкой нового файла изображения через форму.
   - Проверено редактирование товара с заменой фото.
   - Проверено корректное отображение фото в сетке каталога (`/products/`) и в карточке товара (`/products/<uuid>/`).

---

## 6. Результаты тестов

- `python manage.py check`:
  ```
  System check identified no issues (0 silenced).
  ```
- `python manage.py makemigrations --check --dry-run`:
  ```
  No changes detected
  ```
- `pytest tests/test_phase5_finance_costing.py`:
  ```
  16 passed in 1.16s
  ```
- Полный набор тестов pytest (`tests/test_all_routes.py`, `tests/test_phase5_finance_costing.py`, `tests/test_django_suite.py`, `tests/test_production_phase3.py`, `tests/test_phase4_procurement_sales.py`, `tests/test_warehouse_phase2.py`, `tests/test_phase5_5_acceptance.py`):
  ```
  68 passed in 32.63s (100% success rate)
  ```
- Тестирование через Django Test Client всех URL финансового блока:
  - 17/17 запросов (HTML-страницы и Excel-экспорт) завершились со статусом **200 OK**.

---

## 7. Что осталось неисправным

Все выявленные ошибки финансового модуля, отчётов и каталога мебели полностью устранены. Неисправных элементов в рамках поставленных задач не осталось.
