import datetime
import uuid
from decimal import Decimal, InvalidOperation
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.accounts.models import AuditLog, User
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
    CustomerReturn,
    CustomerReturnItem,
    CustomerReturnStatus,
    PaymentMethod,
    PaymentStatus,
)
from apps.production.models import ProductionOrder
from apps.warehouses.models import (
    StockMovement,
    MovementType,
    WarehouseType,
    WarehouseDocument,
    WarehouseDocumentItem,
    WarehouseDocumentType,
    DocumentStatus,
)
from apps.warehouses.services import generate_doc_number, post_document, cancel_document


def _money_amount(value) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError('Укажите корректную сумму в KZT.')
    if not amount.is_finite():
        raise ValidationError('Сумма должна быть конечным числом.')
    return amount


def _idempotent_operation(model, key, expected_fields):
    if not key:
        return None
    existing = model.objects.filter(idempotency_key=key).first()
    if existing is None:
        return None
    if any(getattr(existing, field) != value for field, value in expected_fields.items()):
        raise ValidationError('Ключ повторной отправки уже использован для другой операции.')
    return existing


def _validate_account(account: FinancialAccount):
    if not account.is_active:
        raise ValidationError(f'Денежный счёт «{account.name}» не активен.')
    if account.currency != 'KZT':
        raise ValidationError('Финансовые операции доступны только для счетов в KZT.')


def generate_payment_number(prefix: str = 'PAY') -> str:
    """Генерация уникального номера финансовой операции."""
    today_str = timezone.now().strftime('%y%m%d')
    suffix = uuid.uuid4().hex[:4].upper()
    return f'{prefix}-{today_str}-{suffix}'


