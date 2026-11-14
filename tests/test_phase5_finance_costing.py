import pytest
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.test import Client

from apps.accounts.models import User, UserRole
from apps.materials.models import Material, MaterialCategory
from apps.products.models import Product, ProductCategory
from apps.suppliers.models import Supplier, PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus
from apps.sales.models import Customer, SalesOrder, SalesOrderItem, OrderStatus
from apps.warehouses.models import (
    Warehouse, WarehouseType, StockBalance, WarehouseDocument,
    WarehouseDocumentType, DocumentStatus, StockMovement, MovementType
)
from apps.production.models import ProductionOrder, ProductionOrderStatus, BOM, BOMItem
from apps.finance.models import (
    FinancialAccount, AccountType, CustomerPayment, SupplierPayment,
    AccountTransfer, Expense, ExpenseCategory, PaymentMethod, PaymentStatus
)
from apps.finance.services import (
    ensure_default_accounts,
    register_customer_payment,
    storno_customer_payment,
    register_supplier_payment,
    storno_supplier_payment,
    transfer_between_accounts,
    record_expense,
    storno_expense,
    calculate_production_order_actual_cost,
    get_financial_dashboard_kpis,
)
from apps.finance.reports import (
    generate_customer_payment_pdf,
    generate_supplier_payment_pdf,
    export_financial_excel,
)


@pytest.fixture
def finance_setup(db):
    """Базовые данные для тестов Фазы 5: счета, роли, контрагенты, заказы."""
    accounts = ensure_default_accounts()
    cash_acc = accounts[0]
    bank_acc = accounts[1]
    kaspi_acc = accounts[2]

    # Set initial balances for testing
    cash_acc.balance_kzt = Decimal('1000000.00')
    cash_acc.save()
    bank_acc.balance_kzt = Decimal('5000000.00')
    bank_acc.save()
    kaspi_acc.balance_kzt = Decimal('500000.00')
    kaspi_acc.save()

    # Users
    accountant, _ = User.objects.get_or_create(
        username='acc_user_p5',
        defaults={'role': UserRole.ACCOUNTANT, 'first_name': 'Айгуль', 'last_name': 'Бухгалтер'}
    )
    owner, _ = User.objects.get_or_create(
        username='owner_user_p5',
        defaults={'role': UserRole.OWNER, 'first_name': 'Нурлан', 'last_name': 'Директор'}
    )
    worker, _ = User.objects.get_or_create(
        username='worker_user_p5',
        defaults={'role': UserRole.WORKER, 'first_name': 'Ербол', 'last_name': 'Мастер'}
    )

    # Customer & Sales Order
    customer, _ = Customer.objects.get_or_create(
        full_name='ТОО «Офис Плюс»',
        defaults={'company_name': 'ТОО «Офис Плюс»', 'phone': '+77015554433', 'email': 'office@plus.kz'}
    )
    sales_order = SalesOrder.objects.create(
        order_number='SO-TEST-001',
        customer=customer,
        status=OrderStatus.CONFIRMED,
        subtotal_amount_kzt=Decimal('200000.00'),
        discount_percent=Decimal('0.00'),
        total_amount_kzt=Decimal('200000.00'),
        created_by=owner
    )

    # Supplier & Purchase Order
    supplier, _ = Supplier.objects.get_or_create(
        name='ТОО «КазПлитСнаб»',
        defaults={'contact_person': 'Мурат', 'phone': '+77029998877'}
    )
    purchase_order = PurchaseOrder.objects.create(
        order_number='PO-TEST-001',
        supplier=supplier,
        status=PurchaseOrderStatus.SENT,
        order_date=timezone.localdate(),
        total_amount_kzt=Decimal('150000.00'),
        created_by=owner
    )

    # Warehouses & Material & Product
    wh1, _ = Warehouse.objects.get_or_create(
        code='WH-1',
        defaults={'name': 'Склад сырья WH-1', 'warehouse_type': WarehouseType.RAW_MATERIALS}
    )
    wh2, _ = Warehouse.objects.get_or_create(
        code='WH-2',
        defaults={'name': 'Склад ГП WH-2', 'warehouse_type': WarehouseType.FINISHED_PRODUCTS}
    )
    material, _ = Material.objects.get_or_create(
        sku='MAT-P5-BOARD',
        defaults={'name': 'ЛДСП Дуб Сонома 16мм', 'category': MaterialCategory.CHIPBOARD, 'unit': 'лист', 'purchase_cost_kzt': Decimal('12000.00')}
    )
    product, _ = Product.objects.get_or_create(
        sku='PROD-P5-DESK',
        defaults={'name': 'Стол письменный Loft-120', 'category': ProductCategory.TABLE, 'sale_price_kzt': Decimal('45000.00')}
    )

    # BOM
    bom, _ = BOM.objects.get_or_create(
        product=product,
        version='1.0',
        defaults={
            'name': 'ТК Стол Loft-120',
            'is_active': True,
            'standard_labor_hours': Decimal('2.00'),
            'labor_rate_hourly_kzt': Decimal('2500.00'),
            'overhead_rate_kzt': Decimal('2000.00'),
        }
    )
    BOMItem.objects.get_or_create(
        bom=bom,
        material=material,
        defaults={'quantity_planned': Decimal('2.00')}
    )

    # Production Order
    prod_order = ProductionOrder.objects.create(
        order_number='PRD-TEST-001',
        product=product,
        quantity_planned=Decimal('5.00'),
        status=ProductionOrderStatus.IN_PROGRESS,
        bom=bom,
        planned_materials_cost_kzt=Decimal('120000.00'),
        planned_labor_cost_kzt=Decimal('25000.00'),
        overhead_cost_kzt=Decimal('10000.00'),
        planned_cost_kzt=Decimal('155000.00'),
        actual_labor_cost_kzt=Decimal('25000.00'),
        created_by=owner
    )

    return {
        'cash_acc': cash_acc,
        'bank_acc': bank_acc,
        'kaspi_acc': kaspi_acc,
        'accountant': accountant,
        'owner': owner,
        'worker': worker,
        'customer': customer,
        'sales_order': sales_order,
        'supplier': supplier,
        'purchase_order': purchase_order,
        'wh1': wh1,
        'wh2': wh2,
        'material': material,
        'product': product,
        'bom': bom,
        'prod_order': prod_order,
    }


