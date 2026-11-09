import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from apps.accounts.models import UserRole
from apps.warehouses.models import (
    Warehouse,
    StockBalance,
    StockMovement,
    WarehouseType,
    WarehouseDocument,
    WarehouseDocumentItem,
    WarehouseDocumentType,
    DocumentStatus,
    MovementType,
)
from apps.materials.models import Material
from apps.products.models import Product
from apps.suppliers.models import Supplier
from apps.sales.models import Customer, SalesOrder
from apps.production.models import ProductionOrder
from apps.warehouses.services import (
    generate_doc_number,
    post_document,
    cancel_document,
    create_inventory_sheet,
)
from apps.warehouses.reports import (
    generate_qr_png_bytes,
    generate_document_pdf,
    generate_item_label_pdf,
)


def can_user_manage_warehouses(user) -> bool:
    return user.is_authenticated and (
        user.is_superuser or
        user.role in [UserRole.OWNER, UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER]
    )


def can_user_post_doc(user, doc_type: str) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.role in [UserRole.OWNER, UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER]:
        return True
    if user.role == UserRole.PRODUCTION_MANAGER and doc_type in [
        WarehouseDocumentType.PRODUCTION_ISSUE,
        WarehouseDocumentType.PRODUCTION_RETURN,
    ]:
        return True
    if user.role == UserRole.SALES_MANAGER and doc_type in [
        WarehouseDocumentType.RESERVATION,
        WarehouseDocumentType.UNRESERVATION,
    ]:
        return True
    return False


@login_required
def index(request):
    warehouses = Warehouse.objects.all()

    wh1 = Warehouse.objects.filter(warehouse_type=WarehouseType.RAW_MATERIALS).first()
    wh2 = Warehouse.objects.filter(warehouse_type=WarehouseType.FINISHED_PRODUCTS).first()

    wh1_balances = StockBalance.objects.filter(
        warehouse=wh1, material__isnull=False
    ).select_related('material').order_by('material__name') if wh1 else []

    wh2_balances = StockBalance.objects.filter(
        warehouse=wh2, product__isnull=False
    ).select_related('product').order_by('product__name') if wh2 else []

    wh1_low_stock = [b for b in wh1_balances if b.is_low_stock]

    wh1_total_value = sum(
        (b.current_stock * b.material.purchase_cost_kzt for b in wh1_balances if b.material),
        Decimal('0')
    )
    wh2_total_items = sum((b.current_stock for b in wh2_balances), Decimal('0'))
    wh2_total_reserved = sum((b.reserved_stock for b in wh2_balances), Decimal('0'))
    wh2_total_value = sum(
        (b.current_stock * b.product.sale_price_kzt for b in wh2_balances if b.product),
        Decimal('0')
    )

    recent_movements = StockMovement.objects.select_related(
        'warehouse', 'material', 'product', 'performed_by', 'document'
    ).order_by('-created_at')[:10]

    recent_documents = WarehouseDocument.objects.select_related(
        'warehouse', 'created_by'
    ).order_by('-created_at')[:6]

    context = {
        'page_title': 'Склады',
        'warehouses': warehouses,
        'wh1': wh1,
        'wh2': wh2,
        'wh1_balances': wh1_balances,
        'wh2_balances': wh2_balances,
        'wh1_low_stock': wh1_low_stock,
        'wh1_total_value': wh1_total_value,
        'wh2_total_items': wh2_total_items,
        'wh2_total_reserved': wh2_total_reserved,
        'wh2_total_value': wh2_total_value,
        'recent_movements': recent_movements,
        'recent_documents': recent_documents,
    }
    return render(request, 'warehouses/index.html', context)


@login_required
def wh1_view(request):
    wh1 = Warehouse.objects.filter(warehouse_type=WarehouseType.RAW_MATERIALS).first()
    q = request.GET.get('q', '').strip()
    low_only = request.GET.get('low', '')

    balances_qs = StockBalance.objects.filter(
        warehouse=wh1, material__isnull=False
    ).select_related('material', 'material__supplier')

    if q:
        balances_qs = balances_qs.filter(
            Q(material__name__icontains=q) |
            Q(material__sku__icontains=q) |
            Q(material__barcode__icontains=q) |
            Q(material__location__icontains=q)
        )

    balances = list(balances_qs.order_by('material__name'))
    low_stock_count = sum(1 for b in balances if b.is_low_stock)

    if low_only == '1':
        balances = [b for b in balances if b.is_low_stock]

    total_value = sum(
        (b.current_stock * b.material.purchase_cost_kzt for b in balances if b.material),
        Decimal('0')
    )

    movements = StockMovement.objects.filter(
        warehouse=wh1
    ).select_related('material', 'performed_by', 'document').order_by('-created_at')[:15]

    context = {
        'page_title': 'Склад №1 — Сырьё и материалы',
        'warehouse': wh1,
        'balances': balances,
        'total_positions': len(balances),
        'low_stock_count': low_stock_count,
        'total_value': total_value,
        'q': q,
        'low_only': low_only,
        'movements': movements,
    }
    return render(request, 'warehouses/wh1.html', context)


