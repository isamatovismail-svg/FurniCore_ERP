import pytest
from decimal import Decimal
import datetime
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.accounts.models import UserRole
from apps.employees.models import Employee, Department
from apps.warehouses.models import Warehouse, WarehouseType, StockBalance, WarehouseDocumentType, DocumentStatus
from apps.materials.models import Material, MaterialCategory
from apps.products.models import Product, ProductCategory
from apps.production.models import (
    ProductionOrder,
    ProductionOrderStatus,
    OrderPriority,
    ProductionStage,
    StageStatus,
    BOM,
    BOMItem,
    ProductionWaste,
    WasteType,
    RoutingTemplate,
    RoutingStage,
)
from apps.quality.models import QualityCheck, QCResult
from apps.production.services import (
    ensure_default_routing_templates,
    check_materials_availability,
    initialize_order_stages,
    issue_materials_for_production,
    launch_production_order,
    advance_stage,
    register_waste_or_defect,
    submit_quality_check,
    complete_and_transfer_to_warehouse,
    recalculate_order_costs,
)

User = get_user_model()


@pytest.fixture
def prod_env(db):
    """Фикстура полной среды производства, складов WH-1/WH-2 и ролей."""
    ensure_default_routing_templates()

    # Склады
    wh1, _ = Warehouse.objects.get_or_create(
        code='WH-1',
        defaults={'name': 'Склад сырья и материалов', 'warehouse_type': WarehouseType.RAW_MATERIALS}
    )
    wh2, _ = Warehouse.objects.get_or_create(
        code='WH-2',
        defaults={'name': 'Склад готовой продукции', 'warehouse_type': WarehouseType.FINISHED_PRODUCTS}
    )

    # Пользователи
    mgr_user, _ = User.objects.get_or_create(
        username='test_prod_mgr',
        defaults={'email': 'mgr@furnicore.kz', 'role': UserRole.PRODUCTION_MANAGER, 'first_name': 'Арман', 'last_name': 'Сейткали'}
    )
    mgr_user.set_password('pass123')
    mgr_user.save()

    worker_user, _ = User.objects.get_or_create(
        username='test_worker',
        defaults={'email': 'worker@furnicore.kz', 'role': UserRole.WORKER, 'first_name': 'Иван', 'last_name': 'Петренко'}
    )
    worker_user.set_password('pass123')
    worker_user.save()

    emp_worker, _ = Employee.objects.get_or_create(
        user=worker_user,
        defaults={
            'first_name': 'Иван',
            'last_name': 'Петренко',
            'department': Department.PRODUCTION,
            'position': 'Мастер-сборщик',
            'hire_date': timezone.localdate(),
        }
    )

    # Материалы
    mat_ldsp, _ = Material.objects.get_or_create(
        sku='MAT-TST-001',
        defaults={
            'name': 'Тестовый ЛДСП 16мм',
            'category': MaterialCategory.CHIPBOARD,
            'unit': 'лист',
            'purchase_cost_kzt': Decimal('5000.00'),
        }
    )
    mat_petli, _ = Material.objects.get_or_create(
        sku='MAT-TST-002',
        defaults={
            'name': 'Тестовые петли',
            'category': MaterialCategory.HARDWARE_HINGES,
            'unit': 'шт',
            'purchase_cost_kzt': Decimal('400.00'),
        }
    )

    # Начальные остатки на WH-1
    sb1, _ = StockBalance.objects.get_or_create(warehouse=wh1, material=mat_ldsp)
    sb1.current_stock = Decimal('20.00')
    sb1.save()

    sb2, _ = StockBalance.objects.get_or_create(warehouse=wh1, material=mat_petli)
    sb2.current_stock = Decimal('50.00')
    sb2.save()

    # Продукция: Шкаф
    product, _ = Product.objects.get_or_create(
        sku='PRD-TST-WARDROBE',
        defaults={
            'name': 'Тестовый шкаф 2-дверный',
            'category': ProductCategory.WARDROBE,
            'sale_price_kzt': Decimal('120000.00'),
            'production_cost_kzt': Decimal('60000.00'),
        }
    )

    # BOM для шкафа
    rt = RoutingTemplate.objects.filter(category=ProductCategory.WARDROBE).first()
    bom, _ = BOM.objects.get_or_create(
        product=product,
        name='Техкарта тестового шкафа',
        defaults={
            'version': '1.0',
            'routing_template': rt,
            'standard_labor_hours': Decimal('10.0'),
            'labor_rate_hourly_kzt': Decimal('2000.00'),
            'overhead_rate_kzt': Decimal('5000.00'),
            'is_active': True,
        }
    )
    # Позиции BOM: 2 листа ЛДСП (отход 5%) + 4 петли (отход 0%)
    if bom.items.count() == 0:
        BOMItem.objects.create(bom=bom, material=mat_ldsp, quantity_planned=Decimal('2.000'), unit='лист', waste_percent=Decimal('5.00'))
        BOMItem.objects.create(bom=bom, material=mat_petli, quantity_planned=Decimal('4.000'), unit='шт', waste_percent=Decimal('0.00'))

    return {
        'wh1': wh1,
        'wh2': wh2,
        'mgr_user': mgr_user,
        'worker_user': worker_user,
        'emp_worker': emp_worker,
        'mat_ldsp': mat_ldsp,
        'mat_petli': mat_petli,
        'product': product,
        'bom': bom,
        'rt': rt,
    }


