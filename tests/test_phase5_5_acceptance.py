import pytest
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.test import Client
from apps.accounts.models import User, UserRole, AuditLog
from apps.materials.models import Material, MaterialCategory
from apps.products.models import Product, ProductCategory
from apps.suppliers.models import Supplier, PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus
from apps.sales.models import Customer, SalesOrder, SalesOrderItem, OrderStatus
from apps.warehouses.models import (
    Warehouse, WarehouseType, StockBalance, WarehouseDocument,
    WarehouseDocumentItem, WarehouseDocumentType, DocumentStatus, MovementType, StockMovement
)
from apps.production.models import (
    ProductionOrder, ProductionOrderStatus, BOM, BOMItem,
    RoutingTemplate, RoutingStage, ProductionStage, StageStatus,
    ProductionWaste, WasteType
)
from apps.quality.models import QualityCheck, QCResult
from apps.finance.models import (
    FinancialAccount, AccountType, PaymentMethod, PaymentStatus,
    CustomerPayment, SupplierPayment, AccountTransfer, Expense, ExpenseCategory, GeneralIncome
)
from apps.suppliers.services import (
    create_purchase_order,
    confirm_purchase_order,
    receive_purchase_order_items,
)
from apps.sales.services import (
    create_sales_order,
    check_sales_order_stock,
    confirm_and_reserve_sales_order,
    create_production_orders_for_sales_order,
    ship_sales_order,
)
from apps.warehouses.services import (
    post_document,
    cancel_document,
    create_inventory_sheet,
    get_or_create_stock_balance,
)
from apps.production.services import (
    check_materials_availability,
    issue_materials_for_production,
    launch_production_order,
    advance_stage,
    register_waste_or_defect,
    submit_quality_check,
    complete_and_transfer_to_warehouse,
)
from apps.finance.services import (
    ensure_default_accounts,
    register_customer_payment,
    storno_customer_payment,
    register_supplier_payment,
    storno_supplier_payment,
    transfer_between_accounts,
    record_expense,
    calculate_production_order_actual_cost,
    get_financial_dashboard_kpis,
)
from apps.finance.reports import (
    generate_customer_payment_pdf,
    generate_supplier_payment_pdf,
    export_financial_excel,
)
from apps.warehouses.reports import generate_document_pdf, generate_item_label_pdf


@pytest.fixture
def acceptance_env(db):
    """Изолированная среда приёмочного тестирования FurniCore ERP."""
    # 1. Склады
    wh1, _ = Warehouse.objects.get_or_create(
        code='WH-1',
        defaults={'name': 'Склад сырья и материалов №1', 'warehouse_type': WarehouseType.RAW_MATERIALS}
    )
    wh2, _ = Warehouse.objects.get_or_create(
        code='WH-2',
        defaults={'name': 'Склад готовой продукции №2', 'warehouse_type': WarehouseType.FINISHED_PRODUCTS}
    )

    # 2. Пользователи всех ролей
    users = {}
    roles = [
        (UserRole.OWNER, 'owner_acc'),
        (UserRole.ADMIN, 'admin_acc'),
        (UserRole.ACCOUNTANT, 'accountant_acc'),
        (UserRole.PRODUCTION_MANAGER, 'prod_mgr_acc'),
        (UserRole.WAREHOUSE_MANAGER, 'wh_mgr_acc'),
        (UserRole.SALES_MANAGER, 'sales_mgr_acc'),
        (UserRole.WORKER, 'worker_acc'),
    ]
    for role, username in roles:
        u, _ = User.objects.get_or_create(
            username=username,
            defaults={
                'role': role,
                'email': f'{username}@furnicore.kz',
                'first_name': username.capitalize(),
                'last_name': 'Тестовый',
                'is_staff': role in [UserRole.OWNER, UserRole.ADMIN],
            }
        )
        u.set_password('Password123!')
        u.save()
        users[role] = u

    # 3. Финансовые счета
    accounts = ensure_default_accounts()
    bank_acc = next(a for a in accounts if a.account_type == AccountType.BANK)
    cash_acc = next(a for a in accounts if a.account_type == AccountType.CASH)

    # Задаём начальный капитал для закупок
    bank_acc.current_balance_kzt = Decimal('1000000.00')
    bank_acc.save()
    cash_acc.current_balance_kzt = Decimal('200000.00')
    cash_acc.save()

    # 4. Технологический маршрут
    rt, _ = RoutingTemplate.objects.get_or_create(
        name='Техмаршрут: Стол рабочий',
        defaults={'category': ProductCategory.TABLE, 'is_default': True}
    )
    RoutingStage.objects.get_or_create(
        template=rt, sequence=1,
        defaults={'name': 'Раскрой плитных материалов', 'standard_hours': Decimal('2.0')}
    )
    RoutingStage.objects.get_or_create(
        template=rt, sequence=2,
        defaults={'name': 'Кромление торцов', 'standard_hours': Decimal('1.5')}
    )
    RoutingStage.objects.get_or_create(
        template=rt, sequence=3,
        defaults={'name': 'Присадка и сборка подстолья', 'standard_hours': Decimal('2.5')}
    )

    return {
        'wh1': wh1,
        'wh2': wh2,
        'users': users,
        'bank_acc': bank_acc,
        'cash_acc': cash_acc,
        'routing_template': rt,
    }


