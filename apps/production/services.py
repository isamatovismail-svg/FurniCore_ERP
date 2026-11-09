import uuid
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.accounts.models import AuditLog, UserRole
from apps.warehouses.models import (
    Warehouse,
    WarehouseType,
    StockBalance,
    WarehouseDocument,
    WarehouseDocumentItem,
    WarehouseDocumentType,
    DocumentStatus,
)
from apps.warehouses.services import post_document, generate_doc_number
from apps.production.models import (
    ProductionOrder,
    ProductionOrderStatus,
    ProductionStage,
    StageStatus,
    BOM,
    BOMItem,
    MaterialConsumption,
    ProductionWaste,
    WasteType,
    RoutingTemplate,
    RoutingStage,
)
from apps.quality.models import QualityCheck, QCResult


# Стандартные технологические маршруты по умолчанию для мебельных категорий
DEFAULT_CATEGORY_ROUTES = {
    'WARDROBE': [
        ('Раскрой плит ЛДСП', 'Раскроечный центр ЧПУ', Decimal('2.00')),
        ('Присадка отверстий под фурнитуру', 'Сверлильно-присадочный станок', Decimal('1.50')),
        ('Кромкооблицовка ПВХ', 'Кромкооблицовочный станок', Decimal('1.50')),
        ('Предварительная сборка корпуса', 'Сборочный участок', Decimal('2.00')),
        ('Монтаж фурнитуры и фасадов', 'Сборочный участок', Decimal('1.50')),
        ('Контроль качества (ОТК)', 'Участок ОТК и упаковки', Decimal('0.50')),
    ],
    'KITCHEN': [
        ('Раскрой корпусов ЛДСП', 'Форматно-раскроечный станок', Decimal('3.00')),
        ('Фрезеровка МДФ фасадов', 'Фрезерный центр ЧПУ', Decimal('3.00')),
        ('Кромление и шлифовка', 'Кромочный участок', Decimal('2.00')),
        ('Покраска / эмалировка фасадов', 'Малярная камера', Decimal('4.00')),
        ('Сборка кухонных модулей', 'Сборочный цех', Decimal('3.00')),
        ('Монтаж петель и выдвижных систем', 'Сборочный цех', Decimal('2.00')),
        ('Финальная подгонка и ОТК', 'Участок ОТК', Decimal('1.00')),
    ],
    'SOFA': [
        ('Раскрой массива бруса и фанеры', 'Столярный участок', Decimal('2.50')),
        ('Сборка несущего каркаса', 'Каркасный участок', Decimal('2.50')),
        ('Настил пружин и поролона (ППУ)', 'Обивочный цех', Decimal('2.00')),
        ('Раскрой обивочного текстиля/велюра', 'Раскройный стол', Decimal('1.50')),
        ('Обивка и стяжка мебели', 'Обивочный участок', Decimal('3.00')),
        ('Финальный контроль ОТК', 'Участок ОТК', Decimal('0.50')),
    ],
    'TABLE': [
        ('Раскрой столешницы', 'Форматно-раскроечный станок', Decimal('1.50')),
        ('Фрезеровка и обработка кромки', 'Фрезерный станок', Decimal('1.00')),
        ('Сборка металлического/деревянного подстолья', 'Сборочный цех', Decimal('1.50')),
        ('Шлифовка и защитная лакировка', 'Лакокрасочный участок', Decimal('2.00')),
        ('Контроль качества ОТК', 'Участок ОТК', Decimal('0.50')),
    ],
    'BED': [
        ('Раскрой царг и изголовья', 'Раскроечный станок', Decimal('2.00')),
        ('Шлифовка деревянных элементов', 'Шлифовальный участок', Decimal('1.50')),
        ('Сборка силового каркаса', 'Сборочный цех', Decimal('2.00')),
        ('Обивка изголовья / отделка', 'Обивочный/Малярный участок', Decimal('2.50')),
        ('Контроль качества ОТК', 'Участок ОТК', Decimal('0.50')),
    ],
    'OTHER': [
        ('Раскрой заготовок', 'Раскроечный участок', Decimal('2.00')),
        ('Механическая обработка', 'Станочный участок', Decimal('2.00')),
        ('Сборка изделия', 'Сборочный цех', Decimal('2.00')),
        ('Контроль качества (ОТК)', 'Участок ОТК', Decimal('0.50')),
    ]
}