@login_required
def wh2_view(request):
    wh2 = Warehouse.objects.filter(warehouse_type=WarehouseType.FINISHED_PRODUCTS).first()
    q = request.GET.get('q', '').strip()

    balances_qs = StockBalance.objects.filter(
        warehouse=wh2, product__isnull=False
    ).select_related('product')

    if q:
        balances_qs = balances_qs.filter(
            Q(product__name__icontains=q) |
            Q(product__sku__icontains=q) |
            Q(product__barcode__icontains=q)
        )

    balances = list(balances_qs.order_by('product__name'))

    total_items = sum((b.current_stock for b in balances), Decimal('0'))
    total_reserved = sum((b.reserved_stock for b in balances), Decimal('0'))
    total_available = sum((b.available_stock for b in balances), Decimal('0'))
    total_value = sum(
        (b.current_stock * b.product.sale_price_kzt for b in balances if b.product),
        Decimal('0')
    )
    total_cost_val = sum(
        (b.current_stock * b.product.production_cost_kzt for b in balances if b.product),
        Decimal('0')
    )

    movements = StockMovement.objects.filter(
        warehouse=wh2
    ).select_related('product', 'performed_by', 'document').order_by('-created_at')[:15]

    context = {
        'page_title': 'Склад №2 — Готовая продукция',
        'warehouse': wh2,
        'balances': balances,
        'total_positions': len(balances),
        'total_items': total_items,
        'total_reserved': total_reserved,
        'total_available': total_available,
        'total_value': total_value,
        'total_cost_val': total_cost_val,
        'q': q,
        'movements': movements,
    }
    return render(request, 'warehouses/wh2.html', context)


# ==============================================================================
# ЖУРНАЛ И ОФОРМЛЕНИЕ СКЛАДСКИХ ДОКУМЕНТОВ
# ==============================================================================

@login_required
def document_list(request):
    doc_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    wh_code = request.GET.get('wh', '')
    q = request.GET.get('q', '').strip()

    docs_qs = WarehouseDocument.objects.select_related(
        'warehouse', 'created_by', 'posted_by', 'supplier', 'customer'
    ).all()

    if doc_type:
        docs_qs = docs_qs.filter(doc_type=doc_type)
    if status:
        docs_qs = docs_qs.filter(status=status)
    if wh_code:
        docs_qs = docs_qs.filter(warehouse__code=wh_code)
    if q:
        docs_qs = docs_qs.filter(
            Q(doc_number__icontains=q) |
            Q(notes__icontains=q) |
            Q(supplier__name__icontains=q) |
            Q(customer__full_name__icontains=q) |
            Q(customer__company_name__icontains=q)
        )

    documents = docs_qs.order_by('-created_at')[:100]

    context = {
        'page_title': 'Журнал складских документов',
        'documents': documents,
        'total_count': docs_qs.count(),
        'doc_types': WarehouseDocumentType.choices,
        'doc_statuses': DocumentStatus.choices,
        'selected_type': doc_type,
        'selected_status': status,
        'selected_wh': wh_code,
        'q': q,
    }
    return render(request, 'warehouses/documents/list.html', context)


@login_required
def document_detail(request, pk):
    doc = get_object_or_404(
        WarehouseDocument.objects.select_related(
            'warehouse', 'created_by', 'posted_by', 'supplier', 'customer', 'sales_order', 'production_order'
        ),
        pk=pk
    )
    items = doc.items.select_related('material', 'product').all()
    movements = doc.movements.select_related('material', 'product', 'performed_by').all()

    can_post = can_user_post_doc(request.user, doc.doc_type) and doc.is_draft
    can_cancel = can_user_post_doc(request.user, doc.doc_type) and doc.is_posted

    context = {
        'page_title': f'{doc.get_doc_type_display()} {doc.doc_number}',
        'doc': doc,
        'items': items,
        'movements': movements,
        'can_post': can_post,
        'can_cancel': can_cancel,
    }
    return render(request, 'warehouses/documents/detail.html', context)


