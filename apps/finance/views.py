import datetime
import uuid
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Sum, Q
from django.utils import timezone

from apps.accounts.models import UserRole
from apps.accounts.decorators import deny_demo_viewer
from apps.finance.models import (
    FinancialAccount,
    CustomerPayment,
    SupplierPayment,
    AccountTransfer,
    Expense,
    ExpenseCategory,
    GeneralIncome,
    IncomeCategory,
    PaymentMethod,
    PaymentStatus,
    CustomerReturn,
    CustomerReturnStatus,
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
    record_general_income,
    storno_general_income,
    storno_account_transfer,
    ensure_default_accounts,
    calculate_production_order_actual_cost,
    debt_aging,
    record_customer_return,
    storno_customer_return,
)
from apps.finance.reports import (
    generate_customer_payment_pdf,
    generate_supplier_payment_pdf,
    generate_financial_report_pdf,
    export_financial_excel,
)
from apps.sales.models import SalesOrder, OrderStatus, Customer
from apps.suppliers.models import PurchaseOrder, Supplier, PurchaseOrderStatus
from apps.production.models import ProductionOrder
from apps.warehouses.models import (
    WarehouseDocument,
    WarehouseDocumentType,
    DocumentStatus,
)


def can_manage_finance(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.role in [
        UserRole.OWNER,
        UserRole.ADMIN,
        UserRole.ACCOUNTANT,
    ] or user.is_superuser


def can_view_finance(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.role in [
        UserRole.OWNER,
        UserRole.ADMIN,
        UserRole.ACCOUNTANT,
        UserRole.DEMO_VIEWER,
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
            return None, None
        if end_date < start_date:
            return None, None

    return start_date, end_date


def parse_operation_date(value: str):
    if not value:
        return timezone.localdate()
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValidationError('Укажите корректную дату операции.')


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
    if not can_view_finance(request.user):
        messages.error(request, 'Недостаточно прав для просмотра финансовых данных.')
        return redirect('/')
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
    if not can_view_finance(request.user):
        messages.error(request, 'Недостаточно прав для просмотра финансовых данных.')
        return redirect('/')
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    start_date, end_date = parse_date_filter(
        'custom', request.GET.get('start_date', ''), request.GET.get('end_date', '')
    )

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
    if start_date:
        payments = payments.filter(payment_date__gte=start_date)
    if end_date:
        payments = payments.filter(payment_date__lte=end_date)

    total_amount = payments.filter(status=PaymentStatus.COMPLETED).aggregate(t=Sum('amount_kzt'))['t'] or Decimal('0.00')

    context = {
        'page_title': 'Платежи покупателей',
        'payments': payments,
        'q': q,
        'status_filter': status_filter,
        'start_date': start_date,
        'end_date': end_date,
        'total_amount': total_amount,
        'statuses': PaymentStatus.choices,
        'can_manage': can_manage_finance(request.user),
    }
    return render(request, 'finance/payments/customer_payment_list.html', context)


@login_required
@deny_demo_viewer
def customer_payment_create(request):
    """
    Регистрация оплаты от покупателя (с привязкой к заказу или аванс).
    Поддерживает предзаполнение через ?order_id=...
    """
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для проведения финансовых операций.')
        return redirect('finance:customer_payments')

    ensure_default_accounts()
    idempotency_key = uuid.uuid4()
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
        idempotency_key = request.POST.get('idempotency_key') or None
        selected_order_id = request.POST.get('sales_order_id')
        account_id = request.POST.get('account_id')
        amount_str = request.POST.get('amount_kzt', '').strip()
        payment_method = request.POST.get('payment_method', PaymentMethod.BANK_TRANSFER)
        notes = request.POST.get('notes', '').strip()

        sales_order = None
        if selected_order_id:
            sales_order = get_object_or_404(SalesOrder, pk=selected_order_id)

        account = get_object_or_404(FinancialAccount, pk=account_id)

        try:
            payment = register_customer_payment(
                amount_kzt=amount_str,
                sales_order=sales_order,
                customer=sales_order.customer if sales_order else None,
                account=account,
                payment_method=payment_method,
                payment_date=parse_operation_date(request.POST.get('payment_date', '')),
                reference_number=request.POST.get('reference_number', '').strip(),
                notes=notes,
                recorded_by=request.user,
                idempotency_key=idempotency_key,
            )
            messages.success(request, f'Оплата № {payment.payment_number} на сумму {payment.amount_kzt:,.2f} ₸ успешно принята.')
            if sales_order:
                return redirect('sales:order_detail', pk=sales_order.pk)
        except (ValidationError, ValueError) as e:
            messages.error(request, f'Ошибка проведения оплаты: {str(e)}')

    accounts = FinancialAccount.objects.filter(is_active=True).order_by('name')
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
        'unpaid_orders': unpaid_orders,
        'payment_methods': PaymentMethod.choices,
        'idempotency_key': idempotency_key,
        'today': timezone.localdate(),
    }
    return render(request, 'finance/payments/customer_payment_form.html', context)


@login_required
def customer_payment_pdf(request, pk):
    """Скачать квитанцию об оплате покупателя в PDF."""
    if not can_view_finance(request.user):
        return redirect('/')
    payment = get_object_or_404(CustomerPayment.objects.select_related('customer', 'sales_order', 'account', 'recorded_by'), pk=pk)
    pdf_bytes = generate_customer_payment_pdf(payment)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"Receipt_{payment.payment_number}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
@deny_demo_viewer
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
        except ValidationError as e:
            messages.error(request, f'Ошибка сторнирования: {str(e)}')

    return redirect('finance:customer_payments')


# ==============================================================================
# ОПЛАТЫ ПОСТАВЩИКАМ (SUPPLIER PAYMENTS)
# ==============================================================================

@login_required
def supplier_payment_list(request):
    """Реестр оплат поставщикам."""
    if not can_view_finance(request.user):
        messages.error(request, 'Недостаточно прав для просмотра финансовых данных.')
        return redirect('/')
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    start_date, end_date = parse_date_filter(
        'custom', request.GET.get('start_date', ''), request.GET.get('end_date', '')
    )

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
    if start_date:
        payments = payments.filter(payment_date__gte=start_date)
    if end_date:
        payments = payments.filter(payment_date__lte=end_date)

    total_amount = payments.filter(status=PaymentStatus.COMPLETED).aggregate(t=Sum('amount_kzt'))['t'] or Decimal('0.00')

    context = {
        'page_title': 'Оплаты поставщикам',
        'payments': payments,
        'q': q,
        'status_filter': status_filter,
        'start_date': start_date,
        'end_date': end_date,
        'total_amount': total_amount,
        'statuses': PaymentStatus.choices,
        'can_manage': can_manage_finance(request.user),
    }
    return render(request, 'finance/payments/supplier_payment_list.html', context)


@login_required
@deny_demo_viewer
def supplier_payment_create(request):
    """
    Регистрация оплаты поставщику (с привязкой к заказу закупки).
    Поддерживает предзаполнение через ?po_id=...
    """
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для проведения финансовых операций.')
        return redirect('finance:supplier_payments')

    ensure_default_accounts()
    idempotency_key = uuid.uuid4()
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
        idempotency_key = request.POST.get('idempotency_key') or None
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
            payment = register_supplier_payment(
                amount_kzt=amount_str,
                purchase_order=purchase_order,
                supplier=supplier,
                account=account,
                payment_method=payment_method,
                payment_date=parse_operation_date(request.POST.get('payment_date', '')),
                reference_number=request.POST.get('reference_number', '').strip(),
                notes=notes,
                recorded_by=request.user,
                idempotency_key=idempotency_key,
            )
            messages.success(request, f'Выплата поставщику № {payment.payment_number} на сумму {payment.amount_kzt:,.2f} ₸ проведена.')
            if purchase_order:
                return redirect('suppliers:order_detail', pk=purchase_order.pk)
            return redirect('finance:supplier_payments')
        except (ValidationError, ValueError) as e:
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
        'idempotency_key': idempotency_key,
        'today': timezone.localdate(),
    }
    return render(request, 'finance/payments/supplier_payment_form.html', context)


@login_required
def supplier_payment_pdf(request, pk):
    """Скачать платёжный ордер поставщику в PDF."""
    if not can_view_finance(request.user):
        return redirect('/')
    payment = get_object_or_404(SupplierPayment.objects.select_related('supplier', 'purchase_order', 'account', 'recorded_by'), pk=pk)
    pdf_bytes = generate_supplier_payment_pdf(payment)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"PaymentOrder_{payment.payment_number}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
@deny_demo_viewer
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
        except ValidationError as e:
            messages.error(request, f'Ошибка сторнирования: {str(e)}')

    return redirect('finance:supplier_payments')


# ==============================================================================
# СЧЕТА И КАССЫ / КАЗНАЧЕЙСТВО (FINANCIAL ACCOUNTS & TRANSFERS)
# ==============================================================================

@login_required
def account_list(request):
    """Счета фабрики, кассы и межбанковские переводы."""
    if not can_view_finance(request.user):
        messages.error(request, 'Недостаточно прав для просмотра финансовых данных.')
        return redirect('/')
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
@deny_demo_viewer
def account_transfer(request):
    """Перевод средств между счетами фабрики (инкассация, пополнение)."""
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для перемещения денежных средств.')
        return redirect('finance:accounts')

    idempotency_key = uuid.uuid4()
    if request.method == 'POST':
        idempotency_key = request.POST.get('idempotency_key') or None
        from_acc_id = request.POST.get('from_account_id')
        to_acc_id = request.POST.get('to_account_id')
        amount_str = request.POST.get('amount_kzt', '').strip()
        notes = request.POST.get('notes', '').strip()

        from_acc = get_object_or_404(FinancialAccount, pk=from_acc_id)
        to_acc = get_object_or_404(FinancialAccount, pk=to_acc_id)

        try:
            transfer = transfer_between_accounts(
                from_account=from_acc,
                to_account=to_acc,
                amount_kzt=amount_str,
                transfer_date=parse_operation_date(request.POST.get('transfer_date', '')),
                notes=notes,
                recorded_by=request.user,
                idempotency_key=idempotency_key,
            )
            messages.success(request, f'Перевод № {transfer.transfer_number} на сумму {transfer.amount_kzt:,.2f} ₸ успешно проведён.')
            return redirect('finance:accounts')
        except (ValidationError, ValueError) as e:
            messages.error(request, f'Ошибка выполнения перевода: {str(e)}')

    accounts = FinancialAccount.objects.filter(is_active=True).order_by('name')
    context = {
        'page_title': 'Внутренний перевод средств',
        'accounts': accounts,
        'idempotency_key': idempotency_key,
        'today': timezone.localdate(),
    }
    return render(request, 'finance/accounts/transfer_form.html', context)


@login_required
@deny_demo_viewer
def account_transfer_storno(request, pk):
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для сторнирования перевода.')
        return redirect('finance:accounts')
    if request.method == 'POST':
        transfer = get_object_or_404(AccountTransfer, pk=pk)
        try:
            storno_account_transfer(
                transfer,
                user=request.user,
                reason=request.POST.get('reason', '').strip(),
            )
            messages.warning(request, f'Перевод № {transfer.transfer_number} сторнирован.')
        except ValidationError as e:
            messages.error(request, f'Ошибка сторнирования перевода: {e}')
    return redirect('finance:accounts')


# ==============================================================================
# ОПЕРАЦИОННЫЕ РАСХОДЫ (EXPENSES)
# ==============================================================================

@login_required
def expense_list(request):
    """Реестр расходов предприятия."""
    if not can_view_finance(request.user):
        messages.error(request, 'Недостаточно прав для просмотра финансовых данных.')
        return redirect('/')
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
@deny_demo_viewer
def expense_create(request):
    """Регистрация нового операционного расхода."""
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для регистрации расходов.')
        return redirect('finance:expenses')

    ensure_default_accounts()
    idempotency_key = uuid.uuid4()

    if request.method == 'POST':
        idempotency_key = request.POST.get('idempotency_key') or None
        category = request.POST.get('category')
        amount_str = request.POST.get('amount_kzt', '').strip()
        description = request.POST.get('description', '').strip()
        payee = request.POST.get('payee', '').strip()
        account_id = request.POST.get('account_id')
        payment_method = request.POST.get('payment_method', PaymentMethod.BANK_TRANSFER)

        account = get_object_or_404(FinancialAccount, pk=account_id) if account_id else None

        try:
            expense = record_expense(
                category=category,
                amount_kzt=amount_str,
                description=description,
                payee=payee,
                account=account,
                payment_method=payment_method,
                payment_date=parse_operation_date(request.POST.get('payment_date', '')),
                recorded_by=request.user,
                idempotency_key=idempotency_key,
            )
            messages.success(request, f'Расход № {expense.expense_number} на сумму {expense.amount_kzt:,.2f} ₸ успешно зарегистрирован.')
            return redirect('finance:expenses')
        except (ValidationError, ValueError) as e:
            messages.error(request, f'Ошибка проведения расхода: {str(e)}')

    accounts = FinancialAccount.objects.filter(is_active=True).order_by('name')
    context = {
        'page_title': 'Добавить расход',
        'categories': [(c.value, c.label) for c in ExpenseCategory],
        'accounts': accounts,
        'payment_methods': PaymentMethod.choices,
        'idempotency_key': idempotency_key,
        'today': timezone.localdate(),
    }
    return render(request, 'finance/expenses/expense_form.html', context)


@login_required
@deny_demo_viewer
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
        except ValidationError as e:
            messages.error(request, f'Ошибка сторнирования: {str(e)}')

    return redirect('finance:expenses')


@login_required
def income_list(request):
    if not can_view_finance(request.user):
        messages.error(request, 'Недостаточно прав для просмотра финансовых данных.')
        return redirect('/')
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    incomes = GeneralIncome.objects.select_related('account', 'recorded_by')
    if q:
        incomes = incomes.filter(
            Q(income_number__icontains=q) |
            Q(description__icontains=q) |
            Q(payer__icontains=q)
        )
    if category:
        incomes = incomes.filter(category=category)
    total = incomes.filter(is_storno=False).aggregate(total=Sum('amount_kzt'))['total'] or Decimal('0.00')
    return render(request, 'finance/income/income_list.html', {
        'page_title': 'Прочие доходы',
        'incomes': incomes,
        'q': q,
        'category_filter': category,
        'categories': IncomeCategory.choices,
        'total_income': total,
        'can_manage': can_manage_finance(request.user),
    })


@login_required
@deny_demo_viewer
def income_create(request):
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для регистрации доходов.')
        return redirect('finance:incomes')
    ensure_default_accounts()
    idempotency_key = uuid.uuid4()
    if request.method == 'POST':
        idempotency_key = request.POST.get('idempotency_key') or None
        account = get_object_or_404(FinancialAccount, pk=request.POST.get('account_id'))
        try:
            income = record_general_income(
                category=request.POST.get('category', ''),
                amount_kzt=request.POST.get('amount_kzt', ''),
                account=account,
                description=request.POST.get('description', '').strip(),
                payer=request.POST.get('payer', '').strip(),
                payment_method=request.POST.get('payment_method', PaymentMethod.BANK_TRANSFER),
                income_date=parse_operation_date(request.POST.get('income_date', '')),
                user=request.user,
                idempotency_key=idempotency_key,
            )
            messages.success(request, f'Доход № {income.income_number} зарегистрирован.')
            return redirect('finance:incomes')
        except (ValidationError, ValueError) as e:
            messages.error(request, f'Ошибка регистрации дохода: {e}')
    return render(request, 'finance/income/income_form.html', {
        'page_title': 'Регистрация дохода',
        'categories': IncomeCategory.choices,
        'accounts': FinancialAccount.objects.filter(is_active=True).order_by('name'),
        'payment_methods': PaymentMethod.choices,
        'idempotency_key': idempotency_key,
        'today': timezone.localdate(),
    })


@login_required
@deny_demo_viewer
def income_storno(request, pk):
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для сторнирования доходов.')
        return redirect('finance:incomes')
    if request.method == 'POST':
        income = get_object_or_404(GeneralIncome, pk=pk)
        try:
            storno_general_income(income, request.user, request.POST.get('reason', '').strip())
            messages.warning(request, f'Доход № {income.income_number} сторнирован.')
        except ValidationError as e:
            messages.error(request, f'Ошибка сторнирования дохода: {e}')
    return redirect('finance:incomes')


# ==============================================================================
# ЗАДОЛЖЕННОСТИ (RECEIVABLES & PAYABLES)
# ==============================================================================

@login_required
def receivables_list(request):
    """Дебиторская задолженность (долги покупателей)."""
    if not can_view_finance(request.user):
        messages.error(request, 'Недостаточно прав для просмотра финансовых данных.')
        return redirect('/')
    q = request.GET.get('q', '').strip()
    customer_id = request.GET.get('customer', '').strip()
    start_date, end_date = parse_date_filter(
        'custom', request.GET.get('start_date', ''), request.GET.get('end_date', '')
    )

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
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)

    orders = [o for o in qs if o.remaining_debt_kzt > Decimal('0.00')]
    aging_totals = {'1_30': Decimal('0.00'), '31_60': Decimal('0.00'), '61_90': Decimal('0.00'), 'over_90': Decimal('0.00'), 'not_due': Decimal('0.00'), 'no_due_date': Decimal('0.00')}
    for order in orders:
        aging = debt_aging(order)
        order.aging_data = aging
        aging_totals[aging['bucket']] = aging_totals.get(aging['bucket'], Decimal('0.00')) + aging['debt']
    total_debt = sum((o.remaining_debt_kzt for o in orders), Decimal('0.00'))
    total_sales = sum((o.total_amount_kzt for o in orders), Decimal('0.00'))

    context = {
        'page_title': 'Дебиторская задолженность',
        'orders': orders,
        'q': q,
        'start_date': start_date,
        'end_date': end_date,
        'total_debt': total_debt,
        'total_sales': total_sales,
        'aging_totals': aging_totals,
        'customers': Customer.objects.filter(is_active=True).order_by('full_name'),
        'customer_id': customer_id,
        'can_manage': can_manage_finance(request.user),
    }
    return render(request, 'finance/debts/receivables.html', context)