def ensure_default_routing_templates():
    """Гарантирует наличие базовых технологических маршрутов в БД."""
    for cat, steps in DEFAULT_CATEGORY_ROUTES.items():
        name = f"Типовой маршрут: {dict(RoutingTemplate._meta.get_field('category').choices).get(cat, cat)}"
        tmpl, created = RoutingTemplate.objects.get_or_create(
            category=cat,
            is_default=True,
            defaults={'name': name, 'description': f'Стандартная технологическая цепочка операций для категории {cat}'}
        )
        if created or not tmpl.stages.exists():
            for idx, (s_name, w_station, s_hours) in enumerate(steps, start=1):
                RoutingStage.objects.get_or_create(
                    template=tmpl,
                    sequence=idx,
                    defaults={'name': s_name, 'workstation': w_station, 'standard_hours': s_hours}
                )


def check_materials_availability(order: ProductionOrder) -> dict:
    """
    Расчёт материальной потребности по технологической карте (BOM)
    и проверка физических остатков на Складе №1 (WH-1).
    """
    wh1 = Warehouse.objects.filter(warehouse_type=WarehouseType.RAW_MATERIALS).first()
    if not wh1:
        raise ValidationError('Склад сырья и материалов (WH-1) не найден в системе.')

    if not order.bom:
        return {
            'can_launch': False,
            'reason': 'Для заказа не выбрана технологическая карта (BOM).',
            'items': [],
            'total_deficit_count': 0,
            'planned_materials_cost': Decimal('0.00'),
        }

    bom_items = order.bom.items.select_related('material').all()
    batch_multiplier = Decimal(str(order.quantity_planned))

    items_analysis = []
    total_deficit_count = 0
    total_planned_cost = Decimal('0.00')

    # Словарь текущих остатков на WH-1
    balances_map = {
        b.material_id: b.current_stock
        for b in StockBalance.objects.filter(warehouse=wh1, material__isnull=False)
    }

    for item in bom_items:
        mat = item.material
        waste_coeff = Decimal('1.00') + (item.waste_percent / Decimal('100.00'))
        single_unit_need = (item.quantity_planned * waste_coeff).quantize(Decimal('0.001'))
        total_required = (single_unit_need * batch_multiplier).quantize(Decimal('0.001'))

        current_stock = balances_map.get(mat.id, Decimal('0.000'))
        deficit = max(Decimal('0.000'), total_required - current_stock)
        is_available = (current_stock >= total_required)

        if not is_available:
            total_deficit_count += 1

        unit_cost = mat.purchase_cost_kzt or Decimal('0.00')
        item_cost = (total_required * unit_cost).quantize(Decimal('0.01'))
        total_planned_cost += item_cost

        items_analysis.append({
            'material': mat,
            'sku': mat.sku,
            'name': mat.name,
            'unit': item.unit,
            'waste_percent': item.waste_percent,
            'norm_per_unit': item.quantity_planned,
            'total_required': total_required,
            'current_stock': current_stock,
            'deficit': deficit,
            'is_available': is_available,
            'unit_cost_kzt': unit_cost,
            'total_cost_kzt': item_cost,
            'location': mat.location or 'WH-1',
        })

    can_launch = (total_deficit_count == 0)

    return {
        'can_launch': can_launch,
        'items': items_analysis,
        'total_deficit_count': total_deficit_count,
        'planned_materials_cost': total_planned_cost,
    }