@login_required
def document_create(request):
    default_wh = request.GET.get('wh', 'WH-1')
    default_type = request.GET.get('type', WarehouseDocumentType.RECEIPT)

    if request.method == 'POST':
        warehouse_id = request.POST.get('warehouse')
        doc_type = request.POST.get('doc_type')
        doc_date = request.POST.get('doc_date') or timezone.localdate()
        notes = request.POST.get('notes', '').strip()
        supplier_id = request.POST.get('supplier')
        customer_id = request.POST.get('customer')
        sales_order_id = request.POST.get('sales_order')
        prod_order_id = request.POST.get('production_order')
        action_post = (request.POST.get('action') == 'post')

        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

        # Проверка прав доступа
        if action_post and not can_user_post_doc(request.user, doc_type):
            messages.error(request, 'У вас недостаточно прав для проведения данного документа.')
            return redirect('warehouses:document_list')

        doc_number = generate_doc_number(doc_type)
        doc = WarehouseDocument.objects.create(
            doc_number=doc_number,
            doc_type=doc_type,
            status=DocumentStatus.DRAFT,
            warehouse=warehouse,
            doc_date=doc_date,
            created_by=request.user,
            notes=notes,
            supplier_id=supplier_id if supplier_id else None,
            customer_id=customer_id if customer_id else None,
            sales_order_id=sales_order_id if sales_order_id else None,
            production_order_id=prod_order_id if prod_order_id else None,
        )

        # Сохранение строк документа
        mat_ids = request.POST.getlist('material_id[]')
        prod_ids = request.POST.getlist('product_id[]')
        quantities = request.POST.getlist('quantity[]')
        units = request.POST.getlist('unit[]')
        costs = request.POST.getlist('unit_cost[]')

        total_doc_amount = Decimal('0.00')

        count = max(len(mat_ids), len(prod_ids), len(quantities))
        for i in range(count):
            qty_val = quantities[i] if i < len(quantities) else '0'
            try:
                qty = Decimal(str(qty_val))
            except Exception:
                qty = Decimal('0')

            if qty <= Decimal('0'):
                continue

            unit = units[i] if i < len(units) else 'шт'
            cost_val = costs[i] if i < len(costs) else '0'
            try:
                cost = Decimal(str(cost_val))
            except Exception:
                cost = Decimal('0.00')

            m_id = mat_ids[i] if i < len(mat_ids) and mat_ids[i] else None
            p_id = prod_ids[i] if i < len(prod_ids) and prod_ids[i] else None

            tot = (qty * cost).quantize(Decimal('0.01'))
            total_doc_amount += tot

            WarehouseDocumentItem.objects.create(
                document=doc,
                material_id=m_id,
                product_id=p_id,
                quantity=qty,
                unit=unit,
                unit_cost_kzt=cost,
                total_cost_kzt=tot,
            )

        doc.total_amount_kzt = total_doc_amount
        doc.save(update_fields=['total_amount_kzt'])

        if action_post:
            try:
                post_document(doc, user=request.user)
                messages.success(request, f'Документ {doc.doc_number} успешно создан и проведён.')
            except Exception as e:
                messages.warning(request, f'Документ сохранён как черновик, но не проведён из-за ошибки: {e}')
        else:
            messages.success(request, f'Черновик документа {doc.doc_number} сохранён.')

        return redirect('warehouses:document_detail', pk=doc.id)

    warehouses = Warehouse.objects.all()
    materials = Material.objects.order_by('name')
    products = Product.objects.filter(is_active=True).order_by('name')
    suppliers = Supplier.objects.order_by('name')
    customers = Customer.objects.order_by('full_name')
    sales_orders = SalesOrder.objects.order_by('-created_at')[:30]
    prod_orders = ProductionOrder.objects.order_by('-created_at')[:30]

    context = {
        'page_title': 'Новый складской документ',
        'warehouses': warehouses,
        'materials': materials,
        'products': products,
        'suppliers': suppliers,
        'customers': customers,
        'sales_orders': sales_orders,
        'prod_orders': prod_orders,
        'default_wh': default_wh,
        'default_type': default_type,
        'doc_types': WarehouseDocumentType.choices,
        'today': timezone.localdate().isoformat(),
    }
    return render(request, 'warehouses/documents/create.html', context)


