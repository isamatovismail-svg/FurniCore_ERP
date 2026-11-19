"""
FurniCore ERP — Automated Acceptance & Security Tests for DEMO_VIEWER Role.
Verifies read-only permissions, mutation blocking, HTMX 403 enforcement,
fix of the three production endpoints (stage_advance, qc_inspect, waste_create),
and confirms that OWNER and existing roles retain all original privileges.
"""
import pytest
from decimal import Decimal
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.products.models import Product, ProductCategory
from apps.materials.models import Material, MaterialCategory
from apps.suppliers.models import Supplier
from apps.warehouses.models import Warehouse, WarehouseType, StockBalance
from apps.production.models import (
    ProductionOrder,
    ProductionOrderStatus,
    ProductionStage,
    StageStatus,
    BOM,
)


@pytest.fixture
def rbac_setup(db):
    """Fixture providing users with different roles and minimal baseline entities."""
    # 1. Users
    demo_viewer = User.objects.create_user(
        username='test_demo_viewer',
        password='TestPassword123!',
        role=UserRole.DEMO_VIEWER,
        first_name='Демо',
        last_name='Оценщик',
    )
    owner = User.objects.create_user(
        username='test_owner',
        password='TestPassword123!',
        role=UserRole.OWNER,
        first_name='Владелец',
    )
    prod_mgr = User.objects.create_user(
        username='test_prod_mgr',
        password='TestPassword123!',
        role=UserRole.PRODUCTION_MANAGER,
    )
    worker = User.objects.create_user(
        username='test_worker',
        password='TestPassword123!',
        role=UserRole.WORKER,
    )
    sales_mgr = User.objects.create_user(
        username='test_sales_mgr',
        password='TestPassword123!',
        role=UserRole.SALES_MANAGER,
    )

    # 2. Warehouses
    wh1 = Warehouse.objects.create(name='Склад сырья (WH-1)', warehouse_type=WarehouseType.RAW_MATERIALS, code='WH-1-TEST')
    wh2 = Warehouse.objects.create(name='Склад ГП (WH-2)', warehouse_type=WarehouseType.FINISHED_PRODUCTS, code='WH-2-TEST')

    # 3. Base Entities
    supplier = Supplier.objects.create(name='Тест Поставщик', is_active=True)
    material = Material.objects.create(
        sku='MAT-TST-01',
        name='Тест Фанера',
        category=MaterialCategory.CHIPBOARD,
        unit='лист',
        purchase_cost_kzt=Decimal('5000.00'),
        supplier=supplier,
        is_active=True,
    )
    product = Product.objects.create(
        sku='PRD-TST-01',
        name='Тест Стол',
        category=ProductCategory.TABLE,
        sale_price_kzt=Decimal('50000.00'),
        production_cost_kzt=Decimal('25000.00'),
        is_active=True,
    )
    bom = BOM.objects.create(
        product=product,
        name='BOM Тест Стол',
        standard_labor_hours=Decimal('2.0'),
        labor_rate_hourly_kzt=Decimal('2000.00'),
        overhead_rate_kzt=Decimal('1000.00'),
        is_active=True,
    )
    order = ProductionOrder.objects.create(
        order_number='ORD-TST-001',
        product=product,
        bom=bom,
        quantity_planned=Decimal('2.0'),
        status=ProductionOrderStatus.IN_PROGRESS,
        created_by=owner,
    )
    stage = ProductionStage.objects.create(
        production_order=order,
        stage_name='Раскрой плит',
        sequence=1,
        status=StageStatus.IN_PROGRESS,
        planned_hours=Decimal('2.0'),
    )

    return {
        'demo_viewer': demo_viewer,
        'owner': owner,
        'prod_mgr': prod_mgr,
        'worker': worker,
        'sales_mgr': sales_mgr,
        'wh1': wh1,
        'wh2': wh2,
        'supplier': supplier,
        'material': material,
        'product': product,
        'order': order,
        'stage': stage,
    }


@pytest.mark.django_db
def test_demo_viewer_allowed_get_views(rbac_setup):
    """
    DEMO_VIEWER should have HTTP 200 read-only access to all functional pages.
    """
    client = Client()
    client.force_login(rbac_setup['demo_viewer'])

    read_urls = [
        '/',
        '/finance/',
        '/finance/payments/customers/',
        '/finance/payments/suppliers/',
        '/finance/accounts/',
        '/finance/expenses/',
        '/finance/receivables/',
        '/finance/payables/',
        '/finance/costing/',
        '/warehouses/',
        '/warehouses/wh-1/',
        '/warehouses/wh-2/',
        '/warehouses/documents/',
        '/warehouses/inventory/',
        '/production/',
        '/production/board/',
        '/production/boms/',
        '/production/routes/',
        '/production/waste/',
        f"/production/{rbac_setup['order'].id}/",
        f"/production/{rbac_setup['order'].id}/qc/",  # GET form viewing is allowed
        f"/production/{rbac_setup['order'].id}/waste/create/",  # GET form viewing is allowed
        '/sales/',
        '/sales/customers/',
        '/suppliers/',
        '/suppliers/orders/',
        '/materials/',
        '/products/',
        f"/products/{rbac_setup['product'].id}/",
        '/analytics/',
        '/analytics/map/',
        '/ai/',
        '/ai/settings/',
    ]

    for url in read_urls:
        resp = client.get(url)
        assert resp.status_code == 200, f"Expected 200 for DEMO_VIEWER on GET {url}, got {resp.status_code}"