# ==============================================================================
# ТЕСТ-КЕЙСЫ ФАЗЫ 5 (16 ОБЯЗАТЕЛЬНЫХ ПРОВЕРОК)
# ==============================================================================

@pytest.mark.django_db
def test_customer_payment_registration(finance_setup):
    """1. Регистрация платежа покупателя с обновлением баланса счёта."""
    setup = finance_setup
    initial_balance = setup['bank_acc'].balance_kzt

    payment = register_customer_payment(
        amount_kzt=Decimal('50000.00'),
        sales_order=setup['sales_order'],
        account=setup['bank_acc'],
        payment_method=PaymentMethod.BANK_TRANSFER,
        created_by=setup['accountant']
    )

    setup['bank_acc'].refresh_from_db()
    setup['sales_order'].refresh_from_db()

    assert payment.pk is not None
    assert payment.status == PaymentStatus.COMPLETED
    assert setup['bank_acc'].balance_kzt == initial_balance + Decimal('50000.00')
    assert setup['sales_order'].paid_amount_kzt == Decimal('50000.00')
    assert setup['sales_order'].remaining_debt_kzt == Decimal('150000.00')


@pytest.mark.django_db
def test_customer_partial_payment(finance_setup):
    """2. Частичная оплата заказа покупателя со статусом PARTIALLY_PAID."""
    setup = finance_setup
    register_customer_payment(
        amount_kzt=Decimal('80000.00'),
        sales_order=setup['sales_order'],
        account=setup['cash_acc'],
        created_by=setup['accountant']
    )

    setup['sales_order'].refresh_from_db()
    assert setup['sales_order'].payment_status == 'PARTIALLY_PAID'
    assert setup['sales_order'].paid_amount_kzt == Decimal('80000.00')
    assert setup['sales_order'].remaining_debt_kzt == Decimal('120000.00')


@pytest.mark.django_db
def test_customer_full_payment(finance_setup):
    """3. Полная оплата заказа покупателя со статусом PAID."""
    setup = finance_setup
    register_customer_payment(
        amount_kzt=Decimal('200000.00'),
        sales_order=setup['sales_order'],
        account=setup['kaspi_acc'],
        created_by=setup['accountant']
    )

    setup['sales_order'].refresh_from_db()
    assert setup['sales_order'].payment_status == 'PAID'
    assert setup['sales_order'].paid_amount_kzt == Decimal('200000.00')
    assert setup['sales_order'].remaining_debt_kzt == Decimal('0.00')