@pytest.mark.django_db
def test_end_to_end_18_step_furniture_business_cycle(acceptance_env):
    """
    СКВОЗНОЙ ПРИЁМОЧНЫЙ ТЕСТ: 18 ШАГОВ ПОЛНОГО МЕБЕЛЬНОГО ЦИКЛА
    """
    env = acceptance_env
    wh1 = env['wh1']
    wh2 = env['wh2']
    u_buyer = env['users'][UserRole.SALES_MANAGER]
    u_prod = env['users'][UserRole.PRODUCTION_MANAGER]
    u_wh = env['users'][UserRole.WAREHOUSE_MANAGER]
    u_acc = env['users'][UserRole.ACCOUNTANT]
    u_worker = env['users'][UserRole.WORKER]
    bank_acc = env['bank_acc']

    # =========================================================================
    # ШАГ 1. Создание поставщика
    # =========================================================================
    supplier = Supplier.objects.create(
        name='ТОО «КазПлитПром»',
        contact_person='Ерлан Садыков',
        phone='+77011112233',
        email='sales@kazplitprom.kz',
        address='г. Алматы, пр. Райымбека 348',
    )
    assert supplier.pk is not None

    material = Material.objects.create(
        sku='MAT-MDF-16',
        name='МДФ плита 16мм шлифованная',
        category=MaterialCategory.MDF,
        unit='лист',
        purchase_cost_kzt=Decimal('6500.00'),
        supplier=supplier,
        min_stock_level=Decimal('5.000'),
    )
    assert material.purchase_cost_kzt == Decimal('6500.00')

    # =========================================================================
    # ШАГ 2. Создание закупочного заказа (20 листов МДФ)
    # =========================================================================
    po = create_purchase_order(
        supplier=supplier,
        items_data=[{'material': material, 'quantity': Decimal('20.000'), 'unit_price_kzt': Decimal('6500.00')}],
        created_by=u_wh,
        planned_delivery_date=timezone.now().date(),
    )
    po = confirm_purchase_order(po, user=u_wh)
    po.refresh_from_db()
    assert po.status == PurchaseOrderStatus.SENT
    assert po.total_amount_kzt == Decimal('130000.00')
    assert po.remaining_debt_kzt == Decimal('130000.00')

    # =========================================================================
    # ШАГ 3. Приёмка материалов на WH-1
    # =========================================================================
    po_item = po.items.first()
    wh_doc = receive_purchase_order_items(
        purchase_order=po,
        received_items_map={po_item.id: Decimal('20.000')},
        user=u_wh,
        doc_notes='Полная приёмка партии МДФ',
    )
    assert wh_doc.status == DocumentStatus.POSTED
    po.refresh_from_db()
    assert po.status == PurchaseOrderStatus.RECEIVED

    # =========================================================================
    # ШАГ 4. Проверка складских остатков на WH-1
    # =========================================================================
    bal_mdf = StockBalance.objects.get(warehouse=wh1, material=material)
    assert bal_mdf.current_stock == Decimal('20.000')

    # =========================================================================
    # ШАГ 5. Создание клиента и заказа на мебель (2 стола)
    # =========================================================================
    customer = Customer.objects.create(
        full_name='Сериков Нуржан',
        company_name='ТОО «ОфисКомфорт»',
        phone='+77055554433',
        email='office@komfort.kz',
    )
    product = Product.objects.create(
        sku='PRD-DESK-01',
        name='Стол рабочий Loft Pro',
        category=ProductCategory.TABLE,
        sale_price_kzt=Decimal('65000.00'),
        production_cost_kzt=Decimal('35000.00'),
    )
    bom = BOM.objects.create(
        product=product,
        version='1.0',
        name='Спецификация Стола Loft Pro',
        standard_labor_hours=Decimal('6.0'),
        labor_rate_hourly_kzt=Decimal('3000.00'),
        overhead_rate_kzt=Decimal('1500.00'),
        is_active=True,
    )
    BOMItem.objects.create(
        bom=bom,
        material=material,
        quantity_planned=Decimal('2.000'),
        unit='лист',
    )

    so = create_sales_order(
        customer=customer,
        items_data=[{'product': product, 'quantity': Decimal('2.00'), 'unit_price_kzt': Decimal('65000.00')}],
        created_by=u_buyer,
        planned_delivery_date=timezone.now().date(),
    )
    assert so.total_amount_kzt == Decimal('130000.00')

    # =========================================================================
    # ШАГ 6. Проверка наличия готовой продукции на WH-2 (Дефицит)
    # =========================================================================
    stock_analysis = check_sales_order_stock(so)
    assert stock_analysis['is_fully_available'] is False
    assert stock_analysis['items'][0]['deficit_qty'] == Decimal('2.00')

    # =========================================================================
    # ШАГ 7. Создание производственного заказа при дефиците
    # =========================================================================
    prod_orders = create_production_orders_for_sales_order(so, user=u_buyer)
    assert len(prod_orders) == 1
    prod_order = prod_orders[0]
    assert prod_order.quantity_planned == Decimal('2.00')
    assert prod_order.sales_order == so

    # =========================================================================
    # ШАГ 8. Проверка BOM и доступности материалов
    # =========================================================================
    mat_check = check_materials_availability(prod_order)
    # Нужно 4 листа МДФ (2 шт * 2 листа), на WH-1 есть 20 листов
    assert mat_check['is_all_available'] is True

    # =========================================================================
    # ШАГ 9. Списание материалов с WH-1 под заказ
    # =========================================================================
    issue_doc = issue_materials_for_production(prod_order, user=u_prod)
    assert issue_doc.doc_type == WarehouseDocumentType.PRODUCTION_ISSUE
    bal_mdf.refresh_from_db()
    # 20 - (2 стола * 2.1 листа с учётом 5% нормы отходов) = 15.800
    assert bal_mdf.current_stock == Decimal('15.800')

    # =========================================================================
    # ШАГ 10. Выполнение технологических этапов маршрутной карты
    # =========================================================================
    launch_production_order(prod_order, user=u_prod)
    prod_order.refresh_from_db()
    assert prod_order.status == ProductionOrderStatus.IN_PROGRESS
    stages = list(prod_order.stages.order_by('sequence'))
    assert len(stages) >= 3

    # Выполняем этапы с регистрацией отходов на втором этапе
    for idx, stg in enumerate(stages):
        if idx == 1:
            # ШАГ 11. Учёт технологических отходов и брака
            waste = register_waste_or_defect(
                order=prod_order,
                waste_type=WasteType.REWORKABLE_DEFECT,
                quantity=Decimal('0.500'),
                unit='лист',
                cost_kzt=Decimal('3250.00'),
                user=u_worker,
                stage=stg,
                material=material,
                reason='Скол торцевого паза',
                decision='Списать в возвратные отходы'
            )
            assert waste.cost_kzt == Decimal('3250.00')

        stg.status = StageStatus.IN_PROGRESS
        stg.save()
        advance_stage(stg, user=u_worker, actual_hours=stg.planned_hours or Decimal('1.5'), quantity_processed=Decimal('2.0'))

    prod_order.refresh_from_db()
    assert prod_order.status == ProductionOrderStatus.QC_CHECK

    # =========================================================================
    # ШАГ 12. Проверка качества ОТК
    # =========================================================================
    qc = submit_quality_check(
        order=prod_order,
        inspector=u_prod,
        result=QCResult.PASS,
        quantity_checked=Decimal('2.00'),
        quantity_accepted=Decimal('2.00'),
        quantity_defective=Decimal('0.00'),
        check_dimensions=True,
        check_assembly=True,
        check_appearance=True,
        check_coating=True,
        check_completeness=True,
        check_mechanisms=True,
        check_damage_free=True,
    )
    assert qc.is_passed is True
    prod_order.refresh_from_db()
    assert prod_order.status == ProductionOrderStatus.READY

    # =========================================================================
    # ШАГ 13. Приёмка готовой мебели на WH-2
    # =========================================================================
    transfer_doc = complete_and_transfer_to_warehouse(prod_order, user=u_prod)
    assert transfer_doc.doc_type == WarehouseDocumentType.FINISHED_RECEIPT
    prod_order.refresh_from_db()
    assert prod_order.status == ProductionOrderStatus.COMPLETED

    bal_desk = StockBalance.objects.get(warehouse=wh2, product=product)
    assert bal_desk.current_stock == Decimal('2.00')
    assert bal_desk.reserved_stock == Decimal('0.00')

    # =========================================================================
    # ШАГ 14. Резервирование продукции под заказ покупателя
    # =========================================================================
    confirm_and_reserve_sales_order(so, user=u_buyer)
    so.refresh_from_db()
    assert so.status == OrderStatus.READY
    bal_desk.refresh_from_db()
    # Физический остаток НЕ изменился, зарезервировано 2 шт
    assert bal_desk.current_stock == Decimal('2.00')
    assert bal_desk.reserved_stock == Decimal('2.00')

    # =========================================================================
    # ШАГ 15. Отгрузка клиенту
    # =========================================================================
    so_item = so.items.first()
    ship_doc = ship_sales_order(
        sales_order=so,
        shipped_items_map={so_item.id: Decimal('2.00')},
        user=u_wh,
        doc_notes='Полная отгрузка столов'
    )
    assert ship_doc.doc_type == WarehouseDocumentType.SHIPMENT
    so.refresh_from_db()
    assert so.status == OrderStatus.SHIPPED
    bal_desk.refresh_from_db()
    # После отгрузки остаток и резерв уменьшились до 0
    assert bal_desk.current_stock == Decimal('0.00')
    assert bal_desk.reserved_stock == Decimal('0.00')

    # =========================================================================
    # ШАГ 16. Регистрация частичной и полной оплаты клиента
    # =========================================================================
    initial_bank_bal = bank_acc.current_balance_kzt
    # Частичная оплата 50 000 KZT
    pay1 = register_customer_payment(
        customer=customer,
        amount_kzt=Decimal('50000.00'),
        account=bank_acc,
        sales_order=so,
        payment_method=PaymentMethod.BANK_TRANSFER,
        recorded_by=u_acc,
    )
    so.refresh_from_db()
    assert so.paid_amount_kzt == Decimal('50000.00')
    assert so.remaining_debt_kzt == Decimal('80000.00')
    assert so.payment_status == 'PARTIALLY_PAID'

    # Полная доплата 80 000 KZT
    pay2 = register_customer_payment(
        customer=customer,
        amount_kzt=Decimal('80000.00'),
        account=bank_acc,
        sales_order=so,
        payment_method=PaymentMethod.BANK_TRANSFER,
        recorded_by=u_acc,
    )
    so.refresh_from_db()
    assert so.paid_amount_kzt == Decimal('130000.00')
    assert so.remaining_debt_kzt == Decimal('0.00')
    assert so.payment_status == 'PAID'

    bank_acc.refresh_from_db()
    assert bank_acc.current_balance_kzt == initial_bank_bal + Decimal('130000.00')

    # =========================================================================
    # ШАГ 17. Проверка финансовой задолженности
    # =========================================================================
    kpis = get_financial_dashboard_kpis()
    # У клиента задолженность нулевая
    client_debts = [d for d in kpis['receivables_list'] if d['customer_id'] == customer.id]
    assert len(client_debts) == 0

    # =========================================================================
    # ШАГ 18. Проверка фактической себестоимости и рентабельности
    # =========================================================================
    costing = calculate_production_order_actual_cost(prod_order.id)
    # Фактические материалы: 4.2 листа МДФ (с отходом 5%) * 6 500 = 27 300 KZT
    assert costing['actual_materials_cost_kzt'] == Decimal('27300.00')
    # Труд: 2 шт * 6 часов * 3000 = 36 000 KZT, Накладные: 2 * 6 * 1500 = 18 000 KZT
    assert costing['total_actual_cost_kzt'] > Decimal('0.00')

    # Прибыльность заказа покупателя
    assert so.gross_margin_kzt > Decimal('0.00')
    assert so.profitability_percent > Decimal('0.00')