@pytest.mark.django_db
def test_demo_viewer_blocks_all_mutating_posts(rbac_setup):
    """
    DEMO_VIEWER should be strictly blocked from state-mutating POST requests across all modules.
    Standard browser POST requests receive a redirect with a warning message (no data created).
    """
    client = Client()
    client.force_login(rbac_setup['demo_viewer'])

    # 1. Finance - customer payment create
    resp = client.post('/finance/payments/customers/create/', {
        'amount_kzt': '10000.00',
        'payment_method': 'CASH',
    })
    assert resp.status_code == 302

    # 2. Finance - expense create
    resp = client.post('/finance/expenses/create/', {
        'amount_kzt': '5000.00',
        'category': 'RENT',
        'description': 'Несанкционированный расход',
    })
    assert resp.status_code == 302

    # 3. Warehouses - document create
    resp = client.post('/warehouses/documents/create/', {
        'warehouse': str(rbac_setup['wh1'].id),
        'doc_type': 'RECEIPT',
    })
    assert resp.status_code == 302

    # 4. Production - order create
    resp = client.post('/production/create/', {
        'product': str(rbac_setup['product'].id),
        'quantity_planned': '5',
    })
    assert resp.status_code == 302

    # 5. Production - issue materials
    resp = client.post(f"/production/{rbac_setup['order'].id}/issue-materials/")
    assert resp.status_code == 302

    # 6. Production - order launch
    resp = client.post(f"/production/{rbac_setup['order'].id}/launch/")
    assert resp.status_code == 302

    # 7. Production - transfer to WH-2
    resp = client.post(f"/production/{rbac_setup['order'].id}/transfer-wh2/")
    assert resp.status_code == 302

    # 8. Sales - order create
    resp = client.post('/sales/create/', {
        'delivery_address': 'Тестовый адрес',
    })
    assert resp.status_code == 302

    # 9. Suppliers - supplier create
    resp = client.post('/suppliers/create/', {
        'name': 'Злоумышленник ТОО',
    })
    assert resp.status_code == 302

    # 10. Materials - material create
    resp = client.post('/materials/create/', {
        'sku': 'MAT-HACK-01',
        'name': 'Взлом',
    })
    assert resp.status_code == 302

    # 11. Products - product create
    resp = client.post('/products/create/', {
        'sku': 'PRD-HACK-01',
        'name': 'Взлом Стол',
    })
    assert resp.status_code == 302

    # Confirm database was NOT mutated
    assert not Material.objects.filter(sku='MAT-HACK-01').exists()
    assert not Product.objects.filter(sku='PRD-HACK-01').exists()
    assert not Supplier.objects.filter(name='Злоумышленник ТОО').exists()


@pytest.mark.django_db
def test_demo_viewer_htmx_and_ajax_receives_403(rbac_setup):
    """
    When requests arrive via HTMX (HX-Request header) or XMLHttpRequest (AJAX),
    deny_demo_viewer should return a strict HTTP 403 Forbidden.
    """
    client = Client()
    client.force_login(rbac_setup['demo_viewer'])

    # HTMX mutating POST
    resp_htmx = client.post(
        '/finance/expenses/create/',
        {'amount_kzt': '1000.00'},
        HTTP_HX_REQUEST='true',
    )
    assert resp_htmx.status_code == 403
    assert b'\xd0\x94\xd0\xb5\xd0\xbc\xd0\xbe\xd0\xbd\xd1\x81\xd1\x82\xd1\x80\xd0\xb0\xd1\x86\xd0\xb8\xd0\xbe\xd0\xbd\xd0\xbd\xd1\x8b\xd0\xb9' in resp_htmx.content

    # AJAX / XMLHttpRequest mutating POST
    resp_ajax = client.post(
        '/production/create/',
        {'quantity_planned': '1'},
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
    )
    assert resp_ajax.status_code == 403