def initialize_order_stages(order: ProductionOrder):
    """Инициализация технологических этапов заказа из маршрута BOM или шаблона категории."""
    if order.stages.exists():
        return

    stages_source = []
    if order.bom and order.bom.routing_template:
        stages_source = [
            (s.name, s.workstation, s.standard_hours)
            for s in order.bom.routing_template.stages.order_by('sequence')
        ]

    if not stages_source:
        ensure_default_routing_templates()
        cat = order.product.category if order.product else 'OTHER'
        stages_source = DEFAULT_CATEGORY_ROUTES.get(cat, DEFAULT_CATEGORY_ROUTES['OTHER'])

    batch_qty = order.quantity_planned or Decimal('1.00')

    for idx, (name, workstation, std_h) in enumerate(stages_source, start=1):
        # Плановое время масштабируется пропорционально объёму партии
        batch_hours = (std_h * batch_qty).quantize(Decimal('0.01'))
        ProductionStage.objects.create(
            production_order=order,
            sequence=idx,
            stage_name=name,
            workstation=workstation,
            status=StageStatus.PENDING,
            planned_hours=batch_hours,
            assigned_employee=order.assigned_master,
        )


def issue_materials_for_production(order: ProductionOrder, user=None) -> WarehouseDocument:
    """
    Выдача сырья и фурнитуры со склада WH-1 под производственный заказ.
    - Проверяет наличие всех материалов
    - Оформляет официальный документ PRODUCTION_ISSUE через warehouse service
    - Проводит списание с row-level locking
    - Фиксирует плановый/фактический расход в MaterialConsumption
    - Защищает от повторного списания
    """
    with transaction.atomic():
        ord_locked = ProductionOrder.objects.select_for_update().get(id=order.id)

        if ord_locked.is_materials_issued:
            raise ValidationError(f'Материалы для заказа {ord_locked.order_number} уже были выданы ранее.')

        analysis = check_materials_availability(ord_locked)
        if not analysis['can_launch']:
            missing_names = [i['name'] for i in analysis['items'] if not i['is_available']]
            raise ValidationError(
                f'Невозможно выдать сырьё: дефицит {len(missing_names)} позиций на складе WH-1 '
                f'({", ".join(missing_names[:3])}).'
            )

        wh1 = Warehouse.objects.filter(warehouse_type=WarehouseType.RAW_MATERIALS).first()

        # Создание складского документа выдачи в производство (PRODUCTION_ISSUE)
        doc = WarehouseDocument.objects.create(
            doc_number=generate_doc_number(WarehouseDocumentType.PRODUCTION_ISSUE),
            doc_type=WarehouseDocumentType.PRODUCTION_ISSUE,
            status=DocumentStatus.DRAFT,
            warehouse=wh1,
            production_order=ord_locked,
            created_by=user,
            notes=f'Выдача сырья под производственный заказ {ord_locked.order_number} ({ord_locked.product.name} × {ord_locked.quantity_planned} шт)',
        )

        total_doc_cost = Decimal('0.00')

        # Заполнение строк накладной и журнала расхода MaterialConsumption
        for item in analysis['items']:
            mat = item['material']
            qty = item['total_required']
            cost = item['unit_cost_kzt']
            tot = item['total_cost_kzt']
            total_doc_cost += tot

            WarehouseDocumentItem.objects.create(
                document=doc,
                material=mat,
                quantity=qty,
                unit=item['unit'],
                unit_cost_kzt=cost,
                total_cost_kzt=tot,
            )

            # Сохранение расхода в заказ
            MaterialConsumption.objects.update_or_create(
                production_order=ord_locked,
                material=mat,
                defaults={
                    'quantity_planned': qty,
                    'quantity_actual': qty,
                    'unit': item['unit'],
                    'unit_cost_kzt': cost,
                    'cost_kzt': tot,
                }
            )

        doc.total_amount_kzt = total_doc_cost
        doc.save(update_fields=['total_amount_kzt'])

        # Проведение складского документа через проверенный транзакционный сервис
        post_document(doc, user=user)

        # Обновление показателей себестоимости и статуса заказа
        ord_locked.planned_materials_cost_kzt = total_doc_cost
        ord_locked.actual_materials_cost_kzt = total_doc_cost
        ord_locked.status = ProductionOrderStatus.MATERIALS_RESERVED
        ord_locked.save(update_fields=[
            'planned_materials_cost_kzt', 'actual_materials_cost_kzt', 'status', 'updated_at'
        ])

        AuditLog.objects.create(
            user=user,
            action='ISSUE_MATERIALS_TO_PRODUCTION',
            entity_type='ProductionOrder',
            entity_id=str(ord_locked.id),
            details={
                'order_number': ord_locked.order_number,
                'doc_number': doc.doc_number,
                'items_count': len(analysis['items']),
                'total_cost_kzt': str(total_doc_cost),
            }
        )

        return doc