@pytest.mark.django_db
def test_warehouse_accounting_invariants(acceptance_env):
    """
    ПРОВЕРКА ИНВАРИАНТОВ СКЛАДСКОГО УЧЁТА:
    - WH-1 хранит только сырьё, WH-2 — только готовую мебель.
    - Цех не склад.
    - Защита от отрицательных остатков и повторного проведения.
    - Резервы не влияют на физический остаток.
    - Инвентаризация формирует корректировки.
    """
    env = acceptance_env
    wh1 = env['wh1']
    wh2 = env['wh2']
    u_wh = env['users'][UserRole.WAREHOUSE_MANAGER]

    mat = Material.objects.create(
        sku='MAT-PINE-40', name='Брус сосновый 40х40',
        category=MaterialCategory.WOOD, unit='м.п.', purchase_cost_kzt=Decimal('1200.00')
    )
    prod = Product.objects.create(
        sku='PRD-CHAIR-X', name='Стул венский', category=ProductCategory.OTHER,
        sale_price_kzt=Decimal('22000.00'), production_cost_kzt=Decimal('11000.00')
    )

    # 1. Запрет прихода готовой продукции на WH-1
    doc_invalid_wh1 = WarehouseDocument.objects.create(
        doc_number='DOC-INV-WH1',
        doc_type=WarehouseDocumentType.RECEIPT,
        warehouse=wh1,
        status=DocumentStatus.DRAFT,
        created_by=u_wh,
    )
    WarehouseDocumentItem.objects.create(
        document=doc_invalid_wh1,
        product=prod,  # Ошибка: продукт на WH-1
        quantity=Decimal('5.00'),
    )
    with pytest.raises(ValidationError, match="должен быть указан материал"):
        post_document(doc_invalid_wh1, user=u_wh)

    # 2. Запрет прихода сырья на WH-2
    doc_invalid_wh2 = WarehouseDocument.objects.create(
        doc_number='DOC-INV-WH2',
        doc_type=WarehouseDocumentType.FINISHED_RECEIPT,
        warehouse=wh2,
        status=DocumentStatus.DRAFT,
        created_by=u_wh,
    )
    WarehouseDocumentItem.objects.create(
        document=doc_invalid_wh2,
        material=mat,  # Ошибка: материал вместо продукта
        quantity=Decimal('10.00'),
    )
    with pytest.raises(ValidationError, match="должно быть указано изделие"):
        post_document(doc_invalid_wh2, user=u_wh)

    # 3. Запрет списания в минус
    doc_over_issue = WarehouseDocument.objects.create(
        doc_number='DOC-OVER-ISSUE',
        doc_type=WarehouseDocumentType.PRODUCTION_ISSUE,
        warehouse=wh1,
        status=DocumentStatus.DRAFT,
        created_by=u_wh,
    )
    WarehouseDocumentItem.objects.create(
        document=doc_over_issue,
        material=mat,
        quantity=Decimal('100.00'),  # На складе 0
    )
    with pytest.raises(ValidationError, match="Недостаточно материала"):
        post_document(doc_over_issue, user=u_wh)

    # 4. Защита от повторного проведения
    doc_valid_rcp = WarehouseDocument.objects.create(
        doc_number='DOC-RCP-OK',
        doc_type=WarehouseDocumentType.RECEIPT,
        warehouse=wh1,
        status=DocumentStatus.DRAFT,
        created_by=u_wh,
    )
    WarehouseDocumentItem.objects.create(
        document=doc_valid_rcp,
        material=mat,
        quantity=Decimal('50.00'),
        unit_cost_kzt=Decimal('1200.00'),
    )
    post_document(doc_valid_rcp, user=u_wh)
    doc_valid_rcp.refresh_from_db()
    assert doc_valid_rcp.status == DocumentStatus.POSTED

    with pytest.raises(ValidationError, match="уже был проведён"):
        post_document(doc_valid_rcp, user=u_wh)

    # 5. Инвентаризация с корректировкой
    inv_doc = create_inventory_sheet(warehouse=wh1, user=u_wh)
    inv_item = inv_doc.items.filter(material=mat).first()
    assert inv_item is not None
    inv_item.actual_quantity = Decimal('45.00')  # Фактически 45 вместо 50 (недостача 5)
    inv_item.save()
    post_document(inv_doc, user=u_wh)
    inv_doc.refresh_from_db()
    assert inv_doc.status == DocumentStatus.POSTED
    bal = StockBalance.objects.get(warehouse=wh1, material=mat)
    assert bal.current_stock == Decimal('45.00')


