import datetime
import uuid
from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.accounts.models import AuditLog, UserRole
from apps.sales.models import (
    Customer,
    SalesOrder,
    SalesOrderItem,
    OrderStatus,
)
from apps.products.models import Product
from apps.production.models import ProductionOrder, ProductionOrderStatus, OrderPriority, BOM
from apps.production.services import generate_order_number, recalculate_order_costs, initialize_order_stages
from apps.warehouses.models import (
    Warehouse,
    WarehouseType,
    WarehouseDocument,
    WarehouseDocumentItem,
    WarehouseDocumentType,
    DocumentStatus,
    StockBalance,
)
from apps.warehouses.services import generate_doc_number, post_document, get_or_create_stock_balance
from apps.notifications.services import (
    notify_new_sales_order,
    notify_waiting_production,
    notify_ready_for_shipment,
)


def generate_so_number() -> str:
    """Генерация уникального номера клиентского заказа: SO-YYMMDD-XXXX."""
    today_str = timezone.now().strftime('%y%m%d')
    suffix = uuid.uuid4().hex[:4].upper()
    return f'SO-{today_str}-{suffix}'


@transaction.atomic
def create_sales_order(
    customer: Customer,
    created_by,
    items_data=None,
    planned_delivery_date=None,
    delivery_address: str = '',
    notes: str = '',
    discount_percent: Decimal = Decimal('0.00'),
    deposit_amount_kzt: Decimal = Decimal('0.00'),
) -> SalesOrder:
    """Создание заказа покупателя в статусе DRAFT."""
    if not customer.is_active:
        raise ValidationError('Невозможно создать заказ для неактивного или архивированного клиента.')

    order = SalesOrder.objects.create(
        order_number=generate_so_number(),
        customer=customer,
        status=OrderStatus.DRAFT,
        planned_delivery_date=planned_delivery_date,
        delivery_address=delivery_address or customer.address,
        notes=notes,
        discount_percent=Decimal(str(discount_percent or '0.00')),
        deposit_amount_kzt=Decimal(str(deposit_amount_kzt or '0.00')),
        created_by=created_by,
    )

    if items_data:
        for it in items_data:
            prod = it['product']
            qty = Decimal(str(it['quantity']))
            price = Decimal(str(it.get('unit_price_kzt') or prod.sale_price_kzt))
            disc = Decimal(str(it.get('discount_percent') or '0.00'))

            if qty <= Decimal('0'):
                raise ValidationError(f'Количество для изделия "{prod.name}" должно быть больше нуля.')
            if price < Decimal('0'):
                raise ValidationError('Цена изделия не может быть отрицательной.')

            line_base = qty * price
            line_total = (line_base * (Decimal('100.00') - disc) / Decimal('100.00')).quantize(Decimal('0.01'))

            SalesOrderItem.objects.create(
                order=order,
                product=prod,
                quantity=qty,
                reserved_quantity=Decimal('0.00'),
                shipped_quantity=Decimal('0.00'),
                unit_price_kzt=price,
                discount_percent=disc,
                total_price_kzt=line_total,
            )

    order.recalculate_totals()

    try:
        notify_new_sales_order(order)
    except Exception:
        pass

    AuditLog.objects.create(
        user=created_by,
        action='CREATE_SALES_ORDER',
        entity_type='SalesOrder',
        entity_id=str(order.id),
        details={
            'order_number': order.order_number,
            'customer': customer.name,
            'total_amount': float(order.total_amount_kzt),
            'items_count': len(items_data or []),
        },
    )
    return order


def check_sales_order_stock(sales_order: SalesOrder) -> dict:
    """Анализ доступности готовой продукции на складе WH-2 для выполнения заказа покупателя."""
    wh2 = Warehouse.objects.filter(warehouse_type=WarehouseType.FINISHED_PRODUCTS).first()
    items_report = []
    is_fully_available = True
    total_deficit_count = 0

    for item in sales_order.items.select_related('product').all():
        needed_qty = item.remaining_to_reserve

        if wh2:
            balance = StockBalance.objects.filter(warehouse=wh2, product=item.product).first()
            current_stock = balance.current_stock if balance else Decimal('0.00')
            reserved_stock = balance.reserved_stock if balance else Decimal('0.00')
            available_stock = balance.available_stock if balance else Decimal('0.00')
        else:
            current_stock = Decimal('0.00')
            reserved_stock = Decimal('0.00')
            available_stock = Decimal('0.00')

        active_bom = BOM.objects.filter(product=item.product, is_active=True).first()

        if needed_qty > available_stock:
            deficit_qty = needed_qty - available_stock
            is_fully_available = False
            total_deficit_count += 1
        else:
            deficit_qty = Decimal('0.00')

        items_report.append({
            'item': item,
            'product': item.product,
            'ordered_qty': item.quantity,
            'already_reserved': item.reserved_quantity,
            'already_shipped': item.shipped_quantity,
            'needed_qty': needed_qty,
            'current_stock': current_stock,
            'reserved_stock': reserved_stock,
            'available_stock': available_stock,
            'deficit_qty': deficit_qty,
            'has_active_bom': active_bom is not None,
            'active_bom': active_bom,
            'is_covered': deficit_qty == Decimal('0.00'),
        })

    return {
        'is_fully_available': is_fully_available,
        'items': items_report,
        'total_deficit_count': total_deficit_count,
    }