def launch_production_order(order: ProductionOrder, user=None):
    """
    Запуск производственного заказа в работу цеха.
    - Выдаёт материалы со склада WH-1 (если ещё не выданы)
    - Инициализирует цепочку этапов
    - Активирует первый технологический этап
    - Переводит заказ в статус IN_PROGRESS
    """
    with transaction.atomic():
        ord_locked = ProductionOrder.objects.select_for_update().get(id=order.id)

        if ord_locked.status in [ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CANCELLED]:
            raise ValidationError(f'Нельзя запустить заказ в статусе {ord_locked.get_status_display()}.')

        # Если материалы ещё не выданы со склада — выдаём
        if not ord_locked.is_materials_issued:
            issue_materials_for_production(ord_locked, user=user)

        # Создаём этапы маршрута
        initialize_order_stages(ord_locked)

        # Активируем первый этап
        first_stage = ord_locked.stages.order_by('sequence').first()
        if first_stage and first_stage.status == StageStatus.PENDING:
            first_stage.status = StageStatus.IN_PROGRESS
            first_stage.started_at = timezone.now()
            first_stage.save(update_fields=['status', 'started_at'])

        ord_locked.status = ProductionOrderStatus.IN_PROGRESS
        if not ord_locked.actual_start:
            ord_locked.actual_start = timezone.localdate()

        # Расчёт плановой себестоимости заказа
        recalculate_order_costs(ord_locked)
        ord_locked.save(update_fields=['status', 'actual_start', 'updated_at'])

        AuditLog.objects.create(
            user=user,
            action='LAUNCH_PRODUCTION_ORDER',
            entity_type='ProductionOrder',
            entity_id=str(ord_locked.id),
            details={'order_number': ord_locked.order_number, 'status': ord_locked.status}
        )

        return ord_locked


def advance_stage(stage: ProductionStage, user=None, actual_hours=None, quantity_processed=None, notes: str = '') -> ProductionOrder:
    """
    Фиксация завершения текущего этапа и автоматический перевод заказа на следующий этап маршрута.
    Если завершён последний производственный этап — передаёт партию в ОТК (QC_CHECK).
    """
    with transaction.atomic():
        st = ProductionStage.objects.select_for_update().get(id=stage.id)
        order = ProductionOrder.objects.select_for_update().get(id=st.production_order_id)

        # Завершение текущего этапа
        st.status = StageStatus.DONE
        if not st.started_at:
            st.started_at = timezone.now()
        st.finished_at = timezone.now()

        if actual_hours is not None:
            st.actual_hours = Decimal(str(actual_hours))
        elif st.actual_hours == Decimal('0.00'):
            st.actual_hours = st.planned_hours  # По умолчанию план

        if quantity_processed is not None:
            st.quantity_processed = Decimal(str(quantity_processed))
        else:
            st.quantity_processed = order.quantity_planned

        if notes:
            st.notes = notes

        st.save(update_fields=['status', 'started_at', 'finished_at', 'actual_hours', 'quantity_processed', 'notes'])

        # Поиск следующего этапа
        next_stage = order.stages.filter(sequence__gt=st.sequence).order_by('sequence').first()

        if next_stage:
            next_stage.status = StageStatus.IN_PROGRESS
            next_stage.started_at = timezone.now()
            next_stage.save(update_fields=['status', 'started_at'])
            order.status = ProductionOrderStatus.IN_PROGRESS
        else:
            # Все технологические операции завершены -> Направляем в отдел технического контроля
            order.status = ProductionOrderStatus.QC_CHECK

        # Пересчёт себестоимости заказа (с учётом факта часов)
        recalculate_order_costs(order)
        order.save(update_fields=['status', 'updated_at'])

        AuditLog.objects.create(
            user=user,
            action='ADVANCE_STAGE',
            entity_type='ProductionStage',
            entity_id=str(st.id),
            details={
                'order_number': order.order_number,
                'completed_stage': st.stage_name,
                'actual_hours': str(st.actual_hours),
                'next_status': order.status,
            }
        )

        return order


