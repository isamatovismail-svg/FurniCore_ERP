import uuid
from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.accounts.models import AuditLog, UserRole
from apps.warehouses.models import (
    Warehouse,
    WarehouseType,
    StockBalance,
    StockMovement,
    WarehouseDocument,
    WarehouseDocumentItem,
    WarehouseDocumentType,
    DocumentStatus,
    MovementType,
)


def generate_doc_number(doc_type: str) -> str:
    """Генерация уникального префикса и номера документа."""
    prefixes = {
        WarehouseDocumentType.RECEIPT: 'RCP',
        WarehouseDocumentType.PRODUCTION_ISSUE: 'ISS',
        WarehouseDocumentType.PRODUCTION_RETURN: 'RET-P',
        WarehouseDocumentType.FINISHED_RECEIPT: 'FRCP',
        WarehouseDocumentType.RESERVATION: 'RSV',
        WarehouseDocumentType.UNRESERVATION: 'UNRSV',
        WarehouseDocumentType.SHIPMENT: 'SHP',
        WarehouseDocumentType.CUSTOMER_RETURN: 'RET-C',
        WarehouseDocumentType.INVENTORY: 'INV',
    }
    prefix = prefixes.get(doc_type, 'DOC')
    today_str = timezone.now().strftime('%y%m%d')
    suffix = uuid.uuid4().hex[:6].upper()
    return f'{prefix}-{today_str}-{suffix}'


def generate_movement_number() -> str:
    today_str = timezone.now().strftime('%y%m%d')
    suffix = uuid.uuid4().hex[:6].upper()
    return f'MOV-{today_str}-{suffix}'


def get_or_create_stock_balance(warehouse: Warehouse, material=None, product=None, for_update=False) -> StockBalance:
    """Получить или создать баланс склада с опциональной блокировкой строки."""
    qs = StockBalance.objects
    if for_update:
        qs = qs.select_for_update()

    if material:
        balance, created = qs.get_or_create(
            warehouse=warehouse,
            material=material,
            defaults={'current_stock': Decimal('0.000'), 'reserved_stock': Decimal('0.000')}
        )
    elif product:
        balance, created = qs.get_or_create(
            warehouse=warehouse,
            product=product,
            defaults={'current_stock': Decimal('0.000'), 'reserved_stock': Decimal('0.000')}
        )
    else:
        raise ValidationError('Необходимо указать материал или готовую продукцию.')
    return balance


