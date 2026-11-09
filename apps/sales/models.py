import uuid
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _


class OrderStatus(models.TextChoices):
    NEW          = 'NEW',          _('Новый')
    CONFIRMED    = 'CONFIRMED',    _('Подтверждён')
    IN_PRODUCTION= 'IN_PRODUCTION',_('В производстве')
    READY        = 'READY',        _('Готов к отгрузке')
    SHIPPED      = 'SHIPPED',      _('Отгружен')
    DELIVERED    = 'DELIVERED',    _('Доставлен')
    CANCELLED    = 'CANCELLED',    _('Отменён')


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=200, verbose_name='ФИО / Наименование')
    company_name = models.CharField(max_length=200, blank=True, verbose_name='Юридическое лицо')
    phone = models.CharField(max_length=50, blank=True, verbose_name='Телефон')
    email = models.EmailField(blank=True, verbose_name='Email')
    city = models.CharField(max_length=100, blank=True, verbose_name='Город')
    address = models.CharField(max_length=255, blank=True, verbose_name='Адрес доставки')
    notes = models.TextField(blank=True, verbose_name='Примечания')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ['full_name']

    def __str__(self):
        return self.company_name or self.full_name


class SalesOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True, verbose_name='Номер заказа')
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name='orders', verbose_name='Клиент'
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.NEW,
        verbose_name='Статус',
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
    unit_price_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, verbose_name='Цена за ед. (KZT)'
    )
    total_price_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, verbose_name='Сумма (KZT)'
    )

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self):
        return f'{self.product.name} × {self.quantity}'