@pytest.mark.django_db
def test_1_bom_cost_calculation(prod_env):
    """1. Проверка корректности расчёта плановой себестоимости по спецификации BOM."""
    bom = prod_env['bom']
    # 2 листа * 1.05 = 2.1 листа * 5000 ₸ = 10,500 ₸
    # 4 петли * 1.00 = 4.0 шт * 400 ₸ = 1,600 ₸
    # Материалы: 12,100 ₸
    assert bom.materials_cost_kzt == Decimal('12100.00')
    # Труд: 10 ч * 2000 ₸ = 20,000 ₸
    assert bom.labor_cost_kzt == Decimal('20000.00')
    # Накладные: 5,000 ₸
    # Итого: 12,100 + 20,000 + 5,000 = 37,100 ₸
    assert bom.total_planned_cost_kzt == Decimal('37100.00')


@pytest.mark.django_db
def test_2_production_order_creation_and_planned_costs(prod_env):
    """2. Создание заказа на производство и расчёт плановых затрат на партию."""
    order = ProductionOrder.objects.create(
        order_number='PO-TST-001',
        product=prod_env['product'],
        bom=prod_env['bom'],
        quantity_planned=Decimal('2.00'),
        priority=OrderPriority.HIGH,
        planned_start=timezone.localdate(),
        planned_end=timezone.localdate() + datetime.timedelta(days=7),
        created_by=prod_env['mgr_user'],
    )
    recalculate_order_costs(order)
    order.refresh_from_db()

    # Для 2 шкафов:
    # Материалы: 12,100 * 2 = 24,200 ₸
    # Труд: 20,000 * 2 = 40,000 ₸
    # Накладные: 5,000 * 2 = 10,000 ₸
    assert order.planned_materials_cost_kzt == Decimal('24200.00')
    assert order.planned_labor_cost_kzt == Decimal('40000.00')
    assert order.overhead_cost_kzt == Decimal('10000.00')
    assert order.total_planned_cost_kzt == Decimal('74200.00')
    assert order.unit_planned_cost_kzt == Decimal('37100.00')


@pytest.mark.django_db
def test_3_check_materials_availability(prod_env):
    """3. Сверка потребности сырья по BOM с остатками на складе WH-1."""
    order = ProductionOrder.objects.create(
        order_number='PO-TST-002',
        product=prod_env['product'],
        bom=prod_env['bom'],
        quantity_planned=Decimal('2.00'),
        created_by=prod_env['mgr_user'],
    )
    analysis = check_materials_availability(order)
    # На WH-1: 20 листов ЛДСП (нужно 4.2), 50 петель (нужно 8)
    assert analysis['is_all_available'] is True
    assert analysis['possible_units'] >= Decimal('2.00')


