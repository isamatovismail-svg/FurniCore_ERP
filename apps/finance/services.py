import datetime
import uuid
from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.accounts.models import AuditLog, User, UserRole
from apps.sales.models import SalesOrder, Customer, OrderStatus
from apps.suppliers.models import PurchaseOrder, Supplier, PurchaseOrderStatus
from apps.finance.models import (
    FinancialAccount,
    AccountType,
    CustomerPayment,
    SupplierPayment,
    AccountTransfer,
    Expense,
    ExpenseCategory,
    GeneralIncome,
    IncomeCategory,
    PaymentMethod,
    PaymentStatus,
)
from apps.production.models import ProductionOrder, ProductionOrderStatus
from apps.warehouses.models import Warehouse, WarehouseType, StockMovement, MovementType


def generate_payment_number(prefix: str = 'PAY') -> str:
    """Генерация уникального номера финансовой операции."""
    today_str = timezone.now().strftime('%y%m%d')
    suffix = uuid.uuid4().hex[:4].upper()
    return f'{prefix}-{today_str}-{suffix}'


def ensure_default_accounts() -> list[FinancialAccount]:
    """Гарантирует существование базовых счетов предприятия."""
    defaults = [
        ('Основная касса цеха', AccountType.CASH, '', Decimal('150000.00')),
        ('Расчётный счёт Halyk Bank', AccountType.BANK, 'KZ246012345678901234', Decimal('2500000.00')),
        ('Kaspi Pay (QR/Эквайринг)', AccountType.KASPI, 'KZ888012345678900001', Decimal('450000.00')),
    ]
    accounts = []
    for name, acc_type, acc_num, init_bal in defaults:
        acc, created = FinancialAccount.objects.get_or_create(
            name=name,
            defaults={
                'account_type': acc_type,
                'account_number': acc_num,
                'initial_balance_kzt': init_bal,
                'current_balance_kzt': init_bal,
                'is_active': True,
            }
        )
        accounts.append(acc)
    return accounts


# ==============================================================================
# ПЛАТЕЖИ ПОКУПАТЕЛЕЙ (CUSTOMER PAYMENTS)
# ==============================================================================

@transaction.atomic
def register_customer_payment(
    amount_kzt: Decimal,
    account: FinancialAccount,
    sales_order: SalesOrder = None,
    customer: Customer = None,
    payment_method: str = PaymentMethod.BANK_TRANSFER,
    user: User = None,
    created_by: User = None,
    recorded_by: User = None,
    payment_date=None,
    reference_number: str = '',
    notes: str = '',
) -> CustomerPayment:
    """Регистрация поступившего платежа от клиента по заказу покупателя."""
    user = user or created_by or recorded_by
    amount = Decimal(str(amount_kzt)).quantize(Decimal('0.01'))
    if amount <= Decimal('0.00'):
        raise ValidationError('Сумма платежа должна быть строго больше нуля.')

    acc = FinancialAccount.objects.select_for_update().get(pk=account.pk)
    if not acc.is_active:
        raise ValidationError(f'Денежный счёт «{acc.name}» не активен.')

    so = None
    if sales_order:
        so = SalesOrder.objects.select_for_update().get(pk=sales_order.pk)
        customer = customer or so.customer
        remaining_debt = so.remaining_debt_kzt
        if amount > remaining_debt:
            raise ValidationError(
                f'Сумма платежа ({amount:,.2f} ₸) превышает остаток долга по заказу {so.order_number} ({remaining_debt:,.2f} ₸).'
            )

    if not customer and not so:
        raise ValidationError('Необходимо указать клиента или заказ покупателя.')

    # Защита от дублирования идентичного платежа в течение 10 секунд
    recent_dup = CustomerPayment.objects.filter(
        sales_order=so,
        customer=customer,
        account=acc,
        amount_kzt=amount,
        status=PaymentStatus.COMPLETED,
        reference_number=reference_number,
        created_at__gte=timezone.now() - datetime.timedelta(seconds=10),
    ).first()
    if recent_dup:
        raise ValidationError(f'Платёж с такими параметрами уже зарегистрирован под номером {recent_dup.payment_number}.')

    payment_num = generate_payment_number('PAY-C')
    p_date = payment_date or timezone.localdate()

    payment = CustomerPayment.objects.create(
        payment_number=payment_num,
        sales_order=so,
        customer=customer,
        account=acc,
        amount_kzt=amount,
        payment_date=p_date,
        payment_method=payment_method,
        status=PaymentStatus.COMPLETED,
        reference_number=reference_number,
        notes=notes,
        recorded_by=user,
    )

    # Увеличение баланса денежного счёта
    acc.current_balance_kzt += amount
    acc.save(update_fields=['current_balance_kzt', 'updated_at'])

    AuditLog.objects.create(
        user=user,
        action='REGISTER_CUSTOMER_PAYMENT',
        entity_type='CustomerPayment',
        entity_id=str(payment.id),
        details={
            'payment_number': payment.payment_number,
            'sales_order': so.order_number if so else None,
            'customer': customer.name if customer else None,
            'amount': float(amount),
            'account': acc.name,
            'new_balance': float(acc.current_balance_kzt),
        },
    )
    return payment


