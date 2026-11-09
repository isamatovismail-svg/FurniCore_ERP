import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.accounts.models import User, UserRole, AuditLog
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
from apps.materials.models import Material, MaterialCategory
from apps.products.models import Product, ProductCategory
from apps.warehouses.services import (
    post_document,
    cancel_document,
    create_inventory_sheet,
    get_or_create_stock_balance,
)
from apps.warehouses.reports import generate_document_pdf, generate_item_label_pdf, generate_qr_png_bytes


@pytest.fixture
def wh_setup(db):
    """Базовая настройка для тестирования складского модуля."""
    wh1, _ = Warehouse.objects.get_or_create(
        code='WH-1',
        defaults={
            'name': 'Склад сырья и материалов',
            'warehouse_type': WarehouseType.RAW_MATERIALS,
        }
    )
    wh2, _ = Warehouse.objects.get_or_create(
        code='WH-2',
        defaults={
            'name': 'Склад готовой продукции',
            'warehouse_type': WarehouseType.FINISHED_PRODUCTS,
        }
    )

    manager = User.objects.create_user(
        username='wh_manager_test',
        password='password123',
        role=UserRole.WAREHOUSE_MANAGER,
        first_name='Асет',
        last_name='Искаков',
    )
    worker = User.objects.create_user(
        username='worker_test',
        password='password123',
        role=UserRole.WORKER,
        first_name='Ерлан',
        last_name='Сериков',
    )
    accountant = User.objects.create_user(
        username='accountant_test',
        password='password123',
        role=UserRole.ACCOUNTANT,
        first_name='Алия',
        last_name='Нурланова',
    )

    material = Material.objects.create(
        sku='MAT-TEST-001',
        name='Доска дубовая 50мм',
        category=MaterialCategory.WOOD,
        unit='м3',
        purchase_cost_kzt=Decimal('150000.00'),
        min_stock_level=Decimal('5.000'),
    )

    product = Product.objects.create(
        sku='PRD-TEST-001',
        name='Шкаф платяной "Дуб Хантер"',
        category=ProductCategory.WARDROBE,
        production_cost_kzt=Decimal('75000.00'),
        sale_price_kzt=Decimal('145000.00'),
    )

    return {
        'wh1': wh1,
        'wh2': wh2,
        'manager': manager,
        'worker': worker,
        'accountant': accountant,
        'material': material,
        'product': product,
    }


@pytest.mark.django_db
def test_wh1_receipt_increases_stock(wh_setup):
    """Приходная накладная на WH-1 увеличивает остаток сырья."""
    wh1 = wh_setup['wh1']
    material = wh_setup['material']
    user = wh_setup['manager']

    doc = WarehouseDocument.objects.create(
        doc_number='RCP-TEST-001',
        doc_type=WarehouseDocumentType.RECEIPT,
        status=DocumentStatus.DRAFT,
        warehouse=wh1,
        created_by=user,
    )
    WarehouseDocumentItem.objects.create(
        document=doc,
        material=material,
        quantity=Decimal('10.000'),
        unit='м3',
        unit_cost_kzt=Decimal('150000.00'),
    )

    # Черновик не должен менять остаток
    balance = get_or_create_stock_balance(wh1, material=material)
    assert balance.current_stock == Decimal('0.000')

    # Проведение документа
    post_document(doc, user=user)

    doc.refresh_from_db()
    balance.refresh_from_db()

    assert doc.status == DocumentStatus.POSTED
    assert doc.posted_by == user
    assert balance.current_stock == Decimal('10.000')

    # Проверка регистра движений
    movement = StockMovement.objects.filter(document=doc).first()
    assert movement is not None
    assert movement.movement_type == MovementType.RECEIPT
    assert movement.quantity == Decimal('10.000')
    assert movement.total_cost_kzt == Decimal('1500000.00')


