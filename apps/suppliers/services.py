import uuid
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.accounts.models import AuditLog
from apps.suppliers.models import (
    Supplier,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
)
from apps.warehouses.models import (
    Warehouse,
    WarehouseType,
    WarehouseDocument,
    WarehouseDocumentItem,
    WarehouseDocumentType,
    DocumentStatus,
)
from apps.warehouses.services import generate_doc_number, post_document
from apps.notifications.services import notify_supplier_receipt


def generate_po_number() -> str:
    """Генерация уникального номера заказа на закупку: PO-YYMMDD-XXXX."""
    today_str = timezone.now().strftime('%y%m%d')
    suffix = uuid.uuid4().hex[:4].upper()
    return f'PO-{today_str}-{suffix}'


@transaction.atomic
def create_purchase_order(
    supplier: Supplier,
    created_by,
    planned_delivery_date=None,
    payment_due_date=None,
    notes: str = '',
    items_data=None,
) -> PurchaseOrder:
    """Создание нового заказа поставщику в статусе DRAFT."""
    if not supplier.is_active:
        raise ValidationError('Невозможно создать заказ неактивному / архивированному поставщику.')

    po = PurchaseOrder.objects.create(
        order_number=generate_po_number(),
        supplier=supplier,
        planned_delivery_date=planned_delivery_date,
        payment_due_date=payment_due_date,
        notes=notes,
        created_by=created_by,
        status=PurchaseOrderStatus.DRAFT,
    )

    total_amount = Decimal('0.00')
    if items_data:
        for it in items_data:
            material = it['material']
            qty = Decimal(str(it['quantity']))
            price = Decimal(str(it.get('unit_price_kzt') or material.purchase_cost_kzt))

            if qty <= Decimal('0'):
                raise ValidationError(f'Количество для материала "{material.name}" должно быть строго положительным.')
            if price < Decimal('0'):
                raise ValidationError('Закупочная цена не может быть отрицательной.')

            line_total = (qty * price).quantize(Decimal('0.01'))
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                material=material,
                quantity=qty,
                received_quantity=Decimal('0.000'),
                unit_price_kzt=price,
                total_price_kzt=line_total,
                notes=it.get('notes', ''),
            )
            total_amount += line_total

    po.total_amount_kzt = total_amount
    po.save(update_fields=['total_amount_kzt'])

    AuditLog.objects.create(
        user=created_by,
        action='CREATE_PURCHASE_ORDER',
        entity_type='PurchaseOrder',
        entity_id=str(po.id),
        details={
            'order_number': po.order_number,
            'supplier': supplier.name,
            'total_amount': float(total_amount),
            'items_count': len(items_data or []),
        },
    )
    return po


@transaction.atomic
def confirm_purchase_order(purchase_order: PurchaseOrder, user=None) -> PurchaseOrder:
    """Перевод заказа поставщику из DRAFT в SENT (отправлен)."""
    po = PurchaseOrder.objects.select_for_update().get(pk=purchase_order.pk)
    if po.status != PurchaseOrderStatus.DRAFT:
        raise ValidationError(f'Заказ {po.order_number} не может быть отправлен, т.к. находится в статусе {po.get_status_display()}.')

    if not po.items.exists():
        raise ValidationError(f'Заказ {po.order_number} не содержит ни одной номенклатурной позиции.')

    po.status = PurchaseOrderStatus.SENT
    po.save(update_fields=['status', 'updated_at'])

    AuditLog.objects.create(
        user=user,
        action='CONFIRM_PURCHASE_ORDER',
        entity_type='PurchaseOrder',
        entity_id=str(po.id),
        details={'event': 'confirmed_and_sent', 'order_number': po.order_number},
    )
    return po