@pytest.mark.django_db
def test_4_detect_material_shortage(prod_env):
    """4. Обнаружение дефицита сырья на складе WH-1."""
    # Заказ на 20 шкафов (потребуется 42 листа ЛДСП, а есть только 20)
    order = ProductionOrder.objects.create(
        order_number='PO-TST-003',
        product=prod_env['product'],
        bom=prod_env['bom'],
        quantity_planned=Decimal('20.00'),
        created_by=prod_env['mgr_user'],
    )
    analysis = check_materials_availability(order)
    assert analysis['is_all_available'] is False
    ldsp_item = [m for m in analysis['materials'] if m['material'] == prod_env['mat_ldsp']][0]
    assert ldsp_item['is_available'] is False
    assert ldsp_item['shortage_qty'] > Decimal('0.00')


@pytest.mark.django_db
def test_5_issue_materials_from_wh1(prod_env):
    """5. Выдача сырья под заказ через складской сервис с созданием накладной PRODUCTION_ISSUE."""
    order = ProductionOrder.objects.create(
        order_number='PO-TST-004',
        product=prod_env['product'],
        bom=prod_env['bom'],
        quantity_planned=Decimal('2.00'),
        created_by=prod_env['mgr_user'],
    )
    initial_ldsp_stock = StockBalance.objects.get(warehouse=prod_env['wh1'], material=prod_env['mat_ldsp']).current_stock

    doc = issue_materials_for_production(order, user=prod_env['mgr_user'])
    assert doc.doc_type == WarehouseDocumentType.PRODUCTION_ISSUE
    assert doc.status == DocumentStatus.POSTED

    # Остаток на WH-1 уменьшился на 4.200 листа
    new_ldsp_stock = StockBalance.objects.get(warehouse=prod_env['wh1'], material=prod_env['mat_ldsp']).current_stock
    assert new_ldsp_stock == initial_ldsp_stock - Decimal('4.200')

    order.refresh_from_db()
    assert order.is_materials_issued is True
    assert order.status == ProductionOrderStatus.MATERIALS_RESERVED


@pytest.mark.django_db
def test_6_prevent_double_material_issue(prod_env):
    """6. Защита от повторного списания материалов под один и тот же заказ."""
    order = ProductionOrder.objects.create(
        order_number='PO-TST-005',
        product=prod_env['product'],
        bom=prod_env['bom'],
        quantity_planned=Decimal('2.00'),
        created_by=prod_env['mgr_user'],
    )
    issue_materials_for_production(order, user=prod_env['mgr_user'])

    # Повторная попытка должна вызвать ValidationError
    with pytest.raises(ValidationError, match="уже были выданы"):
        issue_materials_for_production(order, user=prod_env['mgr_user'])


@pytest.mark.django_db
def test_7_order_launch_generates_stages_from_template(prod_env):
    """7. Запуск заказа генерирует этапы по маршруту категории шкафов."""
    order = ProductionOrder.objects.create(
        order_number='PO-TST-006',
        product=prod_env['product'],
        bom=prod_env['bom'],
        quantity_planned=Decimal('1.00'),
        created_by=prod_env['mgr_user'],
    )
    launch_production_order(order, user=prod_env['mgr_user'])
    order.refresh_from_db()

    assert order.status == ProductionOrderStatus.IN_PROGRESS
    stages = list(order.stages.order_by('sequence'))
    assert len(stages) == 6  # 6 этапов шкафа
    # Первый этап активирован
    assert stages[0].status == StageStatus.IN_PROGRESS
    assert stages[1].status == StageStatus.PENDING


@pytest.mark.django_db
def test_8_advance_stage_progress(prod_env):
    """8. Переход между технологическими операциями с фиксацией часов."""
    order = ProductionOrder.objects.create(
        order_number='PO-TST-007',
        product=prod_env['product'],
        bom=prod_env['bom'],
        quantity_planned=Decimal('1.00'),
        created_by=prod_env['mgr_user'],
    )
    launch_production_order(order, user=prod_env['mgr_user'])
    stages = list(order.stages.order_by('sequence'))
    first_stage = stages[0]

    advance_stage(first_stage, user=prod_env['worker_user'], actual_hours=Decimal('3.5'), quantity_processed=Decimal('1.0'))
    first_stage.refresh_from_db()
    assert first_stage.status == StageStatus.DONE
    assert first_stage.actual_hours == Decimal('3.5')

    # Второй этап автоматически перешёл в IN_PROGRESS
    second_stage = order.stages.get(sequence=2)
    assert second_stage.status == StageStatus.IN_PROGRESS


