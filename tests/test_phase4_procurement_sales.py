import pytest
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.accounts.models import User, UserRole
from apps.materials.models import Material, MaterialCategory
from apps.products.models import Product, ProductCategory
from apps.suppliers.models import Supplier, PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus
from apps.sales.models import Customer, SalesOrder, SalesOrderItem, OrderStatus
from apps.warehouses.models import Warehouse, WarehouseType, StockBalance, WarehouseDocumentType, DocumentStatus
from apps.production.models import ProductionOrder, ProductionOrderStatus, BOM, BOMItem
from apps.suppliers.services import (
    create_purchase_order,
    confirm_purchase_order,
    receive_purchase_order_items,
    cancel_purchase_order,
)
from apps.sales.services import (
    create_sales_order,
    check_sales_order_stock,
    confirm_and_reserve_sales_order,
    create_production_orders_for_sales_order,
    ship_sales_order,
    cancel_sales_order,
)
from apps.notifications.models import Notification, NotificationType


@pytest.fixture
def phase4_setup(db):
    """Базовые данные для тестов Фазы 4: склады WH-1 и WH-2, роли, номенклатура."""
    wh1, _ = Warehouse.objects.get_or_create(
        code='WH-1',
        defaults={'name': 'Склад сырья и материалов №1', 'warehouse_type': WarehouseType.RAW_MATERIALS}
    )
    wh2, _ = Warehouse.objects.get_or_create(
        code='WH-2',
        defaults={'name': 'Склад готовой продукции №2', 'warehouse_type': WarehouseType.FINISHED_PRODUCTS}
    )

    manager, _ = User.objects.get_or_create(
        username='manager_phase4',
        defaults={'role': UserRole.PRODUCTION_MANAGER, 'is_staff': True}
    )
    buyer, _ = User.objects.get_or_create(
        username='sales_phase4',
        defaults={'role': UserRole.SALES_MANAGER, 'is_staff': True}
    )

    supplier, _ = Supplier.objects.get_or_create(
        name='ТОО «Фанера-Снаб»',
        defaults={'contact_person': 'Данияр', 'phone': '+77010000001'}
    )

    material, _ = Material.objects.get_or_create(
        sku='MAT-PLY-18',
        defaults={
            'name': 'Фанера березовая ФСФ 18мм',
            'category': MaterialCategory.PLYWOOD,
            'unit': 'лист',
            'purchase_cost_kzt': Decimal('8500.00'),
            'supplier': supplier,
        }
    )
    # Инициализация остатка на WH-1
    sb1, _ = StockBalance.objects.get_or_create(warehouse=wh1, material=material)
    sb1.current_stock = Decimal('10.000')
    sb1.save()

    product, _ = Product.objects.get_or_create(
        sku='PRD-CHAIR-01',
        defaults={
            'name': 'Стул обеденный Loft',
            'category': ProductCategory.OTHER,
            'production_cost_kzt': Decimal('15000.00'),
            'sale_price_kzt': Decimal('28000.00'),
        }
    )
    # Инициализация остатка на WH-2
    sb2, _ = StockBalance.objects.get_or_create(warehouse=wh2, product=product)
    sb2.current_stock = Decimal('5.00')
    sb2.reserved_stock = Decimal('0.00')
    sb2.save()

    # BOM для стула
    bom, _ = BOM.objects.get_or_create(
        product=product,
        version=1,
        defaults={'name': 'Спецификация стула Loft v1', 'is_active': True}
    )
    BOMItem.objects.get_or_create(
        bom=bom,
        material=material,
        defaults={'quantity_planned': Decimal('0.500'), 'unit': 'лист'}
    )

    customer, _ = Customer.objects.get_or_create(
        full_name='Касымов Айдын',
        defaults={'company_name': 'ИП «Касымов»', 'phone': '+77771234567'}
    )

    return {
        'wh1': wh1,
        'wh2': wh2,
        'manager': manager,
        'buyer': buyer,
        'supplier': supplier,
        'material': material,
        'product': product,
        'customer': customer,
        'bom': bom,
    }


# ==============================================================================
# ТЕСТЫ ЗАКУПОК (PROCUREMENT)
# ==============================================================================