@transaction.atomic
def confirm_and_reserve_sales_order(sales_order: SalesOrder, user=None) -> tuple[SalesOrder, WarehouseDocument | None]:
    """Подтверждение заказа покупателя и резервирование доступного остатка на складе WH-2.

    Если продукция доступна целиком: статус становится READY или CONFIRMED.
    Если есть дефицит: статус становится WAITING_PRODUCTION, резервируется доступная часть.
    """
    so = SalesOrder.objects.select_for_update().get(pk=sales_order.pk)
    if so.status not in [OrderStatus.DRAFT, OrderStatus.NEW, OrderStatus.WAITING_PRODUCTION]:
        raise ValidationError(f'Невозможно зарезервировать заказ в статусе "{so.get_status_display()}".')

    wh2 = Warehouse.objects.filter(warehouse_type=WarehouseType.FINISHED_PRODUCTS).first()
    if not wh2:
        raise ValidationError('Склад готовой продукции WH-2 не найден.')

    stock_check = check_sales_order_stock(so)
    items_to_reserve = []
    total_reserve_amount = Decimal('0.00')

    for row in stock_check['items']:
        needed = row['needed_qty']
        avail = row['available_stock']
        qty_can_reserve = min(needed, avail)

        if qty_can_reserve > Decimal('0.00'):
            line_cost = (qty_can_reserve * row['item'].unit_price_kzt).quantize(Decimal('0.01'))
            items_to_reserve.append((row['item'], qty_can_reserve, line_cost))
            total_reserve_amount += line_cost

    reservation_doc = None
    if items_to_reserve:
        doc_number = generate_doc_number(WarehouseDocumentType.RESERVATION)
        reservation_doc = WarehouseDocument.objects.create(
            doc_number=doc_number,
            doc_type=WarehouseDocumentType.RESERVATION,
            status=DocumentStatus.DRAFT,
            warehouse=wh2,
            doc_date=timezone.localdate(),
            created_by=user,
            customer=so.customer,
            sales_order=so,
            total_amount_kzt=total_reserve_amount,
            notes=f'Резервирование готовой мебели под заказ {so.order_number}',
        )

        for item, qty, cost in items_to_reserve:
            WarehouseDocumentItem.objects.create(
                document=reservation_doc,
                product=item.product,
                quantity=qty,
                unit='шт',
                unit_cost_kzt=item.unit_price_kzt,
                total_cost_kzt=cost,
                notes=f'Заказ {so.order_number}',
            )
            item.reserved_quantity += qty
            item.save(update_fields=['reserved_quantity'])

        post_document(reservation_doc, user=user)
        reservation_doc.refresh_from_db()

    # Проверяем, все ли позиции зарезервированы
    so.refresh_from_db()
    all_items_covered = all(
        (it.reserved_quantity + it.shipped_quantity) >= it.quantity for it in so.items.all()
    )

    if all_items_covered:
        so.status = OrderStatus.READY
        try:
            notify_ready_for_shipment(so)
        except Exception:
            pass
    else:
        so.status = OrderStatus.WAITING_PRODUCTION
        deficit_text = f"Дефицит позиций: {stock_check['total_deficit_count']} шт."
        try:
            notify_waiting_production(so, deficit_text)
        except Exception:
            pass

    so.save(update_fields=['status', 'updated_at'])

    AuditLog.objects.create(
        user=user,
        action='RESERVE_SALES_ORDER',
        entity_type='SalesOrder',
        entity_id=str(so.id),
        details={
            'event': 'confirmed_and_reserved',
            'status': so.status,
            'reserved_doc': reservation_doc.doc_number if reservation_doc else None,
        },
    )
    return so, reservation_doc