@transaction.atomic
def storno_customer_payment(payment: CustomerPayment, user: User, reason: str = '') -> CustomerPayment:
    """Сторнирование (отмена) ошибочно проведённого платежа покупателя с возвратом остатка на счёте."""
    pay = CustomerPayment.objects.select_for_update().get(pk=payment.pk)
    if pay.status == PaymentStatus.CANCELLED:
        raise ValidationError(f'Платёж {pay.payment_number} уже был сторнирован ранее.')

    acc = FinancialAccount.objects.select_for_update().get(pk=pay.account.pk)
    if acc.current_balance_kzt < pay.amount_kzt:
        raise ValidationError(
            f'Невозможно сторнировать платёж: на счёте «{acc.name}» недостаточно средств ({acc.current_balance_kzt:,.2f} ₸).'
        )

    acc.current_balance_kzt -= pay.amount_kzt
    acc.save(update_fields=['current_balance_kzt', 'updated_at'])

    pay.status = PaymentStatus.CANCELLED
    if reason:
        pay.notes = f'{pay.notes}\n[Сторнировано {timezone.now().strftime("%d.%m.%Y %H:%M")}: {reason}]'.strip()
    pay.save(update_fields=['status', 'notes'])

    AuditLog.objects.create(
        user=user,
        action='STORNO_CUSTOMER_PAYMENT',
        entity_type='CustomerPayment',
        entity_id=str(pay.id),
        details={
            'payment_number': pay.payment_number,
            'sales_order': pay.sales_order.order_number,
            'storno_amount': float(pay.amount_kzt),
            'reason': reason,
        },
    )
    return pay


# ==============================================================================
# ВЫПЛАТЫ ПОСТАВЩИКАМ (SUPPLIER PAYMENTS)
# ==============================================================================

