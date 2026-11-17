import datetime
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, Http404
from django.db.models import Sum, Q, Count
from django.utils import timezone

from apps.accounts.models import UserRole
from apps.finance.models import (
    FinancialAccount,
    AccountType,
    CustomerPayment,
    SupplierPayment,
    AccountTransfer,
    Expense,
    ExpenseCategory,
    PaymentMethod,
    PaymentStatus,
)
from apps.finance.services import (
    get_financial_dashboard_kpis,
    register_customer_payment,
    storno_customer_payment,
    register_supplier_payment,
    storno_supplier_payment,
    transfer_between_accounts,
    record_expense,
    storno_expense,
    ensure_default_accounts,
    calculate_production_order_actual_cost,
)
from apps.finance.reports import (
    generate_customer_payment_pdf,
    generate_supplier_payment_pdf,
    export_financial_excel,
)
from apps.sales.models import SalesOrder, Customer, OrderStatus
from apps.suppliers.models import PurchaseOrder, Supplier, PurchaseOrderStatus
from apps.production.models import ProductionOrder


def can_manage_finance(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.role in [
        UserRole.OWNER,
        UserRole.ADMIN,
        UserRole.ACCOUNTANT,
    ] or user.is_superuser


def parse_date_filter(period: str, start_date_str: str, end_date_str: str):
    today = timezone.localdate()
    start_date = None
    end_date = None

    if period == 'today':
        start_date = today
        end_date = today
    elif period == 'this_week':
        start_date = today - datetime.timedelta(days=today.weekday())
        end_date = today
    elif period == 'this_month':
        start_date = today.replace(day=1)
        end_date = today
    elif period == 'this_year':
        start_date = today.replace(month=1, day=1)
        end_date = today
    elif period == 'custom' and start_date_str and end_date_str:
        try:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    return start_date, end_date


# ==============================================================================
# ФИНАНСОВЫЙ ДАШБОРД (FINANCE DASHBOARD)
# ==============================================================================

@login_required
def index(request):
    """
    Главный финансовый дашборд фабрики FurniCore ERP.
    Отображает P&L, Cash Flow, остатки на счетах, дебиторку, кредиторку,
    структуру расходов и последние операции.
    """
    ensure_default_accounts()

    period = request.GET.get('period', 'all')
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')

    start_date, end_date = parse_date_filter(period, start_date_str, end_date_str)

    kpis = get_financial_dashboard_kpis(start_date=start_date, end_date=end_date)

    # Recent Customer Payments
    recent_customer_payments = CustomerPayment.objects.select_related(
        'customer', 'sales_order', 'account'
    ).order_by('-payment_date')[:8]

    # Recent Supplier Payments
    recent_supplier_payments = SupplierPayment.objects.select_related(
        'supplier', 'purchase_order', 'account'
    ).order_by('-payment_date')[:8]

    # Recent Expenses
    recent_expenses = Expense.objects.select_related(
        'recorded_by', 'account'
    ).order_by('-payment_date')[:8]

    context = {
        'page_title': 'Финансовый центр',
        'kpis': kpis,
        'period': period,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'recent_customer_payments': recent_customer_payments,
        'recent_supplier_payments': recent_supplier_payments,
        'recent_expenses': recent_expenses,
        'can_manage': can_manage_finance(request.user),
    }
    return render(request, 'finance/index.html', context)


# ==============================================================================
# ПЛАТЕЖИ ПОКУПАТЕЛЕЙ (CUSTOMER PAYMENTS)
# ==============================================================================

@login_required
def customer_payment_list(request):
    """Реестр оплат от клиентов."""
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    payments = CustomerPayment.objects.select_related(
        'customer', 'sales_order', 'account', 'recorded_by'
    ).order_by('-payment_date')

    if q:
        payments = payments.filter(
            Q(payment_number__icontains=q) |
            Q(customer__full_name__icontains=q) |
            Q(customer__company_name__icontains=q) |
            Q(sales_order__order_number__icontains=q)
        )
    if status_filter:
        payments = payments.filter(status=status_filter)

    total_amount = payments.filter(status=PaymentStatus.COMPLETED).aggregate(t=Sum('amount_kzt'))['t'] or Decimal('0.00')

    context = {
        'page_title': 'Платежи покупателей',
        'payments': payments,
        'q': q,
        'status_filter': status_filter,
        'total_amount': total_amount,
        'statuses': PaymentStatus.choices,
        'can_manage': can_manage_finance(request.user),
    }
    return render(request, 'finance/payments/customer_payment_list.html', context)


@login_required
def customer_payment_create(request):
    """
    Регистрация оплаты от покупателя (с привязкой к заказу или аванс).
    Поддерживает предзаполнение через ?order_id=...
    """
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для проведения финансовых операций.')
        return redirect('finance:customer_payments')

    ensure_default_accounts()
    order_id = request.GET.get('order_id')
    preselected_order = None
    preselected_customer = None
    default_amount = Decimal('0.00')

    if order_id:
        try:
            preselected_order = SalesOrder.objects.select_related('customer').get(pk=order_id)
            preselected_customer = preselected_order.customer
            default_amount = max(preselected_order.remaining_debt_kzt, Decimal('0.00'))
        except SalesOrder.DoesNotExist:
            pass

    if request.method == 'POST':
        selected_order_id = request.POST.get('sales_order_id')
        customer_id = request.POST.get('customer_id')
        account_id = request.POST.get('account_id')
        amount_str = request.POST.get('amount_kzt', '').strip()
        payment_method = request.POST.get('payment_method', PaymentMethod.BANK_TRANSFER)
        notes = request.POST.get('notes', '').strip()

        sales_order = None
        customer = None

        if selected_order_id:
            sales_order = get_object_or_404(SalesOrder, pk=selected_order_id)
            customer = sales_order.customer
        elif customer_id:
            customer = get_object_or_404(Customer, pk=customer_id)

        account = get_object_or_404(FinancialAccount, pk=account_id)

        try:
            amount_kzt = Decimal(amount_str)
            payment = register_customer_payment(
                amount_kzt=amount_kzt,
                sales_order=sales_order,
                customer=customer,
                account=account,
                payment_method=payment_method,
                notes=notes,
                recorded_by=request.user
            )
            messages.success(request, f'Оплата № {payment.payment_number} на сумму {payment.amount_kzt:,.2f} ₸ успешно принята.')
            if sales_order:
                return redirect('sales:order_detail', pk=sales_order.pk)
            return redirect('finance:customer_payments')
        except Exception as e:
            messages.error(request, f'Ошибка проведения оплаты: {str(e)}')

    accounts = FinancialAccount.objects.filter(is_active=True).order_by('name')
    customers = Customer.objects.order_by('full_name')
    active_orders = SalesOrder.objects.exclude(
        status__in=[OrderStatus.DRAFT, OrderStatus.CANCELLED]
    ).select_related('customer').order_by('-created_at')
    unpaid_orders = [o for o in active_orders if o.remaining_debt_kzt > Decimal('0.00')][:50]

    context = {
        'page_title': 'Приём оплаты от покупателя',
        'preselected_order': preselected_order,
        'preselected_customer': preselected_customer,
        'default_amount': default_amount,
        'accounts': accounts,
        'customers': customers,
        'unpaid_orders': unpaid_orders,
        'payment_methods': PaymentMethod.choices,
    }
    return render(request, 'finance/payments/customer_payment_form.html', context)


@login_required
def customer_payment_pdf(request, pk):
    """Скачать квитанцию об оплате покупателя в PDF."""
    payment = get_object_or_404(CustomerPayment.objects.select_related('customer', 'sales_order', 'account', 'recorded_by'), pk=pk)
    pdf_bytes = generate_customer_payment_pdf(payment)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"Receipt_{payment.payment_number}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
def customer_payment_storno(request, pk):
    """Сторнирование оплаты покупателя."""
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для отмены финансовых операций.')
        return redirect('finance:customer_payments')

    payment = get_object_or_404(CustomerPayment, pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        try:
            storno_customer_payment(payment, user=request.user, reason=reason)
            messages.warning(request, f'Платёж № {payment.payment_number} успешно сторнирован.')
        except Exception as e:
            messages.error(request, f'Ошибка сторнирования: {str(e)}')

    return redirect('finance:customer_payments')


# ==============================================================================
# ОПЛАТЫ ПОСТАВЩИКАМ (SUPPLIER PAYMENTS)
# ==============================================================================

@login_required
def supplier_payment_list(request):
    """Реестр оплат поставщикам."""
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    payments = SupplierPayment.objects.select_related(
        'supplier', 'purchase_order', 'account', 'recorded_by'
    ).order_by('-payment_date')

    if q:
        payments = payments.filter(
            Q(payment_number__icontains=q) |
            Q(supplier__name__icontains=q) |
            Q(purchase_order__order_number__icontains=q)
        )
    if status_filter:
        payments = payments.filter(status=status_filter)

    total_amount = payments.filter(status=PaymentStatus.COMPLETED).aggregate(t=Sum('amount_kzt'))['t'] or Decimal('0.00')

    context = {
        'page_title': 'Оплаты поставщикам',
        'payments': payments,
        'q': q,
        'status_filter': status_filter,
        'total_amount': total_amount,
        'statuses': PaymentStatus.choices,
        'can_manage': can_manage_finance(request.user),
    }
    return render(request, 'finance/payments/supplier_payment_list.html', context)


@login_required
def supplier_payment_create(request):
    """
    Регистрация оплаты поставщику (с привязкой к заказу закупки).
    Поддерживает предзаполнение через ?po_id=...
    """
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для проведения финансовых операций.')
        return redirect('finance:supplier_payments')

    ensure_default_accounts()
    po_id = request.GET.get('po_id')
    preselected_po = None
    preselected_supplier = None
    default_amount = Decimal('0.00')

    if po_id:
        try:
            preselected_po = PurchaseOrder.objects.select_related('supplier').get(pk=po_id)
            preselected_supplier = preselected_po.supplier
            default_amount = max(preselected_po.remaining_debt_kzt, Decimal('0.00'))
        except PurchaseOrder.DoesNotExist:
            pass

    if request.method == 'POST':
        selected_po_id = request.POST.get('purchase_order_id')
        supplier_id = request.POST.get('supplier_id')
        account_id = request.POST.get('account_id')
        amount_str = request.POST.get('amount_kzt', '').strip()
        payment_method = request.POST.get('payment_method', PaymentMethod.BANK_TRANSFER)
        notes = request.POST.get('notes', '').strip()

        purchase_order = None
        supplier = None

        if selected_po_id:
            purchase_order = get_object_or_404(PurchaseOrder, pk=selected_po_id)
            supplier = purchase_order.supplier
        elif supplier_id:
            supplier = get_object_or_404(Supplier, pk=supplier_id)

        account = get_object_or_404(FinancialAccount, pk=account_id)

        try:
            amount_kzt = Decimal(amount_str)
            payment = register_supplier_payment(
                amount_kzt=amount_kzt,
                purchase_order=purchase_order,
                supplier=supplier,
                account=account,
                payment_method=payment_method,
                notes=notes,
                recorded_by=request.user
            )
            messages.success(request, f'Выплата поставщику № {payment.payment_number} на сумму {payment.amount_kzt:,.2f} ₸ проведена.')
            if purchase_order:
                return redirect('suppliers:order_detail', pk=purchase_order.pk)
            return redirect('finance:supplier_payments')
        except Exception as e:
            messages.error(request, f'Ошибка проведения выплаты: {str(e)}')

    accounts = FinancialAccount.objects.filter(is_active=True).order_by('name')
    suppliers = Supplier.objects.order_by('name')
    active_pos = PurchaseOrder.objects.exclude(
        status__in=[PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.CANCELLED]
    ).select_related('supplier').order_by('-order_date')
    unpaid_pos = [p for p in active_pos if p.remaining_debt_kzt > Decimal('0.00')][:50]

    context = {
        'page_title': 'Оплата поставщику',
        'preselected_po': preselected_po,
        'preselected_supplier': preselected_supplier,
        'default_amount': default_amount,
        'accounts': accounts,
        'suppliers': suppliers,
        'unpaid_pos': unpaid_pos,
        'payment_methods': PaymentMethod.choices,
    }
    return render(request, 'finance/payments/supplier_payment_form.html', context)


@login_required
def supplier_payment_pdf(request, pk):
    """Скачать платёжный ордер поставщику в PDF."""
    payment = get_object_or_404(SupplierPayment.objects.select_related('supplier', 'purchase_order', 'account', 'recorded_by'), pk=pk)
    pdf_bytes = generate_supplier_payment_pdf(payment)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"PaymentOrder_{payment.payment_number}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
def supplier_payment_storno(request, pk):
    """Сторнирование оплаты поставщику."""
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для отмены финансовых операций.')
        return redirect('finance:supplier_payments')

    payment = get_object_or_404(SupplierPayment, pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        try:
            storno_supplier_payment(payment, user=request.user, reason=reason)
            messages.warning(request, f'Выплата № {payment.payment_number} успешно сторнирована.')
        except Exception as e:
            messages.error(request, f'Ошибка сторнирования: {str(e)}')

    return redirect('finance:supplier_payments')


# ==============================================================================
# СЧЕТА И КАССЫ / КАЗНАЧЕЙСТВО (FINANCIAL ACCOUNTS & TRANSFERS)
# ==============================================================================

@login_required
def account_list(request):
    """Счета фабрики, кассы и межбанковские переводы."""
    ensure_default_accounts()
    accounts = FinancialAccount.objects.all().order_by('account_type', 'name')
    total_balance = sum(a.balance_kzt for a in accounts if a.is_active)

    recent_transfers = AccountTransfer.objects.select_related(
        'from_account', 'to_account', 'recorded_by'
    ).order_by('-transfer_date')[:10]

    context = {
        'page_title': 'Счета и кассы',
        'accounts': accounts,
        'total_balance': total_balance,
        'recent_transfers': recent_transfers,
        'can_manage': can_manage_finance(request.user),
    }
    return render(request, 'finance/accounts/account_list.html', context)


@login_required
def account_transfer(request):
    """Перевод средств между счетами фабрики (инкассация, пополнение)."""
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для перемещения денежных средств.')
        return redirect('finance:accounts')

    if request.method == 'POST':
        from_acc_id = request.POST.get('from_account_id')
        to_acc_id = request.POST.get('to_account_id')
        amount_str = request.POST.get('amount_kzt', '').strip()
        notes = request.POST.get('notes', '').strip()

        from_acc = get_object_or_404(FinancialAccount, pk=from_acc_id)
        to_acc = get_object_or_404(FinancialAccount, pk=to_acc_id)

        try:
            amount_kzt = Decimal(amount_str)
            transfer = transfer_between_accounts(
                from_account=from_acc,
                to_account=to_acc,
                amount_kzt=amount_kzt,
                notes=notes,
                recorded_by=request.user
            )
            messages.success(request, f'Перевод № {transfer.transfer_number} на сумму {transfer.amount_kzt:,.2f} ₸ успешно проведён.')
            return redirect('finance:accounts')
        except Exception as e:
            messages.error(request, f'Ошибка выполнения перевода: {str(e)}')

    accounts = FinancialAccount.objects.filter(is_active=True).order_by('name')
    context = {
        'page_title': 'Внутренний перевод средств',
        'accounts': accounts,
    }
    return render(request, 'finance/accounts/transfer_form.html', context)


# ==============================================================================
# ОПЕРАЦИОННЫЕ РАСХОДЫ (EXPENSES)
# ==============================================================================

@login_required
def expense_list(request):
    """Реестр расходов предприятия."""
    q = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '')

    expenses = Expense.objects.select_related('recorded_by', 'account').order_by('-payment_date')

    if q:
        expenses = expenses.filter(
            Q(description__icontains=q) |
            Q(payee__icontains=q) |
            Q(expense_number__icontains=q)
        )
    if category_filter:
        expenses = expenses.filter(category=category_filter)

    total_expenses = expenses.filter(is_storno=False).aggregate(t=Sum('amount_kzt'))['t'] or Decimal('0.00')

    context = {
        'page_title': 'Операционные расходы',
        'expenses': expenses,
        'q': q,
        'category_filter': category_filter,
        'categories': [(c.value, c.label) for c in ExpenseCategory],
        'total_expenses': total_expenses,
        'can_manage': can_manage_finance(request.user),
    }
    return render(request, 'finance/expenses/expense_list.html', context)


@login_required
def expense_create(request):
    """Регистрация нового операционного расхода."""
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для регистрации расходов.')
        return redirect('finance:expenses')

    ensure_default_accounts()

    if request.method == 'POST':
        category = request.POST.get('category')
        amount_str = request.POST.get('amount_kzt', '').strip()
        description = request.POST.get('description', '').strip()
        payee = request.POST.get('payee', '').strip()
        account_id = request.POST.get('account_id')
        payment_method = request.POST.get('payment_method', PaymentMethod.BANK_TRANSFER)

        account = get_object_or_404(FinancialAccount, pk=account_id) if account_id else None

        try:
            amount_kzt = Decimal(amount_str)
            expense = record_expense(
                category=category,
                amount_kzt=amount_kzt,
                description=description,
                payee=payee,
                account=account,
                payment_method=payment_method,
                recorded_by=request.user
            )
            messages.success(request, f'Расход № {expense.expense_number} на сумму {expense.amount_kzt:,.2f} ₸ успешно зарегистрирован.')
            return redirect('finance:expenses')
        except Exception as e:
            messages.error(request, f'Ошибка проведения расхода: {str(e)}')

    accounts = FinancialAccount.objects.filter(is_active=True).order_by('name')
    context = {
        'page_title': 'Добавить расход',
        'categories': [(c.value, c.label) for c in ExpenseCategory],
        'accounts': accounts,
        'payment_methods': PaymentMethod.choices,
    }
    return render(request, 'finance/expenses/expense_form.html', context)


@login_required
def expense_storno(request, pk):
    """Сторнирование операционного расхода."""
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для сторнирования расходов.')
        return redirect('finance:expenses')

    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        try:
            storno_expense(expense, user=request.user, reason=reason)
            messages.warning(request, f'Расход № {expense.expense_number} успешно сторнирован.')
        except Exception as e:
            messages.error(request, f'Ошибка сторнирования: {str(e)}')

    return redirect('finance:expenses')


# ==============================================================================
# ЗАДОЛЖЕННОСТИ (RECEIVABLES & PAYABLES)
# ==============================================================================

@login_required
def receivables_list(request):
    """Дебиторская задолженность (долги покупателей)."""
    q = request.GET.get('q', '').strip()

    qs = SalesOrder.objects.exclude(
        status__in=[OrderStatus.DRAFT, OrderStatus.CANCELLED]
    ).select_related('customer').order_by('-created_at')

    if q:
        qs = qs.filter(
            Q(order_number__icontains=q) |
            Q(customer__full_name__icontains=q) |
            Q(customer__company_name__icontains=q) |
            Q(customer__phone__icontains=q)
        )

    orders = [o for o in qs if o.remaining_debt_kzt > Decimal('0.00')]
    total_debt = sum((o.remaining_debt_kzt for o in orders), Decimal('0.00'))
    total_sales = sum((o.total_amount_kzt for o in orders), Decimal('0.00'))

    context = {
        'page_title': 'Дебиторская задолженность',
        'orders': orders,
        'q': q,
        'total_debt': total_debt,
        'total_sales': total_sales,
        'can_manage': can_manage_finance(request.user),
    }
    return render(request, 'finance/debts/receivables.html', context)


@login_required
def payables_list(request):
    """Кредиторская задолженность (долги фабрики перед поставщиками)."""
    q = request.GET.get('q', '').strip()

    qs = PurchaseOrder.objects.exclude(
        status__in=[PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.CANCELLED]
    ).select_related('supplier').order_by('-order_date')

    if q:
        qs = qs.filter(
            Q(order_number__icontains=q) |
            Q(supplier__name__icontains=q) |
            Q(supplier__contact_person__icontains=q)
        )

    orders = [p for p in qs if p.remaining_debt_kzt > Decimal('0.00')]
    total_debt = sum((p.remaining_debt_kzt for p in orders), Decimal('0.00'))
    total_purchases = sum((p.total_amount_kzt for p in orders), Decimal('0.00'))

    context = {
        'page_title': 'Кредиторская задолженность',
        'orders': orders,
        'q': q,
        'total_debt': total_debt,
        'total_purchases': total_purchases,
        'can_manage': can_manage_finance(request.user),
    }
    return render(request, 'finance/debts/payables.html', context)


# ==============================================================================
# СЕБЕСТОИМОСТЬ ЗАКАЗОВ (COST ACCOUNTING)
# ==============================================================================

@login_required
def cost_accounting_view(request):
    """
    Калькуляция фактической себестоимости производственных заказов:
    План (BOM) vs Факт (списания со склада WH-1) + прямая зарплата + накладные расходы.
    """
    q = request.GET.get('q', '').strip()

    orders = ProductionOrder.objects.select_related('product').all().order_by('-created_at')

    if q:
        orders = orders.filter(
            Q(order_number__icontains=q) |
            Q(product__name__icontains=q) |
            Q(product__sku__icontains=q)
        )

    orders_cost_data = []
    total_actual_costs = Decimal('0.00')
    total_cost_variances = Decimal('0.00')

    for po in orders[:50]:
        cost_info = calculate_production_order_actual_cost(po)
        orders_cost_data.append({
            'order': po,
            'cost': cost_info,
        })
        total_actual_costs += cost_info['total_actual_cost_kzt']
        total_cost_variances += cost_info['cost_variance_kzt']

    context = {
        'page_title': 'Себестоимость производства',
        'orders_cost_data': orders_cost_data,
        'total_actual_costs': total_actual_costs,
        'total_cost_variances': total_cost_variances,
        'q': q,
    }
    return render(request, 'finance/costing/order_cost.html', context)


# ==============================================================================
# ЭКСПОРТ В EXCEL (EXCEL EXPORTS)
# ==============================================================================

@login_required
def export_excel(request):
    """Выгрузка финансовых отчётов в формате Excel (.xlsx)."""
    report_type = request.GET.get('type', 'pandl')
    period = request.GET.get('period', 'all')
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')

    start_date, end_date = parse_date_filter(period, start_date_str, end_date_str)

    excel_bytes = export_financial_excel(report_type, start_date=start_date, end_date=end_date)

    filename_map = {
        'pandl': 'FurniCore_PL_Report.xlsx',
        'cashflow': 'FurniCore_CashFlow_Report.xlsx',
        'receivables': 'FurniCore_Receivables.xlsx',
        'payables': 'FurniCore_Payables.xlsx',
        'costing': 'FurniCore_Cost_Accounting.xlsx',
    }
    filename = filename_map.get(report_type, 'FurniCore_Financial_Report.xlsx')

    response = HttpResponse(
        excel_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