@pytest.mark.django_db
def test_purchase_order_creation_and_confirmation(phase4_setup):
    """1. Создание заказа поставщику в статусе DRAFT и подтверждение/отправка (SENT)."""
    s = phase4_setup
    po = create_purchase_order(
        supplier=s['supplier'],
        created_by=s['manager'],
        planned_delivery_date=timezone.localdate(),
        notes='Тестовая поставка',
        items_data=[{
            'material': s['material'],
            'quantity': Decimal('20.000'),
            'unit_price_kzt': Decimal('8500.00'),
        }]
    )

    assert po.status == PurchaseOrderStatus.DRAFT
    assert po.items.count() == 1
    assert po.total_amount_kzt == Decimal('170000.00')
    assert po.can_send is True

    # Подтверждение и отправка
    po_sent = confirm_purchase_order(po, user=s['manager'])
    assert po_sent.status == PurchaseOrderStatus.SENT
    assert po_sent.can_receive is True


@pytest.mark.django_db
def test_purchase_order_partial_and_full_receipt(phase4_setup):
    """2. Частичная и последующая полная приёмка материалов на склад WH-1."""
    s = phase4_setup
    po = create_purchase_order(
        supplier=s['supplier'],
        created_by=s['manager'],
        items_data=[{
            'material': s['material'],
            'quantity': Decimal('10.000'),
            'unit_price_kzt': Decimal('8500.00'),
        }]
    )
    confirm_purchase_order(po, user=s['manager'])
    po_item = po.items.first()

    sb_before = StockBalance.objects.get(warehouse=s['wh1'], material=s['material'])
    initial_stock = sb_before.current_stock

    # Частичная приёмка: 4 листа
    receipt_doc1 = receive_purchase_order_items(
        purchase_order=po,
        received_items_map={po_item.id: Decimal('4.000')},
        user=s['manager'],
        doc_notes='Первая партия 4 листа'
    )

    assert receipt_doc1.status == DocumentStatus.POSTED
    assert receipt_doc1.doc_type == WarehouseDocumentType.RECEIPT
    assert receipt_doc1.purchase_order == po

    po.refresh_from_db()
    po_item.refresh_from_db()
    assert po.status == PurchaseOrderStatus.PARTIALLY_RECEIVED
    assert po_item.received_quantity == Decimal('4.000')
    assert po_item.remaining_quantity == Decimal('6.000')

    sb_after_part1 = StockBalance.objects.get(warehouse=s['wh1'], material=s['material'])
    assert sb_after_part1.current_stock == initial_stock + Decimal('4.000')

    # Оставшаяся часть приёмки: 6 листов
    receipt_doc2 = receive_purchase_order_items(
        purchase_order=po,
        received_items_map={po_item.id: Decimal('6.000')},
        user=s['manager'],
        doc_notes='Вторая партия 6 листов'
    )

    po.refresh_from_db()
    po_item.refresh_from_db()
    assert po.status == PurchaseOrderStatus.RECEIVED
    assert po_item.is_fully_received is True

    sb_after_part2 = StockBalance.objects.get(warehouse=s['wh1'], material=s['material'])
    assert sb_after_part2.current_stock == initial_stock + Decimal('10.000')


@pytest.mark.django_db
def test_purchase_order_prevent_over_receipt(phase4_setup):
    """3. Защита от оприходования сверх заказанного количества."""
    s = phase4_setup
    po = create_purchase_order(
        supplier=s['supplier'],
        created_by=s['manager'],
        items_data=[{
            'material': s['material'],
            'quantity': Decimal('5.000'),
            'unit_price_kzt': Decimal('8500.00'),
        }]
    )
    confirm_purchase_order(po, user=s['manager'])
    po_item = po.items.first()

    with pytest.raises(ValidationError) as exc:
        receive_purchase_order_items(
            purchase_order=po,
            received_items_map={po_item.id: Decimal('6.000')},
            user=s['manager'],
        )
    assert 'Осталось принять по заказу: 5.000' in str(exc.value)


@pytest.mark.django_db
def test_purchase_order_cancellation(phase4_setup):
    """4. Отмена заказа поставщику (разрешена до приходования, запрещена после)."""
    s = phase4_setup
    po = create_purchase_order(
        supplier=s['supplier'],
        created_by=s['manager'],
        items_data=[{
            'material': s['material'],
            'quantity': Decimal('5.000'),
            'unit_price_kzt': Decimal('8500.00'),
        }]
    )
    cancel_purchase_order(po, user=s['manager'])
    po.refresh_from_db()
    assert po.status == PurchaseOrderStatus.CANCELLED

    # Попытка отправки отменённого заказа должна вызывать ошибку
    with pytest.raises(ValidationError):
        confirm_purchase_order(po, user=s['manager'])