@transaction.atomic
def register_supplier_payment(
    amount_kzt: Decimal,
    account: FinancialAccount,
    supplier: Supplier = None,
    purchase_order: PurchaseOrder = None,
    payment_method: str = PaymentMethod.BANK_TRANSFER,
    user: User = None,
    created_by: User = None,
    recorded_by: User = None,
    payment_date=None,
    reference_number: str = '',
    notes: str = '',
) -> SupplierPayment:
    """Регистрация выплаты поставщику по заказу на закупку или общему договору."""
    user = user or created_by or recorded_by
    amount = Decimal(str(amount_kzt)).quantize(Decimal('0.01'))
    if amount <= Decimal('0.00'):
        raise ValidationError('Сумма выплаты должна быть строго больше нуля.')

    acc = FinancialAccount.objects.select_for_update().get(pk=account.pk)
    if not acc.is_active:
        raise ValidationError(f'Счёт «{acc.name}» не активен.')

    if acc.current_balance_kzt < amount:
        raise ValidationError(
            f'Недостаточно средств на счёте «{acc.name}» для совершения выплаты. '
            f'Доступно: {acc.current_balance_kzt:,.2f} ₸, требуется: {amount:,.2f} ₸.'
        )

    po = None
    if purchase_order:
        po = PurchaseOrder.objects.select_for_update().get(pk=purchase_order.pk)
        supplier = supplier or po.supplier
        rem_debt = po.remaining_debt_kzt
        if amount > rem_debt:
            raise ValidationError(
                f'Сумма выплаты ({amount:,.2f} ₸) превышает остаток задолженности по заказу {po.order_number} ({rem_debt:,.2f} ₸).'
            )

    if not supplier and not po:
        raise ValidationError('Необходимо указать поставщика или заказ закупки.')

    payment_num = generate_payment_number('PAY-S')
    p_date = payment_date or timezone.localdate()

    payment = SupplierPayment.objects.create(
        payment_number=payment_num,
        purchase_order=po,
        supplier=supplier,
        account=acc,
        amount_kzt=amount,
        payment_date=p_date,
        payment_method=payment_method,
        status=PaymentStatus.COMPLETED,
        reference_number=reference_number,
        notes=notes,
        recorded_by=user,
    )

    # Списание денежных средств со счёта
    acc.current_balance_kzt -= amount
    acc.save(update_fields=['current_balance_kzt', 'updated_at'])

    AuditLog.objects.create(
        user=user,
        action='REGISTER_SUPPLIER_PAYMENT',
        entity_type='SupplierPayment',
        entity_id=str(payment.id),
        details={
            'payment_number': payment.payment_number,
            'supplier': supplier.name if supplier else None,
            'purchase_order': po.order_number if po else None,
            'amount': float(amount),
            'account': acc.name,
            'new_balance': float(acc.current_balance_kzt),
        },
    )
    return payment


@transaction.atomic
def storno_supplier_payment(payment: SupplierPayment, user: User, reason: str = '') -> SupplierPayment:
    """Сторнирование выплаты поставщику с возвратом средств на счёт предприятия."""
    pay = SupplierPayment.objects.select_for_update().get(pk=payment.pk)
    if pay.status == PaymentStatus.CANCELLED:
        raise ValidationError(f'Выплата {pay.payment_number} уже была сторнирована ранее.')

    acc = FinancialAccount.objects.select_for_update().get(pk=pay.account.pk)
    acc.current_balance_kzt += pay.amount_kzt
    acc.save(update_fields=['current_balance_kzt', 'updated_at'])

    pay.status = PaymentStatus.CANCELLED
    if reason:
        pay.notes = f'{pay.notes}\n[Сторнировано {timezone.now().strftime("%d.%m.%Y %H:%M")}: {reason}]'.strip()
    pay.save(update_fields=['status', 'notes'])

    AuditLog.objects.create(
        user=user,
        action='STORNO_SUPPLIER_PAYMENT',
        entity_type='SupplierPayment',
        entity_id=str(pay.id),
        details={
            'payment_number': pay.payment_number,
            'supplier': pay.supplier.name,
            'storno_amount': float(pay.amount_kzt),
            'reason': reason,
        },
    )
    return pay


# ==============================================================================
# ПЕРЕВОДЫ МЕЖДУ СЧЕТАМИ (TRANSFERS)
# ==============================================================================