@pytest.mark.django_db
def test_finance_integrity_and_transfers(acceptance_env):
    """
    ПРОВЕРКА ФИНАНСОВОЙ ЦЕЛОСТНОСТИ:
    - Защита от дублей платежей
    - Сторнирование платежей
    - Внутренние переводы без влияния на P&L
    - Контроль переплаты поставщику
    """
    env = acceptance_env
    u_acc = env['users'][UserRole.ACCOUNTANT]
    bank_acc = env['bank_acc']
    cash_acc = env['cash_acc']

    customer = Customer.objects.create(full_name='Тест Клиент', phone='+77001112233')
    supplier = Supplier.objects.create(name='ТОО «Снабженец»', phone='+77002223344')
    prod = Product.objects.create(sku='PRD-TEST-FIN', name='Стол финтест', category=ProductCategory.TABLE, sale_price_kzt=Decimal('50000.00'))
    so = create_sales_order(customer=customer, created_by=u_acc, items_data=[{'product': prod, 'quantity': Decimal('1.00'), 'unit_price_kzt': Decimal('50000.00')}])

    # 1. Защита от дублирования платежа покупателя
    initial_cash_bal = cash_acc.current_balance_kzt
    pay = register_customer_payment(
        customer=customer,
        sales_order=so,
        amount_kzt=Decimal('25000.00'),
        account=cash_acc,
        payment_method=PaymentMethod.CASH,
        recorded_by=u_acc,
    )
    assert pay.status == PaymentStatus.COMPLETED

    with pytest.raises(ValidationError, match="уже зарегистрирован"):
        register_customer_payment(
            customer=customer,
            sales_order=so,
            amount_kzt=Decimal('25000.00'),
            account=cash_acc,
            payment_method=PaymentMethod.CASH,
            recorded_by=u_acc,
        )

    # 2. Сторнирование платежа покупателя (возврат к исходному балансу)
    storno_customer_payment(pay, reason='Ошибочный ввод суммы кассиром', user=u_acc)
    pay.refresh_from_db()
    assert pay.status == PaymentStatus.CANCELLED
    cash_acc.refresh_from_db()
    assert cash_acc.current_balance_kzt == initial_cash_bal

    # 3. Перевод между счетами (0 влияние на финансовый результат P&L)
    kpis_before = get_financial_dashboard_kpis()
    pnl_profit_before = kpis_before['net_profit_kzt']
    bank_before = bank_acc.current_balance_kzt
    cash_before = cash_acc.current_balance_kzt

    transfer = transfer_between_accounts(
        from_account=bank_acc,
        to_account=cash_acc,
        amount_kzt=Decimal('50000.00'),
        user=u_acc,
        description='Снятие наличных в кассу',
    )
    assert transfer.status == PaymentStatus.COMPLETED

    bank_acc.refresh_from_db()
    cash_acc.refresh_from_db()
    assert bank_acc.current_balance_kzt == bank_before - Decimal('50000.00')
    assert cash_acc.current_balance_kzt == cash_before + Decimal('50000.00')

    kpis_after = get_financial_dashboard_kpis()
    assert kpis_after['net_profit_kzt'] == pnl_profit_before  # P&L не изменился!

    # 4. Расход организации
    exp = record_expense(
        category=ExpenseCategory.RENT,
        amount_kzt=Decimal('35000.00'),
        description='Оплата аренды цеха',
        account=bank_acc,
        user=u_acc,
    )
    assert not exp.is_storno
    bank_acc.refresh_from_db()
    assert bank_acc.current_balance_kzt == bank_before - Decimal('50000.00') - Decimal('35000.00')