def ensure_default_accounts() -> list[FinancialAccount]:
    """Гарантирует существование базовых счетов предприятия."""
    defaults = [
        ('Основная касса цеха', AccountType.CASH, '', Decimal('0.00')),
        ('Расчётный счёт', AccountType.BANK, '', Decimal('0.00')),
        ('Kaspi Pay (QR/Эквайринг)', AccountType.KASPI, '', Decimal('0.00')),
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
    idempotency_key=None,
) -> CustomerPayment:
    """Регистрация поступившего платежа от клиента по заказу покупателя."""
    user = user or created_by or recorded_by
    amount = _money_amount(amount_kzt)
    if amount <= Decimal('0.00'):
        raise ValidationError('Сумма платежа должна быть строго больше нуля.')
    if payment_method not in PaymentMethod.values:
        raise ValidationError('Выберите допустимый способ оплаты.')

    so = None
    if sales_order:
        so = SalesOrder.objects.select_for_update().get(pk=sales_order.pk)
        customer = customer or so.customer
    if not so:
        raise ValidationError('Платёж покупателя должен быть привязан к заказу.')
    acc = FinancialAccount.objects.select_for_update().get(pk=account.pk)
    if customer.pk != so.customer_id:
        raise ValidationError('Покупатель не совпадает с покупателем выбранного заказа.')

    replay = _idempotent_operation(CustomerPayment, idempotency_key, {
        'sales_order_id': so.pk,
        'customer_id': customer.pk,
        'account_id': acc.pk,
        'amount_kzt': amount,
        'payment_method': payment_method,
        'reference_number': reference_number,
        'payment_date': payment_date or timezone.localdate(),
        'notes': notes,
    })
    if replay:
        return replay
    _validate_account(acc)

    duplicate = CustomerPayment.objects.filter(
        sales_order=so,
        customer=customer,
        account=acc,
        amount_kzt=amount,
        payment_method=payment_method,
        reference_number=reference_number,
        status=PaymentStatus.COMPLETED,
        created_at__gte=timezone.now() - datetime.timedelta(seconds=10),
    ).first()
    if duplicate:
        raise ValidationError(
            f'Платёж с такими параметрами уже зарегистрирован под номером {duplicate.payment_number}.'
        )

    remaining_debt = so.remaining_debt_kzt
    if amount > remaining_debt:
        raise ValidationError(
            f'Сумма платежа ({amount:,.2f} ₸) превышает остаток долга по заказу {so.order_number} ({remaining_debt:,.2f} ₸).'
        )

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
        idempotency_key=idempotency_key,
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
            'amount': str(amount),
            'account': acc.name,
            'new_balance': str(acc.current_balance_kzt),
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
            'sales_order': pay.sales_order.order_number if pay.sales_order else None,
            'storno_amount': str(pay.amount_kzt),
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
    idempotency_key=None,
) -> SupplierPayment:
    """Регистрация выплаты поставщику по заказу на закупку или общему договору."""
    user = user or created_by or recorded_by
    amount = _money_amount(amount_kzt)
    if amount <= Decimal('0.00'):
        raise ValidationError('Сумма выплаты должна быть строго больше нуля.')
    if payment_method not in PaymentMethod.values:
        raise ValidationError('Выберите допустимый способ оплаты.')

    acc = FinancialAccount.objects.select_for_update().get(pk=account.pk)

    po = None
    if purchase_order:
        po = PurchaseOrder.objects.select_for_update().get(pk=purchase_order.pk)
        supplier = supplier or po.supplier
    if not supplier:
        raise ValidationError('Необходимо указать поставщика.')
    if po and supplier.pk != po.supplier_id:
        raise ValidationError('Поставщик не совпадает с поставщиком выбранного заказа закупки.')

    replay = _idempotent_operation(SupplierPayment, idempotency_key, {
        'purchase_order_id': po.pk if po else None,
        'supplier_id': supplier.pk,
        'account_id': acc.pk,
        'amount_kzt': amount,
        'payment_method': payment_method,
        'reference_number': reference_number,
        'payment_date': payment_date or timezone.localdate(),
        'notes': notes,
    })
    if replay:
        return replay
    _validate_account(acc)

    duplicate = SupplierPayment.objects.filter(
        purchase_order=po,
        supplier=supplier,
        account=acc,
        amount_kzt=amount,
        payment_method=payment_method,
        reference_number=reference_number,
        status=PaymentStatus.COMPLETED,
        created_at__gte=timezone.now() - datetime.timedelta(seconds=10),
    ).first()
    if duplicate:
        raise ValidationError(
            f'Платёж с такими параметрами уже зарегистрирован под номером {duplicate.payment_number}.'
        )

    if po and amount > po.remaining_debt_kzt:
        raise ValidationError(
            f'Сумма выплаты ({amount:,.2f} ₸) превышает остаток задолженности по заказу {po.order_number} ({po.remaining_debt_kzt:,.2f} ₸).'
        )
    if acc.current_balance_kzt < amount:
        raise ValidationError(
            f'Недостаточно средств на счёте «{acc.name}» для совершения выплаты. '
            f'Доступно: {acc.current_balance_kzt:,.2f} ₸, требуется: {amount:,.2f} ₸.'
        )

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
        idempotency_key=idempotency_key,
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
            'amount': str(amount),
            'account': acc.name,
            'new_balance': str(acc.current_balance_kzt),
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
            'supplier': pay.supplier.name if pay.supplier else None,
            'purchase_order': pay.purchase_order.order_number if pay.purchase_order else None,
            'storno_amount': str(pay.amount_kzt),
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
    idempotency_key=None,
) -> AccountTransfer:
    """Внутренний перевод между счетами и кассами (не влияет на P&L)."""
    user = user or created_by or recorded_by
    notes = notes or description
    if from_account.pk == to_account.pk:
        raise ValidationError('Нельзя выполнить перевод на один и тот же счёт.')

    amount = _money_amount(amount_kzt)
    if amount <= Decimal('0.00'):
        raise ValidationError('Сумма перевода должна быть больше нуля.')

    # Сортировка по id для исключения взаимоблокировок (deadlocks)
    acc_ids = sorted([from_account.pk, to_account.pk])
    locked = {a.pk: a for a in FinancialAccount.objects.select_for_update().filter(pk__in=acc_ids)}

    acc_from = locked[from_account.pk]
    acc_to = locked[to_account.pk]

    replay = _idempotent_operation(AccountTransfer, idempotency_key, {
        'from_account_id': acc_from.pk,
        'to_account_id': acc_to.pk,
        'amount_kzt': amount,
        'transfer_date': transfer_date or timezone.localdate(),
        'notes': notes,
    })
    if replay:
        return replay

    _validate_account(acc_from)
    _validate_account(acc_to)

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
        idempotency_key=idempotency_key,
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
            'amount': str(amount),
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
    idempotency_key=None,
) -> Expense:
    """Запись операционного расхода; денежный счёт связывается, если расход оплачен."""
    user = user or recorded_by
    amount = _money_amount(amount_kzt)
    if amount <= Decimal('0.00'):
        raise ValidationError('Сумма расхода должна быть строго положительной.')
    if category not in ExpenseCategory.values:
        raise ValidationError('Выберите допустимую статью расходов.')
    if payment_method not in PaymentMethod.values:
        raise ValidationError('Выберите допустимый способ оплаты.')
    acc = FinancialAccount.objects.select_for_update().get(pk=account.pk) if account else None
    replay = _idempotent_operation(Expense, idempotency_key, {
        'category': category,
        'amount_kzt': amount,
        'description': description,
        'account_id': acc.pk if acc else None,
        'payee': payee,
        'payment_method': payment_method,
        'payment_date': payment_date or timezone.localdate(),
    })
    if replay:
        return replay
    if acc:
        _validate_account(acc)
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
        idempotency_key=idempotency_key,
    )

    AuditLog.objects.create(
        user=user,
        action='RECORD_EXPENSE',
        entity_type='Expense',
        entity_id=str(exp.id),
        details={'expense_number': exp.expense_number, 'category': category, 'amount': str(amount)},
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
        details={'expense_number': exp.expense_number,         'amount': str(exp.amount_kzt), 'reason': reason},
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
    idempotency_key=None,
) -> GeneralIncome:
    """Регистрация прочего дохода (не привязанного к заказам) с зачислением на счёт."""
    amount = _money_amount(amount_kzt)
    if amount <= Decimal('0.00'):
        raise ValidationError('Сумма дохода должна быть больше нуля.')
    if category not in IncomeCategory.values:
        raise ValidationError('Выберите допустимую статью доходов.')
    if payment_method not in PaymentMethod.values:
        raise ValidationError('Выберите допустимый способ оплаты.')

    acc = FinancialAccount.objects.select_for_update().get(pk=account.pk)
    replay = _idempotent_operation(GeneralIncome, idempotency_key, {
        'category': category,
        'amount_kzt': amount,
        'account_id': acc.pk,
        'description': description,
        'payer': payer,
        'payment_method': payment_method,
        'income_date': income_date or timezone.localdate(),
    })
    if replay:
        return replay
    _validate_account(acc)
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
        idempotency_key=idempotency_key,
    )

    AuditLog.objects.create(
        user=user,
        action='RECORD_GENERAL_INCOME',
        entity_type='GeneralIncome',
        entity_id=str(inc.id),
        details={'income_number': inc.income_number, 'category': category, 'amount': str(amount)},
    )
    return inc