@transaction.atomic
def transfer_between_accounts(
    from_account: FinancialAccount,
    to_account: FinancialAccount,
    amount_kzt: Decimal,
    user: User = None,
    created_by: User = None,
    recorded_by: User = None,
    transfer_date=None,
    notes: str = '',
    description: str = '',
) -> AccountTransfer:
    """Внутренний перевод между счетами и кассами (не влияет на P&L)."""
    user = user or created_by or recorded_by
    notes = notes or description
    if from_account.pk == to_account.pk:
        raise ValidationError('Нельзя выполнить перевод на один и тот же счёт.')

    amount = Decimal(str(amount_kzt)).quantize(Decimal('0.01'))
    if amount <= Decimal('0.00'):
        raise ValidationError('Сумма перевода должна быть больше нуля.')

    # Сортировка по id для исключения взаимоблокировок (deadlocks)
    acc_ids = sorted([from_account.pk, to_account.pk])
    locked = {a.pk: a for a in FinancialAccount.objects.select_for_update().filter(pk__in=acc_ids)}

    acc_from = locked[from_account.pk]
    acc_to = locked[to_account.pk]

    if not acc_from.is_active or not acc_to.is_active:
        raise ValidationError('Один из выбранных счетов деактивирован.')

    if acc_from.current_balance_kzt < amount:
        raise ValidationError(
            f'Недостаточно средств на счёте «{acc_from.name}». '
            f'Баланс: {acc_from.current_balance_kzt:,.2f} ₸, перевод: {amount:,.2f} ₸.'
        )

    acc_from.current_balance_kzt -= amount
    acc_to.current_balance_kzt += amount
    acc_from.save(update_fields=['current_balance_kzt', 'updated_at'])
    acc_to.save(update_fields=['current_balance_kzt', 'updated_at'])

    t_num = generate_payment_number('TRF')
    trf = AccountTransfer.objects.create(
        transfer_number=t_num,
        from_account=acc_from,
        to_account=acc_to,
        amount_kzt=amount,
        transfer_date=transfer_date or timezone.localdate(),
        status=PaymentStatus.COMPLETED,
        notes=notes,
        recorded_by=user,
    )

    AuditLog.objects.create(
        user=user,
        action='ACCOUNT_TRANSFER',
        entity_type='AccountTransfer',
        entity_id=str(trf.id),
        details={
            'transfer_number': trf.transfer_number,
            'from_account': acc_from.name,
            'to_account': acc_to.name,
            'amount': float(amount),
        },
    )
    return trf


# ==============================================================================
# УЧЁТ РАСХОДОВ И ПРОЧИХ ДОХОДОВ
# ==============================================================================

@transaction.atomic
def record_expense(
    category: str,
    amount_kzt: Decimal,
    description: str,
    user: User = None,
    recorded_by: User = None,
    account: FinancialAccount = None,
    payee: str = '',
    payment_method: str = PaymentMethod.BANK_TRANSFER,
    payment_date=None,
) -> Expense:
    """Регистрация операционного расхода предприятия с опциональным списанием с кассы/счёта."""
    user = user or recorded_by
    amount = Decimal(str(amount_kzt)).quantize(Decimal('0.01'))
    if amount <= Decimal('0.00'):
        raise ValidationError('Сумма расхода должна быть строго положительной.')

    acc = None
    if account:
        acc = FinancialAccount.objects.select_for_update().get(pk=account.pk)
        if acc.current_balance_kzt < amount:
            raise ValidationError(
                f'Недостаточно средств на счёте «{acc.name}». '
                f'Остаток: {acc.current_balance_kzt:,.2f} ₸, расход: {amount:,.2f} ₸.'
            )
        acc.current_balance_kzt -= amount
        acc.save(update_fields=['current_balance_kzt', 'updated_at'])

    exp = Expense.objects.create(
        expense_number=generate_payment_number('EXP'),
        category=category,
        amount_kzt=amount,
        payment_date=payment_date or timezone.localdate(),
        description=description,
        payee=payee,
        account=acc,
        payment_method=payment_method,
        recorded_by=user,
    )

    AuditLog.objects.create(
        user=user,
        action='RECORD_EXPENSE',
        entity_type='Expense',
        entity_id=str(exp.id),
        details={'expense_number': exp.expense_number, 'category': category, 'amount': float(amount)},
    )
    return exp


