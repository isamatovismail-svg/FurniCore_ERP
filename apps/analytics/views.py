from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg
from decimal import Decimal
from apps.sales.models import SalesOrder, OrderStatus
from apps.finance.models import Expense
from apps.products.models import Product
from apps.production.models import ProductionOrder, ProductionOrderStatus
from apps.warehouses.models import StockBalance


@login_required
def index(request):
    # Total sales
    total_sales = SalesOrder.objects.filter(
        status__in=[OrderStatus.CONFIRMED, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    ).aggregate(t=Sum('total_amount_kzt'))['t'] or Decimal('0.00')

    avg_order_check = SalesOrder.objects.aggregate(a=Avg('total_amount_kzt'))['a'] or Decimal('0.00')

    # Total expenses
    total_expenses = Expense.objects.aggregate(t=Sum('amount_kzt'))['t'] or Decimal('0.00')

    # Net margin
    net_margin_pct = round(float((total_sales - total_expenses) / total_sales) * 100, 1) if total_sales > Decimal('0') else 0

    # Production stats
    completed_orders = ProductionOrder.objects.filter(status=ProductionOrderStatus.COMPLETED).count()
    active_orders = ProductionOrder.objects.filter(status=ProductionOrderStatus.IN_PROGRESS).count()

    # Product margins
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