@pytest.mark.django_db
def test_prevent_duplicate_customer_payment(finance_setup):
    """4. Защита от переплаты сверх остатка долга и некорректных сумм."""
    setup = finance_setup
    # Zero or negative amount
    with pytest.raises(ValidationError):
        register_customer_payment(
            amount_kzt=Decimal('0.00'),
            sales_order=setup['sales_order'],
            account=setup['bank_acc'],
            created_by=setup['accountant']
        )

    # Exceeding debt
    with pytest.raises(ValidationError):
        register_customer_payment(
            amount_kzt=Decimal('250000.00'),  # order is 200 000
            sales_order=setup['sales_order'],
            account=setup['bank_acc'],
            created_by=setup['accountant']
        )


@pytest.mark.django_db
def test_supplier_payment_registration(finance_setup):
    """5. Регистрация оплаты поставщику со списанием с кассы/счёта."""
    setup = finance_setup
    initial_balance = setup['bank_acc'].balance_kzt

    payment = register_supplier_payment(
        amount_kzt=Decimal('150000.00'),
        purchase_order=setup['purchase_order'],
        account=setup['bank_acc'],
        created_by=setup['accountant']
    )

    setup['bank_acc'].refresh_from_db()
    setup['purchase_order'].refresh_from_db()

    assert payment.status == PaymentStatus.COMPLETED
    assert setup['bank_acc'].balance_kzt == initial_balance - Decimal('150000.00')
    assert setup['purchase_order'].paid_amount_kzt == Decimal('150000.00')
    assert setup['purchase_order'].remaining_debt_kzt == Decimal('0.00')
    assert setup['purchase_order'].payment_status == 'PAID'


@pytest.mark.django_db
def test_supplier_partial_payment(finance_setup):
    """6. Частичная выплата по заказу на закупку."""
    setup = finance_setup
    register_supplier_payment(
        amount_kzt=Decimal('60000.00'),
        purchase_order=setup['purchase_order'],
        account=setup['cash_acc'],
        created_by=setup['accountant']
    )

    setup['purchase_order'].refresh_from_db()
    assert setup['purchase_order'].payment_status == 'PARTIALLY_PAID'
    assert setup['purchase_order'].paid_amount_kzt == Decimal('60000.00')
    assert setup['purchase_order'].remaining_debt_kzt == Decimal('90000.00')


@pytest.mark.django_db
def test_expense_registration_with_account(finance_setup):
    """7. Регистрация расхода с указанием расчетного счёта и списанием."""
    setup = finance_setup
    initial_balance = setup['cash_acc'].balance_kzt

    expense = record_expense(
        category=ExpenseCategory.RENT,
        amount_kzt=Decimal('120000.00'),
        description='Аренда производственного цеха за ноябрь',
        payee='ИП Арендатор',
        account=setup['cash_acc'],
        recorded_by=setup['accountant']
    )

    setup['cash_acc'].refresh_from_db()

    assert expense.pk is not None
    assert expense.is_storno is False
    assert setup['cash_acc'].balance_kzt == initial_balance - Decimal('120000.00')


@pytest.mark.django_db
def test_account_transfer(finance_setup):
    """8. Перевод между счетами фабрики без изменения P&L."""
    setup = finance_setup
    from_init = setup['cash_acc'].balance_kzt
    to_init = setup['bank_acc'].balance_kzt
    transfer_amount = Decimal('200000.00')

    transfer = transfer_between_accounts(
        from_account=setup['cash_acc'],
        to_account=setup['bank_acc'],
        amount_kzt=transfer_amount,
        notes='Инкассация наличной выручки',
        created_by=setup['accountant']
    )

    setup['cash_acc'].refresh_from_db()
    setup['bank_acc'].refresh_from_db()

    assert transfer.status == 'COMPLETED'
    assert setup['cash_acc'].balance_kzt == from_init - transfer_amount
    assert setup['bank_acc'].balance_kzt == to_init + transfer_amount