@transaction.atomic
def storno_expense(expense: Expense, user: User, reason: str = '') -> Expense:
    """Сторнирование расхода с возвратом средств на счёт (если расход был привязан к счёту)."""
    exp = Expense.objects.select_for_update().get(pk=expense.pk)
    if exp.is_storno:
        raise ValidationError('Расход уже был сторнирован ранее.')

    if exp.account:
        acc = FinancialAccount.objects.select_for_update().get(pk=exp.account.pk)
        acc.current_balance_kzt += exp.amount_kzt
        acc.save(update_fields=['current_balance_kzt', 'updated_at'])

    exp.is_storno = True
    if reason:
        exp.description = f'{exp.description} [Сторно: {reason}]'
    exp.save(update_fields=['is_storno', 'description'])

    AuditLog.objects.create(
        user=user,
        action='STORNO_EXPENSE',
        entity_type='Expense',
        entity_id=str(exp.id),
        details={'expense_number': exp.expense_number, 'amount': float(exp.amount_kzt), 'reason': reason},
    )
    return exp


@transaction.atomic
def record_general_income(
    category: str,
    amount_kzt: Decimal,
    account: FinancialAccount,
    description: str,
    user: User,
    payer: str = '',
    payment_method: str = PaymentMethod.BANK_TRANSFER,
    income_date=None,
) -> GeneralIncome:
    """Регистрация прочего дохода (не привязанного к заказам) с зачислением на счёт."""
    amount = Decimal(str(amount_kzt)).quantize(Decimal('0.01'))
    if amount <= Decimal('0.00'):
        raise ValidationError('Сумма дохода должна быть больше нуля.')

    acc = FinancialAccount.objects.select_for_update().get(pk=account.pk)
    acc.current_balance_kzt += amount
    acc.save(update_fields=['current_balance_kzt', 'updated_at'])

    inc = GeneralIncome.objects.create(
        income_number=generate_payment_number('INC'),
        category=category,
        amount_kzt=amount,
        income_date=income_date or timezone.localdate(),
        payer=payer,
        account=acc,
        payment_method=payment_method,
        description=description,
        recorded_by=user,
    )

    AuditLog.objects.create(
        user=user,
        action='RECORD_GENERAL_INCOME',
        entity_type='GeneralIncome',
        entity_id=str(inc.id),
        details={'income_number': inc.income_number, 'category': category, 'amount': float(amount)},
    )
    return inc


# ==============================================================================
# СВОДНЫЕ ФИНАНСОВЫЕ KPI И РАСЧЁТЫ
# ==============================================================================

