# FurniCore ERP — Furniture Management System

Профессиональная модульная ERP-платформа для управления мебельным производством.

## 1. Архитектура и стек технологий

- **Монорепозиторий:** `pnpm` workspaces
- **Frontend (`apps/web`):** Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Lucide React, Recharts
- **Backend (`apps/api`):** NestJS 10, TypeScript, REST API, Passport JWT, class-validator
- **Database (`packages/database`):** PostgreSQL 16 (Docker Compose), Prisma ORM 6
- **Shared (`packages/shared`):** Общие типы, константы, утилиты форматирования валюты KZT (₸)
- **Валюта учета:** Казахстанский тенге (KZT, ₸)
- **Интерфейс:** Полная локализация на русский язык

---

## 2. Складская топология (Ровно 2 склада)

1. **Склад №1 — Сырье и материалы (`WH-1`):**
   - Древесина (массив дуба, массив сосны)
   - Плитные материалы (МДФ 16–18мм, ЛДСП Egger, березовая фанера)
   - Мебельная фурнитура (петли Blum, направляющие скрытого монтажа Tandem, ручки, конфирматы)
   - Лакокрасочные материалы и клей (Renner, Sayerlack, Titebond II)
   - Обивка и наполнители (велюр Teddy, высокоэластичный поролон HR3535)
   - Учет минимального буфера и оперативный мониторинг дефицита.

2. **Склад №2 — Готовая продукция (`WH-2`):**
   - Шкафы (распашные и купе)
   - Обеденные столы
   - Кровати двуспальные с подъемным механизмом
   - Модульные кухни
   - Прямые и угловые диваны
   - Учет свободных остатков, клиентских резервов и защита от повторных списаний при отгрузках.

> **Важно:** Производственный цех выделен в самостоятельный технологический модуль (техкарты BOM, наряды, списание расхода), а не третий склад.

---

## 3. Запуск проекта

### Шаг 1: Поднятие базы данных (PostgreSQL)
```bash
cd furnicore
docker compose up -d
```
База данных поднимается на порту `5435` (`furnicore_postgres`), чтобы исключить конфликты с локальными сервисами на портах 5432 и 5434.

### Шаг 2: Синхронизация схемы и заполнение DEMO-данными
```bash
pnpm db:push
pnpm db:seed
```

### Шаг 3: Сборка пакетов и приложений
```bash
pnpm --filter @furnicore/shared build
pnpm --filter @furnicore/database build
pnpm --filter @furnicore/api build
pnpm --filter @furnicore/web build
```

### Шаг 4: Запуск в режиме разработки
```bash
# Запуск Backend API (порт 4000)
pnpm --filter @furnicore/api dev

# Запуск Frontend Web (порт 3000)
pnpm --filter @furnicore/web dev
```

---

## 4. Демо-пользователи в базе данных

| Email | Роль | Пароль |
| :--- | :--- | :--- |
| `admin@furnicore.kz` | OWNER (Владелец) | `furnicore123` |
| `production@furnicore.kz` | PRODUCTION_MANAGER (Начальник производства) | `furnicore123` |
| `warehouse@furnicore.kz` | WAREHOUSE_MANAGER (Зав. складом) | `furnicore123` |
| `sales@furnicore.kz` | SALES_MANAGER (Менеджер по продажам) | `furnicore123` |
| `worker@furnicore.kz` | WORKER (Мастер цеха) | `furnicore123` |