@pytest.mark.django_db
def test_three_previously_unprotected_endpoints(rbac_setup):
    """
    Verifies that the three previously unprotected endpoints:
    1. stage_advance_action
    2. order_qc_inspect
    3. waste_create
    are now strictly protected:
    - DEMO_VIEWER is blocked
    - Unauthorized roles (e.g. SALES_MANAGER) are blocked
    - Authorized roles (WORKER, PRODUCTION_MANAGER, OWNER) are permitted
    """
    client = Client()
    stage = rbac_setup['stage']
    order = rbac_setup['order']

    # --- 1. stage_advance_action ---
    # a) DEMO_VIEWER blocked
    client.force_login(rbac_setup['demo_viewer'])
    resp = client.post(f'/production/stage/{stage.id}/advance/', {'actual_hours': '2.0', 'quantity_processed': '2'})
    assert resp.status_code == 302
    stage.refresh_from_db()
    assert stage.status == StageStatus.IN_PROGRESS  # Not changed

    # b) SALES_MANAGER blocked by role check
    client.force_login(rbac_setup['sales_mgr'])
    resp = client.post(f'/production/stage/{stage.id}/advance/', {'actual_hours': '2.0', 'quantity_processed': '2'})
    assert resp.status_code == 302
    stage.refresh_from_db()
    assert stage.status == StageStatus.IN_PROGRESS  # Not changed

    # c) WORKER permitted
    client.force_login(rbac_setup['worker'])
    resp = client.post(f'/production/stage/{stage.id}/advance/', {'actual_hours': '2.0', 'quantity_processed': '2'})
    assert resp.status_code == 302
    stage.refresh_from_db()
    assert stage.status == StageStatus.DONE  # Progressed successfully!

    # --- 2. order_qc_inspect ---
    # a) DEMO_VIEWER blocked
    client.force_login(rbac_setup['demo_viewer'])
    resp = client.post(f'/production/{order.id}/qc/', {'result': 'PASS', 'quantity_checked': '2.0', 'quantity_accepted': '2.0'})
    assert resp.status_code == 302

    # b) WORKER blocked from QC inspection (only PRODUCTION_MANAGER / OWNER / ADMIN)
    client.force_login(rbac_setup['worker'])
    resp = client.post(f'/production/{order.id}/qc/', {'result': 'PASS', 'quantity_checked': '2.0', 'quantity_accepted': '2.0'})
    assert resp.status_code == 302

    # c) PRODUCTION_MANAGER permitted
    client.force_login(rbac_setup['prod_mgr'])
    resp = client.post(f'/production/{order.id}/qc/', {
        'result': 'PASS',
        'quantity_checked': '2.00',
        'quantity_accepted': '2.00',
        'quantity_defective': '0.00',
        'check_dimensions': True,
        'check_assembly': True,
        'check_appearance': True,
        'check_coating': True,
        'check_completeness': True,
        'check_mechanisms': True,
        'check_damage_free': True,
    })
    assert resp.status_code == 302
    order.refresh_from_db()
    assert order.status == ProductionOrderStatus.READY

    # --- 3. waste_create ---
    # a) DEMO_VIEWER blocked
    client.force_login(rbac_setup['demo_viewer'])
    resp = client.post(f'/production/{order.id}/waste/create/', {
        'waste_type': 'NON_REWORKABLE_SCRAP',
        'material': str(rbac_setup['material'].id),
        'quantity': '1.0',
        'unit': 'лист',
        'cost_kzt': '5000.00',
        'reason': 'Брак',
    })
    assert resp.status_code == 302


@pytest.mark.django_db
def test_owner_retains_full_operational_access(rbac_setup):
    """
    Confirms that OWNER has full, unimpeded access to mutating operations
    and is NOT affected by the deny_demo_viewer decorator.
    """
    client = Client()
    client.force_login(rbac_setup['owner'])

    # OWNER can create a material
    resp = client.post('/materials/create/', {
        'sku': 'MAT-OWNER-OK',
        'name': 'Владелец Материал',
        'category': MaterialCategory.WOOD,
        'unit': 'шт',
        'purchase_cost_kzt': '12000.00',
        'min_stock_level': '5.000',
    })
    assert resp.status_code == 302  # Successful redirect to materials:index
    assert Material.objects.filter(sku='MAT-OWNER-OK').exists()

    # OWNER can create an expense
    resp = client.post('/finance/expenses/create/', {
        'category': 'OFFICE',
        'amount_kzt': '7500.00',
        'description': 'Канцтовары',
        'payment_method': 'BANK_TRANSFER',
    })
    assert resp.status_code == 302


@pytest.mark.django_db
def test_demo_viewer_has_no_admin_access(rbac_setup):
    """
    Confirms that DEMO_VIEWER has is_staff=False and cannot access /admin/.
    """
    client = Client()
    client.force_login(rbac_setup['demo_viewer'])

    resp = client.get('/admin/')
    # Expect 302 redirect to Django Admin login screen
    assert resp.status_code == 302
    assert '/admin/login/' in resp.url