# ==============================================================================
# ТЕСТЫ ПРОДАЖ (SALES & RESERVATION & PRODUCTION)
# ==============================================================================

@pytest.mark.django_db
def test_sales_order_creation_and_discounts(phase4_setup):
    """5. Создание заказа покупателя с позициями и скидкой."""
    s = phase4_setup
    so = create_sales_order(
        customer=s['customer'],
        created_by=s['buyer'],
        items_data=[{
            'product': s['product'],
            'quantity': Decimal('2.00'),
            'unit_price_kzt': Decimal('28000.00'),
            'discount_percent': Decimal('10.00'),
        }],
        discount_percent=Decimal('5.00'),
    )

    # 2 * 28000 = 56000. Скидка позиции 10% = 50400. Скидка заказа 5% = 47880.
    assert so.subtotal_amount_kzt == Decimal('50400.00')
    assert so.total_amount_kzt == Decimal('47880.00')
    assert so.status == OrderStatus.DRAFT


@pytest.mark.django_db
def test_sales_order_stock_check_and_full_reservation(phase4_setup):
    """6. Проверка наличия и резервирование готовой мебели на складе WH-2 при достаточном остатке."""
    s = phase4_setup
    # На WH-2 в фикстуре числится 5 стульев. Заказываем 3 шт.
    so = create_sales_order(
        customer=s['customer'],
        created_by=s['buyer'],
        items_data=[{
            'product': s['product'],
            'quantity': Decimal('3.00'),
            'unit_price_kzt': Decimal('28000.00'),
        }]
    )

    check = check_sales_order_stock(so)
    assert check['is_fully_available'] is True
    assert check['total_deficit_count'] == 0

    updated_so, res_doc = confirm_and_reserve_sales_order(so, user=s['buyer'])
    assert updated_so.status == OrderStatus.READY
    assert res_doc is not None
    assert res_doc.doc_type == WarehouseDocumentType.RESERVATION

    # Проверяем изменение баланса на WH-2
    sb2 = StockBalance.objects.get(warehouse=s['wh2'], product=s['product'])
    assert sb2.reserved_stock == Decimal('3.00')
    assert sb2.available_stock == Decimal('2.00')


@pytest.mark.django_db
def test_sales_order_deficit_and_production_trigger(phase4_setup):
    """7. Обнаружение дефицита на WH-2 и создание производственного заказа только по команде."""
    s = phase4_setup
    # На WH-2 свободно 5 шт. Клиент заказывает 8 шт. Дефицит = 3 шт.
    so = create_sales_order(
        customer=s['customer'],
        created_by=s['buyer'],
        items_data=[{
            'product': s['product'],
            'quantity': Decimal('8.00'),
            'unit_price_kzt': Decimal('28000.00'),
        }]
    )

    check = check_sales_order_stock(so)
    assert check['is_fully_available'] is False
    assert check['total_deficit_count'] == 1
    assert check['items'][0]['deficit_qty'] == Decimal('3.00')

    # Резервируем доступные 5 шт
    updated_so, res_doc = confirm_and_reserve_sales_order(so, user=s['buyer'])
    assert updated_so.status == OrderStatus.WAITING_PRODUCTION

    sb2 = StockBalance.objects.get(warehouse=s['wh2'], product=s['product'])
    assert sb2.reserved_stock == Decimal('5.00')
    assert sb2.available_stock == Decimal('0.00')

    # До подтверждения пользователя производственный заказ НЕ создается автоматически!
    assert ProductionOrder.objects.filter(sales_order=so).count() == 0

    # Менеджер подтверждает запуск производства на недостающие 3 шт
    created_pos = create_production_orders_for_sales_order(so, user=s['buyer'])
    assert len(created_pos) == 1
    prod_order = created_pos[0]

    assert prod_order.product == s['product']
    assert prod_order.quantity_planned == Decimal('3.00')
    assert prod_order.sales_order == so
    assert prod_order.status == ProductionOrderStatus.WAITING

    so.refresh_from_db()
    assert so.status == OrderStatus.IN_PRODUCTION