@login_required
def payables_list(request):
    """Кредиторская задолженность (долги фабрики перед поставщиками)."""
    if not can_view_finance(request.user):
        messages.error(request, 'Недостаточно прав для просмотра финансовых данных.')
        return redirect('/')
    q = request.GET.get('q', '').strip()
    supplier_id = request.GET.get('supplier', '').strip()
    start_date, end_date = parse_date_filter(
        'custom', request.GET.get('start_date', ''), request.GET.get('end_date', '')
    )

    qs = PurchaseOrder.objects.exclude(
        status__in=[PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.CANCELLED]
    ).select_related('supplier').order_by('-order_date')

    if q:
        qs = qs.filter(
            Q(order_number__icontains=q) |
            Q(supplier__name__icontains=q) |
            Q(supplier__contact_person__icontains=q)
        )
    if supplier_id:
        qs = qs.filter(supplier_id=supplier_id)
    if start_date:
        qs = qs.filter(order_date__gte=start_date)
    if end_date:
        qs = qs.filter(order_date__lte=end_date)

    orders = [p for p in qs if p.remaining_debt_kzt > Decimal('0.00')]
    aging_totals = {'1_30': Decimal('0.00'), '31_60': Decimal('0.00'), '61_90': Decimal('0.00'), 'over_90': Decimal('0.00'), 'not_due': Decimal('0.00'), 'no_due_date': Decimal('0.00')}
    for order in orders:
        aging = debt_aging(order)
        order.aging_data = aging
        aging_totals[aging['bucket']] = aging_totals.get(aging['bucket'], Decimal('0.00')) + aging['debt']
    total_debt = sum((p.remaining_debt_kzt for p in orders), Decimal('0.00'))
    total_purchases = sum((p.total_amount_kzt for p in orders), Decimal('0.00'))

    context = {
        'page_title': 'Кредиторская задолженность',
        'orders': orders,
        'q': q,
        'start_date': start_date,
        'end_date': end_date,
        'total_debt': total_debt,
        'total_purchases': total_purchases,
        'aging_totals': aging_totals,
        'suppliers': Supplier.objects.filter(is_active=True).order_by('name'),
        'supplier_id': supplier_id,
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
    if not can_view_finance(request.user):
        messages.error(request, 'Недостаточно прав для просмотра финансовых данных.')
        return redirect('/')
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
# ВОЗВРАТЫ ПОКУПАТЕЛЕЙ
# ==============================================================================

@login_required
def customer_return_list(request):
    if not can_view_finance(request.user):
        messages.error(request, 'Недостаточно прав для просмотра возвратов.')
        return redirect('/')
    returns = CustomerReturn.objects.select_related(
        'sales_order', 'shipment', 'customer', 'account', 'recorded_by'
    ).prefetch_related('items__shipment_item').order_by('-created_at')
    return render(request, 'finance/returns/return_list.html', {
        'page_title': 'Возвраты покупателей',
        'returns': returns,
        'can_manage': can_manage_finance(request.user),
    })


@login_required
@deny_demo_viewer
def customer_return_create(request):
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для проведения возврата.')
        return redirect('finance:customer_returns')

    order_id = request.GET.get('order_id', '')
    shipment_id = request.GET.get('shipment_id') or request.POST.get('shipment_id', '')
    preselected_order = None
    shipments = WarehouseDocument.objects.filter(
        doc_type=WarehouseDocumentType.SHIPMENT,
        status=DocumentStatus.POSTED,
    ).select_related('sales_order', 'customer', 'warehouse').order_by('-doc_date')
    if order_id:
        preselected_order = get_object_or_404(SalesOrder, pk=order_id)
        shipments = shipments.filter(sales_order=preselected_order)
    elif shipment_id:
        selected = shipments.filter(pk=shipment_id).first()
        if selected:
            preselected_order = selected.sales_order
            order_id = str(preselected_order.pk)
            shipments = shipments.filter(sales_order=preselected_order)

    if request.method == 'POST':
        order = get_object_or_404(SalesOrder, pk=request.POST.get('sales_order_id'))
        shipment = get_object_or_404(
            WarehouseDocument,
            pk=request.POST.get('shipment_id'),
            doc_type=WarehouseDocumentType.SHIPMENT,
            status=DocumentStatus.POSTED,
            sales_order=order,
        )
        account = get_object_or_404(FinancialAccount, pk=request.POST.get('account_id'))
        returned_items = {}
        invalid_quantity = False
        for line in shipment.items.filter(product__isnull=False).select_related('product'):
            quantity = request.POST.get(f'qty_{line.pk}', '').strip()
            if quantity:
                try:
                    quantity_value = Decimal(quantity)
                except InvalidOperation:
                    messages.error(request, f'Укажите корректное количество для изделия «{line.product.name}».')
                    invalid_quantity = True
                    continue
                if not quantity_value.is_finite():
                    messages.error(request, f'Количество для изделия «{line.product.name}» должно быть конечным числом.')
                    invalid_quantity = True
                    continue
                if quantity_value < Decimal('0'):
                    messages.error(request, f'Количество возврата для изделия «{line.product.name}» не может быть отрицательным.')
                    invalid_quantity = True
                    continue
                if quantity_value > Decimal('0'):
                    returned_items[line.pk] = quantity_value
        if not invalid_quantity:
            try:
                customer_return = record_customer_return(
                    sales_order=order,
                    shipment=shipment,
                    account=account,
                    returned_items=returned_items,
                    user=request.user,
                    reason=request.POST.get('reason', '').strip(),
                    idempotency_key=request.POST.get('idempotency_key') or uuid.uuid4(),
                )
                messages.success(
                    request,
                    f'Возврат № {customer_return.return_number} проведён на сумму '
                    f'{customer_return.refund_amount_kzt:,.2f} ₸.',
                )
                return redirect('finance:customer_returns')
            except (ValidationError, ValueError) as exc:
                messages.error(request, f'Ошибка проведения возврата: {exc}')

    selected_shipment = None
    if shipment_id:
        selected_shipment = shipments.filter(pk=shipment_id).first()
    return render(request, 'finance/returns/return_form.html', {
        'page_title': 'Возврат покупателю',
        'orders': SalesOrder.objects.exclude(status__in=[OrderStatus.DRAFT, OrderStatus.CANCELLED]).order_by('-created_at'),
        'shipments': shipments,
        'selected_shipment': selected_shipment,
        'preselected_order': preselected_order,
        'accounts': FinancialAccount.objects.filter(is_active=True, currency='KZT').order_by('name'),
        'idempotency_key': uuid.uuid4(),
        'today': timezone.localdate(),
    })


@login_required
@deny_demo_viewer
def customer_return_storno(request, pk):
    if not can_manage_finance(request.user):
        messages.error(request, 'Недостаточно прав для сторнирования возврата.')
        return redirect('finance:customer_returns')
    if request.method == 'POST':
        customer_return = get_object_or_404(CustomerReturn, pk=pk)
        try:
            storno_customer_return(
                customer_return,
                request.user,
                request.POST.get('reason', '').strip(),
            )
            messages.warning(request, f'Возврат № {customer_return.return_number} сторнирован.')
        except ValidationError as exc:
            messages.error(request, f'Ошибка сторнирования возврата: {exc}')
    return redirect('finance:customer_returns')


# ==============================================================================
# ЭКСПОРТ В EXCEL (EXCEL EXPORTS)
# ==============================================================================

@login_required
def export_excel(request):
    """Выгрузка финансовых отчётов в формате Excel (.xlsx)."""
    if not can_view_finance(request.user):
        messages.error(request, 'Недостаточно прав для просмотра финансовых отчётов.')
        return redirect('/')
    report_type = request.GET.get('type', 'pandl')
    period = request.GET.get('period', 'all')
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')

    start_date, end_date = parse_date_filter(period, start_date_str, end_date_str)

    supported_reports = {
        'pandl', 'cashflow', 'receivables', 'payables', 'costing',
        'payments', 'income_expenses', 'profitability',
    }
    if report_type not in supported_reports:
        messages.error(request, 'Неизвестный тип финансового отчёта.')
        return redirect('finance:index')

    excel_bytes = export_financial_excel(report_type, start_date=start_date, end_date=end_date)

    filename_map = {
        'pandl': 'FurniCore_PL_Report.xlsx',
        'cashflow': 'FurniCore_CashFlow_Report.xlsx',
        'receivables': 'FurniCore_Receivables.xlsx',
        'payables': 'FurniCore_Payables.xlsx',
        'costing': 'FurniCore_Cost_Accounting.xlsx',
        'payments': 'FurniCore_Payment_Report.xlsx',
        'income_expenses': 'FurniCore_Income_Expenses.xlsx',
        'profitability': 'FurniCore_Order_Profitability.xlsx',
    }
    filename = filename_map.get(report_type, 'FurniCore_Financial_Report.xlsx')

    response = HttpResponse(
        excel_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_pdf(request):
    """Выгрузка сводного финансового отчёта PDF с кириллическим шрифтом."""
    if not can_view_finance(request.user):
        messages.error(request, 'Недостаточно прав для просмотра финансовых отчётов.')
        return redirect('/')
    period = request.GET.get('period', 'all')
    start_date, end_date = parse_date_filter(
        period,
        request.GET.get('start_date', ''),
        request.GET.get('end_date', ''),
    )
    kpis = get_financial_dashboard_kpis(start_date=start_date, end_date=end_date)
    pdf_bytes = generate_financial_report_pdf(kpis, start_date=start_date, end_date=end_date)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="FurniCore_Financial_Report.pdf"'
    return response
