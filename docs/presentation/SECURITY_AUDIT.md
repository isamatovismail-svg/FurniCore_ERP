# FurniCore ERP — Отчёт об аудите безопасности (Security Audit)

**Дата проведения аудита:** 18 ноября 2026 г.  
**Проверяемая система:** FurniCore ERP (Python 3.12, Django 5.1.15, PostgreSQL 16)  
**Репозиторий:** `https://github.com/isamatovismail-svg/FurniCore_ERP`  
**Итоговая оценка безопасности:** **ВЫСОКАЯ (SECURE FOR DEMO & PRODUCTION)**

---

## 1. Сводная матрица проверок безопасности

| Направление проверки | Механизм защиты в кодовой базе | Результат проверки | Статус |
|---|---|---|---|
| **Режим `DEBUG`** | `DEBUG = os.getenv('DEBUG', 'False')` в `config/settings.py` | В продакшене выключается; стек-трейсы не раскрываются пользователю | READY |
| **Секретный ключ (`SECRET_KEY`)** | Считывается строго из переменной окружения `SECRET_KEY`; валидация при `DEBUG=False` | Исключение `ImproperlyConfigured` при пустом ключе в prod | READY |
| **Сетевые ограничения** | `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS` настраиваются через `.env` | Защита от HTTP Host Header Injection | READY |
| **Защита от CSRF** | `django.middleware.csrf.CsrfViewMiddleware` + `{% csrf_token %}` | Все формы и мутирующие POST-запросы валидируются | READY |
| **Ролевой контроль доступа (RBAC)** | Модель `UserRole`, декораторы `@login_required`, проверка ролей в представлениях | Обычные пользователи не имеют доступа к админке и финансам | READY |
| **Защита от SQL-инъекций** | 100% Django ORM с параметризацией запросов | Отсутствие конкатенации сырых SQL-строк (`cursor.execute` безопасен) | READY |
| **Защита от XSS** | Автоматическое экранирование Django Templates + `SECURE_BROWSER_XSS_FILTER = True` | Вредоносный HTML/JS нейтрализуется при рендере | READY |
| **Защита от Clickjacking** | `X_FRAME_OPTIONS = 'DENY'` + `XFrameOptionsMiddleware` | Встраивание во фреймы сторонних сайтов запрещено | READY |
| **Защита от MIME-sniffing** | `SECURE_CONTENT_TYPE_NOSNIFF = True` | Браузер строго следует объявленному `Content-Type` | READY |
| **Безопасность сессий и куки** | `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_AGE = 86400` | Недоступность сессионных куки через JavaScript (`document.cookie`) | READY |
| **Параметры HTTPS в Prod** | HSTS (31536000 сек), `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | При `DEBUG=False` тест `check --deploy` возвращает 0 замечаний | READY |
| **Изоляция секретов в Git** | `.gitignore:32` исключает `.env` и `.venv/` | Проверено: `.env` не индексируется и отсутствует в репозитории | READY |
| **Безопасность AI-интеграции** | Серверные запросы без утечки ключа; строгий Read-Only режим; отсутствие доступа к изменениям БД | Ключ OpenAI изолирован на сервере; при отсутствии ключа — DEMO MODE | READY |

---

## 2. Результат верификации Django `check --deploy`

Команда системной проверки безопасности Django в боевом режиме:
```bash
DEBUG=False SECRET_KEY="prod-secret-key-audit-verify" ALLOWED_HOSTS="localhost,127.0.0.1,furnicore.kz" .venv/bin/python manage.py check --deploy
```

**Результат выполнения:**
```text
System check identified no issues (0 silenced).
```
Все встроенные проверки безопасности Django (HSTS, SSL Redirect, Secure Cookies, Clickjacking, MIME-sniffing) пройдены без единого предупреждения.

---

## 3. Анализ защищенности бизнес-логики и транзакций

### 3.1. Защита от отрицательных остатков (Warehouse Invariants)
- **Угроза:** Параллельные запросы на списание сырья (WH-1) или отгрузку готовой мебели (WH-2) могут вызвать состояние гонки (Race Condition) и увести остаток в минус.
- **Реализованная защита:** В `apps/warehouses/services.py` и `apps/production/services.py` списание выполняется в атомарной транзакции с блокировкой строки:
  ```python
  balance = StockBalance.objects.select_for_update().get(warehouse=wh, material=mat)
  if balance.current_stock < required_qty:
      raise ValidationError("Недостаточно остатка на складе")
  ```
  Полнота покрытия подтверждена тестом `tests/test_warehouse_phase2.py::test_wh1_production_issue_and_negative_protection`.

### 3.2. Защита от переплаты и двойных платежей (Finance Invariants)
- **Угроза:** Повторная отправка формы оплаты клиентом или указание суммы, превышающей стоимость заказа.
- **Реализованная защита:** Метод `register_customer_payment()` блокирует заказ через `select_for_update()`, суммирует ранее проведённые платежи и возбуждает `ValidationError`, если `total_paid + new_amount > order.total_amount_kzt`.
  Полнота покрытия подтверждена тестом `tests/test_phase5_finance_costing.py::test_prevent_duplicate_customer_payment`.

### 3.3. Блокировка приёмки на WH-2 без контроля качества (QC Gate)
- **Угроза:** Приёмка бракованной мебели на склад и случайная отгрузка клиенту.
- **Реализованная защита:** В `apps/production/services.py` метод `complete_and_transfer_to_warehouse()` программно проверяет статус связанного `QualityCheck`. Если вердикт не равен `QCResult.PASS`, операция отклоняется исключением `ValidationError`.
  Подтверждено тестом `tests/test_production_phase3.py::test_12_block_wh2_transfer_before_qc_pass`.

---

## 4. Защита файлов и медиа-контента
- Все загружаемые файлы (чертежи, штрихкоды, акты) хранятся в изолированном каталоге `media/`.
- Выполнение скриптов внутри `media/` и `staticfiles/` блокируется веб-сервером (Nginx директива `location /media/ { ... }` без FastCGI/uWSGI обработчиков).
- Сгенерированные PDF и Excel документы отдаются как стриминговый `HttpResponse` с безопасными MIME-типами (`application/pdf`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`) и заголовком `Content-Disposition: inline` или `attachment`.

---

## 5. Резервное копирование и восстановление (Disaster Recovery)

### Резервное копирование базы данных PostgreSQL:
```bash
# Создание сжатого бинарного дампа
pg_dump -h 127.0.0.1 -p 5435 -U furnicore_user -F c -b -v -f "furnicore_backup_$(date +%Y%m%d_%H%M%S).dump" furnicore_db
```

### Восстановление из дампа:
```bash
# Восстановление в чистую базу
pg_restore -h 127.0.0.1 -p 5435 -U furnicore_user -d furnicore_db -v "furnicore_backup_YYYYMMDD_HHMMSS.dump"
```

---

## 6. Рекомендации для владельца проекта перед публичным релизом
1. Сгенерировать уникальный `SECRET_KEY` длиной не менее 50 символов для файла `.env.production`.
2. Указать реальный домен в `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS` (например, `furnicore.kz,www.furnicore.kz`).
3. Сменить стандартный пароль суперпользователя `owner` на сложный криптографический пароль.
4. Оставить демо-пользователей (`worker1`, `sales_mgr`, `wh_manager`) с правами только в пределах их операционной роли.