def register_waste_or_defect(
    order: ProductionOrder,
    waste_type: str,
    reason: str,
    quantity: Decimal,
    unit: str = 'шт',
    material=None,
    stage: ProductionStage = None,
    cost_kzt: Decimal = None,
    decision: str = '',
    user=None,
) -> ProductionWaste:
    """
    Регистрация отходов производства, исправимого или неисправимого брака.
    При исправимом браке переводит заказ в статус REWORK (Доработка).
    """
    with transaction.atomic():
        ord_locked = ProductionOrder.objects.select_for_update().get(id=order.id)

        if cost_kzt is None:
            if material:
                cost_kzt = (Decimal(str(quantity)) * (material.purchase_cost_kzt or Decimal('0.00'))).quantize(Decimal('0.01'))
            else:
                cost_kzt = Decimal('0.00')

        waste = ProductionWaste.objects.create(
            production_order=ord_locked,
            waste_type=waste_type,
            stage=stage,
            material=material,
            quantity=quantity,
            unit=unit,
            cost_kzt=cost_kzt,
            reason=reason,
            decision=decision or ('Направлено на исправление' if waste_type == WasteType.REWORKABLE_DEFECT else 'Списание в отходы'),
            reported_by=user,
        )

        if waste_type == WasteType.REWORKABLE_DEFECT:
            ord_locked.status = ProductionOrderStatus.REWORK
            if stage:
                stage.status = StageStatus.REWORK
                stage.save(update_fields=['status'])
            ord_locked.save(update_fields=['status', 'updated_at'])

        # Пересчёт себестоимости с учётом брака
        recalculate_order_costs(ord_locked)

        AuditLog.objects.create(
            user=user,
            action=f'REPORT_{waste_type}',
            entity_type='ProductionWaste',
            entity_id=str(waste.id),
            details={
                'order_number': ord_locked.order_number,
                'waste_type': waste_type,
                'quantity': str(quantity),
                'cost_kzt': str(cost_kzt),
            }
        )

        return waste