@pytest.mark.django_db
def test_sales_order_partial_and_full_shipment(phase4_setup):
    """8. Частичная и полная отгрузка клиенту со склада WH-2 со списанием остатков и снятием резервов."""
    s = phase4_setup
    so = create_sales_order(
        customer=s['customer'],
        created_by=s['buyer'],
        items_data=[{
            'product': s['product'],
            'quantity': Decimal('4.00'),
            'unit_price_kzt': Decimal('28000.00'),
        }]
    )
    confirm_and_reserve_sales_order(so, user=s['buyer'])
    item = so.items.first()

    sb_start = StockBalance.objects.get(warehouse=s['wh2'], product=s['product'])
    assert sb_start.current_stock == Decimal('5.00')
    assert sb_start.reserved_stock == Decimal('4.00')

    # Частичная отгрузка: 2 шт
    ship_doc1 = ship_sales_order(
        sales_order=so,
        shipped_items_map={item.id: Decimal('2.00')},
        user=s['buyer'],
        doc_notes='Отгрузка 1-й партии 2 шт'
    )
    assert ship_doc1.doc_type == WarehouseDocumentType.SHIPMENT

    so.refresh_from_db()
    item.refresh_from_db()
    assert so.status == OrderStatus.PARTIALLY_SHIPPED
    assert item.shipped_quantity == Decimal('2.00')
    assert item.reserved_quantity == Decimal('2.00')

    sb_part1 = StockBalance.objects.get(warehouse=s['wh2'], product=s['product'])
    assert sb_part1.current_stock == Decimal('3.00')
    assert sb_part1.reserved_stock == Decimal('2.00')

    # Финальная отгрузка: оставшиеся 2 шт
    ship_doc2 = ship_sales_order(
        sales_order=so,
        shipped_items_map={item.id: Decimal('2.00')},
        user=s['buyer'],
        doc_notes='Отгрузка 2-й партии 2 шт'
    )
    so.refresh_from_db()
    item.refresh_from_db()
    assert so.status == OrderStatus.SHIPPED
    assert item.is_fully_shipped is True

    sb_final = StockBalance.objects.get(warehouse=s['wh2'], product=s['product'])
    assert sb_final.current_stock == Decimal('1.00')
    assert sb_final.reserved_stock == Decimal('0.00')


@pytest.mark.django_db
def test_sales_order_cancellation_releases_reservation(phase4_setup):
    """9. Отмена клиентского заказа корректно освобождает зарезервированные остатки на WH-2."""
    s = phase4_setup
    so = create_sales_order(
        customer=s['customer'],
        created_by=s['buyer'],
        items_data=[{
            'product': s['product'],
            'quantity': Decimal('3.00'),
            'unit_price_kzt': Decimal('28000.00'),
        }]
    )
    confirm_and_reserve_sales_order(so, user=s['buyer'])

    sb_res = StockBalance.objects.get(warehouse=s['wh2'], product=s['product'])
    assert sb_res.reserved_stock == Decimal('3.00')

    cancel_sales_order(so, user=s['buyer'])

    so.refresh_from_db()
    assert so.status == OrderStatus.CANCELLED

    sb_after_cancel = StockBalance.objects.get(warehouse=s['wh2'], product=s['product'])
    assert sb_after_cancel.reserved_stock == Decimal('0.00')
    assert sb_after_cancel.available_stock == Decimal('5.00')


@pytest.mark.django_db
def test_safe_archiving_for_catalog(phase4_setup):
    """10. Безопасное архивирование номенклатуры (Material, Product, Customer, Supplier) через is_active."""
    s = phase4_setup

    mat = s['material']
    assert mat.is_active is True
    mat.is_active = False
    mat.save()
    assert Material.objects.filter(is_active=False, id=mat.id).exists()

    prod = s['product']
    assert prod.is_active is True
    prod.is_active = False
    prod.save()
    assert Product.objects.filter(is_active=False, id=prod.id).exists()

    cust = s['customer']
    assert cust.is_active is True
    cust.is_active = False
    cust.save()
    assert Customer.objects.filter(is_active=False, id=cust.id).exists()

    sup = s['supplier']
    assert sup.is_active is True
    sup.is_active = False
    sup.save()
    assert Supplier.objects.filter(is_active=False, id=sup.id).exists()
