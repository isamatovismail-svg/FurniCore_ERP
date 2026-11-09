from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q, Count
from apps.sales.models import SalesOrder, OrderStatus, Customer


@login_required
def index(request):
    status_filter = request.GET.get('status', '')
    q = request.GET.get('q', '').strip()

    orders = SalesOrder.objects.select_related('customer', 'created_by').prefetch_related('items')
    if status_filter:
        orders = orders.filter(status=status_filter)
    if q:
        orders = orders.filter(
            Q(order_number__icontains=q) |
            Q(customer__full_name__icontains=q) |
            Q(customer__company_name__icontains=q)
        )
    orders = orders.order_by('-created_at')

    statuses = [(s.value, s.label) for s in OrderStatus]
    status_counts = {s.value: SalesOrder.objects.filter(status=s.value).count() for s in OrderStatus}

    total_revenue = SalesOrder.objects.filter(
        status__in=[OrderStatus.DELIVERED, OrderStatus.SHIPPED, OrderStatus.CONFIRMED]
    ).aggregate(total=Sum('total_amount_kzt'))['total'] or 0

    context = {
        'page_title': 'Продажи',
        'orders': orders,
        'statuses': statuses,
        'status_filter': status_filter,
        'status_counts': status_counts,
        'q': q,
        'total_revenue': total_revenue,
        'total_orders': SalesOrder.objects.count(),
        'total_customers': Customer.objects.count(),
    }
    return render(request, 'sales/index.html', context)


@login_required
def customers_list(request):
    q = request.GET.get('q', '').strip()
    customers = Customer.objects.annotate(order_count=Count('orders')).all()
    if q:
        customers = customers.filter(
            Q(full_name__icontains=q) |
            Q(company_name__icontains=q) |
            Q(phone__icontains=q) |
            Q(city__icontains=q)
        )
    customers = customers.order_by('full_name')

    context = {
        'page_title': 'Клиенты (CRM)',
        'customers': customers,
        'q': q,
        'total_customers': Customer.objects.count(),
    }
    return render(request, 'sales/customers.html', context)