def submit_quality_check(
    order: ProductionOrder,
    inspector,
    result: str,
    quantity_checked: Decimal,
    quantity_accepted: Decimal,
    quantity_defective: Decimal = Decimal('0.00'),
    check_dimensions: bool = True,
    check_assembly: bool = True,
    check_appearance: bool = True,
    check_coating: bool = True,
    check_completeness: bool = True,
    check_mechanisms: bool = True,
    check_damage_free: bool = True,
    defect_description: str = '',
    rework_instructions: str = '',
    notes: str = '',
) -> QualityCheck:
    """
    Регистрация акта контроля качества (ОТК).
    - При PASS: переводит заказ в статус READY (Готов к приёмке на WH-2), фиксирует годное количество
    - При REWORK: переводит заказ в статус REWORK (На доработку в цех)
    - При FAIL: фиксирует брак
    """
    with transaction.atomic():
        ord_locked = ProductionOrder.objects.select_for_update().get(id=order.id)

        qc = QualityCheck.objects.create(
            production_order=ord_locked,
            checked_by=inspector,
            result=result,
            quantity_checked=quantity_checked,
            quantity_accepted=quantity_accepted,
            quantity_defective=quantity_defective,
            check_dimensions=check_dimensions,
            check_assembly=check_assembly,
            check_appearance=check_appearance,
            check_coating=check_coating,
            check_completeness=check_completeness,
            check_mechanisms=check_mechanisms,
            check_damage_free=check_damage_free,
            defect_description=defect_description,
            rework_instructions=rework_instructions,
            notes=notes,
        )

        if result == QCResult.PASS:
            ord_locked.status = ProductionOrderStatus.READY
            ord_locked.quantity_produced = quantity_accepted
            ord_locked.save(update_fields=['status', 'quantity_produced', 'updated_at'])
        elif result == QCResult.REWORK:
            ord_locked.status = ProductionOrderStatus.REWORK
            ord_locked.save(update_fields=['status', 'updated_at'])
        elif result == QCResult.FAIL:
            ord_locked.status = ProductionOrderStatus.REWORK
            ord_locked.save(update_fields=['status', 'updated_at'])

        AuditLog.objects.create(
            user=inspector,
            action=f'QC_INSPECTION_{result}',
            entity_type='QualityCheck',
            entity_id=str(qc.id),
            details={
                'order_number': ord_locked.order_number,
                'result': result,
                'accepted': str(quantity_accepted),
                'defective': str(quantity_defective),
            }
        )

        return qc


def complete_and_transfer_to_warehouse(order: ProductionOrder, user=None) -> WarehouseDocument:
    """
    Официальная сдача готовой мебели из цеха на Склад готовой продукции (WH-2).
    - Строго контролирует успешное прохождение ОТК (статус READY)
    - Исключает повторную приёмку
    - Создаёт и проводит складской документ FINISHED_RECEIPT на WH-2
    - Переводит заказ в COMPLETED
    - Фиксирует фактическую себестоимость выпуска
    """
    with transaction.atomic():
        ord_locked = ProductionOrder.objects.select_for_update().get(id=order.id)

        if ord_locked.status == ProductionOrderStatus.COMPLETED:
            raise ValidationError(f'Заказ {ord_locked.order_number} уже был сдан на склад ранее.')

        # Проверка обязательного прохождения ОТК
        last_qc = ord_locked.quality_checks.order_by('-checked_at').first()
        if not (ord_locked.status == ProductionOrderStatus.READY or (last_qc and last_qc.is_passed)):
            raise ValidationError(
                f'Заказ {ord_locked.order_number} не может быть принят на склад WH-2 без успешного прохождения ОТК!'
            )

        qty_to_receive = ord_locked.quantity_produced
        if qty_to_receive <= Decimal('0.00'):
            qty_to_receive = ord_locked.quantity_planned

        wh2 = Warehouse.objects.filter(warehouse_type=WarehouseType.FINISHED_PRODUCTS).first()
        if not wh2:
            raise ValidationError('Склад готовой продукции (WH-2) не найден.')

        # Пересчитываем себестоимость перед сдачей
        recalculate_order_costs(ord_locked)
        unit_cost = ord_locked.unit_actual_cost_kzt
        total_cost = (qty_to_receive * unit_cost).quantize(Decimal('0.01'))

        # Оформляем приёмку на WH-2 (FINISHED_RECEIPT)
        doc = WarehouseDocument.objects.create(
            doc_number=generate_doc_number(WarehouseDocumentType.FINISHED_RECEIPT),
            doc_type=WarehouseDocumentType.FINISHED_RECEIPT,
            status=DocumentStatus.DRAFT,
            warehouse=wh2,
            production_order=ord_locked,
            created_by=user,
            total_amount_kzt=total_cost,
            notes=f'Приёмка готовой мебели из цеха: заказ {ord_locked.order_number} (ОТК пройден)',
        )

        WarehouseDocumentItem.objects.create(
            document=doc,
            product=ord_locked.product,
            quantity=qty_to_receive,
            unit='шт',
            unit_cost_kzt=unit_cost,
            total_cost_kzt=total_cost,
        )

        # Проводим складской документ (пополняет остаток на WH-2)
        post_document(doc, user=user)

        # Финализируем заказ
        ord_locked.status = ProductionOrderStatus.COMPLETED
        ord_locked.actual_end = timezone.localdate()
        ord_locked.save(update_fields=['status', 'actual_end', 'actual_cost_kzt', 'updated_at'])

        AuditLog.objects.create(
            user=user,
            action='COMPLETE_PRODUCTION_AND_RECEIVE_WH2',
            entity_type='ProductionOrder',
            entity_id=str(ord_locked.id),
            details={
                'order_number': ord_locked.order_number,
                'doc_number': doc.doc_number,
                'quantity_produced': str(qty_to_receive),
                'actual_cost_kzt': str(ord_locked.actual_cost_kzt),
            }
        )

        return doc


