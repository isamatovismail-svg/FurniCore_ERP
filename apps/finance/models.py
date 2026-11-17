import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AccountType(models.TextChoices):
    CASH  = 'CASH',  _('Касса (Наличные)')
    BANK  = 'BANK',  _('Банковский расчётный счёт')
    KASPI = 'KASPI', _('Kaspi Pay / Эквайринг')
    OTHER = 'OTHER', _('Прочий счёт')


class PaymentMethod(models.TextChoices):
    CASH          = 'CASH',          _('Наличные в кассу')
    BANK_TRANSFER = 'BANK_TRANSFER', _('Безналичный банковский перевод')
    KASPI_PAY     = 'KASPI_PAY',     _('Kaspi Pay / QR')
    CARD          = 'CARD',          _('Банковская карта (POS-терминал)')


class PaymentStatus(models.TextChoices):
    COMPLETED = 'COMPLETED', _('Проведён')
    CANCELLED = 'CANCELLED', _('Сторнирован / Аннулирован')


class FinancialAccount(models.Model):
    """Денежные счета, кассы и эквайринг фабрики."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, verbose_name='Наименование счёта')
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.BANK,
        verbose_name='Тип счёта',
    )
    account_number = models.CharField(max_length=50, blank=True, verbose_name='Номер счёта / IBAN')
    currency = models.CharField(max_length=10, default='KZT', verbose_name='Валюта')
    initial_balance_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Начальный остаток (KZT)',
    )
    current_balance_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Текущий баланс (KZT)',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлен')

    class Meta:
        verbose_name = 'Денежный счёт / Касса'
        verbose_name_plural = 'Денежные счета и кассы'
        ordering = ['name']

    @property
    def created_by(self):
        return getattr(self, 'recorded_by', None)

    def __str__(self):
        return f'{self.name} ({self.current_balance_kzt:,.2f} ₸)'

    @property
    def balance_kzt(self):
        return self.current_balance_kzt

    @balance_kzt.setter
    def balance_kzt(self, value):
        self.current_balance_kzt = value

    @property
    def type_label(self):
        return self.get_account_type_display()

    def get_type_display(self):
        return self.get_account_type_display()


class CustomerPayment(models.Model):
    """Поступление оплаты от клиента по заказу покупателя."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_number = models.CharField(max_length=50, unique=True, verbose_name='Номер квитанции')
    sales_order = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='Заказ покупателя',
    )
    customer = models.ForeignKey(
        'sales.Customer',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='Покупатель',
    )
    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name='customer_payments',
        verbose_name='Счёт зачисления',
    )
    amount_kzt = models.DecimalField(
        max_digits=16, decimal_places=2,
        verbose_name='Сумма платежа (KZT)',
    )
    payment_date = models.DateField(default=timezone.localdate, verbose_name='Дата платежа')
    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.BANK_TRANSFER,
        verbose_name='Способ оплаты',
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.COMPLETED,
        verbose_name='Статус',
    )
    reference_number = models.CharField(
        max_length=100, blank=True,
        verbose_name='Чек / Транзакция банка',
    )
    notes = models.TextField(blank=True, verbose_name='Примечания к платежу')
    recorded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='recorded_customer_payments',
        verbose_name='Бухгалтер / Кассир',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Платёж покупателя'
        verbose_name_plural = 'Платежи покупателей'
        ordering = ['-payment_date', '-created_at']

    @property
    def created_by(self):
        return self.recorded_by

    def __str__(self):
        return f'{self.payment_number} — {self.amount_kzt:,.2f} ₸ ({self.customer.name})'

    @property
    def is_storno(self) -> bool:
        return self.status == PaymentStatus.CANCELLED


class SupplierPayment(models.Model):
    """Выплата поставщику сырья / фурнитуры по заказу на закупку."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_number = models.CharField(max_length=50, unique=True, verbose_name='Номер платёжки')
    purchase_order = models.ForeignKey(
        'suppliers.PurchaseOrder',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='payments',
        verbose_name='Заказ на закупку',
    )
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='Поставщик',
    )
    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name='supplier_payments',
        verbose_name='Счёт списания',
    )
    amount_kzt = models.DecimalField(
        max_digits=16, decimal_places=2,
        verbose_name='Сумма выплаты (KZT)',
    )
    payment_date = models.DateField(default=timezone.localdate, verbose_name='Дата выплаты')
    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.BANK_TRANSFER,
        verbose_name='Способ оплаты',
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.COMPLETED,
        verbose_name='Статус',
    )
    reference_number = models.CharField(
        max_length=100, blank=True,
        verbose_name='Платёжное поручение №',
    )
    notes = models.TextField(blank=True, verbose_name='Назначение платежа')
    recorded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='recorded_supplier_payments',
        verbose_name='Бухгалтер',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Платёж поставщику'
        verbose_name_plural = 'Платежи поставщикам'
        ordering = ['-payment_date', '-created_at']

    @property
    def created_by(self):
        return self.recorded_by

    def __str__(self):
        return f'{self.payment_number} — {self.amount_kzt:,.2f} ₸ ({self.supplier.name})'

    @property
    def is_storno(self) -> bool:
        return self.status == PaymentStatus.CANCELLED


class AccountTransfer(models.Model):
    """Внутренний перевод денежных средств между счетами и кассами фабрики."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer_number = models.CharField(max_length=50, unique=True, verbose_name='Номер перевода')
    from_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name='transfers_out',
        verbose_name='Со счёта',
    )
    to_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name='transfers_in',
        verbose_name='На счёт',
    )
    amount_kzt = models.DecimalField(
        max_digits=16, decimal_places=2,
        verbose_name='Сумма перевода (KZT)',
    )
    transfer_date = models.DateField(default=timezone.localdate, verbose_name='Дата перевода')
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.COMPLETED,
        verbose_name='Статус',
    )
    notes = models.TextField(blank=True, verbose_name='Основание / Примечание')
    recorded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='recorded_transfers',
        verbose_name='Бухгалтер / Кассир',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Внутренний перевод'
        verbose_name_plural = 'Внутренние переводы'
        ordering = ['-transfer_date', '-created_at']

    @property
    def created_by(self):
        return self.recorded_by

    def __str__(self):
        return f'{self.transfer_number}: {self.from_account.name} → {self.to_account.name} ({self.amount_kzt:,.2f} ₸)'


