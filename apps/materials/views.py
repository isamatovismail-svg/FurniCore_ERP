from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q


@login_required
def index(request):
    from apps.materials.models import Material, MaterialCategory
    from apps.warehouses.models import StockBalance

    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')

    materials = Material.objects.select_related('supplier').all()
    if q:
        materials = materials.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    if category:
        materials = materials.filter(category=category)
    materials = materials.order_by('name')

    # Attach stock balances
    balances = {
        sb.material_id: sb
        for sb in StockBalance.objects.filter(
            warehouse__warehouse_type='RAW_MATERIALS',
            material__isnull=False,
        )
    }
    materials_with_stock = []
    for mat in materials:
        sb = balances.get(mat.id)
        stock = sb.current_stock if sb else 0
        low = sb.is_low_stock if sb else False
        materials_with_stock.append({'material': mat, 'stock': stock, 'low': low, 'sb': sb})

    categories = [(c.value, c.label) for c in MaterialCategory]

    context = {
        'page_title': 'Материалы и сырьё',
        'materials_with_stock': materials_with_stock,
        'categories': categories,
        'q': q,
        'selected_category': category,
        'total_count': len(materials_with_stock),
    }
    return render(request, 'materials/index.html', context)