def get_financial_dashboard_kpis(date_from=None, date_to=None, start_date=None, end_date=None) -> dict:
    """Расчёт финансовых показателей за период (начисление vs кассовый метод, задолженности)."""
    date_from = date_from or start_date
    date_to = date_to or end_date
    # 1. Доходы по начислению (Accrual Revenue)
    sales_qs = SalesOrder.objects.filter(
        status__in=[OrderStatus.CONFIRMED, OrderStatus.READY, OrderStatus.PARTIALLY_SHIPPED, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    )
    if date_from:
        sales_qs = sales_qs.filter(created_at__date__gte=date_from)
    if date_to:
        sales_qs = sales_qs.filter(created_at__date__lte=date_to)

    total_accrual_revenue = sales_qs.aggregate(t=models.Sum('total_amount_kzt'))['t'] or Decimal('0.00')

    # Прочие доходы
    incomes_qs = GeneralIncome.objects.filter(is_storno=False)
    if date_from:
        incomes_qs = incomes_qs.filter(income_date__gte=date_from)
    if date_to:
        incomes_qs = incomes_qs.filter(income_date__lte=date_to)
    other_income = incomes_qs.aggregate(t=models.Sum('amount_kzt'))['t'] or Decimal('0.00')

    total_revenue_all = total_accrual_revenue + other_income

    # 2. Фактическое движение денег (Cash Inflow & Cash Outflow)
    pay_cust_qs = CustomerPayment.objects.filter(status=PaymentStatus.COMPLETED)
    if date_from:
        pay_cust_qs = pay_cust_qs.filter(payment_date__gte=date_from)
    if date_to:
        pay_cust_qs = pay_cust_qs.filter(payment_date__lte=date_to)
    cash_inflow = (pay_cust_qs.aggregate(t=models.Sum('amount_kzt'))['t'] or Decimal('0.00')) + other_income

    pay_sup_qs = SupplierPayment.objects.filter(status=PaymentStatus.COMPLETED)
    if date_from:
        pay_sup_qs = pay_sup_qs.filter(payment_date__gte=date_from)
    if date_to:
        pay_sup_qs = pay_sup_qs.filter(payment_date__lte=date_to)
    supplier_cash_paid = pay_sup_qs.aggregate(t=models.Sum('amount_kzt'))['t'] or Decimal('0.00')

    exp_qs = Expense.objects.filter(is_storno=False)
    if date_from:
        exp_qs = exp_qs.filter(payment_date__gte=date_from)
    if date_to:
        exp_qs = exp_qs.filter(payment_date__lte=date_to)
    general_expenses = exp_qs.aggregate(t=models.Sum('amount_kzt'))['t'] or Decimal('0.00')

    cash_outflow = supplier_cash_paid + general_expenses
    net_cash_flow = cash_inflow - cash_outflow

    # 3. Расходы по начислению и Финансовый результат (P&L)
    net_profit = total_revenue_all - general_expenses

    # 4. Балансы на счетах и в кассе
    accounts = FinancialAccount.objects.filter(is_active=True).order_by('name')
    total_cash_and_bank = accounts.aggregate(t=models.Sum('current_balance_kzt'))['t'] or Decimal('0.00')

    # 5. Дебиторская задолженность (Долги клиентов перед фабрикой)
    active_sales = SalesOrder.objects.exclude(status__in=[OrderStatus.DRAFT, OrderStatus.CANCELLED])
    receivables_total = Decimal('0.00')
    receivables_list = []
    for so in active_sales:
        debt = so.remaining_debt_kzt
        if debt > Decimal('0.00'):
            receivables_total += debt
            receivables_list.append({
                'order': so,
                'customer': so.customer,
                'total': so.total_amount_kzt,
                'paid': so.paid_amount_kzt,
                'debt': debt,
            })
    receivables_list.sort(key=lambda x: x['debt'], reverse=True)

    # 6. Кредиторская задолженность (Долги фабрики перед поставщиками)
    active_pos = PurchaseOrder.objects.exclude(status__in=[PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.CANCELLED])
    payables_total = Decimal('0.00')
    payables_list = []
    for po in active_pos:
        debt = po.remaining_debt_kzt
        if debt > Decimal('0.00'):
            payables_total += debt
            payables_list.append({
                'order': po,
                'supplier': po.supplier,
                'total': po.total_amount_kzt,
                'paid': po.paid_amount_kzt,
                'debt': debt,
            })
    payables_list.sort(key=lambda x: x['debt'], reverse=True)

    # 7. Структура расходов по категориям
    expense_structure = []
    for cat in ExpenseCategory:
        tot = exp_qs.filter(category=cat.value).aggregate(t=models.Sum('amount_kzt'))['t'] or Decimal('0.00')
        if tot > Decimal('0.00'):
            pct = round(float(tot / general_expenses) * 100, 1) if general_expenses > Decimal('0.00') else 0.0
            expense_structure.append({
                'category': cat.value,
                'label': cat.label,
                'amount': tot,
                'total': tot,
                'percent': pct,
            })
    expense_structure.sort(key=lambda x: x['amount'], reverse=True)

    return {
        'total_accrual_revenue': total_accrual_revenue,
        'accrual_revenue_kzt': total_accrual_revenue,
        'other_income': other_income,
        'other_income_kzt': other_income,
        'total_revenue_all': total_revenue_all,
        'total_revenue_kzt': total_revenue_all,
        'general_expenses': general_expenses,
        'cash_expenses_kzt': general_expenses,
        'purchases_total': supplier_cash_paid,
        'purchases_total_kzt': supplier_cash_paid,
        'net_profit': net_profit,
        'net_profit_kzt': net_profit,
        'cash_inflow': cash_inflow,
        'cash_inflow_kzt': cash_inflow,
        'cash_outflow': cash_outflow,
        'cash_outflow_kzt': cash_outflow,
        'net_cash_flow': net_cash_flow,
        'net_cash_flow_kzt': net_cash_flow,
        'total_cash_and_bank': total_cash_and_bank,
        'total_account_balance_kzt': total_cash_and_bank,
        'accounts': accounts,
        'receivables_total': receivables_total,
        'total_receivables_kzt': receivables_total,
        'receivables_count': len(receivables_list),
        'receivables_list': receivables_list[:10],
        'payables_total': payables_total,
        'total_payables_kzt': payables_total,
        'payables_count': len(payables_list),
        'payables_list': payables_list[:10],
        'expense_structure': expense_structure,
        'expenses_breakdown': expense_structure,
    }


def calculate_production_order_actual_cost(order) -> dict:
    """Детальный расчёт план-факт себестоимости производственного заказа на основе складских списаний."""
    if not isinstance(order, ProductionOrder):
        order = ProductionOrder.objects.get(pk=order)

    # 1. Фактические материалы со склада WH-1
    actual_materials_cost = Decimal('0.00')
    actual_materials_items = []

    # Анализируем складские движения отпуска сырья под заказ
    movements = StockMovement.objects.filter(
        movement_type=MovementType.ISSUE,
        document__production_order=order,
    ).select_related('material')

    for m in movements:
        cost = (m.quantity * m.unit_cost_kzt).quantize(Decimal('0.01'))
        actual_materials_cost += cost
        actual_materials_items.append({
            'material': m.material,
            'quantity': m.quantity,
            'unit': m.unit,
            'unit_cost': m.unit_cost_kzt,
            'total_cost': cost,
        })

    # Если списаний через движения нет, берем материальные списания заказа
    if actual_materials_cost == Decimal('0.00'):
        actual_materials_cost = order.actual_materials_cost_kzt

    # 2. ФОТ и трудочасы
    actual_labor_cost = order.actual_labor_cost_kzt
    overhead_cost = order.overhead_cost_kzt

    # 3. Брак и потери
    waste_cost = sum((w.cost_kzt for w in order.wastes.all()), Decimal('0.00'))

    # Итого
    actual_total_cost = actual_materials_cost + actual_labor_cost + overhead_cost + waste_cost
    qty_produced = order.quantity_produced if order.quantity_produced > Decimal('0.00') else order.quantity_planned
    unit_cost = (actual_total_cost / qty_produced).quantize(Decimal('0.01')) if qty_produced > Decimal('0.00') else Decimal('0.00')

    # Отклонение план/факт
    cost_variance = actual_total_cost - order.planned_cost_kzt
    variance_pct = round(float(cost_variance / order.planned_cost_kzt) * 100, 1) if order.planned_cost_kzt > Decimal('0.00') else 0.0

    return {
        'planned_cost': order.planned_cost_kzt,
        'planned_cost_kzt': order.planned_cost_kzt,
        'planned_materials': order.planned_materials_cost_kzt,
        'planned_materials_cost_kzt': order.planned_materials_cost_kzt,
        'planned_labor': order.planned_labor_cost_kzt,
        'planned_labor_cost_kzt': order.planned_labor_cost_kzt,
        'planned_overhead': order.overhead_cost_kzt,
        'planned_overhead_cost_kzt': order.overhead_cost_kzt,
        'actual_materials': actual_materials_cost,
        'actual_materials_cost_kzt': actual_materials_cost,
        'actual_material_cost_kzt': actual_materials_cost,
        'actual_labor': actual_labor_cost,
        'actual_labor_cost_kzt': actual_labor_cost,
        'actual_overhead': overhead_cost,
        'actual_overhead_cost_kzt': overhead_cost,
        'labor_and_overhead_cost_kzt': actual_labor_cost + overhead_cost,
        'waste_cost': waste_cost,
        'waste_cost_kzt': waste_cost,
        'actual_total_cost': actual_total_cost,
        'total_actual_cost_kzt': actual_total_cost,
        'quantity_produced': qty_produced,
        'unit_cost': unit_cost,
        'actual_unit_cost_kzt': unit_cost,
        'cost_variance': cost_variance,
        'cost_variance_kzt': cost_variance,
        'variance_pct': variance_pct,
        'is_over_budget': cost_variance > Decimal('0.00'),
    }