@transaction.atomic
def create_production_orders_for_sales_order(
    sales_order: SalesOrder,
    user=None,
    quantities_map: dict = None,
) -> list[ProductionOrder]:
    """Создание производственных заказов для покрытия дефицита готовой мебели по заказу клиента.

    :param sales_order: исходный заказ покупателя
    :param user: сотрудник (менеджер/мастер)
    :param quantities_map: словарь {product_id_str: qty_to_produce}. Если None, берется расчетный дефицит.
    """
    so = SalesOrder.objects.select_for_update().get(pk=sales_order.pk)
    stock_check = check_sales_order_stock(so)

    created_orders = []

    for row in stock_check['items']:
        product = row['product']
        prod_id_str = str(product.id)

        if quantities_map is not None:
            if prod_id_str not in quantities_map:
                continue
            qty_to_make = Decimal(str(quantities_map[prod_id_str]))
        else:
            qty_to_make = row['deficit_qty']

        if qty_to_make <= Decimal('0.00'):
            continue

        active_bom = BOM.objects.filter(product=product, is_active=True).first()

        po_number = generate_order_number()
        today = timezone.localdate()

        po = ProductionOrder.objects.create(
            order_number=po_number,
            product=product,
            bom=active_bom,
            quantity_planned=qty_to_make,
            sales_order=so,
            status=ProductionOrderStatus.WAITING,
            priority=OrderPriority.HIGH,
            planned_start=today,
            planned_end=today + datetime.timedelta(days=10),
            created_by=user,
            notes=f'Сформирован под клиентский заказ {so.order_number} ({so.customer.name})',
        )

        if active_bom:
            recalculate_order_costs(po)
        initialize_order_stages(po)

        created_orders.append(po)

    if created_orders:
        so.status = OrderStatus.IN_PRODUCTION
        so.save(update_fields=['status', 'updated_at'])

        AuditLog.objects.create(
            user=user,
            action='CREATE_PRODUCTION_ORDERS',
            entity_type='SalesOrder',
            entity_id=str(so.id),
            details={
                'event': 'production_orders_created_from_sales',
                'sales_order': so.order_number,
                'orders': [o.order_number for o in created_orders],
            },
        )

    return created_orders


@transaction.atomic
def ship_sales_order(
    sales_order: SalesOrder,
    shipped_items_map: dict,
    user=None,
    doc_notes: str = '',
) -> WarehouseDocument:
    """Отгрузка готовой продукции со склада WH-2 клиенту (полная или частичная).

    :param sales_order: заказ клиента
    :param shipped_items_map: dict вида {item_id: quantity_to_ship}
    :param user: кладовщик / менеджер
    :param doc_notes: примечания к накладной
    :return: проведенный WarehouseDocument (SHIPMENT)
    """
    so = SalesOrder.objects.select_for_update().get(pk=sales_order.pk)
    if not so.can_ship:
        raise ValidationError(
            f'Невозможно выполнить отгрузку: заказ {so.order_number} находится в статусе "{so.get_status_display()}".'
        )

    wh2 = Warehouse.objects.filter(warehouse_type=WarehouseType.FINISHED_PRODUCTS).first()
    if not wh2:
        raise ValidationError('Склад готовой продукции WH-2 не найден.')

    items_to_process = []
    total_shipped_amount = Decimal('0.00')

    for item_id, qty_raw in shipped_items_map.items():
        try:
            qty = Decimal(str(qty_raw))
        except Exception:
            continue

        if qty <= Decimal('0'):
            continue

        item = so.items.select_for_update().filter(id=item_id).first()
        if not item:
            continue

        rem = item.remaining_to_ship
        if qty > rem:
            raise ValidationError(
                f'Нельзя отгрузить {qty} шт. изделия "{item.product.name}". '
                f'Осталось к отгрузке по заказу: {rem} шт.'
            )

        # Проверяем фактическое наличие на складе WH-2
        balance = get_or_create_stock_balance(wh2, product=item.product, for_update=True)
        if balance.current_stock < qty:
            raise ValidationError(
                f'Недостаточно изделий "{item.product.name}" на складе WH-2. '
                f'В наличии: {balance.current_stock} шт., запрошено к отгрузке: {qty} шт.'
            )

        line_amount = (qty * item.unit_price_kzt * (Decimal('100.00') - item.discount_percent) / Decimal('100.00')).quantize(Decimal('0.01'))
        total_shipped_amount += line_amount
        items_to_process.append((item, qty, line_amount))

    if not items_to_process:
        raise ValidationError('Не указано ни одно количество изделий для отгрузки.')

    # Формируем документ SHIPMENT на WH-2
    doc_number = generate_doc_number(WarehouseDocumentType.SHIPMENT)
    shipment_doc = WarehouseDocument.objects.create(
        doc_number=doc_number,
        doc_type=WarehouseDocumentType.SHIPMENT,
        status=DocumentStatus.DRAFT,
        warehouse=wh2,
        doc_date=timezone.localdate(),
        created_by=user,
        customer=so.customer,
        sales_order=so,
        total_amount_kzt=total_shipped_amount,
        notes=f'Отгрузка по клиентскому заказу {so.order_number}. {doc_notes}'.strip(),
    )

    for item, qty, cost in items_to_process:
        WarehouseDocumentItem.objects.create(
            document=shipment_doc,
            product=item.product,
            quantity=qty,
            unit='шт',
            unit_cost_kzt=item.unit_price_kzt,
            total_cost_kzt=cost,
            notes=f'Заказ {so.order_number}',
        )
        item.shipped_quantity += qty
        if item.reserved_quantity > Decimal('0.00'):
            res_reduction = min(item.reserved_quantity, qty)
            item.reserved_quantity -= res_reduction
        item.save(update_fields=['shipped_quantity', 'reserved_quantity'])

    # Проводим складской документ отгрузки
    post_document(shipment_doc, user=user)
    shipment_doc.refresh_from_db()

    # Обновляем статус заказа покупателя
    so.refresh_from_db()
    if so.is_fully_shipped:
        so.status = OrderStatus.SHIPPED
    else:
        so.status = OrderStatus.PARTIALLY_SHIPPED
    so.save(update_fields=['status', 'updated_at'])

    AuditLog.objects.create(
        user=user,
        action='SHIP_SALES_ORDER',
        entity_type='WarehouseDocument',
        entity_id=str(shipment_doc.id),
        details={
            'doc_number': shipment_doc.doc_number,
            'sales_order': so.order_number,
            'total_amount': float(total_shipped_amount),
            'order_status': so.status,
        },
    )
    return shipment_doc