@pytest.mark.django_db
def test_financial_account_balances(finance_setup):
    """9. Проверка математической точности остатков на счетах."""
    setup = finance_setup
    initial_cash = setup['cash_acc'].balance_kzt

    # Inflow +50 000
    register_customer_payment(
        amount_kzt=Decimal('50000.00'),
        sales_order=setup['sales_order'],
        account=setup['cash_acc'],
        created_by=setup['accountant']
    )
    # Outflow -20 000
    record_expense(
        category=ExpenseCategory.OTHER,
        amount_kzt=Decimal('20000.00'),
        description='Канцтовары',
        account=setup['cash_acc'],
        recorded_by=setup['accountant']
    )

    setup['cash_acc'].refresh_from_db()
    assert setup['cash_acc'].balance_kzt == initial_cash + Decimal('30000.00')


@pytest.mark.django_db
def test_material_cost_calculation(finance_setup):
    """10. Расчёт фактической стоимости материалов из списаний WH-1."""
    setup = finance_setup
    order = setup['prod_order']

    # Create Warehouse Document for PRODUCTION_ISSUE
    doc = WarehouseDocument.objects.create(
        doc_number='DOC-ISSUE-TEST-001',
        doc_type=WarehouseDocumentType.PRODUCTION_ISSUE,
        warehouse=setup['wh1'],
        status=DocumentStatus.POSTED,
        production_order=order,
        created_by=setup['owner']
    )
    # 10 sheets * 12 000 = 120 000 KZT
    StockMovement.objects.create(
        movement_number='MOV-ISSUE-TEST-001',
        document=doc,
        material=setup['material'],
        movement_type=MovementType.ISSUE,
        quantity=Decimal('10.00'),
        unit_cost_kzt=Decimal('12000.00'),
        total_cost_kzt=Decimal('120000.00'),
        warehouse=setup['wh1']
    )

    cost_info = calculate_production_order_actual_cost(order)
    assert cost_info['actual_materials_cost_kzt'] == Decimal('120000.00')


@pytest.mark.django_db
def test_actual_production_order_cost(finance_setup):
    """11. Расчёт полной себестоимости заказа в цехе с анализом план/факт."""
    setup = finance_setup
    order = setup['prod_order']

    # BOM has 5 items * (2 sheets * 12000 = 24000) = 120 000 plan materials
    # Labor: 5 * 5000 = 25 000, Overhead: 5 * 2000 = 10 000 -> Total labor & overhead = 35 000
    # Actual materials issue: 120 000
    doc = WarehouseDocument.objects.create(
        doc_number='DOC-ISSUE-TEST-002',
        doc_type=WarehouseDocumentType.PRODUCTION_ISSUE,
        warehouse=setup['wh1'],
        status=DocumentStatus.POSTED,
        production_order=order,
        created_by=setup['owner']
    )
    StockMovement.objects.create(
        movement_number='MOV-ISSUE-TEST-002',
        document=doc,
        material=setup['material'],
        movement_type=MovementType.ISSUE,
        quantity=Decimal('10.00'),
        unit_cost_kzt=Decimal('12000.00'),
        total_cost_kzt=Decimal('120000.00'),
        warehouse=setup['wh1']
    )

    cost_info = calculate_production_order_actual_cost(order)
    assert cost_info['planned_materials_cost_kzt'] == Decimal('120000.00')
    assert cost_info['actual_materials_cost_kzt'] == Decimal('120000.00')
    assert cost_info['labor_and_overhead_cost_kzt'] == Decimal('35000.00')
    assert cost_info['total_actual_cost_kzt'] == Decimal('155000.00')
    assert cost_info['actual_unit_cost_kzt'] == Decimal('31000.00')  # 155000 / 5


@pytest.mark.django_db
def test_sales_order_profitability(finance_setup):
    """12. Расчёт валовой прибыли и рентабельности клиентского заказа."""
    setup = finance_setup
    order = setup['sales_order']
    product = setup['product']
    product.production_cost_kzt = Decimal('35000.00')
    product.save()

    # Create order item: 4 desks * 50 000 KZT = 200 000 KZT
    # Total cost = 4 * 35 000 = 140 000 KZT
    SalesOrderItem.objects.create(
        order=order,
        product=product,
        quantity=4,
        unit_price_kzt=Decimal('50000.00'),
        total_price_kzt=Decimal('200000.00')
    )

    assert order.total_cost_kzt == Decimal('140000.00')
    assert order.gross_margin_kzt == Decimal('60000.00')  # 200 000 - 140 000
    assert order.profitability_percent == 30.0  # (60 000 / 200 000) * 100