def post_document(document: WarehouseDocument, user=None) -> WarehouseDocument:
    """
    Транзакционное проведение складского документа с блокировкой остатков (select_for_update).
    Гарантирует:
    - Невозможность повторного проведения (идемпотентность)
    - Невозможность отрицательных остатков
    - Обновление резервов
    - Создание записей в регистре движений StockMovement
    - Запись в журнал аудита AuditLog
    """
    with transaction.atomic():
        # Блокируем сам документ для исключения параллельного двойного проведения
        doc = WarehouseDocument.objects.select_for_update().get(id=document.id)

        if doc.status == DocumentStatus.POSTED:
            raise ValidationError(f'Документ {doc.doc_number} уже был проведён ранее.')
        if doc.status == DocumentStatus.CANCELLED:
            raise ValidationError(f'Нельзя провести отменённый документ {doc.doc_number}.')

        items = list(doc.items.select_related('material', 'product').all())
        if not items:
            raise ValidationError(f'Документ {doc.doc_number} не содержит позиций номенклатуры.')

        warehouse = doc.warehouse

        # Валидация соответствия склада и типа документа
        if doc.doc_type in [
            WarehouseDocumentType.RECEIPT,
            WarehouseDocumentType.PRODUCTION_ISSUE,
            WarehouseDocumentType.PRODUCTION_RETURN
        ] and warehouse.warehouse_type != WarehouseType.RAW_MATERIALS:
            raise ValidationError(
                f'Операция {doc.get_doc_type_display()} допустима только на складе сырья и материалов (WH-1).'
            )

        if doc.doc_type in [
            WarehouseDocumentType.FINISHED_RECEIPT,
            WarehouseDocumentType.RESERVATION,
            WarehouseDocumentType.UNRESERVATION,
            WarehouseDocumentType.SHIPMENT,
            WarehouseDocumentType.CUSTOMER_RETURN
        ] and warehouse.warehouse_type != WarehouseType.FINISHED_PRODUCTS:
            raise ValidationError(
                f'Операция {doc.get_doc_type_display()} допустима только на складе готовой продукции (WH-2).'
            )

        total_amount = Decimal('0.00')

        # Обработка позиций по типам документов
        for item in items:
            qty = Decimal(str(item.quantity))
            if qty <= 0 and doc.doc_type != WarehouseDocumentType.INVENTORY:
                raise ValidationError(f'Количество позиции должно быть строго больше 0: {item}')

            item_cost = Decimal(str(item.unit_cost_kzt or '0.00'))
            item.total_cost_kzt = (qty * item_cost).quantize(Decimal('0.01'))
            item.save(update_fields=['total_cost_kzt'])
            total_amount += item.total_cost_kzt

            # 1. Приход материалов (WH-1)
            if doc.doc_type == WarehouseDocumentType.RECEIPT:
                if not item.material:
                    raise ValidationError('В строке прихода на WH-1 должен быть указан материал.')
                balance = get_or_create_stock_balance(warehouse, material=item.material, for_update=True)
                balance.current_stock += qty
                balance.save(update_fields=['current_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.RECEIPT,
                    warehouse=warehouse,
                    document=doc,
                    material=item.material,
                    quantity=qty,
                    unit=item.unit or item.material.unit,
                    unit_cost_kzt=item_cost,
                    total_cost_kzt=item.total_cost_kzt,
                    reference_number=doc.doc_number,
                    notes=f'Приход от поставщика {doc.supplier.name if doc.supplier else "—"}',
                    performed_by=user,
                )

            # 2. Отпуск сырья в цех (WH-1)
            elif doc.doc_type == WarehouseDocumentType.PRODUCTION_ISSUE:
                if not item.material:
                    raise ValidationError('В строке отпуска сырья должен быть указан материал.')
                balance = get_or_create_stock_balance(warehouse, material=item.material, for_update=True)
                if balance.current_stock < qty:
                    raise ValidationError(
                        f'Недостаточно материала "{item.material.name}" на складе WH-1. '
                        f'В наличии: {balance.current_stock} {item.unit}, запрошено: {qty} {item.unit}.'
                    )
                balance.current_stock -= qty
                balance.save(update_fields=['current_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.ISSUE,
                    warehouse=warehouse,
                    document=doc,
                    material=item.material,
                    quantity=qty,
                    unit=item.unit or item.material.unit,
                    unit_cost_kzt=item_cost,
                    total_cost_kzt=item.total_cost_kzt,
                    reference_number=doc.doc_number,
                    notes=f'Отпуск в цех под заказ {doc.production_order.order_number if doc.production_order else "—"}',
                    performed_by=user,
                )

            # 3. Возврат материалов из цеха (WH-1)
            elif doc.doc_type == WarehouseDocumentType.PRODUCTION_RETURN:
                if not item.material:
                    raise ValidationError('В строке возврата должен быть указан материал.')
                balance = get_or_create_stock_balance(warehouse, material=item.material, for_update=True)
                balance.current_stock += qty
                balance.save(update_fields=['current_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.PRODUCTION_RETURN,
                    warehouse=warehouse,
                    document=doc,
                    material=item.material,
                    quantity=qty,
                    unit=item.unit or item.material.unit,
                    unit_cost_kzt=item_cost,
                    total_cost_kzt=item.total_cost_kzt,
                    reference_number=doc.doc_number,
                    notes=f'Возврат из цеха: заказ {doc.production_order.order_number if doc.production_order else "—"}',
                    performed_by=user,
                )

            # 4. Приёмка готовой продукции из цеха (WH-2)
            elif doc.doc_type == WarehouseDocumentType.FINISHED_RECEIPT:
                if not item.product:
                    raise ValidationError('В строке приёмки готовой мебели должно быть указано изделие.')
                balance = get_or_create_stock_balance(warehouse, product=item.product, for_update=True)
                balance.current_stock += qty
                balance.save(update_fields=['current_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.FINISHED_RECEIPT,
                    warehouse=warehouse,
                    document=doc,
                    product=item.product,
                    quantity=qty,
                    unit=item.unit,
                    unit_cost_kzt=item_cost,
                    total_cost_kzt=item.total_cost_kzt,
                    reference_number=doc.doc_number,
                    notes=f'Приёмка из цеха (ОТК пройден): заказ {doc.production_order.order_number if doc.production_order else "—"}',
                    performed_by=user,
                )

            # 5. Резервирование под клиентский заказ (WH-2)
            elif doc.doc_type == WarehouseDocumentType.RESERVATION:
                if not item.product:
                    raise ValidationError('В строке резервирования должно быть указано изделие.')
                balance = get_or_create_stock_balance(warehouse, product=item.product, for_update=True)
                if balance.available_stock < qty:
                    raise ValidationError(
                        f'Недостаточно свободной мебели "{item.product.name}" на складе WH-2 для резервирования. '
                        f'Свободно: {balance.available_stock} {item.unit}, требуется: {qty} {item.unit}.'
                    )
                balance.reserved_stock += qty
                balance.save(update_fields=['reserved_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.RESERVATION,
                    warehouse=warehouse,
                    document=doc,
                    product=item.product,
                    quantity=qty,
                    unit=item.unit,
                    unit_cost_kzt=item_cost,
                    total_cost_kzt=item.total_cost_kzt,
                    reference_number=doc.doc_number,
                    notes=f'Резерв под заказ клиента {doc.customer.name if doc.customer else "—"}',
                    performed_by=user,
                )

            # 6. Снятие с резерва (WH-2)
            elif doc.doc_type == WarehouseDocumentType.UNRESERVATION:
                if not item.product:
                    raise ValidationError('В строке снятия с резерва должно быть указано изделие.')
                balance = get_or_create_stock_balance(warehouse, product=item.product, for_update=True)
                if balance.reserved_stock < qty:
                    raise ValidationError(
                        f'Невозможно снять с резерва {qty} {item.unit} изделия "{item.product.name}": '
                        f'в резерве числится только {balance.reserved_stock} {item.unit}.'
                    )
                balance.reserved_stock -= qty
                balance.save(update_fields=['reserved_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.UNRESERVATION,
                    warehouse=warehouse,
                    document=doc,
                    product=item.product,
                    quantity=qty,
                    unit=item.unit,
                    unit_cost_kzt=item_cost,
                    total_cost_kzt=item.total_cost_kzt,
                    reference_number=doc.doc_number,
                    notes=f'Снятие с резерва: заказ {doc.sales_order.order_number if doc.sales_order else "—"}',
                    performed_by=user,
                )

            # 7. Отгрузка клиенту (WH-2)
            elif doc.doc_type == WarehouseDocumentType.SHIPMENT:
                if not item.product:
                    raise ValidationError('В строке отгрузки должно быть указано изделие.')
                balance = get_or_create_stock_balance(warehouse, product=item.product, for_update=True)
                if balance.current_stock < qty:
                    raise ValidationError(
                        f'Недостаточно готовой мебели "{item.product.name}" на складе WH-2. '
                        f'В наличии: {balance.current_stock} {item.unit}, к отгрузке: {qty} {item.unit}.'
                    )
                balance.current_stock -= qty
                # Если отгружается из резерва, уменьшаем также reserved_stock
                if balance.reserved_stock > Decimal('0'):
                    reserved_reduction = min(balance.reserved_stock, qty)
                    balance.reserved_stock -= reserved_reduction

                balance.save(update_fields=['current_stock', 'reserved_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.SHIPMENT,
                    warehouse=warehouse,
                    document=doc,
                    product=item.product,
                    quantity=qty,
                    unit=item.unit,
                    unit_cost_kzt=item_cost,
                    total_cost_kzt=item.total_cost_kzt,
                    reference_number=doc.doc_number,
                    notes=f'Отгрузка клиенту {doc.customer.name if doc.customer else "—"} по накладной {doc.doc_number}',
                    performed_by=user,
                )

            # 8. Возврат готового изделия от клиента (WH-2)
            elif doc.doc_type == WarehouseDocumentType.CUSTOMER_RETURN:
                if not item.product:
                    raise ValidationError('В строке возврата должно быть указано изделие.')
                balance = get_or_create_stock_balance(warehouse, product=item.product, for_update=True)
                balance.current_stock += qty
                balance.save(update_fields=['current_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.CUSTOMER_RETURN,
                    warehouse=warehouse,
                    document=doc,
                    product=item.product,
                    quantity=qty,
                    unit=item.unit,
                    unit_cost_kzt=item_cost,
                    total_cost_kzt=item.total_cost_kzt,
                    reference_number=doc.doc_number,
                    notes=f'Возврат от клиента {doc.customer.name if doc.customer else "—"}',
                    performed_by=user,
                )

            # 9. Акт инвентаризации (WH-1 или WH-2)
            elif doc.doc_type == WarehouseDocumentType.INVENTORY:
                if item.actual_quantity is None:
                    raise ValidationError(f'Не заполнено фактическое количество в строке: {item}')

                actual = Decimal(str(item.actual_quantity))
                if warehouse.warehouse_type == WarehouseType.RAW_MATERIALS:
                    if not item.material:
                        raise ValidationError('В строке инвентаризации WH-1 должен быть указан материал.')
                    balance = get_or_create_stock_balance(warehouse, material=item.material, for_update=True)
                    recorded = balance.current_stock
                    diff = actual - recorded
                    item.discrepancy_quantity = diff
                    item.save(update_fields=['discrepancy_quantity'])

                    balance.current_stock = actual
                    balance.last_counted_at = timezone.now()
                    balance.save(update_fields=['current_stock', 'last_counted_at', 'updated_at'])

                    if diff != Decimal('0'):
                        StockMovement.objects.create(
                            movement_number=generate_movement_number(),
                            movement_type=MovementType.ADJUSTMENT,
                            warehouse=warehouse,
                            document=doc,
                            material=item.material,
                            quantity=abs(diff),
                            unit=item.unit or item.material.unit,
                            unit_cost_kzt=item_cost,
                            total_cost_kzt=(abs(diff) * item_cost).quantize(Decimal('0.01')),
                            reference_number=doc.doc_number,
                            notes=f'Инвентаризация {doc.doc_number}: {"Излишек" if diff > 0 else "Недостача"} {diff:+0.3f}',
                            performed_by=user,
                        )
                else:
                    if not item.product:
                        raise ValidationError('В строке инвентаризации WH-2 должно быть указано изделие.')
                    balance = get_or_create_stock_balance(warehouse, product=item.product, for_update=True)
                    recorded = balance.current_stock
                    diff = actual - recorded
                    item.discrepancy_quantity = diff
                    item.save(update_fields=['discrepancy_quantity'])

                    balance.current_stock = actual
                    balance.last_counted_at = timezone.now()
                    balance.save(update_fields=['current_stock', 'last_counted_at', 'updated_at'])

                    if diff != Decimal('0'):
                        StockMovement.objects.create(
                            movement_number=generate_movement_number(),
                            movement_type=MovementType.ADJUSTMENT,
                            warehouse=warehouse,
                            document=doc,
                            product=item.product,
                            quantity=abs(diff),
                            unit=item.unit,
                            unit_cost_kzt=item_cost,
                            total_cost_kzt=(abs(diff) * item_cost).quantize(Decimal('0.01')),
                            reference_number=doc.doc_number,
                            notes=f'Инвентаризация {doc.doc_number}: {"Излишек" if diff > 0 else "Недостача"} {diff:+0.3f}',
                            performed_by=user,
                        )

        doc.status = DocumentStatus.POSTED
        doc.posted_by = user
        doc.posted_at = timezone.now()
        doc.total_amount_kzt = total_amount
        doc.save(update_fields=['status', 'posted_by', 'posted_at', 'total_amount_kzt', 'updated_at'])

        AuditLog.objects.create(
            user=user,
            action=f'POST_{doc.doc_type}',
            entity_type='WarehouseDocument',
            entity_id=str(doc.id),
            details={
                'doc_number': doc.doc_number,
                'doc_type': doc.doc_type,
                'warehouse': doc.warehouse.code,
                'items_count': len(items),
                'total_amount_kzt': str(doc.total_amount_kzt),
            }
        )

        return doc


def cancel_document(document: WarehouseDocument, user=None) -> WarehouseDocument:
    """
    Транзакционная отмена (сторно) проведённого складского документа с компенсационными проводками.
    Гарантирует:
    - Отмена только статуса POSTED
    - Проверку достаточного остатка при отмене прихода (нельзя уйти в минус)
    - Создание обратных сторнирующих движений
    - Запись в журнал аудита
    """
    with transaction.atomic():
        doc = WarehouseDocument.objects.select_for_update().get(id=document.id)

        if doc.status != DocumentStatus.POSTED:
            raise ValidationError(f'Отменить можно только проведённый документ. Текущий статус: {doc.get_status_display()}')

        items = list(doc.items.select_related('material', 'product').all())
        warehouse = doc.warehouse

        for item in items:
            qty = Decimal(str(item.quantity))

            # Отмена приходов (RECEIPT, PRODUCTION_RETURN, FINISHED_RECEIPT, CUSTOMER_RETURN) -> Уменьшаем текущий остаток
            if doc.doc_type in [
                WarehouseDocumentType.RECEIPT,
                WarehouseDocumentType.PRODUCTION_RETURN,
            ]:
                balance = get_or_create_stock_balance(warehouse, material=item.material, for_update=True)
                if balance.current_stock < qty:
                    raise ValidationError(
                        f'Невозможно отменить документ {doc.doc_number}: материал "{item.material.name}" '
                        f'уже израсходован. Текущий остаток: {balance.current_stock}, требуется для отмены: {qty}.'
                    )
                balance.current_stock -= qty
                balance.save(update_fields=['current_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.ADJUSTMENT,
                    warehouse=warehouse,
                    document=doc,
                    material=item.material,
                    quantity=qty,
                    unit=item.unit,
                    unit_cost_kzt=item.unit_cost_kzt,
                    total_cost_kzt=item.total_cost_kzt,
                    reference_number=f'СТОPНО-{doc.doc_number}',
                    notes=f'Компенсация (сторно прихода) при отмене документа {doc.doc_number}',
                    performed_by=user,
                )

            elif doc.doc_type in [
                WarehouseDocumentType.FINISHED_RECEIPT,
                WarehouseDocumentType.CUSTOMER_RETURN,
            ]:
                balance = get_or_create_stock_balance(warehouse, product=item.product, for_update=True)
                if balance.current_stock < qty:
                    raise ValidationError(
                        f'Невозможно отменить документ {doc.doc_number}: изделие "{item.product.name}" '
                        f'уже отгружено или зарезервировано. Остаток: {balance.current_stock}, требуется: {qty}.'
                    )
                balance.current_stock -= qty
                balance.save(update_fields=['current_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.ADJUSTMENT,
                    warehouse=warehouse,
                    document=doc,
                    product=item.product,
                    quantity=qty,
                    unit=item.unit,
                    unit_cost_kzt=item.unit_cost_kzt,
                    total_cost_kzt=item.total_cost_kzt,
                    reference_number=f'СТОРНО-{doc.doc_number}',
                    notes=f'Компенсация (сторно приёмки) при отмене документа {doc.doc_number}',
                    performed_by=user,
                )

            # Отмена расходов (PRODUCTION_ISSUE, SHIPMENT) -> Возвращаем на баланс
            elif doc.doc_type == WarehouseDocumentType.PRODUCTION_ISSUE:
                balance = get_or_create_stock_balance(warehouse, material=item.material, for_update=True)
                balance.current_stock += qty
                balance.save(update_fields=['current_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.ADJUSTMENT,
                    warehouse=warehouse,
                    document=doc,
                    material=item.material,
                    quantity=qty,
                    unit=item.unit,
                    unit_cost_kzt=item.unit_cost_kzt,
                    total_cost_kzt=item.total_cost_kzt,
                    reference_number=f'СТОРНО-{doc.doc_number}',
                    notes=f'Компенсация (возврат списания) при отмене документа {doc.doc_number}',
                    performed_by=user,
                )

            elif doc.doc_type == WarehouseDocumentType.SHIPMENT:
                balance = get_or_create_stock_balance(warehouse, product=item.product, for_update=True)
                balance.current_stock += qty
                balance.save(update_fields=['current_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.ADJUSTMENT,
                    warehouse=warehouse,
                    document=doc,
                    product=item.product,
                    quantity=qty,
                    unit=item.unit,
                    unit_cost_kzt=item.unit_cost_kzt,
                    total_cost_kzt=item.total_cost_kzt,
                    reference_number=f'СТОРНО-{doc.doc_number}',
                    notes=f'Компенсация (возврат отгрузки) при отмене документа {doc.doc_number}',
                    performed_by=user,
                )

            # Отмена резерва (RESERVATION) -> Освобождаем резерв
            elif doc.doc_type == WarehouseDocumentType.RESERVATION:
                balance = get_or_create_stock_balance(warehouse, product=item.product, for_update=True)
                if balance.reserved_stock < qty:
                    raise ValidationError('Нельзя отменить резервирование: в резерве числится меньше товара.')
                balance.reserved_stock -= qty
                balance.save(update_fields=['reserved_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.UNRESERVATION,
                    warehouse=warehouse,
                    document=doc,
                    product=item.product,
                    quantity=qty,
                    unit=item.unit,
                    reference_number=f'СТОРНО-{doc.doc_number}',
                    notes=f'Снятие резерва при отмене документа {doc.doc_number}',
                    performed_by=user,
                )

            # Отмена снятия с резерва (UNRESERVATION) -> Возвращаем в резерв
            elif doc.doc_type == WarehouseDocumentType.UNRESERVATION:
                balance = get_or_create_stock_balance(warehouse, product=item.product, for_update=True)
                if balance.available_stock < qty:
                    raise ValidationError('Недостаточно свободной продукции для восстановления резерва.')
                balance.reserved_stock += qty
                balance.save(update_fields=['reserved_stock', 'updated_at'])

                StockMovement.objects.create(
                    movement_number=generate_movement_number(),
                    movement_type=MovementType.RESERVATION,
                    warehouse=warehouse,
                    document=doc,
                    product=item.product,
                    quantity=qty,
                    unit=item.unit,
                    reference_number=f'СТОРНО-{doc.doc_number}',
                    notes=f'Восстановление резерва при отмене документа {doc.doc_number}',
                    performed_by=user,
                )

            # Отмена инвентаризации -> Откатываем расхождения
            elif doc.doc_type == WarehouseDocumentType.INVENTORY:
                diff = Decimal(str(item.discrepancy_quantity or '0.000'))
                if warehouse.warehouse_type == WarehouseType.RAW_MATERIALS:
                    balance = get_or_create_stock_balance(warehouse, material=item.material, for_update=True)
                    if balance.current_stock - diff < 0:
                        raise ValidationError(
                            f'Невозможно отменить инвентаризацию: расчетный остаток материала {item.material.name} '
                            f'уйдёт в минус ({balance.current_stock - diff}).'
                        )
                    balance.current_stock -= diff
                    balance.save(update_fields=['current_stock', 'updated_at'])
                else:
                    balance = get_or_create_stock_balance(warehouse, product=item.product, for_update=True)
                    if balance.current_stock - diff < 0:
                        raise ValidationError(
                            f'Невозможно отменить инвентаризацию: расчетный остаток изделия {item.product.name} '
                            f'уйдёт в минус ({balance.current_stock - diff}).'
                        )
                    balance.current_stock -= diff
                    balance.save(update_fields=['current_stock', 'updated_at'])

        doc.status = DocumentStatus.CANCELLED
        doc.cancelled_at = timezone.now()
        doc.save(update_fields=['status', 'cancelled_at', 'updated_at'])

        AuditLog.objects.create(
            user=user,
            action=f'CANCEL_{doc.doc_type}',
            entity_type='WarehouseDocument',
            entity_id=str(doc.id),
            details={
                'doc_number': doc.doc_number,
                'doc_type': doc.doc_type,
                'warehouse': doc.warehouse.code,
                'cancelled_at': doc.cancelled_at.isoformat(),
            }
        )

        return doc


def create_inventory_sheet(warehouse: Warehouse, user=None, notes: str = '') -> WarehouseDocument:
    """
    Создаёт черновик акта инвентаризации с заполнением текущих учётных остатков всех позиций склада.
    """
    with transaction.atomic():
        doc_number = generate_doc_number(WarehouseDocumentType.INVENTORY)
        doc = WarehouseDocument.objects.create(
            doc_number=doc_number,
            doc_type=WarehouseDocumentType.INVENTORY,
            status=DocumentStatus.DRAFT,
            warehouse=warehouse,
            created_by=user,
            notes=notes or f'Инвентаризационная ведомость остатков {warehouse.name}',
        )

        balances = StockBalance.objects.filter(warehouse=warehouse).select_related('material', 'product')

        for b in balances:
            if warehouse.warehouse_type == WarehouseType.RAW_MATERIALS and b.material:
                WarehouseDocumentItem.objects.create(
                    document=doc,
                    material=b.material,
                    quantity=b.current_stock,  # Учётное количество на момент старта инвентаризации
                    unit=b.material.unit,
                    unit_cost_kzt=b.material.purchase_cost_kzt,
                    actual_quantity=b.current_stock,  # По умолчанию равно учетному до ручной проверки
                    discrepancy_quantity=Decimal('0.000'),
                )
            elif warehouse.warehouse_type == WarehouseType.FINISHED_PRODUCTS and b.product:
                WarehouseDocumentItem.objects.create(
                    document=doc,
                    product=b.product,
                    quantity=b.current_stock,
                    unit='шт',
                    unit_cost_kzt=b.product.production_cost_kzt,
                    actual_quantity=b.current_stock,
                    discrepancy_quantity=Decimal('0.000'),
                )

        return doc
