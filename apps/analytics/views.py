import json
from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Avg
from apps.sales.models import SalesOrder, OrderStatus, Customer
from apps.finance.models import Expense
from apps.products.models import Product
from apps.production.models import ProductionOrder, ProductionOrderStatus
from apps.suppliers.models import Supplier


@login_required
def index(request):
    """General factory analytical overview."""
    total_sales = SalesOrder.objects.filter(
        status__in=[OrderStatus.CONFIRMED, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    ).aggregate(t=Sum('total_amount_kzt'))['t'] or Decimal('0.00')

    avg_order_check = SalesOrder.objects.aggregate(a=Avg('total_amount_kzt'))['a'] or Decimal('0.00')
    total_expenses = Expense.objects.aggregate(t=Sum('amount_kzt'))['t'] or Decimal('0.00')

    net_margin_pct = round(float((total_sales - total_expenses) / total_sales) * 100, 1) if total_sales > Decimal('0') else 0

    completed_orders = ProductionOrder.objects.filter(status=ProductionOrderStatus.COMPLETED).count()
    active_orders = ProductionOrder.objects.filter(status=ProductionOrderStatus.IN_PROGRESS).count()
    products = Product.objects.all().order_by('-sale_price_kzt')[:6]

    context = {
        'page_title': 'Аналитика и отчёты',
        'total_sales': total_sales,
        'total_expenses': total_expenses,
        'avg_order_check': avg_order_check,
        'net_margin_pct': net_margin_pct,
        'completed_orders': completed_orders,
        'active_orders': active_orders,
        'products': products,
    }
    return render(request, 'analytics/index.html', context)


@login_required
def logistics_map(request):
    """
    Interactive Logistics & Geography Map of FurniCore ERP:
    Displays Factory & Warehouses (WH-1, WH-2), Suppliers, and Client Delivery Destinations.
    Powered by Leaflet and OpenStreetMap.
    """
    # 1. Factory & Warehouses (Almaty Industrial Zone)
    locations = [
        {
            'id': 'factory-wh',
            'type': 'factory',
            'name': 'Фабрика FurniCore & Склады WH-1/WH-2',
            'category_label': 'Фабрика и Склады',
            'city': 'Алматы',
            'address': 'г. Алматы, ул. Промышленная, 12',
            'lat': 43.2775,
            'lng': 76.8958,
            'details': 'Склад сырья WH-1 и склад готовой мебели WH-2. Производственный цех.',
            'status': 'Штатный режим',
            'color': '#173B35',
        }
    ]

    # City coordinate heuristics for demo partners
    CITY_COORDS = {
        'алматы': (43.238949, 76.889709),
        'нур-султан': (51.169392, 71.449074),
        'астана': (51.169392, 71.449074),
        'шымкент': (42.341667, 69.5901),
    }

    # 2. Suppliers
    suppliers = Supplier.objects.filter(is_active=True)
    coords_offset = 0.015
    for idx, sup in enumerate(suppliers):
        addr_lower = (sup.address or '').lower()
        base_lat, base_lng = (43.238949, 76.889709)  # default Almaty
        city_name = 'Алматы'
        for k, coords in CITY_COORDS.items():
            if k in addr_lower:
                base_lat, base_lng = coords
                city_name = k.capitalize()
                break

        # Slight jitter to avoid perfect overlap of pins in same city
        lat = base_lat + ((idx % 3) - 1) * coords_offset + 0.005
        lng = base_lng + ((idx // 3) + 1) * coords_offset

        po_count = sup.purchase_orders.count()
        locations.append({
            'id': f'supplier-{sup.id}',
            'type': 'supplier',
            'name': sup.name,
            'category_label': 'Поставщик материалов',
            'city': city_name,
            'address': sup.address or 'Адрес не указан',
            'lat': round(lat, 5),
            'lng': round(lng, 5),
            'details': f'Контакт: {sup.contact_person or "—"} ({sup.phone or "—"}). Активных заказов на закупку: {po_count}.',
            'status': 'Активен',
            'color': '#1E40AF',  # Blue
        })

    # 3. Customers & Delivery points
    customers = Customer.objects.filter(is_active=True)
    for idx, cust in enumerate(customers):
        city_str = (cust.city or '').lower()
        addr_lower = (cust.address or '').lower()
        base_lat, base_lng = (43.238949, 76.889709)
        city_name = cust.city or 'Алматы'
        for k, coords in CITY_COORDS.items():
            if k in city_str or k in addr_lower:
                base_lat, base_lng = coords
                city_name = k.capitalize()
                break

        lat = base_lat - ((idx % 2) + 1) * coords_offset - 0.004
        lng = base_lng - ((idx % 3) - 1) * coords_offset

        orders_count = cust.orders.count()
        locations.append({
            'id': f'customer-{cust.id}',
            'type': 'customer',
            'name': cust.company_name or cust.full_name,
            'category_label': 'Клиент / Точка доставки',
            'city': city_name,
            'address': cust.address or f'г. {city_name}',
            'lat': round(lat, 5),
            'lng': round(lng, 5),
            'details': f'Телефон: {cust.phone or "—"}. Заказов мебели в системе: {orders_count}.',
            'status': 'Постоянный клиент',
            'color': '#D97706',  # Amber
        })

    context = {
        'page_title': 'Логистическая карта партнёров',
        'locations_json': json.dumps(locations, ensure_ascii=False),
        'total_locations': len(locations),
        'suppliers_count': suppliers.count(),
        'customers_count': customers.count(),
    }
    return render(request, 'analytics/map.html', context)