@pytest.mark.django_db
def test_wh1_production_issue_and_negative_protection(wh_setup):
    """Отпуск в цех уменьшает остаток сырья, попытка списать больше остатка блокируется."""
    wh1 = wh_setup['wh1']
    material = wh_setup['material']
    user = wh_setup['manager']

    balance = get_or_create_stock_balance(wh1, material=material)
    balance.current_stock = Decimal('8.000')
    balance.save()

    # 1. Попытка списать больше остатка (15 при наличии 8)
    doc_excess = WarehouseDocument.objects.create(
        doc_number='ISS-TEST-EXCESS',
        doc_type=WarehouseDocumentType.PRODUCTION_ISSUE,
        status=DocumentStatus.DRAFT,
        warehouse=wh1,
        created_by=user,
    )
    WarehouseDocumentItem.objects.create(
        document=doc_excess,
        material=material,
        quantity=Decimal('15.000'),
        unit='м3',
    )

    with pytest.raises(ValidationError) as exc_info:
        post_document(doc_excess, user=user)
    assert 'Недостаточно материала' in str(exc_info.value)

    balance.refresh_from_db()
    assert balance.current_stock == Decimal('8.000')  # Остаток не изменился

    # 2. Корректный отпуск в цех (3 м3)
    doc_valid = WarehouseDocument.objects.create(
        doc_number='ISS-TEST-VALID',
        doc_type=WarehouseDocumentType.PRODUCTION_ISSUE,
        status=DocumentStatus.DRAFT,
        warehouse=wh1,
        created_by=user,
    )
    WarehouseDocumentItem.objects.create(
        document=doc_valid,
        material=material,
        quantity=Decimal('3.000'),
        unit='м3',
        unit_cost_kzt=Decimal('150000.00'),
    )

    post_document(doc_valid, user=user)
    balance.refresh_from_db()
    assert balance.current_stock == Decimal('5.000')


@pytest.mark.django_db
def test_wh1_production_return(wh_setup):
    """Возврат неиспользованных материалов из цеха увеличивает остаток на WH-1."""
    wh1 = wh_setup['wh1']
    material = wh_setup['material']
    user = wh_setup['manager']

    balance = get_or_create_stock_balance(wh1, material=material)
    balance.current_stock = Decimal('5.000')
    balance.save()

    doc = WarehouseDocument.objects.create(
        doc_number='RET-TEST-001',
        doc_type=WarehouseDocumentType.PRODUCTION_RETURN,
        status=DocumentStatus.DRAFT,
        warehouse=wh1,
        created_by=user,
    )
    WarehouseDocumentItem.objects.create(
        document=doc,
        material=material,
        quantity=Decimal('2.500'),
        unit='м3',
    )

    post_document(doc, user=user)
    balance.refresh_from_db()
    assert balance.current_stock == Decimal('7.500')


@pytest.mark.django_db
def test_wh2_finished_receipt_and_reservation(wh_setup):
    """Приёмка мебели на WH-2, резервирование и контроль доступного остатка."""
    wh2 = wh_setup['wh2']
    product = wh_setup['product']
    user = wh_setup['manager']

    # 1. Приёмка 5 готовых шкафов из цеха
    doc_rcp = WarehouseDocument.objects.create(
        doc_number='FRCP-TEST-001',
        doc_type=WarehouseDocumentType.FINISHED_RECEIPT,
        status=DocumentStatus.DRAFT,
        warehouse=wh2,
        created_by=user,
    )
    WarehouseDocumentItem.objects.create(
        document=doc_rcp,
        product=product,
        quantity=Decimal('5.000'),
        unit='шт',
        unit_cost_kzt=Decimal('75000.00'),
    )
    post_document(doc_rcp, user=user)

    balance = get_or_create_stock_balance(wh2, product=product)
    assert balance.current_stock == Decimal('5.000')
    assert balance.reserved_stock == Decimal('0.000')
    assert balance.available_stock == Decimal('5.000')

    # 2. Резервирование 3 шкафов под клиента
    doc_rsv = WarehouseDocument.objects.create(
        doc_number='RSV-TEST-001',
        doc_type=WarehouseDocumentType.RESERVATION,
        status=DocumentStatus.DRAFT,
        warehouse=wh2,
        created_by=user,
    )
    WarehouseDocumentItem.objects.create(
        document=doc_rsv,
        product=product,
        quantity=Decimal('3.000'),
        unit='шт',
    )
    post_document(doc_rsv, user=user)

    balance.refresh_from_db()
    assert balance.current_stock == Decimal('5.000')
    assert balance.reserved_stock == Decimal('3.000')
    assert balance.available_stock == Decimal('2.000')

    # 3. Попытка зарезервировать ещё 3 шкафа (доступно только 2) -> Ошибка
    doc_rsv_fail = WarehouseDocument.objects.create(
        doc_number='RSV-TEST-FAIL',
        doc_type=WarehouseDocumentType.RESERVATION,
        status=DocumentStatus.DRAFT,
        warehouse=wh2,
        created_by=user,
    )
    WarehouseDocumentItem.objects.create(
        document=doc_rsv_fail,
        product=product,
        quantity=Decimal('3.000'),
        unit='шт',
    )
    with pytest.raises(ValidationError) as exc:
        post_document(doc_rsv_fail, user=user)
    assert 'Недостаточно свободной мебели' in str(exc.value)

    # 4. Снятие 1 шкафа с резерва (UNRESERVATION)
    doc_unrsv = WarehouseDocument.objects.create(
        doc_number='UNRSV-TEST-001',
        doc_type=WarehouseDocumentType.UNRESERVATION,
        status=DocumentStatus.DRAFT,
        warehouse=wh2,
        created_by=user,
    )
    WarehouseDocumentItem.objects.create(
        document=doc_unrsv,
        product=product,
        quantity=Decimal('1.000'),
        unit='шт',
    )
    post_document(doc_unrsv, user=user)

    balance.refresh_from_db()
    assert balance.reserved_stock == Decimal('2.000')
    assert balance.available_stock == Decimal('3.000')


