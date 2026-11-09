from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q


@login_required
def index(request):
    from apps.products.models import Product, ProductCategory
    from apps.warehouses.models import StockBalance

    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')

    products = Product.objects.all()
    if q:
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    if category:
        products = products.filter(category=category)
    products = products.order_by('name')

    balances = {
        sb.product_id: sb.current_stock
        for sb in StockBalance.objects.filter(
            warehouse__warehouse_type='FINISHED_PRODUCTS',
            product__isnull=False,
        )
    }
    products_with_stock = [
        {'product': p, 'stock': balances.get(p.id, 0)}
        for p in products
    ]

    categories = [(c.value, c.label) for c in ProductCategory]

    context = {
        'page_title': 'Каталог продукции',
        'products_with_stock': products_with_stock,
        'categories': categories,
        'q': q,
        'selected_category': category,
        'total_count': len(products_with_stock),
    }
    return render(request, 'products/index.html', context)


@login_required
def detail(request, pk):
    from apps.products.models import Product
    from apps.warehouses.models import StockBalance
    product = get_object_or_404(Product, pk=pk)
    stock_balance = StockBalance.objects.filter(
        warehouse__warehouse_type='FINISHED_PRODUCTS', product=product
    ).first()
    context = {
        'page_title': product.name,
        'product': product,
        'stock_balance': stock_balance,
    }
    return render(request, 'products/detail.html', context)