def recalculate_order_costs(order: ProductionOrder):
    """
    Расчёт плановой и фактической себестоимости производственного заказа.
    - Материалы (нормативные vs фактически списанные)
    - ФОТ рабочих (плановые часы vs фактически отработанные табели)
    - Накладные производственные затраты
    - Стоимость зарегистрированного брака
    """
    batch_qty = order.quantity_planned if order.quantity_planned > Decimal('0') else Decimal('1.00')

    # 1. ПЛАНОВАЯ СЕБЕСТОИМОСТЬ
    if order.bom:
        bom = order.bom
        plan_mat = (bom.total_materials_cost_kzt * batch_qty).quantize(Decimal('0.01'))
        plan_labor_hours = (bom.standard_labor_hours * batch_qty)
        plan_labor = (plan_labor_hours * bom.labor_rate_hourly_kzt).quantize(Decimal('0.01'))
        plan_overhead = (bom.overhead_rate_kzt * batch_qty).quantize(Decimal('0.01'))
    else:
        # Оценка по себестоимости изделия из каталога
        plan_mat = (order.product.production_cost_kzt * batch_qty * Decimal('0.60')).quantize(Decimal('0.01'))
        plan_labor = (order.product.production_cost_kzt * batch_qty * Decimal('0.30')).quantize(Decimal('0.01'))
        plan_overhead = (order.product.production_cost_kzt * batch_qty * Decimal('0.10')).quantize(Decimal('0.01'))

    order.planned_materials_cost_kzt = plan_mat
    order.planned_labor_cost_kzt = plan_labor
    order.overhead_cost_kzt = plan_overhead
    order.planned_cost_kzt = plan_mat + plan_labor + plan_overhead

    # 2. ФАКТИЧЕСКАЯ СЕБЕСТОИМОСТЬ
    actual_mat = sum(
        (c.cost_kzt for c in order.material_consumptions.all()),
        Decimal('0.00')
    )
    if actual_mat == Decimal('0.00') and order.is_materials_issued:
        actual_mat = plan_mat

    # Фактический труд по часам этапов
    stages = list(order.stages.all())
    rate = order.bom.labor_rate_hourly_kzt if order.bom else Decimal('2500.00')
    actual_hours_total = sum((s.actual_hours for s in stages), Decimal('0.00'))
    actual_labor = (actual_hours_total * rate).quantize(Decimal('0.01'))

    # Добавляем стоимость брака
    waste_cost = sum((w.cost_kzt for w in order.wastes.all()), Decimal('0.00'))

    order.actual_materials_cost_kzt = actual_mat
    order.actual_labor_cost_kzt = actual_labor
    order.actual_cost_kzt = actual_mat + actual_labor + plan_overhead + waste_cost
    order.save(update_fields=[
        'planned_materials_cost_kzt', 'planned_labor_cost_kzt', 'overhead_cost_kzt', 'planned_cost_kzt',
        'actual_materials_cost_kzt', 'actual_labor_cost_kzt', 'actual_cost_kzt',
    ])