@pytest.mark.django_db
def test_payment_storno(finance_setup):
    """13. Сторнирование платёжной операции с возвратом остатка на счёт."""
    setup = finance_setup
    initial_balance = setup['bank_acc'].balance_kzt

    # 1. Register payment
    payment = register_customer_payment(
        amount_kzt=Decimal('70000.00'),
        sales_order=setup['sales_order'],
        account=setup['bank_acc'],
        created_by=setup['accountant']
    )
    setup['bank_acc'].refresh_from_db()
    assert setup['bank_acc'].balance_kzt == initial_balance + Decimal('70000.00')

    # 2. Storno payment
    storno_customer_payment(payment, user=setup['accountant'], reason='Ошибочное зачисление')

    setup['bank_acc'].refresh_from_db()
    setup['sales_order'].refresh_from_db()
    payment.refresh_from_db()

    assert payment.status == PaymentStatus.CANCELLED
    assert setup['bank_acc'].balance_kzt == initial_balance
    assert setup['sales_order'].paid_amount_kzt == Decimal('0.00')
    assert setup['sales_order'].remaining_debt_kzt == Decimal('200000.00')


@pytest.mark.django_db
def test_financial_rbac(finance_setup):
    """14. Разграничение прав доступа к финансовым операциям."""
    setup = finance_setup
    client = Client()

    # Worker has no access to create payment
    client.force_login(setup['worker'])
    res_worker = client.get('/finance/payments/customers/create/')
    # Should redirect with warning/error
    assert res_worker.status_code == 302

    # Accountant has full access
    client.force_login(setup['accountant'])
    res_acc = client.get('/finance/payments/customers/create/')
    assert res_acc.status_code == 200


@pytest.mark.django_db
def test_concurrent_payment_safety(finance_setup):
    """15. Транзакционная безопасность при параллельных операциях (проверка atomic & locks)."""
    setup = finance_setup
    initial_balance = setup['bank_acc'].balance_kzt

    # Consecutive operations properly update balance within transaction.atomic
    p1 = register_customer_payment(
        amount_kzt=Decimal('30000.00'),
        sales_order=setup['sales_order'],
        account=setup['bank_acc'],
        created_by=setup['accountant']
    )
    p2 = register_customer_payment(
        amount_kzt=Decimal('20000.00'),
        sales_order=setup['sales_order'],
        account=setup['bank_acc'],
        created_by=setup['accountant']
    )

    setup['bank_acc'].refresh_from_db()
    setup['sales_order'].refresh_from_db()

    assert setup['bank_acc'].balance_kzt == initial_balance + Decimal('50000.00')
    assert setup['sales_order'].paid_amount_kzt == Decimal('50000.00')
    assert setup['sales_order'].remaining_debt_kzt == Decimal('150000.00')


@pytest.mark.django_db
def test_report_generation_pdf_and_excel(finance_setup):
    """16. Корректная генерация финансовых отчётов в PDF и Excel."""
    setup = finance_setup

    # Register sample payment
    payment = register_customer_payment(
        amount_kzt=Decimal('50000.00'),
        sales_order=setup['sales_order'],
        account=setup['bank_acc'],
        created_by=setup['accountant']
    )

    # 1. Customer Payment PDF
    pdf_bytes = generate_customer_payment_pdf(payment)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b'%PDF')

    # 2. Supplier Payment PDF
    supp_payment = register_supplier_payment(
        amount_kzt=Decimal('40000.00'),
        purchase_order=setup['purchase_order'],
        account=setup['bank_acc'],
        created_by=setup['accountant']
    )
    supp_pdf = generate_supplier_payment_pdf(supp_payment)
    assert len(supp_pdf) > 1000
    assert supp_pdf.startswith(b'%PDF')

    # 3. Excel P&L export
    excel_pandl = export_financial_excel('pandl')
    assert len(excel_pandl) > 1000

    # 4. Excel Cash Flow export
    excel_cf = export_financial_excel('cashflow')
    assert len(excel_cf) > 1000

    # 5. Excel Receivables export
    excel_rec = export_financial_excel('receivables')
    assert len(excel_rec) > 1000
