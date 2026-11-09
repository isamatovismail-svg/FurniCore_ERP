"""
seed_demo.py — Management command to populate FurniCore ERP with labeled DEMO data.

All created records are explicitly labeled (DEMO) in their names.
Do NOT present this data as real business results.

Usage:
    python manage.py seed_demo
    python manage.py seed_demo --clear  # clears existing demo data first
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import datetime


class Command(BaseCommand):
    help = 'Создаёт демонстрационные данные (DEMO) для FurniCore ERP.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Удалить существующие демо-данные перед созданием новых',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            '\n⚠  ВНИМАНИЕ: Создаются ДЕМОНСТРАЦИОННЫЕ данные.\n'
            '   Они не являются реальными финансовыми показателями.\n'
        ))

        from apps.accounts.models import User, UserRole
        from apps.employees.models import Employee, Department
        from apps.warehouses.models import Warehouse, WarehouseType, StockBalance, StockMovement, MovementType
        from apps.materials.models import Material, MaterialCategory
        from apps.products.models import Product
        from apps.suppliers.models import Supplier
        from apps.sales.models import Customer, SalesOrder, SalesOrderItem, OrderStatus
        from apps.finance.models import Expense, ExpenseCategory

        if options['clear']:
            self.stdout.write('Очистка существующих демо-данных...')
            SalesOrderItem.objects.all().delete()
            SalesOrder.objects.all().delete()
            Customer.objects.all().delete()
            Expense.objects.all().delete()
            StockMovement.objects.all().delete()
            StockBalance.objects.all().delete()
            Material.objects.all().delete()
            Product.objects.all().delete()
            Supplier.objects.all().delete()
            Warehouse.objects.all().delete()
            Employee.objects.all().delete()
            User.objects.filter(username__in=[
                'owner', 'admin_sys', 'accountant', 'prod_manager',
                'wh_manager', 'sales_mgr', 'worker1', 'worker2',
            ]).delete()
            self.stdout.write(self.style.SUCCESS('✓ Демо-данные очищены'))

        # ── 1. USERS ──────────────────────────────────────────────────────
        self.stdout.write('Создание пользователей...')
        DEMO_PASSWORD = 'furnicore123'

        users_data = [
            dict(username='owner',        first_name='Арман',   last_name='Сейткали',    email='owner@furnicore.kz',    role=UserRole.OWNER,              is_staff=True, is_superuser=True),
            dict(username='admin_sys',    first_name='Дмитрий', last_name='Носов',        email='admin@furnicore.kz',    role=UserRole.ADMIN,              is_staff=True),
            dict(username='accountant',   first_name='Айгуль',  last_name='Мусина',       email='acc@furnicore.kz',      role=UserRole.ACCOUNTANT),
            dict(username='prod_manager', first_name='Сергей',  last_name='Быков',        email='prod@furnicore.kz',     role=UserRole.PRODUCTION_MANAGER),
            dict(username='wh_manager',   first_name='Нурлан',  last_name='Ахметов',      email='wh@furnicore.kz',       role=UserRole.WAREHOUSE_MANAGER),
            dict(username='sales_mgr',    first_name='Алина',   last_name='Касымова',     email='sales@furnicore.kz',    role=UserRole.SALES_MANAGER),
            dict(username='worker1',      first_name='Кайрат',  last_name='Джаксыбеков', email='worker1@furnicore.kz',  role=UserRole.WORKER),
            dict(username='worker2',      first_name='Иван',    last_name='Петренко',     email='worker2@furnicore.kz',  role=UserRole.WORKER),
        ]

        created_users = {}
        for ud in users_data:
            username = ud.pop('username')
            u, created = User.objects.get_or_create(username=username, defaults=ud)
            if created:
                u.set_password(DEMO_PASSWORD)
                u.save()
                self.stdout.write(f'  ✓ Создан: {username}')
            else:
                self.stdout.write(f'  · Уже существует: {username}')
            created_users[username] = u

        # ── 2. EMPLOYEES ─────────────────────────────────────────────────
        self.stdout.write('Создание сотрудников...')
        employees_data = [
            dict(employee_number='EMP-001', last_name='Сейткали',    first_name='Арман',   department=Department.MANAGEMENT,  position='Директор',          salary_kzt=Decimal('500000'), hire_date=datetime.date(2020, 1, 15), user=created_users['owner']),
            dict(employee_number='EMP-002', last_name='Быков',       first_name='Сергей',  department=Department.PRODUCTION,  position='Начальник цеха',    salary_kzt=Decimal('350000'), hire_date=datetime.date(2020, 3, 1),  user=created_users['prod_manager']),
            dict(employee_number='EMP-003', last_name='Ахметов',     first_name='Нурлан',  department=Department.WAREHOUSE,   position='Зав. складом',       salary_kzt=Decimal('280000'), hire_date=datetime.date(2021, 5, 10), user=created_users['wh_manager']),
            dict(employee_number='EMP-004', last_name='Мусина',      first_name='Айгуль',  department=Department.ACCOUNTING,  position='Главный бухгалтер', salary_kzt=Decimal('320000'), hire_date=datetime.date(2020, 6, 1),  user=created_users['accountant']),
            dict(employee_number='EMP-005', last_name='Касымова',    first_name='Алина',   department=Department.SALES,       position='Менеджер продаж',   salary_kzt=Decimal('260000'), hire_date=datetime.date(2022, 2, 14), user=created_users['sales_mgr']),
            dict(employee_number='EMP-006', last_name='Джаксыбеков', first_name='Кайрат',  department=Department.PRODUCTION,  position='Столяр-плотник',    salary_kzt=Decimal('200000'), hire_date=datetime.date(2021, 8, 20), user=created_users['worker1']),
            dict(employee_number='EMP-007', last_name='Петренко',    first_name='Иван',    department=Department.PRODUCTION,  position='Оператор ЧПУ',      salary_kzt=Decimal('220000'), hire_date=datetime.date(2022, 4, 5),  user=created_users['worker2']),
        ]
        for ed in employees_data:
            emp, created = Employee.objects.get_or_create(employee_number=ed['employee_number'], defaults=ed)
            if created:
                self.stdout.write(f'  ✓ Сотрудник: {emp.get_full_name()}')

        # ── 3. SUPPLIERS ─────────────────────────────────────────────────
        self.stdout.write('Создание поставщиков...')
        suppliers_data = [
            dict(name='(DEMO) ТОО «КазДревМатериал»', contact_person='Асет Нурмаганбетов', phone='+7 727 300-11-22', email='info@kazdrev.kz',       address='г. Алматы, ул. Складская, 5'),
            dict(name='(DEMO) ТОО «МетизКомплект»',   contact_person='Руслан Иванченко',    phone='+7 717 220-33-44', email='sales@metiz.kz',        address='г. Нур-Султан, пр. Индустриальный, 12'),
            dict(name='(DEMO) ИП Сатпаев Б.К.',        contact_person='Болат Сатпаев',       phone='+7 701 555-77-88', email='bolat.satpaev@mail.ru', address='г. Шымкент, ул. Базарная, 3'),
        ]
        created_suppliers = []
        for sd in suppliers_data:
            sup, created = Supplier.objects.get_or_create(name=sd['name'], defaults=sd)
            if created:
                self.stdout.write(f'  ✓ Поставщик: {sup.name}')
            created_suppliers.append(sup)

        sup1, sup2, sup3 = created_suppliers

        # ── 4. WAREHOUSES ────────────────────────────────────────────────
        self.stdout.write('Создание складов...')
        wh1, _ = Warehouse.objects.get_or_create(
            code='WH-1',
            defaults=dict(
                name='WH-1 — Склад сырья и материалов',
                warehouse_type=WarehouseType.RAW_MATERIALS,
                address='г. Алматы, ул. Промышленная, 12А',
                description='Основной склад сырья, материалов и комплектующих для производства мебели.',
            )
        )
        wh2, _ = Warehouse.objects.get_or_create(
            code='WH-2',
            defaults=dict(
                name='WH-2 — Склад готовой продукции',
                warehouse_type=WarehouseType.FINISHED_PRODUCTS,
                address='г. Алматы, ул. Промышленная, 12Б',
                description='Склад готовых изделий: шкафы, столы, кровати, кухни, диваны.',
            )
        )
        self.stdout.write(f'  ✓ {wh1.name}')
        self.stdout.write(f'  ✓ {wh2.name}')

        # ── 5. MATERIALS ────────────────────────────────────────────────
        self.stdout.write('Создание материалов...')
        wh_manager_user = created_users.get('wh_manager')

        materials_data = [
            dict(sku='MAT-001', name='(DEMO) ЛДСП 16мм (белый)',         category=MaterialCategory.CHIPBOARD,       unit='лист',  purchase_cost_kzt=Decimal('4500'),   min_stock_level=Decimal('20'), location='A-01', supplier=sup1, stock=Decimal('85')),
            dict(sku='MAT-002', name='(DEMO) ЛДСП 16мм (венге)',         category=MaterialCategory.CHIPBOARD,       unit='лист',  purchase_cost_kzt=Decimal('4800'),   min_stock_level=Decimal('15'), location='A-02', supplier=sup1, stock=Decimal('42')),
            dict(sku='MAT-003', name='(DEMO) МДФ 18мм (фасад)',          category=MaterialCategory.MDF,             unit='лист',  purchase_cost_kzt=Decimal('6200'),   min_stock_level=Decimal('10'), location='B-01', supplier=sup1, stock=Decimal('28')),
            dict(sku='MAT-004', name='(DEMO) Фанера берёзовая 10мм',     category=MaterialCategory.PLYWOOD,         unit='лист',  purchase_cost_kzt=Decimal('3800'),   min_stock_level=Decimal('10'), location='B-02', supplier=sup1, stock=Decimal('5')),
            dict(sku='MAT-005', name='(DEMO) Массив дерева (дуб)',        category=MaterialCategory.WOOD,            unit='м.куб', purchase_cost_kzt=Decimal('180000'), min_stock_level=Decimal('2'),  location='C-01', supplier=sup1, stock=Decimal('1.5')),
            dict(sku='MAT-006', name='(DEMO) Конфирматы 5×50',           category=MaterialCategory.HARDWARE_SCREWS, unit='упак', purchase_cost_kzt=Decimal('850'),    min_stock_level=Decimal('20'), location='D-01', supplier=sup2, stock=Decimal('65')),
            dict(sku='MAT-007', name='(DEMO) Петли Blum 110°',           category=MaterialCategory.HARDWARE_HINGES, unit='шт',    purchase_cost_kzt=Decimal('320'),    min_stock_level=Decimal('50'), location='D-02', supplier=sup2, stock=Decimal('320')),
            dict(sku='MAT-008', name='(DEMO) Ручки мебельные (хром)',    category=MaterialCategory.HARDWARE_HANDLES, unit='шт',   purchase_cost_kzt=Decimal('480'),    min_stock_level=Decimal('30'), location='D-03', supplier=sup2, stock=Decimal('145')),
            dict(sku='MAT-009', name='(DEMO) Направляющие Boyard 450мм', category=MaterialCategory.HARDWARE_RAILS,  unit='пара',  purchase_cost_kzt=Decimal('1200'),   min_stock_level=Decimal('30'), location='D-04', supplier=sup2, stock=Decimal('88')),
            dict(sku='MAT-010', name='(DEMO) Клей ПВА столярный',        category=MaterialCategory.GLUE,            unit='кг',    purchase_cost_kzt=Decimal('1500'),   min_stock_level=Decimal('10'), location='E-01', supplier=sup3, stock=Decimal('22')),
            dict(sku='MAT-011', name='(DEMO) Лак нитроцеллюлозный',      category=MaterialCategory.VARNISH,         unit='л',     purchase_cost_kzt=Decimal('3200'),   min_stock_level=Decimal('5'),  location='E-02', supplier=sup3, stock=Decimal('3')),
            dict(sku='MAT-012', name='(DEMO) Краска акриловая (белая)',   category=MaterialCategory.PAINT,           unit='л',     purchase_cost_kzt=Decimal('2800'),   min_stock_level=Decimal('5'),  location='E-03', supplier=sup3, stock=Decimal('12')),
            dict(sku='MAT-013', name='(DEMO) Велюр мебельный (серый)',    category=MaterialCategory.FABRIC,          unit='м.п.',  purchase_cost_kzt=Decimal('3500'),   min_stock_level=Decimal('20'), location='F-01', supplier=sup3, stock=Decimal('48')),
            dict(sku='MAT-014', name='(DEMO) Поролон ППУ 80мм',          category=MaterialCategory.FOAM,            unit='м.куб', purchase_cost_kzt=Decimal('45000'),  min_stock_level=Decimal('1'),  location='F-02', supplier=sup3, stock=Decimal('0.8')),
            dict(sku='MAT-015', name='(DEMO) Задняя стенка ХДФ 3мм',     category=MaterialCategory.OTHER,           unit='лист',  purchase_cost_kzt=Decimal('900'),    min_stock_level=Decimal('20'), location='A-03', supplier=sup1, stock=Decimal('95')),
        ]

        for md in materials_data:
            stock_qty = md.pop('stock')
            mat, created = Material.objects.get_or_create(sku=md['sku'], defaults=md)
            if not created:
                continue
            self.stdout.write(f'  ✓ {mat.sku} — {mat.name}')
            sb, _ = StockBalance.objects.get_or_create(
                warehouse=wh1, material=mat,
                defaults=dict(current_stock=stock_qty, min_stock_level=mat.min_stock_level)
            )
            if stock_qty > 0:
                StockMovement.objects.create(
                    movement_number=f'MOV-{mat.sku}-001',
                    movement_type=MovementType.RECEIPT,
                    warehouse=wh1,
                    material=mat,
                    quantity=stock_qty,
                    unit=mat.unit,
                    unit_cost_kzt=mat.purchase_cost_kzt,
                    total_cost_kzt=stock_qty * mat.purchase_cost_kzt,
                    reference_number='DEMO-OPENING',
                    notes='(DEMO) Начальный остаток',
                    performed_by=wh_manager_user,
                )

        # ── 6. PRODUCTS ──────────────────────────────────────────────────
        self.stdout.write('Создание продукции...')
        products_data = [
            dict(sku='PRD-001', name='(DEMO) Шкаф-купе «Классик» 3-дверный', category='WARDROBE', sale_price_kzt=Decimal('180000'), production_cost_kzt=Decimal('95000'),  stock=Decimal('4')),
            dict(sku='PRD-002', name='(DEMO) Кухонный гарнитур «Уют» 2.4м',  category='KITCHEN',  sale_price_kzt=Decimal('320000'), production_cost_kzt=Decimal('165000'), stock=Decimal('2')),
            dict(sku='PRD-003', name='(DEMO) Кровать «Скандинавия» 160×200',  category='BED',      sale_price_kzt=Decimal('145000'), production_cost_kzt=Decimal('72000'),  stock=Decimal('3')),
            dict(sku='PRD-004', name='(DEMO) Обеденный стол «Лофт» 120×80',   category='TABLE',    sale_price_kzt=Decimal('95000'),  production_cost_kzt=Decimal('48000'),  stock=Decimal('6')),
            dict(sku='PRD-005', name='(DEMO) Диван угловой «Комфорт» 2.8м',   category='SOFA',     sale_price_kzt=Decimal('260000'), production_cost_kzt=Decimal('138000'), stock=Decimal('1')),
        ]
        created_products = []
        for pd_data in products_data:
            stock_qty = pd_data.pop('stock')
            prod, created = Product.objects.get_or_create(sku=pd_data['sku'], defaults=pd_data)
            if created:
                self.stdout.write(f'  ✓ {prod.sku} — {prod.name}')
                StockBalance.objects.get_or_create(
                    warehouse=wh2, product=prod,
                    defaults=dict(current_stock=stock_qty)
                )
                if stock_qty > 0:
                    StockMovement.objects.create(
                        movement_number=f'MOV-{prod.sku}-001',
                        movement_type=MovementType.RECEIPT,
                        warehouse=wh2,
                        product=prod,
                        quantity=stock_qty,
                        unit='шт',
                        unit_cost_kzt=prod.production_cost_kzt,
                        total_cost_kzt=stock_qty * prod.production_cost_kzt,
                        reference_number='DEMO-OPENING',
                        notes='(DEMO) Начальный остаток',
                        performed_by=wh_manager_user,
                    )
            created_products.append(prod)

        # ── 7. CUSTOMERS ─────────────────────────────────────────────────
        self.stdout.write('Создание клиентов...')
        customers_data = [
            dict(full_name='(DEMO) Алтынбек Жумабеков',  company_name='(DEMO) ТОО «Уют Плюс»', phone='+7 701 100-20-30', email='altynbek@uytplus.kz', city='Алматы'),
            dict(full_name='(DEMO) Марина Волкова',       company_name='',                        phone='+7 702 300-40-50', email='m.volkova@mail.ru',    city='Нур-Султан'),
            dict(full_name='(DEMO) Серик Оспанов',        company_name='(DEMO) ИП Оспанов',       phone='+7 777 500-60-70', email='ospanov.s@gmail.com', city='Шымкент'),
        ]
        created_customers = []
        for cd in customers_data:
            cust, cr = Customer.objects.get_or_create(email=cd['email'], defaults=cd)
            if cr:
                self.stdout.write(f'  ✓ Клиент: {cust.full_name}')
            created_customers.append(cust)

        # ── 8. SALES ORDERS ──────────────────────────────────────────────
        self.stdout.write('Создание заказов...')
        sales_mgr_user = created_users.get('sales_mgr')
        today = timezone.localdate()

        orders_def = [
            dict(order_number='SO-2026-001', customer=created_customers[0], status=OrderStatus.DELIVERED,  offset=160, items=[(created_products[0], 2), (created_products[3], 1)]),
            dict(order_number='SO-2026-002', customer=created_customers[1], status=OrderStatus.DELIVERED,  offset=130, items=[(created_products[2], 1)]),
            dict(order_number='SO-2026-003', customer=created_customers[2], status=OrderStatus.SHIPPED,    offset=90,  items=[(created_products[1], 1)]),
            dict(order_number='SO-2026-004', customer=created_customers[0], status=OrderStatus.CONFIRMED,  offset=45,  items=[(created_products[4], 1), (created_products[3], 2)]),
            dict(order_number='SO-2026-005', customer=created_customers[1], status=OrderStatus.NEW,        offset=5,   items=[(created_products[0], 1)]),
        ]
        for od in orders_def:
            if SalesOrder.objects.filter(order_number=od['order_number']).exists():
                continue
            import datetime as dt
            order_date = timezone.now() - dt.timedelta(days=od['offset'])
            items_data = od['items']
            order = SalesOrder.objects.create(
                order_number=od['order_number'],
                customer=od['customer'],
                status=od['status'],
                created_by=sales_mgr_user,
                notes='(DEMO) Демонстрационный заказ',
                total_amount_kzt=Decimal('0'),
            )
            order.created_at = order_date
            order.save(update_fields=['created_at'])
            total = Decimal('0')
            for prod, qty in items_data:
                item_total = prod.sale_price_kzt * qty
                SalesOrderItem.objects.create(
                    order=order,
                    product=prod,
                    quantity=Decimal(str(qty)),
                    unit_price_kzt=prod.sale_price_kzt,
                    total_price_kzt=item_total,
                )
                total += item_total
            order.total_amount_kzt = total
            order.save(update_fields=['total_amount_kzt'])
            self.stdout.write(f'  ✓ {order.order_number} — {total:,.0f} ₸')

        # ── 9. EXPENSES ──────────────────────────────────────────────────
        self.stdout.write('Создание расходов...')
        accountant_user = created_users.get('accountant')
        today = timezone.localdate()

        # Map ExpenseCategory — using actual choices from model
        try:
            RENT_CAT = ExpenseCategory.RENT
        except AttributeError:
            RENT_CAT = 'RENT'
        try:
            SALARY_CAT = ExpenseCategory.PAYROLL
        except AttributeError:
            SALARY_CAT = 'PAYROLL'
        try:
            UTIL_CAT = ExpenseCategory.ELECTRICITY
        except AttributeError:
            UTIL_CAT = 'ELECTRICITY'
        try:
            MAT_CAT = ExpenseCategory.MATERIALS
        except AttributeError:
            MAT_CAT = 'MATERIALS'

        expenses_data = []
        for i in range(6):
            d = today - datetime.timedelta(days=i * 30)
            expenses_data.append(dict(
                description='(DEMO) Аренда производственного цеха',
                category=RENT_CAT,
                amount_kzt=Decimal('450000'),
                payment_date=d,
                recorded_by=accountant_user,
            ))

        expenses_data += [
            dict(description='(DEMO) ФОТ — октябрь 2026',    category=SALARY_CAT, amount_kzt=Decimal('1830000'), payment_date=today - datetime.timedelta(days=30),  recorded_by=accountant_user),
            dict(description='(DEMO) ФОТ — ноябрь 2026',     category=SALARY_CAT, amount_kzt=Decimal('1830000'), payment_date=today,                                recorded_by=accountant_user),
            dict(description='(DEMO) Электроэнергия сен.',    category=UTIL_CAT,   amount_kzt=Decimal('85000'),   payment_date=today - datetime.timedelta(days=60),  recorded_by=accountant_user),
            dict(description='(DEMO) Электроэнергия окт.',    category=UTIL_CAT,   amount_kzt=Decimal('92000'),   payment_date=today - datetime.timedelta(days=30),  recorded_by=accountant_user),
            dict(description='(DEMO) Закупка ЛДСП',           category=MAT_CAT,    amount_kzt=Decimal('680000'),  payment_date=today - datetime.timedelta(days=20),  recorded_by=accountant_user),
            dict(description='(DEMO) Закупка фурнитуры',      category=MAT_CAT,    amount_kzt=Decimal('320000'),  payment_date=today - datetime.timedelta(days=10),  recorded_by=accountant_user),
        ]

        for ed in expenses_data:
            Expense.objects.create(**ed)
        self.stdout.write(f'  ✓ Создано {len(expenses_data)} записей расходов')

        # ── 10. PRODUCTION ORDERS ─────────────────────────────────────────
        self.stdout.write('Создание производственных заказов...')
        from apps.production.models import ProductionOrder, ProductionOrderStatus, ProductionStage, StageStatus
        prod_manager_user = created_users.get('prod_manager')
        prod_employees = list(Employee.objects.filter(department=Department.PRODUCTION))

        stage_templates = {
            'WARDROBE': ['Раскрой ЛДСП', 'Присадка отверстий', 'Кромление', 'Сборка корпуса', 'Монтаж фурнитуры', 'ОТК'],
            'KITCHEN':  ['Раскрой ЛДСП', 'Фрезеровка фасадов', 'Кромление', 'Сборка корпусов', 'Монтаж петель', 'Финальная сборка', 'ОТК'],
            'BED':      ['Раскрой деталей', 'Шлифовка', 'Сборка каркаса', 'ОТК'],
            'TABLE':    ['Раскрой столешницы', 'Фрезеровка кромки', 'Сборка', 'Лакировка', 'ОТК'],
            'SOFA':     ['Раскрой каркаса', 'Сборка каркаса', 'Настил поролона', 'Обивка', 'ОТК'],
        }

        po_data = [
            dict(order_number='PO-2026-001', product=created_products[0], status=ProductionOrderStatus.COMPLETED,  qty=2, offset=50),
            dict(order_number='PO-2026-002', product=created_products[2], status=ProductionOrderStatus.IN_PROGRESS, qty=1, offset=10),
            dict(order_number='PO-2026-003', product=created_products[1], status=ProductionOrderStatus.PLANNED,     qty=1, offset=5),
            dict(order_number='PO-2026-004', product=created_products[4], status=ProductionOrderStatus.IN_PROGRESS, qty=2, offset=7),
        ]
        for pod in po_data:
            if ProductionOrder.objects.filter(order_number=pod['order_number']).exists():
                continue
            import datetime as dt
            start = today - dt.timedelta(days=pod['offset'])
            po = ProductionOrder.objects.create(
                order_number=pod['order_number'],
                product=pod['product'],
                quantity_planned=Decimal(str(pod['qty'])),
                status=pod['status'],
                planned_start=start,
                planned_end=start + dt.timedelta(days=14),
                created_by=prod_manager_user,
                notes='(DEMO) Демонстрационный заказ',
            )
            cat = pod['product'].category
            stages = stage_templates.get(cat, ['Раскрой', 'Сборка', 'ОТК'])
            for idx, stage_name in enumerate(stages, 1):
                st = StageStatus.DONE if pod['status'] == ProductionOrderStatus.COMPLETED else (
                    StageStatus.DONE if idx < 3 else (StageStatus.IN_PROGRESS if idx == 3 else StageStatus.PENDING)
                )
                emp = prod_employees[idx % len(prod_employees)] if prod_employees else None
                ProductionStage.objects.create(
                    production_order=po,
                    stage_name=stage_name,
                    sequence=idx,
                    status=st,
                    assigned_employee=emp,
                    planned_hours=Decimal('4.0'),
                )
            self.stdout.write(f'  ✓ {po.order_number} — {po.product.name}')

        # ── 11. WAREHOUSE DOCUMENTS & AUDITS ─────────────────────────────
        self.stdout.write('Создание складских документов и актов инвентаризации...')
        from apps.warehouses.models import WarehouseDocument, WarehouseDocumentItem, WarehouseDocumentType, DocumentStatus
        wh_manager_user = created_users.get('wh_manager')
        wh1 = Warehouse.objects.filter(warehouse_type=WarehouseType.RAW_MATERIALS).first()
        wh2 = Warehouse.objects.filter(warehouse_type=WarehouseType.FINISHED_PRODUCTS).first()
        mats = list(Material.objects.all()[:5])
        prods = list(Product.objects.all()[:3])
        sups = list(Supplier.objects.all()[:2])

        if wh1 and wh2 and not WarehouseDocument.objects.exists():
            # Документ 1: Приходная накладная на WH-1 (Проведён)
            doc_rcp = WarehouseDocument.objects.create(
                doc_number='RCP-261101-A1',
                doc_type=WarehouseDocumentType.RECEIPT,
                status=DocumentStatus.POSTED,
                warehouse=wh1,
                doc_date=today - datetime.timedelta(days=5),
                created_by=wh_manager_user,
                posted_by=wh_manager_user,
                posted_at=timezone.now() - datetime.timedelta(days=5),
                supplier=sups[0] if sups else None,
                notes='(DEMO) Поставка массива и плит ЛДСП от основного поставщика',
                total_amount_kzt=Decimal('785000.00'),
            )
            if mats:
                WarehouseDocumentItem.objects.create(
                    document=doc_rcp,
                    material=mats[0],
                    quantity=Decimal('4.000'),
                    unit=mats[0].unit,
                    unit_cost_kzt=mats[0].purchase_cost_kzt,
                    total_cost_kzt=Decimal('4.000') * mats[0].purchase_cost_kzt,
                )
                if len(mats) > 1:
                    WarehouseDocumentItem.objects.create(
                        document=doc_rcp,
                        material=mats[1],
                        quantity=Decimal('20.000'),
                        unit=mats[1].unit,
                        unit_cost_kzt=mats[1].purchase_cost_kzt,
                        total_cost_kzt=Decimal('20.000') * mats[1].purchase_cost_kzt,
                    )

            # Документ 2: Отпуск в цех (Проведён)
            doc_iss = WarehouseDocument.objects.create(
                doc_number='ISS-261102-B2',
                doc_type=WarehouseDocumentType.PRODUCTION_ISSUE,
                status=DocumentStatus.POSTED,
                warehouse=wh1,
                doc_date=today - datetime.timedelta(days=3),
                created_by=wh_manager_user,
                posted_by=wh_manager_user,
                posted_at=timezone.now() - datetime.timedelta(days=3),
                production_order=ProductionOrder.objects.first(),
                notes='(DEMO) Отпуск ЛДСП и конфирматов под заказ шкафа',
                total_amount_kzt=Decimal('185000.00'),
            )
            if mats:
                WarehouseDocumentItem.objects.create(
                    document=doc_iss,
                    material=mats[0],
                    quantity=Decimal('1.500'),
                    unit=mats[0].unit,
                    unit_cost_kzt=mats[0].purchase_cost_kzt,
                    total_cost_kzt=Decimal('1.500') * mats[0].purchase_cost_kzt,
                )

            # Документ 3: Приёмка готовой продукции на WH-2 (Проведён)
            doc_frcp = WarehouseDocument.objects.create(
                doc_number='FRCP-261103-C3',
                doc_type=WarehouseDocumentType.FINISHED_RECEIPT,
                status=DocumentStatus.POSTED,
                warehouse=wh2,
                doc_date=today - datetime.timedelta(days=2),
                created_by=wh_manager_user,
                posted_by=wh_manager_user,
                posted_at=timezone.now() - datetime.timedelta(days=2),
                production_order=ProductionOrder.objects.first(),
                notes='(DEMO) Приёмка после 100% контроля ОТК',
                total_amount_kzt=Decimal('150000.00'),
            )
            if prods:
                WarehouseDocumentItem.objects.create(
                    document=doc_frcp,
                    product=prods[0],
                    quantity=Decimal('2.000'),
                    unit='шт',
                    unit_cost_kzt=prods[0].production_cost_kzt,
                    total_cost_kzt=Decimal('2.000') * prods[0].production_cost_kzt,
                )

            # Документ 4: Акт плановой инвентаризации WH-1 (Черновик для сверки)
            doc_inv = WarehouseDocument.objects.create(
                doc_number='INV-261104-D4',
                doc_type=WarehouseDocumentType.INVENTORY,
                status=DocumentStatus.DRAFT,
                warehouse=wh1,
                doc_date=today,
                created_by=wh_manager_user,
                notes='(DEMO) Сличительная ведомость остатков сырья на WH-1',
                total_amount_kzt=Decimal('0.00'),
            )
            for mat in mats:
                WarehouseDocumentItem.objects.create(
                    document=doc_inv,
                    material=mat,
                    quantity=Decimal('10.000'),
                    actual_quantity=Decimal('10.000'),
                    discrepancy_quantity=Decimal('0.000'),
                    unit=mat.unit,
                    unit_cost_kzt=mat.purchase_cost_kzt,
                )
            self.stdout.write('  ✓ Созданы демонстрационные складские документы и акт инвентаризации')

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Демо-данные успешно созданы!\n'
            '\n📋 Учётные записи (пароль для всех: furnicore123):\n'
            '   owner         — Владелец (суперпользователь)\n'
            '   admin_sys     — Системный администратор\n'
            '   accountant    — Главный бухгалтер\n'
            '   prod_manager  — Начальник производства\n'
            '   wh_manager    — Заведующий складом\n'
            '   sales_mgr     — Менеджер по продажам\n'
            '   worker1       — Мастер цеха\n'
            '   worker2       — Оператор ЧПУ\n'
            '\n⚠  Данные помечены (DEMO) и не отражают реальную деятельность.\n'
            '\n🌐 Откройте браузер: http://127.0.0.1:8000/\n'
        ))