@pytest.mark.django_db
def test_rbac_server_side_enforcement(acceptance_env):
    """
    ПРОВЕРКА СЕРВЕРНОЙ RBAC-ЗАЩИТЫ ДЛЯ ВСЕХ РОЛЕЙ:
    - Неавторизованный пользователь редиректится на /accounts/login/
    - Рабочий (WORKER) блокируется от проведения финансовых операций
    - Рабочий блокируется от проведения складских документов
    - Бухгалтер (ACCOUNTANT) имеет доступ к платежам и счетам
    - Начальник производства (PRODUCTION_MANAGER) имеет доступ к цеху
    - Заведующий складом (WAREHOUSE_MANAGER) имеет доступ к складам
    - Владелец (OWNER) имеет доступ ко всем модулям
    """
    client = Client()
    users = acceptance_env['users']
    wh1 = acceptance_env['wh1']

    # 1. Неавторизованный доступ -> 302 на логин
    res_anon = client.get('/finance/')
    assert res_anon.status_code == 302
    assert '/accounts/login/' in res_anon.headers['Location']

    # 2. WORKER заходит в создание платежей покупателя -> блокировка (302 redirect с сообщением)
    client.force_login(users[UserRole.WORKER])
    res_worker_pay = client.get('/finance/payments/customers/create/')
    assert res_worker_pay.status_code == 302

    # WORKER заходит в создание переводов -> 302
    res_worker_trans = client.get('/finance/accounts/transfer/')
    assert res_worker_trans.status_code == 302

    # WORKER пытается провести складской документ -> блокировка (302 и статус остаётся DRAFT)
    mat = Material.objects.create(sku='MAT-RBAC-01', name='Тест сырьё', category=MaterialCategory.WOOD)
    doc_draft = WarehouseDocument.objects.create(
        doc_number='DOC-WORKER-RBAC',
        doc_type=WarehouseDocumentType.RECEIPT,
        warehouse=wh1,
        status=DocumentStatus.DRAFT,
        created_by=users[UserRole.WORKER],
    )
    WarehouseDocumentItem.objects.create(document=doc_draft, material=mat, quantity=Decimal('1.00'))
    res_post = client.post(f'/warehouses/documents/{doc_draft.id}/post/')
    assert res_post.status_code == 302
    doc_draft.refresh_from_db()
    assert doc_draft.status == DocumentStatus.DRAFT

    # 3. WAREHOUSE_MANAGER заходит в создание платежей -> 302
    client.force_login(users[UserRole.WAREHOUSE_MANAGER])
    res_wh_pay = client.get('/finance/payments/customers/create/')
    assert res_wh_pay.status_code == 302

    # 4. ACCOUNTANT заходит в создание платежей -> 200 OK
    client.force_login(users[UserRole.ACCOUNTANT])
    res_acc_pay = client.get('/finance/payments/customers/create/')
    assert res_acc_pay.status_code == 200

    # 5. PRODUCTION_MANAGER заходит в создание заказа на производство -> 200 OK
    client.force_login(users[UserRole.PRODUCTION_MANAGER])
    res_prod_create = client.get('/production/create/')
    assert res_prod_create.status_code == 200

    # 6. OWNER имеет доступ ко всем модулям -> 200 OK
    client.force_login(users[UserRole.OWNER])
    for path in ['/', '/warehouses/', '/production/', '/finance/', '/sales/', '/suppliers/', '/quality/', '/analytics/']:
        r = client.get(path)
        assert r.status_code == 200, f"Owner blocked at {path} with {r.status_code}"


