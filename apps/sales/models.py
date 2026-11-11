import uuid
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _


class OrderStatus(models.TextChoices):
    DRAFT               = 'DRAFT',               _('Черновик')
    NEW                 = 'NEW',                 _('Новый')
    CONFIRMED           = 'CONFIRMED',           _('Подтверждён')
    WAITING_PRODUCTION  = 'WAITING_PRODUCTION',  _('Ожидает производства')
    IN_PRODUCTION       = 'IN_PRODUCTION',       _('В производстве')
    READY               = 'READY',               _('Готов к отгрузке')
    PARTIALLY_SHIPPED   = 'PARTIALLY_SHIPPED',   _('Частично отгружен')
    SHIPPED             = 'SHIPPED',             _('Отгружен')
    DELIVERED           = 'DELIVERED',           _('Доставлен')
    CANCELLED           = 'CANCELLED',           _('Отменён')


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=200, verbose_name='ФИО / Наименование')
    company_name = models.CharField(max_length=200, blank=True, verbose_name='Юридическое лицо')
    phone = models.CharField(max_length=50, blank=True, verbose_name='Телефон')
    email = models.EmailField(blank=True, verbose_name='Email')
    city = models.CharField(max_length=100, blank=True, verbose_name='Город')
    address = models.CharField(max_length=255, blank=True, verbose_name='Адрес доставки')
    notes = models.TextField(blank=True, verbose_name='Примечания')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ['full_name']

    def __str__(self):
        return self.company_name or self.full_name

    @property
    def name(self) -> str:
        return self.company_name or self.full_name


class SalesOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True, verbose_name='Номер заказа')
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name='orders', verbose_name='Клиент'
    )
    status = models.CharField(
        max_length=30,
        choices=OrderStatus.choices,
        default=OrderStatus.DRAFT,
        verbose_name='Статус',
    )
    subtotal_amount_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Сумма без скидки (KZT)',
    )
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Общая скидка (%)',
    )
    total_amount_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Итоговая сумма (KZT)',
    )
    deposit_amount_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Предоплата (KZT)',
    )
    planned_delivery_date = models.DateField(null=True, blank=True, verbose_name='Плановая дата доставки')
    delivery_address = models.CharField(max_length=255, blank=True, verbose_name='Адрес доставки')
    notes = models.TextField(blank=True, verbose_name='Комментарии')
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Менеджер',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Заказ клиента'
        verbose_name_plural = 'Заказы клиентов'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order_number} — {self.customer}'

    @property
    def can_edit(self) -> bool:
        return self.status in [OrderStatus.DRAFT, OrderStatus.NEW]

    @property
    def can_confirm(self) -> bool:
        return self.status in [OrderStatus.DRAFT, OrderStatus.NEW]

    @property
    def can_ship(self) -> bool:
        return self.status in [
            OrderStatus.CONFIRMED,
            OrderStatus.READY,
            OrderStatus.PARTIALLY_SHIPPED,
        ]

    @property
    def can_cancel(self) -> bool:
        return self.status not in [OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.CANCELLED]

    @property
    def is_fully_shipped(self) -> bool:
        items = list(self.items.all())
        if not items:
            return False
        return all(it.shipped_quantity >= it.quantity for it in items)

    def recalculate_totals(self):
        subtotal = Decimal('0.00')
        for item in self.items.all():
            base_price = Decimal(str(item.quantity)) * Decimal(str(item.unit_price_kzt))
            disc = Decimal(str(item.discount_percent or '0.00'))
            item_total = base_price * (Decimal('100.00') - disc) / Decimal('100.00')
            item.total_price_kzt = item_total.quantize(Decimal('0.01'))
            item.save(update_fields=['total_price_kzt'])
            subtotal += item.total_price_kzt

        self.subtotal_amount_kzt = subtotal
        order_disc = Decimal(str(self.discount_percent or '0.00'))
        total = subtotal * (Decimal('100.00') - order_disc) / Decimal('100.00')
        self.total_amount_kzt = total.quantize(Decimal('0.01'))
        self.save(update_fields=['subtotal_amount_kzt', 'total_amount_kzt', 'updated_at'])


class SalesOrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        SalesOrder, on_delete=models.CASCADE, related_name='items', verbose_name='Заказ'
    )
    product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT, verbose_name='Изделие'
    )
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('1.00'), verbose_name='Количество'
    )
    reserved_quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='В резерве'
    )
    shipped_quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Отгружено'
    )
    unit_price_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, verbose_name='Цена за ед. (KZT)'
    )
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name='Скидка (%)'
    )
    total_price_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='Сумма (KZT)'
    )

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self):
        return f'{self.product.name} × {self.quantity}'

    @property
    def remaining_to_ship(self) -> Decimal:
        rem = Decimal(str(self.quantity)) - Decimal(str(self.shipped_quantity))
        return rem if rem > Decimal('0') else Decimal('0.00')

    @property
    def is_fully_shipped(self) -> bool:
        return self.shipped_quantity >= self.quantity

    @property
    def remaining_to_reserve(self) -> Decimal:
        rem = Decimal(str(self.quantity)) - Decimal(str(self.reserved_quantity)) - Decimal(str(self.shipped_quantity))
        return rem if rem > Decimal('0') else Decimal('0.00')