@transaction.atomic
def cancel_sales_order(sales_order: SalesOrder, user=None) -> SalesOrder:
    """Отмена заказа клиента и освобождение зарезервированной мебели на WH-2."""
    so = SalesOrder.objects.select_for_update().get(pk=sales_order.pk)
    if not so.can_cancel:
        raise ValidationError(f'Невозможно отменить заказ в статусе "{so.get_status_display()}".')

    has_shipments = any(it.shipped_quantity > Decimal('0.00') for it in so.items.all())
    if has_shipments:
        raise ValidationError('Нельзя полностью отменить заказ, по которому уже производились отгрузки со склада.')

    wh2 = Warehouse.objects.filter(warehouse_type=WarehouseType.FINISHED_PRODUCTS).first()

    # Снимаем резервы с WH-2
    items_to_unreserve = []
    total_unreserve_amount = Decimal('0.00')

    for it in so.items.select_for_update().all():
        if it.reserved_quantity > Decimal('0.00'):
            line_cost = (it.reserved_quantity * it.unit_price_kzt).quantize(Decimal('0.01'))
            items_to_unreserve.append((it, it.reserved_quantity, line_cost))
            total_unreserve_amount += line_cost

    if items_to_unreserve and wh2:
        unres_doc = WarehouseDocument.objects.create(
            doc_number=generate_doc_number(WarehouseDocumentType.UNRESERVATION),
            doc_type=WarehouseDocumentType.UNRESERVATION,
            status=DocumentStatus.DRAFT,
            warehouse=wh2,
            doc_date=timezone.localdate(),
            created_by=user,
            customer=so.customer,
            sales_order=so,
            total_amount_kzt=total_unreserve_amount,
            notes=f'Снятие резерва при отмене заказа {so.order_number}',
        )
        for it, qty, cost in items_to_unreserve:
            WarehouseDocumentItem.objects.create(
                document=unres_doc,
                product=it.product,
                quantity=qty,
                unit='шт',
                unit_cost_kzt=it.unit_price_kzt,
                total_cost_kzt=cost,
                notes=f'Отмена заказа {so.order_number}',
            )
            it.reserved_quantity = Decimal('0.00')
            it.save(update_fields=['reserved_quantity'])

        post_document(unres_doc, user=user)

    so.status = OrderStatus.CANCELLED
    so.save(update_fields=['status', 'updated_at'])

    AuditLog.objects.create(
        user=user,
        action='CANCEL_SALES_ORDER',
        entity_type='SalesOrder',
        entity_id=str(so.id),
        details={'event': 'order_cancelled', 'order_number': so.order_number},
    )
    return so