@transaction.atomic
def receive_purchase_order_items(
    purchase_order: PurchaseOrder,
    received_items_map: dict,
    user=None,
    doc_notes: str = '',
) -> WarehouseDocument:
    """Приемка сырья по заказу поставщика на склад WH-1 (полная или частичная).

    :param purchase_order: заказ на закупку
    :param received_items_map: dict вида {item_id: quantity_received_in_this_batch}
    :param user: сотрудник, принимающий товар
    :param doc_notes: примечание к складской накладной
    :return: проведенный WarehouseDocument (RECEIPT)
    """
    po = PurchaseOrder.objects.select_for_update().get(pk=purchase_order.pk)

    if po.status not in [PurchaseOrderStatus.SENT, PurchaseOrderStatus.PARTIALLY_RECEIVED]:
        raise ValidationError(
            f'Невозможно принять поставку: заказ {po.order_number} находится в статусе "{po.get_status_display()}".'
        )

    wh1 = Warehouse.objects.filter(warehouse_type=WarehouseType.RAW_MATERIALS).first()
    if not wh1:
        raise ValidationError('Склад сырья WH-1 (RAW_MATERIALS) не найден в системе.')

    # Проверка позиций
    items_to_process = []
    total_received_amount = Decimal('0.00')

    for item_id, qty_raw in received_items_map.items():
        try:
            qty = Decimal(str(qty_raw))
        except Exception:
            continue

        if qty <= Decimal('0'):
            continue

        po_item = po.items.select_for_update().filter(id=item_id).first()
        if not po_item:
            continue

        rem = po_item.remaining_quantity
        if qty > rem:
            raise ValidationError(
                f'Нельзя принять {qty} {po_item.material.unit} материала "{po_item.material.name}". '
                f'Осталось принять по заказу: {rem} {po_item.material.unit}.'
            )

        line_total = (qty * po_item.unit_price_kzt).quantize(Decimal('0.01'))
        total_received_amount += line_total
        items_to_process.append((po_item, qty, line_total))

    if not items_to_process:
        raise ValidationError('Не указано ни одно положительное количество материала для оприходования.')

    # Формируем складской документ поступления
    doc_number = generate_doc_number(WarehouseDocumentType.RECEIPT)
    receipt_doc = WarehouseDocument.objects.create(
        doc_number=doc_number,
        doc_type=WarehouseDocumentType.RECEIPT,
        status=DocumentStatus.DRAFT,
        warehouse=wh1,
        doc_date=timezone.localdate(),
        created_by=user,
        supplier=po.supplier,
        purchase_order=po,
        total_amount_kzt=total_received_amount,
        notes=f'Поступление по заказу {po.order_number}. {doc_notes}'.strip(),
    )

    for po_item, qty, line_total in items_to_process:
        WarehouseDocumentItem.objects.create(
            document=receipt_doc,
            material=po_item.material,
            quantity=qty,
            unit=po_item.material.unit,
            unit_cost_kzt=po_item.unit_price_kzt,
            total_cost_kzt=line_total,
            notes=f'Заказ {po.order_number}',
        )
        # Увеличиваем фактически принятое количество в строке заказа
        po_item.received_quantity += qty
        po_item.save(update_fields=['received_quantity'])

    # Проводим складской документ через существующий складской сервис
    post_document(receipt_doc, user=user)
    receipt_doc.refresh_from_db()

    # Обновляем статус заказа поставщику
    po.update_totals_and_status()

    # Уведомляем менеджеров
    try:
        notify_supplier_receipt(po, receipt_doc)
    except Exception:
        pass

    AuditLog.objects.create(
        user=user,
        action='POST_RECEIPT',
        entity_type='WarehouseDocument',
        entity_id=str(receipt_doc.id),
        details={
            'doc_number': receipt_doc.doc_number,
            'purchase_order': po.order_number,
            'items_count': len(items_to_process),
            'total_amount': float(total_received_amount),
        },
    )
    return receipt_doc


@transaction.atomic
def cancel_purchase_order(purchase_order: PurchaseOrder, user=None) -> PurchaseOrder:
    """Отмена заказа поставщику, если по нему еще не было приходов."""
    po = PurchaseOrder.objects.select_for_update().get(pk=purchase_order.pk)
    if po.status not in [PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.SENT]:
        raise ValidationError(f'Нельзя отменить заказ в статусе "{po.get_status_display()}".')

    has_receipts = any(it.received_quantity > Decimal('0') for it in po.items.all())
    if has_receipts:
        raise ValidationError('Невозможно отменить заказ: по нему уже зафиксированы частичные поступления материалов.')

    po.status = PurchaseOrderStatus.CANCELLED
    po.save(update_fields=['status', 'updated_at'])

    AuditLog.objects.create(
        user=user,
        action='CANCEL_PURCHASE_ORDER',
        entity_type='PurchaseOrder',
        entity_id=str(po.id),
        details={'event': 'cancelled', 'order_number': po.order_number},
    )
    return po
