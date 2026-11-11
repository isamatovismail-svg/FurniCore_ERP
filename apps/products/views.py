from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from apps.accounts.models import UserRole
from apps.products.models import Product, ProductCategory, ProductVariant
from apps.warehouses.models import StockBalance, Warehouse, WarehouseType


def can_manage_products(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.role in [
        UserRole.ADMIN,
        UserRole.PRODUCTION_HEAD,
        UserRole.SALES_MANAGER,
        UserRole.WAREHOUSE_MANAGER,
    ] or user.is_superuser


@login_required
def index(request):
    """Каталог продукции с фильтрами, поиском и складскими остатками на WH-2."""
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    status_filter = request.GET.get('status', 'active')

    products = Product.objects.all()

    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'archived':
        products = products.filter(is_active=False)

    if q:
        products = products.filter(
            Q(name__icontains=q) |
            Q(sku__icontains=q) |
            Q(barcode__icontains=q) |
            Q(dimensions__icontains=q)
        )
    if category:
        products = products.filter(category=category)
    products = products.order_by('name')

    balances = {
        sb.product_id: sb
        for sb in StockBalance.objects.filter(
            warehouse__warehouse_type=WarehouseType.FINISHED_PRODUCTS,
            product__isnull=False,
        )
    }
    products_with_stock = []
    for p in products:
        sb = balances.get(p.id)
        stock = sb.current_stock if sb else Decimal('0.00')
        reserved = sb.reserved_stock if sb else Decimal('0.00')
        available = sb.available_stock if sb else Decimal('0.00')
        products_with_stock.append({
            'product': p,
            'stock': stock,
            'reserved': reserved,
            'available': available,
        })

    categories = [(c.value, c.label) for c in ProductCategory]
    total_active = Product.objects.filter(is_active=True).count()
    total_archived = Product.objects.filter(is_active=False).count()

    context = {
        'page_title': 'Каталог готовой мебели',
        'products_with_stock': products_with_stock,
        'categories': categories,
        'q': q,
        'selected_category': category,
        'status_filter': status_filter,
        'total_count': len(products_with_stock),
        'total_active': total_active,
        'total_archived': total_archived,
        'can_manage': can_manage_products(request.user),
    }
    return render(request, 'products/index.html', context)


@login_required
def detail(request, pk):
    """Карточка изделия с характеристиками, активным BOM и историей."""
    product = get_object_or_404(Product, pk=pk)
    stock_balance = StockBalance.objects.filter(
        warehouse__warehouse_type=WarehouseType.FINISHED_PRODUCTS, product=product
    ).first()

    context = {
        'page_title': product.name,
        'product': product,
        'stock_balance': stock_balance,
        'boms': product.boms.all().order_by('-version'),
        'can_manage': can_manage_products(request.user),
    }
    return render(request, 'products/detail.html', context)


@login_required
def product_create(request):
    """Создание нового изделия в каталоге."""
    if not can_manage_products(request.user):
        messages.error(request, 'У вас недостаточно прав для добавления изделий.')
        return redirect('products:index')

    if request.method == 'POST':
        sku = request.POST.get('sku', '').strip()
        barcode = request.POST.get('barcode', '').strip()
        name = request.POST.get('name', '').strip()
        category = request.POST.get('category', ProductCategory.WARDROBE)
        dimensions = request.POST.get('dimensions', '').strip()
        description = request.POST.get('description', '').strip()
        cost = Decimal(str(request.POST.get('production_cost_kzt') or '0.00'))
        price = Decimal(str(request.POST.get('sale_price_kzt') or '0.00'))

        if not sku or not name:
            messages.error(request, 'Артикул и наименование изделия обязательны.')
        elif Product.objects.filter(sku=sku).exists():
            messages.error(request, f'Изделие с артикулом «{sku}» уже существует.')
        else:
            product = Product.objects.create(
                sku=sku,
                barcode=barcode,
                name=name,
                category=category,
                dimensions=dimensions,
                description=description,
                production_cost_kzt=cost,
                sale_price_kzt=price,
            )
            # Инициализация баланса на WH-2
            wh2 = Warehouse.objects.filter(warehouse_type=WarehouseType.FINISHED_PRODUCTS).first()
            if wh2:
                StockBalance.objects.get_or_create(warehouse=wh2, product=product)

            messages.success(request, f'Изделие «{product.name}» успешно создано.')
            return redirect('products:detail', pk=product.id)

    return render(request, 'products/form.html', {
        'page_title': 'Новое мебельное изделие',
        'product': None,
        'categories': ProductCategory.choices,
    })


@login_required
def product_edit(request, pk):
    """Редактирование карточки изделия."""
    if not can_manage_products(request.user):
        messages.error(request, 'У вас недостаточно прав для редактирования изделий.')
        return redirect('products:index')

    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        sku = request.POST.get('sku', '').strip()
        barcode = request.POST.get('barcode', '').strip()
        name = request.POST.get('name', '').strip()
        category = request.POST.get('category', ProductCategory.WARDROBE)
        dimensions = request.POST.get('dimensions', '').strip()
        description = request.POST.get('description', '').strip()
        cost = Decimal(str(request.POST.get('production_cost_kzt') or '0.00'))
        price = Decimal(str(request.POST.get('sale_price_kzt') or '0.00'))

        if not sku or not name:
            messages.error(request, 'Артикул и наименование изделия обязательны.')
        elif Product.objects.filter(sku=sku).exclude(id=product.id).exists():
            messages.error(request, f'Артикул «{sku}» уже используется другим изделием.')
        else:
            product.sku = sku
            product.barcode = barcode
            product.name = name
            product.category = category
            product.dimensions = dimensions
            product.description = description
            product.production_cost_kzt = cost
            product.sale_price_kzt = price
            product.save()
            messages.success(request, f'Карточка изделия «{product.name}» обновлена.')
            return redirect('products:detail', pk=product.id)

    return render(request, 'products/form.html', {
        'page_title': f'Редактирование: {product.name}',
        'product': product,
        'categories': ProductCategory.choices,
    })


@login_required
def product_archive(request, pk):
    """Архивирование изделия."""
    if not can_manage_products(request.user):
        messages.error(request, 'У вас недостаточно прав.')
        return redirect('products:index')

    product = get_object_or_404(Product, pk=pk)
    product.is_active = not product.is_active
    product.save(update_fields=['is_active'])

    action_word = 'активировано' if product.is_active else 'перенесено в архив'
    messages.success(request, f'Изделие «{product.name}» {action_word}.')
    return redirect('products:index')