class ExpenseCategory(models.TextChoices):
    MATERIALS   = 'MATERIALS',   _('Закупка сырья и комплектующих')
    ELECTRICITY = 'ELECTRICITY', _('Электроэнергия')
    GAS         = 'GAS',         _('Отопление и газ')
    WATER       = 'WATER',       _('Водоснабжение')
    RENT        = 'RENT',        _('Аренда помещений цеха и склада')
    PAYROLL     = 'PAYROLL',     _('Фонд оплаты труда (ФОТ)')
    TRANSPORT   = 'TRANSPORT',   _('Транспорт и доставка')
    REPAIRS     = 'REPAIRS',     _('Техобслуживание станков и оборудования')
    EQUIPMENT   = 'EQUIPMENT',   _('Инструмент, фрезы, пилы и оснастка')
    PACKAGING   = 'PACKAGING',   _('Упаковочные материалы (гофрокартон, стретч)')
    MARKETING   = 'MARKETING',   _('Реклама и маркетинг')
    TAXES       = 'TAXES',       _('Налоги и сборы')
    OTHER       = 'OTHER',       _('Прочие хозяйственные расходы')


class Expense(models.Model):
    """Учёт операционных расходов фабрики."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense_number = models.CharField(max_length=50, blank=True, verbose_name='Номер расхода')
    category = models.CharField(
        max_length=50,
        choices=ExpenseCategory.choices,
        verbose_name='Статья расходов',
    )
    amount_kzt = models.DecimalField(
        max_digits=16, decimal_places=2,
        verbose_name='Сумма расхода (KZT)',
    )
    payment_date = models.DateField(default=timezone.localdate, verbose_name='Дата платежа')
    description = models.CharField(max_length=255, verbose_name='Назначение платежа')
    payee = models.CharField(max_length=200, blank=True, verbose_name='Получатель / Контрагент')
    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='expenses',
        verbose_name='Счёт списания',
    )
    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.BANK_TRANSFER,
        verbose_name='Способ оплаты',
    )
    is_storno = models.BooleanField(default=False, verbose_name='Сторнирован')
    recorded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Бухгалтер',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Расходная операция'
        verbose_name_plural = 'Финансовые расходы'
        ordering = ['-payment_date', '-created_at']

    @property
    def created_by(self):
        return self.recorded_by

    def __str__(self):
        return f'{self.get_category_display()}: {self.amount_kzt:,.2f} ₸ ({self.payment_date})'


class IncomeCategory(models.TextChoices):
    FURNITURE_SALE = 'FURNITURE_SALE', _('Выручка от продажи мебели')
    SERVICES       = 'SERVICES',       _('Услуги сборки / монтажа / дизайн')
    SCRAP_SALE     = 'SCRAP_SALE',     _('Реализация деловых отходов / опилок')
    OTHER          = 'OTHER',          _('Прочие доходы')


class GeneralIncome(models.Model):
    """Учёт прочих операционных доходов (не привязанных к конкретному заказу покупателя)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    income_number = models.CharField(max_length=50, unique=True, verbose_name='Номер документа')
    category = models.CharField(
        max_length=50,
        choices=IncomeCategory.choices,
        default=IncomeCategory.SERVICES,
        verbose_name='Статья доходов',
    )
    amount_kzt = models.DecimalField(
        max_digits=16, decimal_places=2,
        verbose_name='Сумма дохода (KZT)',
    )
    income_date = models.DateField(default=timezone.localdate, verbose_name='Дата поступления')
    payer = models.CharField(max_length=200, blank=True, verbose_name='Плательщик')
    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name='general_incomes',
        verbose_name='Счёт зачисления',
    )
    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.BANK_TRANSFER,
        verbose_name='Способ оплаты',
    )
    description = models.CharField(max_length=255, verbose_name='Назначение платежа')
    is_storno = models.BooleanField(default=False, verbose_name='Сторнирован')
    recorded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Бухгалтер',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Прочий доход'
        verbose_name_plural = 'Прочие доходы'
        ordering = ['-income_date', '-created_at']

    @property
    def created_by(self):
        return self.recorded_by

    def __str__(self):
        return f'{self.get_category_display()}: {self.amount_kzt:,.2f} ₸ ({self.income_date})'