@transaction.atomic
def storno_general_income(income: GeneralIncome, user: User, reason: str = '') -> GeneralIncome:
    inc = GeneralIncome.objects.select_for_update().get(pk=income.pk)
    if inc.is_storno:
        raise ValidationError('Доход уже был сторнирован ранее.')
    acc = FinancialAccount.objects.select_for_update().get(pk=inc.account_id)
    if acc.current_balance_kzt < inc.amount_kzt:
        raise ValidationError(
            f'Невозможно сторнировать доход: на счёте «{acc.name}» недостаточно средств.'
        )
    acc.current_balance_kzt -= inc.amount_kzt
    acc.save(update_fields=['current_balance_kzt', 'updated_at'])
    inc.is_storno = True
    if reason:
        inc.description = f'{inc.description} [Сторно: {reason}]'
    inc.save(update_fields=['is_storno', 'description'])
    AuditLog.objects.create(
        user=user,
        action='STORNO_GENERAL_INCOME',
        entity_type='GeneralIncome',
        entity_id=str(inc.pk),
        details={'income_number': inc.income_number, 'amount': str(inc.amount_kzt), 'reason': reason},
    )
    return inc


@transaction.atomic
def storno_account_transfer(transfer: AccountTransfer, user: User, reason: str = '') -> AccountTransfer:
    trf = AccountTransfer.objects.select_for_update().get(pk=transfer.pk)
    if trf.status == PaymentStatus.CANCELLED:
        raise ValidationError('Перевод уже был сторнирован ранее.')
    account_ids = sorted([trf.from_account_id, trf.to_account_id])
    locked = {
        account.pk: account
        for account in FinancialAccount.objects.select_for_update().filter(pk__in=account_ids)
    }
    source = locked[trf.from_account_id]
    target = locked[trf.to_account_id]
    if target.current_balance_kzt < trf.amount_kzt:
        raise ValidationError(
            f'Невозможно сторнировать перевод: на счёте «{target.name}» недостаточно средств.'
        )
    target.current_balance_kzt -= trf.amount_kzt
    source.current_balance_kzt += trf.amount_kzt
    target.save(update_fields=['current_balance_kzt', 'updated_at'])
    source.save(update_fields=['current_balance_kzt', 'updated_at'])
    trf.status = PaymentStatus.CANCELLED
    if reason:
        trf.notes = f'{trf.notes}\n[Сторно: {reason}]'.strip()
    trf.save(update_fields=['status', 'notes'])
    AuditLog.objects.create(
        user=user,
        action='STORNO_ACCOUNT_TRANSFER',
        entity_type='AccountTransfer',
        entity_id=str(trf.pk),
        details={'transfer_number': trf.transfer_number, 'amount': str(trf.amount_kzt), 'reason': reason},
    )
    return trf


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

    gross_accrual_revenue = sales_qs.aggregate(t=models.Sum('total_amount_kzt'))['t'] or Decimal('0.00')
    returns_qs = CustomerReturn.objects.filter(status=CustomerReturnStatus.POSTED)
    if date_from:
        returns_qs = returns_qs.filter(posted_at__date__gte=date_from)
    if date_to:
        returns_qs = returns_qs.filter(posted_at__date__lte=date_to)
    customer_refunds = returns_qs.aggregate(
        t=models.Sum('refund_amount_kzt')
    )['t'] or Decimal('0.00')
    total_accrual_revenue = gross_accrual_revenue - customer_refunds

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
    paid_expenses = exp_qs.filter(account__isnull=False).aggregate(
        t=models.Sum('amount_kzt')
    )['t'] or Decimal('0.00')

    cash_outflow = supplier_cash_paid + paid_expenses + customer_refunds
    net_cash_flow = cash_inflow - cash_outflow

    # 3. Расходы по начислению и Финансовый результат (P&L)
    production_orders = ProductionOrder.objects.exclude(status='CANCELLED')
    if date_from:
        production_orders = production_orders.filter(created_at__date__gte=date_from)
    if date_to:
        production_orders = production_orders.filter(created_at__date__lte=date_to)
    production_costs = sum(
        (calculate_production_order_actual_cost(order)['total_actual_cost_kzt']
         for order in production_orders.select_related('product')),
        Decimal('0.00'),
    )
    net_profit = total_revenue_all - general_expenses - production_costs

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

    sales_order_profits = []
    for order in sales_qs.select_related('customer').prefetch_related('items__product'):
        gross = sales_order_gross_profit(order)
        sales_order_profits.append({
            'order': order,
            'revenue': gross['revenue_kzt'],
            'cost': gross['cogs_kzt'],
            'profit': gross['gross_profit_kzt'],
            'cost_basis': gross['cost_basis'],
        })
    sales_order_profits.sort(key=lambda row: row['profit'], reverse=True)

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
        'cash_expenses_paid_kzt': paid_expenses,
        'customer_refunds_kzt': customer_refunds,
        'purchases_total': supplier_cash_paid,
        'purchases_total_kzt': supplier_cash_paid,
        'net_profit': net_profit,
        'net_profit_kzt': net_profit,
        'production_costs': production_costs,
        'production_costs_kzt': production_costs,
        'sales_order_profits': sales_order_profits[:10],
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
        movement_type__in=[MovementType.ISSUE, MovementType.PRODUCTION_RETURN],
        document__production_order=order,
        document__status='POSTED',
    ).select_related('material')

    has_posted_material_movements = movements.exists()
    for movement in movements:
        movement_cost = movement.total_cost_kzt
        if movement_cost == Decimal('0.00'):
            movement_cost = (movement.quantity * movement.unit_cost_kzt).quantize(Decimal('0.01'))
        cost = -movement_cost if movement.movement_type == MovementType.PRODUCTION_RETURN else movement_cost
        actual_materials_cost += cost
        actual_materials_items.append({
            'material': movement.material,
            'quantity': movement.quantity,
            'unit': movement.unit,
            'unit_cost': movement.unit_cost_kzt,
            'total_cost': cost,
            'movement_type': movement.movement_type,
        })

    if not has_posted_material_movements:
        actual_materials_cost = order.actual_materials_cost_kzt

    # 2. ФОТ и накладные расходы из существующих производственных данных
    actual_labor_cost = order.actual_labor_cost_kzt
    overhead_cost = order.overhead_cost_kzt

    # 3. Производственный сервис учитывает стоимость брака отдельно от списаний.
    waste_cost = sum((w.cost_kzt for w in order.wastes.all()), Decimal('0.00'))

    planned_materials_cost = order.planned_materials_cost_kzt
    planned_labor_cost = order.planned_labor_cost_kzt
    planned_overhead_cost = order.overhead_cost_kzt
    if order.bom_id:
        batch_quantity = order.quantity_planned
        if planned_materials_cost == Decimal('0.00'):
            planned_materials_cost = (order.bom.total_materials_cost_kzt * batch_quantity).quantize(Decimal('0.01'))
        if planned_labor_cost == Decimal('0.00'):
            planned_labor_cost = (
                order.bom.standard_labor_hours
                * order.bom.labor_rate_hourly_kzt
                * batch_quantity
            ).quantize(Decimal('0.01'))
        if planned_overhead_cost == Decimal('0.00'):
            planned_overhead_cost = (order.bom.overhead_rate_kzt * batch_quantity).quantize(Decimal('0.01'))
    planned_total_cost = order.planned_cost_kzt or (
        planned_materials_cost + planned_labor_cost + planned_overhead_cost
    )
    if actual_labor_cost == Decimal('0.00') and order.bom_id:
        actual_hours = sum((stage.actual_hours for stage in order.stages.all()), Decimal('0.00'))
        actual_labor_cost = (actual_hours * order.bom.labor_rate_hourly_kzt).quantize(Decimal('0.01'))
    actual_total_cost = actual_materials_cost + actual_labor_cost + overhead_cost + waste_cost
    qty_produced = order.quantity_produced if order.quantity_produced > Decimal('0.00') else order.quantity_planned
    unit_cost = (actual_total_cost / qty_produced).quantize(Decimal('0.01')) if qty_produced > Decimal('0.00') else Decimal('0.00')

    # Отклонение план/факт
    cost_variance = actual_total_cost - planned_total_cost
    variance_pct = round(float(cost_variance / planned_total_cost) * 100, 1) if planned_total_cost > Decimal('0.00') else 0.0

    return {
        'planned_cost': planned_total_cost,
        'planned_cost_kzt': planned_total_cost,
        'planned_materials': planned_materials_cost,
        'planned_materials_cost_kzt': planned_materials_cost,
        'planned_labor': planned_labor_cost,
        'planned_labor_cost_kzt': planned_labor_cost,
        'planned_overhead': planned_overhead_cost,
        'planned_overhead_cost_kzt': planned_overhead_cost,
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


@transaction.atomic
def record_customer_return(
    sales_order: SalesOrder,
    shipment: WarehouseDocument,
    account: FinancialAccount,
    returned_items: dict,
    user: User,
    reason: str = '',
    idempotency_key=None,
) -> CustomerReturn:
    """Register a partial/full buyer return and refund via existing WH-2 document service."""
    if not idempotency_key:
        raise ValidationError('Для возврата обязателен ключ идемпотентности.')
    try:
        key = uuid.UUID(str(idempotency_key))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Некорректный ключ идемпотентности возврата.')

    so = SalesOrder.objects.select_for_update().get(pk=sales_order.pk)
    shipment_doc = WarehouseDocument.objects.select_for_update().get(pk=shipment.pk)
    acc = FinancialAccount.objects.get(pk=account.pk)

    replay = CustomerReturn.objects.filter(idempotency_key=key).first()
    if replay:
        normalized_items = {}
        for item_id, raw_quantity in returned_items.items():
            try:
                quantity = Decimal(str(raw_quantity)).quantize(Decimal('0.001'))
            except (InvalidOperation, TypeError, ValueError):
                raise ValidationError('Укажите корректное количество возврата.')
            normalized_items[str(item_id)] = quantity
        existing_items = {
            str(item_id): quantity
            for item_id, quantity in replay.items.values_list('shipment_item_id', 'quantity')
        }
        if (
            replay.sales_order_id != so.pk
            or replay.shipment_id != shipment_doc.pk
            or replay.account_id != acc.pk
            or replay.reason != reason
            or existing_items != normalized_items
        ):
            raise ValidationError('Ключ повторной отправки уже использован для другого возврата.')
        if replay.status != CustomerReturnStatus.POSTED:
            raise ValidationError('Возврат с этим ключом уже сторнирован и не может быть проведён повторно.')
        return replay

    if (
        shipment_doc.doc_type != WarehouseDocumentType.SHIPMENT
        or shipment_doc.status != DocumentStatus.POSTED
        or shipment_doc.sales_order_id != so.pk
        or shipment_doc.warehouse.warehouse_type != WarehouseType.FINISHED_PRODUCTS
    ):
        raise ValidationError('Возврат должен ссылаться на проведённую отгрузку этого заказа с WH-2.')
    if shipment_doc.customer_id != so.customer_id:
        raise ValidationError('Покупатель исходной отгрузки не совпадает с заказом.')
    if not acc.is_active or acc.currency != 'KZT':
        raise ValidationError('Для возврата выберите активный счёт в KZT.')

    refund_total = Decimal('0.00')
    lines = []
    for item_id, raw_quantity in returned_items.items():
        try:
            quantity = Decimal(str(raw_quantity)).quantize(Decimal('0.001'))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError('Укажите корректное количество возврата.')
        if quantity <= Decimal('0.000'):
            raise ValidationError('Количество возврата должно быть больше нуля.')

        shipment_item = (
            WarehouseDocumentItem.objects.select_for_update(of=('self',))
            .select_related('product', 'sales_order_item')
            .filter(pk=item_id, document=shipment_doc)
            .first()
        )
        if not shipment_item or not shipment_item.product_id:
            raise ValidationError('Позиция не принадлежит исходной отгрузке.')

        returned = CustomerReturnItem.objects.filter(
            shipment_item=shipment_item,
            customer_return__status=CustomerReturnStatus.POSTED,
        ).aggregate(total=models.Sum('quantity'))['total'] or Decimal('0.000')
        remaining = shipment_item.quantity - returned
        if quantity > remaining:
            raise ValidationError(
                f'Нельзя вернуть {quantity} шт.; по отгрузке доступно {remaining} шт.'
            )

        sale_unit_price = shipment_item.sale_unit_price_kzt
        if sale_unit_price <= Decimal('0.00') and shipment_item.sales_order_item:
            order_item = shipment_item.sales_order_item
            sale_unit_price = (
                order_item.unit_price_kzt
                * (Decimal('100.00') - order_item.discount_percent)
                / Decimal('100.00')
            ).quantize(Decimal('0.01'))
        cogs_unit = shipment_item.unit_cost_kzt
        line_refund = (quantity * sale_unit_price).quantize(Decimal('0.01'))
        line_cogs = (quantity * cogs_unit).quantize(Decimal('0.01'))
        refund_total += line_refund
        lines.append((shipment_item, quantity, line_refund, line_cogs))

    if not lines:
        raise ValidationError('Укажите хотя бы одну позицию возврата.')
    completed_payments = list(
        CustomerPayment.objects.select_for_update()
        .filter(sales_order=so, status=PaymentStatus.COMPLETED)
        .values_list('amount_kzt', flat=True)
    )
    paid_amount = sum(completed_payments, Decimal('0.00'))
    already_refunded = CustomerReturn.objects.filter(
        sales_order=so,
        status=CustomerReturnStatus.POSTED,
    ).aggregate(total=models.Sum('refund_amount_kzt'))['total'] or Decimal('0.00')
    refundable_amount = max(Decimal('0.00'), paid_amount - already_refunded)
    if refund_total > refundable_amount:
        raise ValidationError(
            f'Возврат {refund_total:,.2f} ₸ превышает фактически оплаченную сумму, '
            f'доступную к возврату ({refundable_amount:,.2f} ₸).'
        )
    acc = FinancialAccount.objects.select_for_update().get(pk=acc.pk)
    if not acc.is_active or acc.currency != 'KZT':
        raise ValidationError('Для возврата выберите активный счёт в KZT.')
    if acc.current_balance_kzt < refund_total:
        raise ValidationError(
            f'Недостаточно средств на счёте «{acc.name}» для возврата {refund_total:,.2f} ₸.'
        )

    return_doc = WarehouseDocument.objects.create(
        doc_number=generate_doc_number(WarehouseDocumentType.CUSTOMER_RETURN),
        doc_type=WarehouseDocumentType.CUSTOMER_RETURN,
        status=DocumentStatus.DRAFT,
        warehouse=shipment_doc.warehouse,
        customer=so.customer,
        sales_order=so,
        created_by=user,
        notes=f'Возврат по отгрузке {shipment_doc.doc_number}. {reason}'.strip(),
    )
    customer_return = CustomerReturn.objects.create(
        return_number=generate_payment_number('RET-C'),
        idempotency_key=key,
        sales_order=so,
        shipment=shipment_doc,
        warehouse_document=return_doc,
        customer=so.customer,
        account=acc,
        refund_amount_kzt=refund_total,
        reason=reason,
        recorded_by=user,
    )
    for shipment_item, quantity, line_refund, line_cogs in lines:
        WarehouseDocumentItem.objects.create(
            document=return_doc,
            product=shipment_item.product,
            sales_order_item=shipment_item.sales_order_item,
            quantity=quantity,
            unit=shipment_item.unit,
            unit_cost_kzt=shipment_item.unit_cost_kzt,
            total_cost_kzt=line_cogs,
            sale_unit_price_kzt=shipment_item.sale_unit_price_kzt,
            costing_method=shipment_item.costing_method,
            notes=f'Возврат по отгрузке {shipment_doc.doc_number}',
        )
        CustomerReturnItem.objects.create(
            customer_return=customer_return,
            shipment_item=shipment_item,
            quantity=quantity,
            refund_amount_kzt=line_refund,
            cogs_amount_kzt=line_cogs,
        )

    post_document(return_doc, user=user)
    acc.current_balance_kzt -= refund_total
    acc.save(update_fields=['current_balance_kzt', 'updated_at'])
    AuditLog.objects.create(
        user=user,
        action='POST_CUSTOMER_RETURN',
        entity_type='CustomerReturn',
        entity_id=str(customer_return.pk),
        details={
            'return_number': customer_return.return_number,
            'sales_order': so.order_number,
            'shipment': shipment_doc.doc_number,
            'warehouse_document': return_doc.doc_number,
            'refund_amount_kzt': str(refund_total),
        },
    )
    return customer_return


@transaction.atomic
def storno_customer_return(customer_return: CustomerReturn, user: User, reason: str = '') -> CustomerReturn:
    ret = CustomerReturn.objects.select_for_update().get(pk=customer_return.pk)
    if ret.status == CustomerReturnStatus.CANCELLED:
        raise ValidationError('Возврат уже был сторнирован ранее.')
    acc = FinancialAccount.objects.select_for_update().get(pk=ret.account_id)
    cancel_document(ret.warehouse_document, user=user)
    acc.current_balance_kzt += ret.refund_amount_kzt
    acc.save(update_fields=['current_balance_kzt', 'updated_at'])
    ret.status = CustomerReturnStatus.CANCELLED
    if reason:
        ret.reason = f'{ret.reason}\n[Сторно: {reason}]'.strip()
    ret.save(update_fields=['status', 'reason'])
    AuditLog.objects.create(
        user=user,
        action='STORNO_CUSTOMER_RETURN',
        entity_type='CustomerReturn',
        entity_id=str(ret.pk),
        details={'return_number': ret.return_number, 'reason': reason},
    )
    return ret


def debt_aging(order, today=None) -> dict:
    today = today or timezone.localdate()
    debt = order.remaining_debt_kzt
    due_date = order.payment_due_date
    overdue_days = max((today - due_date).days, 0) if due_date and debt > Decimal('0.00') else 0
    if debt <= Decimal('0.00'):
        bucket = 'settled'
    elif not due_date:
        bucket = 'no_due_date'
    elif overdue_days == 0:
        bucket = 'not_due'
    elif overdue_days <= 30:
        bucket = '1_30'
    elif overdue_days <= 60:
        bucket = '31_60'
    elif overdue_days <= 90:
        bucket = '61_90'
    else:
        bucket = 'over_90'
    return {
        'due_date': due_date,
        'overdue_days': overdue_days,
        'is_overdue': overdue_days > 0,
        'bucket': bucket,
        'debt': debt,
    }


def sales_order_gross_profit(order: SalesOrder) -> dict:
    shipments = order.warehouse_documents.filter(
        doc_type=WarehouseDocumentType.SHIPMENT,
        status=DocumentStatus.POSTED,
    )
    if not shipments.exists():
        return {
            'revenue_kzt': order.total_amount_kzt,
            'cogs_kzt': order.total_cost_kzt,
            'gross_profit_kzt': order.total_amount_kzt - order.total_cost_kzt,
            'cost_basis': 'planned',
        }

    revenue = Decimal('0.00')
    revenue_complete = True
    for shipment_item in WarehouseDocumentItem.objects.filter(
        document__in=shipments,
        product__isnull=False,
    ).select_related('sales_order_item'):
        sale_unit_price = shipment_item.sale_unit_price_kzt
        if sale_unit_price <= Decimal('0.00') and shipment_item.sales_order_item_id:
            order_item = shipment_item.sales_order_item
            sale_unit_price = (
                order_item.unit_price_kzt
                * (Decimal('100.00') - order_item.discount_percent)
                * (Decimal('100.00') - order.discount_percent)
                / Decimal('10000.00')
            ).quantize(Decimal('0.01'))
        if sale_unit_price <= Decimal('0.00'):
            revenue_complete = False
            break
        revenue += (shipment_item.quantity * sale_unit_price).quantize(Decimal('0.01'))
    if not revenue_complete:
        revenue = order.total_amount_kzt
    cogs = StockMovement.objects.filter(
        document__in=shipments,
        movement_type=MovementType.SHIPMENT,
    ).aggregate(total=models.Sum('total_cost_kzt'))['total'] or Decimal('0.00')
    posted_returns = order.customer_returns.filter(status=CustomerReturnStatus.POSTED)
    refund = posted_returns.aggregate(total=models.Sum('refund_amount_kzt'))['total'] or Decimal('0.00')
    returned_cogs = CustomerReturnItem.objects.filter(
        customer_return__in=posted_returns
    ).aggregate(total=models.Sum('cogs_amount_kzt'))['total'] or Decimal('0.00')
    net_revenue = max(Decimal('0.00'), revenue - refund)
    net_cogs = max(Decimal('0.00'), cogs - returned_cogs)
    lines = WarehouseDocumentItem.objects.filter(
        document__in=shipments,
        product__isnull=False,
    )
    methods = set(lines.values_list('costing_method', flat=True))
    basis = 'actual' if methods == {'ACTUAL'} else ('mixed' if methods else 'planned')
    return {
        'revenue_kzt': net_revenue,
        'cogs_kzt': net_cogs,
        'gross_profit_kzt': net_revenue - net_cogs,
        'cost_basis': basis,
    }