@pytest.mark.django_db
def test_wh2_shipment(wh_setup):
    """Расходная накладная отгрузки клиенту списывает складской остаток."""
    wh2 = wh_setup['wh2']
    product = wh_setup['product']
    user = wh_setup['manager']

    balance = get_or_create_stock_balance(wh2, product=product)
    balance.current_stock = Decimal('10.000')
    balance.reserved_stock = Decimal('4.000')
    balance.save()

    doc_ship = WarehouseDocument.objects.create(
        doc_number='SHP-TEST-001',
        doc_type=WarehouseDocumentType.SHIPMENT,
        status=DocumentStatus.DRAFT,
        warehouse=wh2,
        created_by=user,
    )
    WarehouseDocumentItem.objects.create(
        document=doc_ship,
        product=product,
        quantity=Decimal('4.000'),
        unit='шт',
        unit_cost_kzt=Decimal('145000.00'),
    )
    post_document(doc_ship, user=user)

    balance.refresh_from_db()
    assert balance.current_stock == Decimal('6.000')
    assert balance.reserved_stock == Decimal('0.000')
    assert balance.available_stock == Decimal('6.000')


@pytest.mark.django_db
def test_prevent_double_posting(wh_setup):
    """Повторное проведение проведённого документа невозможно (идемпотентность)."""
    wh1 = wh_setup['wh1']
    material = wh_setup['material']
    user = wh_setup['manager']

    doc = WarehouseDocument.objects.create(
        doc_number='RCP-IDEM-001',
        doc_type=WarehouseDocumentType.RECEIPT,
        status=DocumentStatus.DRAFT,
        warehouse=wh1,
        created_by=user,
    )
    WarehouseDocumentItem.objects.create(
        document=doc,
        material=material,
        quantity=Decimal('5.000'),
        unit='м3',
    )
    post_document(doc, user=user)

    with pytest.raises(ValidationError) as exc:
        post_document(doc, user=user)
    assert 'уже был проведён' in str(exc.value)


@pytest.mark.django_db
def test_cancel_document_creates_compensatory_movements(wh_setup):
    """Отмена проведённого документа создаёт сторнирующие проводки и восстанавливает остатки."""
    wh1 = wh_setup['wh1']
    material = wh_setup['material']
    user = wh_setup['manager']

    doc = WarehouseDocument.objects.create(
        doc_number='RCP-CANCEL-001',
        doc_type=WarehouseDocumentType.RECEIPT,
        status=DocumentStatus.DRAFT,
        warehouse=wh1,
        created_by=user,
    )
    WarehouseDocumentItem.objects.create(
        document=doc,
        material=material,
        quantity=Decimal('10.000'),
        unit='м3',
        unit_cost_kzt=Decimal('150000.00'),
    )
    post_document(doc, user=user)

    balance = get_or_create_stock_balance(wh1, material=material)
    assert balance.current_stock == Decimal('10.000')

    # Отмена документа
    cancel_document(doc, user=user)

    doc.refresh_from_db()
    balance.refresh_from_db()

    assert doc.status == DocumentStatus.CANCELLED
    assert doc.cancelled_at is not None
    assert balance.current_stock == Decimal('0.000')

    # В журнале появилась сторно-проводка
    movements = StockMovement.objects.filter(document=doc)
    assert movements.count() == 2
    assert movements.filter(movement_type=MovementType.ADJUSTMENT).exists()


