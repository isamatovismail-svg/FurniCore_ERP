from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from apps.accounts.models import UserRole
from apps.accounts.decorators import deny_demo_viewer
from apps.materials.models import Material, MaterialCategory
from apps.suppliers.models import Supplier
from apps.warehouses.models import StockBalance, Warehouse, WarehouseType


def can_manage_materials(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.role in [
        UserRole.OWNER,
        UserRole.ADMIN,
        UserRole.PRODUCTION_MANAGER,
        UserRole.WAREHOUSE_MANAGER,
    ] or user.is_superuser


@login_required
def index(request):
    """Каталог материалов с фильтрацией по категориям, поиском и складскими остатками WH-1."""
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    status_filter = request.GET.get('status', 'active')

    materials = Material.objects.select_related('supplier').all()

    if status_filter == 'active':
        materials = materials.filter(is_active=True)
    elif status_filter == 'archived':
        materials = materials.filter(is_active=False)

    if q:
        materials = materials.filter(
            Q(name__icontains=q) |
            Q(sku__icontains=q) |
            Q(barcode__icontains=q) |
            Q(location__icontains=q)
        )
    if category:
        materials = materials.filter(category=category)
    materials = materials.order_by('name')

    # Складские остатки на складе WH-1
    balances = {
        sb.material_id: sb
        for sb in StockBalance.objects.filter(
            warehouse__warehouse_type=WarehouseType.RAW_MATERIALS,
            material__isnull=False,
        )
    }
    materials_with_stock = []
    for mat in materials:
        sb = balances.get(mat.id)
        stock = sb.current_stock if sb else Decimal('0.000')
        low = sb.is_low_stock if sb else False
        materials_with_stock.append({'material': mat, 'stock': stock, 'low': low, 'sb': sb})

    categories = [(c.value, c.label) for c in MaterialCategory]

    total_active = Material.objects.filter(is_active=True).count()
    total_archived = Material.objects.filter(is_active=False).count()

    context = {
        'page_title': 'Материалы и сырьё',
        'materials_with_stock': materials_with_stock,
        'categories': categories,
        'q': q,
        'selected_category': category,
        'status_filter': status_filter,
        'total_count': len(materials_with_stock),
        'total_active': total_active,
        'total_archived': total_archived,
        'can_manage': can_manage_materials(request.user),
    }
    return render(request, 'materials/index.html', context)


@login_required
@deny_demo_viewer
def material_create(request):
    """Создание нового материала / позиции сырья."""
    if not can_manage_materials(request.user):
        messages.error(request, 'У вас недостаточно прав для добавления материалов.')
        return redirect('materials:index')

    suppliers = Supplier.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        sku = request.POST.get('sku', '').strip()
        barcode = request.POST.get('barcode', '').strip()
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', MaterialCategory.OTHER)
        unit = request.POST.get('unit', 'шт').strip()
        purchase_cost = Decimal(str(request.POST.get('purchase_cost_kzt') or '0.00'))
        min_stock = Decimal(str(request.POST.get('min_stock_level') or '0.000'))
        location = request.POST.get('location', '').strip()
        supplier_id = request.POST.get('supplier') or None

        supplier = Supplier.objects.filter(id=supplier_id).first() if supplier_id else None

        if not sku or not name:
            messages.error(request, 'Артикул и наименование материала обязательны для заполнения.')
        elif Material.objects.filter(sku=sku).exists():
            messages.error(request, f'Материал с артикулом «{sku}» уже зарегистрирован в системе.')
        else:
            mat = Material.objects.create(
                sku=sku,
                barcode=barcode,
                name=name,
                description=description,
                category=category,
                unit=unit,
                purchase_cost_kzt=purchase_cost,
                min_stock_level=min_stock,
                location=location,
                supplier=supplier,
            )
            # Инициализация нулевого остатка на WH-1
            wh1 = Warehouse.objects.filter(warehouse_type=WarehouseType.RAW_MATERIALS).first()
            if wh1:
                StockBalance.objects.get_or_create(warehouse=wh1, material=mat)

            messages.success(request, f'Материал «{mat.name}» ({mat.sku}) успешно добавлен.')
            return redirect('materials:index')

    return render(request, 'materials/form.html', {
        'page_title': 'Новый материал / сырье',
        'material': None,
        'categories': MaterialCategory.choices,
        'suppliers': suppliers,
    })


@login_required
@deny_demo_viewer
def material_edit(request, pk):
    """Редактирование карточки материала."""
    if not can_manage_materials(request.user):
        messages.error(request, 'У вас недостаточно прав для редактирования материалов.')
        return redirect('materials:index')

    mat = get_object_or_404(Material, pk=pk)
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        sku = request.POST.get('sku', '').strip()
        barcode = request.POST.get('barcode', '').strip()
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', MaterialCategory.OTHER)
        unit = request.POST.get('unit', 'шт').strip()
        purchase_cost = Decimal(str(request.POST.get('purchase_cost_kzt') or '0.00'))
        min_stock = Decimal(str(request.POST.get('min_stock_level') or '0.000'))
        location = request.POST.get('location', '').strip()
        supplier_id = request.POST.get('supplier') or None

        supplier = Supplier.objects.filter(id=supplier_id).first() if supplier_id else None

        if not sku or not name:
            messages.error(request, 'Артикул и наименование обязательны.')
        elif Material.objects.filter(sku=sku).exclude(id=mat.id).exists():
            messages.error(request, f'Артикул «{sku}» уже используется другим материалом.')
        else:
            mat.sku = sku
            mat.barcode = barcode
            mat.name = name
            mat.description = description
            mat.category = category
            mat.unit = unit
            mat.purchase_cost_kzt = purchase_cost
            mat.min_stock_level = min_stock
            mat.location = location
            mat.supplier = supplier
            mat.save()
            messages.success(request, f'Данные материала «{mat.name}» обновлены.')
            return redirect('materials:index')

    return render(request, 'materials/form.html', {
        'page_title': f'Редактирование: {mat.name}',
        'material': mat,
        'categories': MaterialCategory.choices,
        'suppliers': suppliers,
    })


@login_required
@deny_demo_viewer
def material_archive(request, pk):
    """Архивирование материала (безопасное снятие с активности)."""
    if not can_manage_materials(request.user):
        messages.error(request, 'У вас недостаточно прав.')
        return redirect('materials:index')

    mat = get_object_or_404(Material, pk=pk)
    mat.is_active = not mat.is_active
    mat.save(update_fields=['is_active'])

    action_word = 'активирован' if mat.is_active else 'перенесён в архив'
    messages.success(request, f'Материал «{mat.name}» {action_word}.')
    return redirect('materials:index')
