from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
import datetime


@login_required
def index(request):
    """Dashboard 2.0 — real-time analytics & operational KPIs from PostgreSQL."""
    today = timezone.localdate()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    # Date filter
    period = request.GET.get('period', 'month')
    if period == 'today':
        date_from = today
        date_to = today
        period_label = 'за сегодня'
    elif period == 'yesterday':
        date_from = today - datetime.timedelta(days=1)
        date_to = today - datetime.timedelta(days=1)
        period_label = 'за вчера'
    elif period == 'week':
        date_from = today - datetime.timedelta(days=7)
        date_to = today
        period_label = 'за последние 7 дней'
    elif period == 'month':
        date_from = month_start
        date_to = today
        period_label = 'за текущий месяц'
    elif period == 'year':
        date_from = year_start
        date_to = today
        period_label = 'за текущий год'
    else:
        date_from = month_start
        date_to = today
        period = 'month'
        period_label = 'за текущий месяц'

    from apps.warehouses.models import StockBalance, Warehouse, StockMovement, WarehouseType
    from apps.materials.models import Material
    from apps.products.models import Product, ProductCategory
    from apps.sales.models import SalesOrder, OrderStatus
    from apps.finance.models import Expense
    from apps.production.models import ProductionOrder, ProductionOrderStatus
    from apps.notifications.models import Notification

    # 1. Warehouses stats
    wh1 = Warehouse.objects.filter(warehouse_type=WarehouseType.RAW_MATERIALS).first()
    wh2 = Warehouse.objects.filter(warehouse_type=WarehouseType.FINISHED_PRODUCTS).first()

    wh1_balances = list(StockBalance.objects.filter(
        warehouse=wh1, material__isnull=False
    ).select_related('material')) if wh1 else []

    wh2_balances = list(StockBalance.objects.filter(
        warehouse=wh2, product__isnull=False
    ).select_related('product')) if wh2 else []

    # Monetary value of WH-1
    wh1_total_value = sum(
        (b.current_stock * b.material.purchase_cost_kzt for b in wh1_balances if b.material),
        Decimal('0')
    )
    wh1_positions_count = len(wh1_balances)

    # Physical items on WH-2
    wh2_items_count = sum(b.current_stock for b in wh2_balances)
    wh2_reserved_count = sum(b.reserved_stock for b in wh2_balances)
    wh2_available_count = sum(b.available_stock for b in wh2_balances)
    wh2_total_value = sum(
        (b.current_stock * b.product.sale_price_kzt for b in wh2_balances if b.product),
        Decimal('0')
    )

    # Low-stock materials
    low_stock_materials = [b for b in wh1_balances if b.is_low_stock]
    low_stock_count = len(low_stock_materials)

    # 2. Sales stats for selected period
    sales_qs = SalesOrder.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )
    total_revenue = sales_qs.filter(
        status__in=[OrderStatus.CONFIRMED, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    ).aggregate(total=Sum('total_amount_kzt'))['total'] or Decimal('0.00')

    # All-time revenue if period revenue is 0 for clear context
    all_time_revenue = SalesOrder.objects.filter(
        status__in=[OrderStatus.CONFIRMED, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    ).aggregate(total=Sum('total_amount_kzt'))['total'] or Decimal('0.00')

    pending_orders = SalesOrder.objects.filter(
        status__in=[OrderStatus.NEW, OrderStatus.CONFIRMED]
    ).count()

    recent_orders = SalesOrder.objects.select_related('customer').order_by('-created_at')[:5]

    # 3. Expenses stats for selected period
    expenses_qs = Expense.objects.filter(
        payment_date__gte=date_from,
        payment_date__lte=date_to,
    )
    total_expenses = expenses_qs.aggregate(total=Sum('amount_kzt'))['total'] or Decimal('0.00')

    gross_profit = total_revenue - total_expenses
    net_profit = gross_profit

    # 4. Production orders
    active_production = ProductionOrder.objects.filter(
        status__in=[ProductionOrderStatus.IN_PROGRESS, ProductionOrderStatus.MATERIALS_RESERVED]
    ).count()
    planned_production = ProductionOrder.objects.filter(
        status__in=[ProductionOrderStatus.DRAFT, ProductionOrderStatus.WAITING, ProductionOrderStatus.CHECKING_MATERIALS]
    ).count()
    completed_production = ProductionOrder.objects.filter(
        status=ProductionOrderStatus.COMPLETED
    ).count()
    total_production = ProductionOrder.objects.count()

    # 5. Recent warehouse operations
    recent_movements = StockMovement.objects.select_related(
        'warehouse', 'material', 'product', 'performed_by'
    ).order_by('-created_at')[:6]

    # 6. Unread notifications
    unread_notifications = Notification.objects.filter(
        user=request.user, is_read=False
    ).count()

    # 7. Chart 1: Monthly revenue and expenses (last 6 months)
    chart_labels = []
    chart_revenue = []
    chart_expenses = []
    for i in range(5, -1, -1):
        d = today.replace(day=1) - datetime.timedelta(days=i * 28)
        m_start = d.replace(day=1)
        if d.month == 12:
            m_end = d.replace(year=d.year + 1, month=1, day=1) - datetime.timedelta(days=1)
        else:
            m_end = d.replace(month=d.month + 1, day=1) - datetime.timedelta(days=1)

        rev = SalesOrder.objects.filter(
            created_at__date__gte=m_start,
            created_at__date__lte=m_end,
            status__in=[OrderStatus.CONFIRMED, OrderStatus.SHIPPED, OrderStatus.DELIVERED],
        ).aggregate(total=Sum('total_amount_kzt'))['total'] or Decimal('0')

        exp = Expense.objects.filter(
            payment_date__gte=m_start,
            payment_date__lte=m_end,
        ).aggregate(total=Sum('amount_kzt'))['total'] or Decimal('0')

        MONTHS_RU = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
                     'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
        chart_labels.append(f"{MONTHS_RU[m_start.month - 1]} {m_start.year}")
        chart_revenue.append(float(rev))
        chart_expenses.append(float(exp))

    # 8. Chart 2: Finished furniture production stock by category
    category_labels = []
    category_stock = []
    category_colors = [
        '#173B35', '#285F4D', '#4D8D83', '#75A69E', '#C5D8D4'
    ]
    for idx, cat in enumerate(ProductCategory):
        cat_balances = [b for b in wh2_balances if b.product and b.product.category == cat.value]
        qty = sum((float(b.current_stock) for b in cat_balances), 0.0)
        if qty > 0 or len(category_labels) < 5:
            category_labels.append(cat.label)
            category_stock.append(qty)

    period_choices = {
        'today': 'Сегодня',
        'yesterday': 'Вчера',
        'week': 'Неделя',
        'month': 'Месяц',
        'year': 'Год',
    }

    context = {
        'page_title': 'Дашборд',
        'period': period,
        'period_label': period_label,
        'period_choices': period_choices,
        'date_from': date_from,
        'date_to': date_to,
        # Financial KPIs
        'total_revenue': total_revenue,
        'all_time_revenue': all_time_revenue,
        'total_expenses': total_expenses,
        'gross_profit': gross_profit,
        'net_profit': net_profit,
        # Warehouses
        'wh1': wh1,
        'wh2': wh2,
        'wh1_total_value': wh1_total_value,
        'wh1_positions_count': wh1_positions_count,
        'wh2_items_count': wh2_items_count,
        'wh2_reserved_count': wh2_reserved_count,
        'wh2_available_count': wh2_available_count,
        'wh2_total_value': wh2_total_value,
        'low_stock_count': low_stock_count,
        'low_stock_materials': low_stock_materials[:5],
        # Operations
        'active_production': active_production,
        'planned_production': planned_production,
        'completed_production': completed_production,
        'total_production': total_production,
        'pending_orders': pending_orders,
        'recent_orders': recent_orders,
        'recent_movements': recent_movements,
        # Counts
        'materials_count': Material.objects.count(),
        'products_count': Product.objects.count(),
        'unread_notifications': unread_notifications,
        # Chart data
        'chart_labels': chart_labels,
        'chart_revenue': chart_revenue,
        'chart_expenses': chart_expenses,
        'category_labels': category_labels,
        'category_stock': category_stock,
        'category_colors': category_colors[:len(category_labels)],
    }
    return render(request, 'dashboard/index.html', context)