@login_required
@require_POST
def document_post(request, pk):
    doc = get_object_or_404(WarehouseDocument, pk=pk)

    if not can_user_post_doc(request.user, doc.doc_type):
        messages.error(request, 'У вас недостаточно прав для проведения данного складского документа.')
        return redirect('warehouses:document_detail', pk=doc.id)

    try:
        post_document(doc, user=request.user)
        messages.success(request, f'Документ {doc.doc_number} успешно проведён. Движения зафиксированы.')
    except Exception as e:
        messages.error(request, f'Ошибка проведения документа: {e}')

    return redirect('warehouses:document_detail', pk=doc.id)


@login_required
@require_POST
def document_cancel(request, pk):
    doc = get_object_or_404(WarehouseDocument, pk=pk)

    if not can_user_post_doc(request.user, doc.doc_type):
        messages.error(request, 'У вас недостаточно прав для отмены данного складского документа.')
        return redirect('warehouses:document_detail', pk=doc.id)

    try:
        cancel_document(doc, user=request.user)
        messages.warning(request, f'Документ {doc.doc_number} отменён. Выполнены сторнирующие проводки.')
    except Exception as e:
        messages.error(request, f'Не удалось отменить документ: {e}')

    return redirect('warehouses:document_detail', pk=doc.id)


@login_required
def document_pdf(request, pk):
    doc = get_object_or_404(WarehouseDocument, pk=pk)
    pdf_bytes = generate_document_pdf(doc)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"{doc.doc_number}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


# ==============================================================================
# ИНВЕНТАРИЗАЦИЯ
# ==============================================================================

@login_required
def inventory_list(request):
    audits = WarehouseDocument.objects.filter(
        doc_type=WarehouseDocumentType.INVENTORY
    ).select_related('warehouse', 'created_by', 'posted_by').order_by('-created_at')

    context = {
        'page_title': 'Акты инвентаризации складов',
        'audits': audits,
        'can_manage': can_user_manage_warehouses(request.user),
    }
    return render(request, 'warehouses/inventory/list.html', context)


@login_required
def inventory_create(request):
    if not can_user_manage_warehouses(request.user):
        messages.error(request, 'У вас недостаточно прав для создания инвентаризации.')
        return redirect('warehouses:inventory_list')

    if request.method == 'POST':
        warehouse_id = request.POST.get('warehouse')
        notes = request.POST.get('notes', '').strip()
        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

        doc = create_inventory_sheet(warehouse, user=request.user, notes=notes)
        messages.success(request, f'Инвентаризационная ведомость {doc.doc_number} сформирована.')
        return redirect('warehouses:inventory_detail', pk=doc.id)

    warehouses = Warehouse.objects.all()
    context = {
        'page_title': 'Новая инвентаризация склада',
        'warehouses': warehouses,
    }
    return render(request, 'warehouses/inventory/create.html', context)


@login_required
def inventory_detail(request, pk):
    doc = get_object_or_404(
        WarehouseDocument.objects.select_related('warehouse', 'created_by', 'posted_by'),
        pk=pk,
        doc_type=WarehouseDocumentType.INVENTORY
    )
    items = list(doc.items.select_related('material', 'product').all())

    if request.method == 'POST' and doc.is_draft:
        if not can_user_manage_warehouses(request.user):
            messages.error(request, 'У вас недостаточно прав для сохранения результатов инвентаризации.')
            return redirect('warehouses:inventory_detail', pk=doc.id)

        action = request.POST.get('action')

        # Сохранение фактических количеств
        for item in items:
            field_name = f'actual_{item.id}'
            if field_name in request.POST:
                try:
                    actual = Decimal(str(request.POST.get(field_name, '0')))
                except Exception:
                    actual = item.quantity

                item.actual_quantity = actual
                item.discrepancy_quantity = actual - item.quantity
                item.save(update_fields=['actual_quantity', 'discrepancy_quantity'])

        if action == 'reconcile':
            try:
                post_document(doc, user=request.user)
                messages.success(request, f'Инвентаризация {doc.doc_number} успешно проведена. Корректировки внесены.')
            except Exception as e:
                messages.error(request, f'Ошибка проведения инвентаризации: {e}')
        else:
            messages.success(request, 'Фактические остатки успешно сохранены в ведомости.')

        return redirect('warehouses:inventory_detail', pk=doc.id)

    can_edit = can_user_manage_warehouses(request.user) and doc.is_draft

    total_surplus = sum((i.discrepancy_quantity for i in items if i.discrepancy_quantity and i.discrepancy_quantity > 0), Decimal('0'))
    total_shortage = sum((abs(i.discrepancy_quantity) for i in items if i.discrepancy_quantity and i.discrepancy_quantity < 0), Decimal('0'))

    context = {
        'page_title': f'Инвентаризация {doc.doc_number}',
        'doc': doc,
        'items': items,
        'can_edit': can_edit,
        'total_surplus': total_surplus,
        'total_shortage': total_shortage,
    }
    return render(request, 'warehouses/inventory/detail.html', context)