@pytest.mark.django_db
def test_9_waste_and_defect_registration(prod_env):
    """9. Регистрация технологических отходов и брака с переводом в REWORK."""
    order = ProductionOrder.objects.create(
        order_number='PO-TST-008',
        product=prod_env['product'],
        bom=prod_env['bom'],
        quantity_planned=Decimal('1.00'),
        created_by=prod_env['mgr_user'],
    )
    launch_production_order(order, user=prod_env['mgr_user'])
    stage1 = order.stages.first()

    waste = register_waste_or_defect(
        order=order,
        waste_type=WasteType.REWORKABLE_DEFECT,
        quantity=Decimal('1.000'),
        unit='лист',
        cost_kzt=Decimal('2500.00'),
        user=prod_env['worker_user'],
        stage=stage1,
        material=prod_env['mat_ldsp'],
        reason='Скол ламината при раскрое',
        decision='Переторцевать деталь под полку'
    )
    assert waste.cost_kzt == Decimal('2500.00')
    order.refresh_from_db()
    assert order.status == ProductionOrderStatus.REWORK


@pytest.mark.django_db
def test_10_last_stage_advance_moves_to_qc(prod_env):
    """10. Завершение последнего этапа автоматически переводит заказ на контроль ОТК."""
    order = ProductionOrder.objects.create(
        order_number='PO-TST-009',
        product=prod_env['product'],
        bom=prod_env['bom'],
        quantity_planned=Decimal('1.00'),
        created_by=prod_env['mgr_user'],
    )
    launch_production_order(order, user=prod_env['mgr_user'])
    
    stages = list(order.stages.order_by('sequence'))
    for s in stages:
        s.status = StageStatus.IN_PROGRESS
        s.save()
        advance_stage(s, user=prod_env['worker_user'], actual_hours=s.planned_hours)

    order.refresh_from_db()
    assert order.status == ProductionOrderStatus.QC_CHECK


