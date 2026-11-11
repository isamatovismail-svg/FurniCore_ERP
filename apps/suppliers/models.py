import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Supplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name='Наименование компании')
    contact_person = models.CharField(max_length=150, blank=True, verbose_name='Контактное лицо')
    phone = models.CharField(max_length=50, blank=True, verbose_name='Телефон')
    email = models.EmailField(blank=True, verbose_name='Email')
    address = models.CharField(max_length=255, blank=True, verbose_name='Адрес склада / офиса')
    notes = models.TextField(blank=True, verbose_name='Примечания')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Поставщик'
        verbose_name_plural = 'Поставщики'
        ordering = ['name']

    def __str__(self):
        return self.name


class PurchaseOrderStatus(models.TextChoices):
    DRAFT = 'DRAFT', _('Черновик')
    SENT = 'SENT', _('Отправлен поставщику')
    PARTIALLY_RECEIVED = 'PARTIALLY_RECEIVED', _('Частично получен')
    RECEIVED = 'RECEIVED', _('Получен полностью')
    CANCELLED = 'CANCELLED', _('Отменён')


class PurchaseOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=50, unique=True, verbose_name='Номер заказа')
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='purchase_orders',
        verbose_name='Поставщик',
    )
    status = models.CharField(
        max_length=30,
        choices=PurchaseOrderStatus.choices,
        default=PurchaseOrderStatus.DRAFT,
        verbose_name='Статус',
    )
    order_date = models.DateField(default=timezone.localdate, verbose_name='Дата заказа')
    planned_delivery_date = models.DateField(null=True, blank=True, verbose_name='Плановая дата поставки')
    total_amount_kzt = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Итоговая сумма (KZT)',
    )
    notes = models.TextField(blank=True, verbose_name='Комментарии и условия поставки')
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_purchase_orders',
        verbose_name='Создал заказ',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлен')

    class Meta:
        verbose_name = 'Заказ поставщику'
        verbose_name_plural = 'Заказы поставщикам'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order_number} — {self.supplier.name} ({self.get_status_display()})'

    @property
    def can_edit(self) -> bool:
        return self.status == PurchaseOrderStatus.DRAFT

    @property
    def can_send(self) -> bool:
        return self.status == PurchaseOrderStatus.DRAFT

    @property
    def can_receive(self) -> bool:
        return self.status in [PurchaseOrderStatus.SENT, PurchaseOrderStatus.PARTIALLY_RECEIVED]

    @property
    def can_cancel(self) -> bool:
        return self.status in [PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.SENT]

    @property
    def items_count(self) -> int:
        return self.items.count()

    def update_totals_and_status(self):
        """Пересчитывает общую сумму и обновляет статус заказа на основе принятых позиций."""
        total = Decimal('0.00')
        all_fully_received = True
        any_received = False
        items = list(self.items.all())

        if not items:
            return

        for it in items:
            it.total_price_kzt = Decimal(str(it.quantity)) * Decimal(str(it.unit_price_kzt))
            it.save(update_fields=['total_price_kzt'])
            total += it.total_price_kzt

            if it.received_quantity > Decimal('0'):
                any_received = True
            if it.received_quantity < it.quantity:
                all_fully_received = False

        self.total_amount_kzt = total

        if self.status != PurchaseOrderStatus.CANCELLED and self.status != PurchaseOrderStatus.DRAFT:
            if all_fully_received:
                self.status = PurchaseOrderStatus.RECEIVED
            elif any_received:
                self.status = PurchaseOrderStatus.PARTIALLY_RECEIVED
            else:
                self.status = PurchaseOrderStatus.SENT

        self.save(update_fields=['total_amount_kzt', 'status', 'updated_at'])


class PurchaseOrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Заказ на закупку',
    )
    material = models.ForeignKey(
        'materials.Material',
        on_delete=models.PROTECT,
        related_name='purchase_order_items',
        verbose_name='Материал',
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        verbose_name='Заказанное количество',
    )
    received_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name='Полученное количество',
    )
    unit_price_kzt = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        verbose_name='Закупочная цена (KZT)',
    )
    total_price_kzt = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Сумма (KZT)',
    )
    notes = models.CharField(max_length=255, blank=True, verbose_name='Примечание')

    class Meta:
        verbose_name = 'Позиция заказа поставщику'
        verbose_name_plural = 'Позиции заказа поставщику'

    def __str__(self):
        return f'{self.material.name} × {self.quantity} ({self.received_quantity} получено)'

    @property
    def remaining_quantity(self) -> Decimal:
        rem = Decimal(str(self.quantity)) - Decimal(str(self.received_quantity))
        return rem if rem > Decimal('0') else Decimal('0.000')

    @property
    def is_fully_received(self) -> bool:
        return self.received_quantity >= self.quantity
