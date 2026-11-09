from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from decimal import Decimal


@login_required
def index(request):
    from apps.finance.models import Expense, ExpenseCategory
    from apps.sales.models import SalesOrder, OrderStatus

    category_filter = request.GET.get('category', '')
    q = request.GET.get('q', '').strip()

    expenses = Expense.objects.select_related('recorded_by').all()
    if category_filter:
        expenses = expenses.filter(category=category_filter)
    if q:
        expenses = expenses.filter(
            Q(description__icontains=q) |
            Q(payee__icontains=q)
        )
    expenses = expenses.order_by('-payment_date')

    categories = [(c.value, c.label) for c in ExpenseCategory]

    # Revenue from confirmed/delivered/shipped orders
    total_revenue = SalesOrder.objects.filter(
        status__in=[OrderStatus.CONFIRMED, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    ).aggregate(t=Sum('total_amount_kzt'))['t'] or Decimal('0.00')

    # Total expenses
    grand_total_expenses = Expense.objects.aggregate(t=Sum('amount_kzt'))['t'] or Decimal('0.00')

    # Net / Gross Profit
    net_profit = total_revenue - grand_total_expenses

    # Total by categories
    categories_breakdown = []
    for c in ExpenseCategory:
        total = Expense.objects.filter(category=c.value).aggregate(t=Sum('amount_kzt'))['t'] or Decimal('0.00')
        if total > Decimal('0'):
            pct = round(float(total / grand_total_expenses) * 100, 1) if grand_total_expenses > Decimal('0') else 0
            categories_breakdown.append({
                'key': c.value,
                'label': c.label,
                'total': total,
                'percent': pct,
            })
    categories_breakdown.sort(key=lambda x: x['total'], reverse=True)

    context = {
        'page_title': 'Финансы',
        'expenses': expenses,
        'categories': categories,
        'category_filter': category_filter,
        'q': q,
        'total_revenue': total_revenue,
        'grand_total_expenses': grand_total_expenses,
        'net_profit': net_profit,
        'categories_breakdown': categories_breakdown,
        'total_transactions': expenses.count(),
    }
    return render(request, 'finance/index.html', context)