@pytest.mark.django_db
def test_11_quality_check_pass(prod_env):
    """11. Успешное прохождение 7 пунктов чек-листа ОТК переводит заказ в READY."""
    order = ProductionOrder.objects.create(
        order_number='PO-TST-010',
        product=prod_env['product'],
        bom=prod_env['bom'],
        quantity_planned=Decimal('2.00'),
        status=ProductionOrderStatus.QC_CHECK,
        created_by=prod_env['mgr_user'],
    )
    qc = submit_quality_check(
        order=order,
        inspector=prod_env['mgr_user'],
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
    order.refresh_from_db()
    assert order.status == ProductionOrderStatus.READY
    assert order.quantity_produced == Decimal('2.00')


@pytest.mark.django_db
def test_12_block_wh2_transfer_before_qc_pass(prod_env):
    """12. Запрет сдачи продукции на склад WH-2 до успешного прохождения ОТК."""
    order = ProductionOrder.objects.create(
        order_number='PO-TST-011',
        product=prod_env['product'],
        bom=prod_env['bom'],
        quantity_planned=Decimal('1.00'),
        status=ProductionOrderStatus.IN_PROGRESS,  # Не READY и не прошёл ОТК
        created_by=prod_env['mgr_user'],
    )
    with pytest.raises(ValidationError, match="без успешного прохождения ОТК"):
        complete_and_transfer_to_warehouse(order, user=prod_env['mgr_user'])


@pytest.mark.django_db
def test_13_complete_and_transfer_to_wh2_success(prod_env):
    """13. Приёмка готовой продукции на WH-2 через складской сервис с созданием FINISHED_RECEIPT."""
    order = ProductionOrder.objects.create(
        order_number='PO-TST-012',
        product=prod_env['product'],
        bom=prod_env['bom'],
        quantity_planned=Decimal('3.00'),
        status=ProductionOrderStatus.READY,
        quantity_produced=Decimal('3.00'),
        created_by=prod_env['mgr_user'],
    )
    # Создаём успешную запись ОТК
    QualityCheck.objects.create(
        production_order=order,
        checked_by=prod_env['mgr_user'],
        result=QCResult.PASS,
        quantity_checked=Decimal('3.00'),
        quantity_accepted=Decimal('3.00'),
        check_dimensions=True, check_assembly=True, check_appearance=True,
        check_coating=True, check_completeness=True, check_mechanisms=True, check_damage_free=True,
    )

    initial_wh2_stock = StockBalance.objects.filter(warehouse=prod_env['wh2'], product=prod_env['product']).first()
    initial_qty = initial_wh2_stock.current_stock if initial_wh2_stock else Decimal('0.00')

    doc = complete_and_transfer_to_warehouse(order, user=prod_env['mgr_user'])
    assert doc.doc_type == WarehouseDocumentType.FINISHED_RECEIPT
    assert doc.status == DocumentStatus.POSTED

    # Остаток на WH-2 увеличился на 3 шт
    new_wh2_stock = StockBalance.objects.get(warehouse=prod_env['wh2'], product=prod_env['product']).current_stock
    assert new_wh2_stock == initial_qty + Decimal('3.00')

    order.refresh_from_db()
    assert order.status == ProductionOrderStatus.COMPLETED
    assert order.actual_end is not None


@pytest.mark.django_db
def test_14_cost_variance_calculation(prod_env):
    """14. Точность калькуляции фактической себестоимости и отклонений от плана."""
    order = ProductionOrder.objects.create(
        order_number='PO-TST-013',
        product=prod_env['product'],
        bom=prod_env['bom'],
        quantity_planned=Decimal('1.00'),
        quantity_produced=Decimal('1.00'),
        created_by=prod_env['mgr_user'],
    )
    # План: 37,100 ₸
    recalculate_order_costs(order)
    order.refresh_from_db()

    # Факт: потратили материалов на 13,000 ₸, работы на 22,000 ₸, накладные 5,000 ₸
    order.actual_materials_cost_kzt = Decimal('13000.00')
    order.actual_labor_cost_kzt = Decimal('22000.00')
    order.overhead_cost_kzt = Decimal('5000.00')
    order.actual_cost_kzt = order.actual_materials_cost_kzt + order.actual_labor_cost_kzt + order.overhead_cost_kzt
    order.save()

    assert order.total_actual_cost_kzt == Decimal('40000.00')
    assert order.unit_actual_cost_kzt == Decimal('40000.00')
    # Перерасход: 40,000 - 37,100 = +2,900 ₸
    assert order.cost_variance_kzt == Decimal('2900.00')


@pytest.mark.django_db
def test_15_rbac_production_controls(client, prod_env):
    """15. Ролевые ограничения: рабочий не может создавать заказы или передавать их на склад."""
    client.force_login(prod_env['worker_user'])

    # Попытка создать заказ
    resp = client.get('/production/create/')
    # Должен быть редирект с сообщением о правах
    assert resp.status_code == 302

    # Менеджер может открыть форму создания
    client.force_login(prod_env['mgr_user'])
    resp = client.get('/production/create/')
    assert resp.status_code == 200


@pytest.mark.django_db
def test_16_my_tasks_worker_interface(client, prod_env):
    """16. Доступность страниц Канбан-доски, Моих заданий и перечня техкарт."""
    client.force_login(prod_env['worker_user'])

    resp_tasks = client.get('/production/my-tasks/')
    assert resp_tasks.status_code == 200

    resp_board = client.get('/production/board/')
    assert resp_board.status_code == 200

    resp_boms = client.get('/production/boms/')
    assert resp_boms.status_code == 200

    resp_routes = client.get('/production/routes/')
    assert resp_routes.status_code == 200

    resp_waste = client.get('/production/waste/')
    assert resp_waste.status_code == 200