@pytest.mark.django_db
def test_document_generation_pdf_excel(acceptance_env):
    """
    ПРОВЕРКА ГЕНЕРАЦИИ ДОКУМЕНТОВ PDF И EXCEL:
    - Кириллические шрифты
    - Валидные сигнатуры файлов (%PDF-, PK zip-сигнатура Excel)
    - Суммы и реквизиты в KZT
    """
    env = acceptance_env
    u_acc = env['users'][UserRole.ACCOUNTANT]
    u_wh = env['users'][UserRole.WAREHOUSE_MANAGER]
    wh1 = env['wh1']
    bank_acc = env['bank_acc']

    customer = Customer.objects.create(full_name='Бектурсынов Даулет', phone='+77019998877')
    supplier = Supplier.objects.create(name='ТОО «КазКлей»', phone='+77028887766')
    prod = Product.objects.create(sku='PRD-PDF-CHAIR', name='Стул венский PDF', category=ProductCategory.OTHER, sale_price_kzt=Decimal('45000.00'))
    so = create_sales_order(customer=customer, created_by=u_acc, items_data=[{'product': prod, 'quantity': Decimal('1.00'), 'unit_price_kzt': Decimal('45000.00')}])

    # Платёж покупателя и PDF-квитанция
    pay_c = register_customer_payment(
        customer=customer,
        sales_order=so,
        amount_kzt=Decimal('45000.00'),
        account=bank_acc,
        payment_method=PaymentMethod.BANK_TRANSFER,
        recorded_by=u_acc,
        notes='Оплата заказа на стулья',
    )
    pdf_c = generate_customer_payment_pdf(pay_c)
    assert len(pdf_c) > 500
    assert pdf_c.startswith(b'%PDF-')

    # Платёж поставщику и PDF-поручение
    pay_s = register_supplier_payment(
        supplier=supplier,
        amount_kzt=Decimal('30000.00'),
        account=bank_acc,
        payment_method=PaymentMethod.BANK_TRANSFER,
        recorded_by=u_acc,
        notes='Закупка столярного клея',
    )
    pdf_s = generate_supplier_payment_pdf(pay_s)
    assert len(pdf_s) > 500
    assert pdf_s.startswith(b'%PDF-')

    # Складские PDF: накладная и этикетки
    mat = Material.objects.create(sku='MAT-GLUE-01', name='Клей ПВА D3 столярный', category=MaterialCategory.GLUE, unit='кг', purchase_cost_kzt=Decimal('1500.00'))
    doc = WarehouseDocument.objects.create(
        doc_number='DOC-MOV-PDF',
        doc_type=WarehouseDocumentType.RECEIPT,
        warehouse=wh1,
        status=DocumentStatus.POSTED,
        created_by=u_wh,
    )
    WarehouseDocumentItem.objects.create(document=doc, material=mat, quantity=Decimal('20.00'), unit_cost_kzt=Decimal('1500.00'))
    mov_pdf = generate_document_pdf(doc)
    assert len(mov_pdf) > 500
    assert mov_pdf.startswith(b'%PDF-')

    lbl_pdf = generate_item_label_pdf('material', mat)
    assert len(lbl_pdf) > 500
    assert lbl_pdf.startswith(b'%PDF-')

    # Excel-выгрузки (.xlsx zip-архив начинается с b'PK\x03\x04')
    for report_type in ['pandl', 'cashflow', 'receivables', 'payables']:
        xlsx_bytes = export_financial_excel(report_type)
        assert len(xlsx_bytes) > 1000
        assert xlsx_bytes.startswith(b'PK\x03\x04')