@pytest.mark.django_db
def test_inventory_reconciliation(wh_setup):
    """Инвентаризация фиксирует расхождения и создает регулировочные проводки."""
    wh1 = wh_setup['wh1']
    material = wh_setup['material']
    user = wh_setup['manager']

    balance = get_or_create_stock_balance(wh1, material=material)
    balance.current_stock = Decimal('10.000')
    balance.save()

    # Создание ведомости
    inv_doc = create_inventory_sheet(wh1, user=user)
    assert inv_doc.status == DocumentStatus.DRAFT
    item = inv_doc.items.first()
    assert item.quantity == Decimal('10.000')

    # Фактически насчитали 8.5 (недостача 1.5)
    item.actual_quantity = Decimal('8.500')
    item.save()

    post_document(inv_doc, user=user)

    balance.refresh_from_db()
    assert balance.current_stock == Decimal('8.500')
    assert balance.last_counted_at is not None

    item.refresh_from_db()
    assert item.discrepancy_quantity == Decimal('-1.500')

    adj_movement = StockMovement.objects.filter(document=inv_doc, movement_type=MovementType.ADJUSTMENT).first()
    assert adj_movement is not None
    assert adj_movement.quantity == Decimal('1.500')


@pytest.mark.django_db
def test_pdf_and_labels_generation(wh_setup):
    """Генерация PDF накладной, термоэтикетки и QR-кода без исключений."""
    wh1 = wh_setup['wh1']
    material = wh_setup['material']
    user = wh_setup['manager']

    doc = WarehouseDocument.objects.create(
        doc_number='RCP-PDF-001',
        doc_type=WarehouseDocumentType.RECEIPT,
        status=DocumentStatus.POSTED,
        warehouse=wh1,
        created_by=user,
        posted_by=user,
        posted_at=timezone.now(),
    )
    WarehouseDocumentItem.objects.create(
        document=doc,
        material=material,
        quantity=Decimal('4.000'),
        unit='м3',
        unit_cost_kzt=Decimal('150000.00'),
        total_cost_kzt=Decimal('600000.00'),
    )

    pdf_doc = generate_document_pdf(doc)
    assert len(pdf_doc) > 1000
    assert pdf_doc.startswith(b'%PDF')

    label_mat = generate_item_label_pdf('material', material)
    assert len(label_mat) > 1000
    assert label_mat.startswith(b'%PDF')

    qr_bytes = generate_qr_png_bytes('TEST-DATA')
    assert len(qr_bytes) > 100


@pytest.mark.django_db
def test_http_views_and_scanner(client, wh_setup):
    """Проверка всех веб-маршрутов и API терминала сканирования."""
    manager = wh_setup['manager']
    material = wh_setup['material']
    client.force_login(manager)

    # 1. Сводка складов
    resp = client.get('/warehouses/')
    assert resp.status_code == 200

    # 2. WH-1
    resp = client.get('/warehouses/wh-1/')
    assert resp.status_code == 200

    # 3. WH-2
    resp = client.get('/warehouses/wh-2/')
    assert resp.status_code == 200

    # 4. Журнал документов
    resp = client.get('/warehouses/documents/')
    assert resp.status_code == 200

    # 5. Создание документа
    resp = client.get('/warehouses/documents/create/')
    assert resp.status_code == 200

    # 6. Реестр инвентаризаций
    resp = client.get('/warehouses/inventory/')
    assert resp.status_code == 200

    # 7. Терминал сканирования
    resp = client.get('/warehouses/scan/')
    assert resp.status_code == 200

    # 8. API поиска по штрихкоду
    resp = client.get(f'/warehouses/scan/lookup/?code={material.sku}')
    assert resp.status_code == 200
    data = resp.json()
    assert data['found'] is True
    assert data['sku'] == material.sku
    assert data['warehouse_code'] == 'WH-1'


@pytest.mark.django_db
def test_http_rbac_protection(client, wh_setup):
    """Сотрудник роли WORKER не имеет права проводить складские ордера."""
    worker = wh_setup['worker']
    wh1 = wh_setup['wh1']
    material = wh_setup['material']

    doc = WarehouseDocument.objects.create(
        doc_number='RCP-RBAC-001',
        doc_type=WarehouseDocumentType.RECEIPT,
        status=DocumentStatus.DRAFT,
        warehouse=wh1,
        created_by=worker,
    )
    WarehouseDocumentItem.objects.create(
        document=doc,
        material=material,
        quantity=Decimal('2.000'),
        unit='м3',
    )

    client.force_login(worker)
    # Попытка провести документ
    resp = client.post(f'/warehouses/documents/{doc.id}/post/')
    assert resp.status_code == 302  # Редирект с сообщением об ошибке прав

    doc.refresh_from_db()
    assert doc.status == DocumentStatus.DRAFT  # Не проведён