# ==============================================================================
# QR-КОДЫ, ШТРИХКОДЫ И ЭТИКЕТКИ
# ==============================================================================

@login_required
def qr_image_view(request, sku):
    """Возвращает PNG изображение QR-кода по артикулу."""
    png_bytes = generate_qr_png_bytes(sku, box_size=6, border=2)
    return HttpResponse(png_bytes, content_type='image/png')


@login_required
def item_label_pdf_view(request, item_type, item_id):
    """Печать термоэтикетки со штрихкодом и QR-кодом для ТМЦ."""
    if item_type == 'material':
        obj = get_object_or_404(Material, pk=item_id)
    elif item_type == 'product':
        obj = get_object_or_404(Product, pk=item_id)
    else:
        return HttpResponse('Неизвестный тип ТМЦ', status=400)

    pdf_bytes = generate_item_label_pdf(item_type, obj)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="label_{obj.sku}.pdf"'
    return response


# ==============================================================================
# СКАНЕР ШТРИХКОДОВ И QR
# ==============================================================================

@login_required
def scanner_view(request):
    """Терминал сканирования штрихкодов и QR-кодов."""
    return render(request, 'warehouses/scan.html', {'page_title': 'Терминал сканирования QR/Штрихкодов'})


@login_required
def scanner_lookup(request):
    """API поиска ТМЦ по считанному штрихкоду или артикулу."""
    code = request.GET.get('code', '').strip()
    if not code:
        return JsonResponse({'found': False, 'error': 'Пустой штрихкод'})

    # Очистка возможных префиксов системы
    clean_code = code.replace('FURNICORE:MATERIAL:', '').replace('FURNICORE:PRODUCT:', '').replace('FURNICORE:', '')
    if ':' in clean_code:
        parts = clean_code.split(':')
        clean_code = parts[0]

    # 1. Поиск в материалах (WH-1)
    material = Material.objects.filter(
        Q(sku__iexact=clean_code) | Q(barcode__iexact=clean_code)
    ).first()

    if material:
        wh1 = Warehouse.objects.filter(warehouse_type=WarehouseType.RAW_MATERIALS).first()
        balance = StockBalance.objects.filter(warehouse=wh1, material=material).first()
        current_stock = balance.current_stock if balance else Decimal('0.000')

        return JsonResponse({
            'found': True,
            'item_type': 'material',
            'id': str(material.id),
            'name': material.name,
            'sku': material.sku,
            'barcode': material.effective_barcode,
            'category': material.get_category_display(),
            'warehouse': 'WH-1 (Склад сырья)',
            'warehouse_code': 'WH-1',
            'location': material.location or 'Не указана',
            'unit': material.unit,
            'current_stock': float(current_stock),
            'min_stock': float(material.min_stock_level),
            'is_low_stock': current_stock <= material.min_stock_level,
            'price_kzt': float(material.purchase_cost_kzt),
            'supplier': material.supplier.name if material.supplier else '—',
            'label_url': f'/warehouses/label/material/{material.id}/',
        })

    # 2. Поиск в готовой продукции (WH-2)
    product = Product.objects.filter(
        Q(sku__iexact=clean_code) | Q(barcode__iexact=clean_code)
    ).first()

    if product:
        wh2 = Warehouse.objects.filter(warehouse_type=WarehouseType.FINISHED_PRODUCTS).first()
        balance = StockBalance.objects.filter(warehouse=wh2, product=product).first()
        current_stock = balance.current_stock if balance else Decimal('0.000')
        reserved_stock = balance.reserved_stock if balance else Decimal('0.000')
        available_stock = balance.available_stock if balance else Decimal('0.000')

        return JsonResponse({
            'found': True,
            'item_type': 'product',
            'id': str(product.id),
            'name': product.name,
            'sku': product.sku,
            'barcode': product.effective_barcode,
            'category': product.get_category_display(),
            'warehouse': 'WH-2 (Склад готовой продукции)',
            'warehouse_code': 'WH-2',
            'unit': 'шт',
            'current_stock': float(current_stock),
            'reserved_stock': float(reserved_stock),
            'available_stock': float(available_stock),
            'sale_price_kzt': float(product.sale_price_kzt),
            'label_url': f'/warehouses/label/product/{product.id}/',
        })

    return JsonResponse({
        'found': False,
        'code': code,
        'message': f'Позиция с кодом "{code}" не найдена в каталогах FurniCore.'
    })
