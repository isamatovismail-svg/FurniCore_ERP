import uuid
from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class WarehouseType(models.TextChoices):
    RAW_MATERIALS = 'RAW_MATERIALS', _('Склад сырья и материалов (WH-1)')
    FINISHED_PRODUCTS = 'FINISHED_PRODUCTS', _('Склад готовой продукции (WH-2)')


class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, verbose_name='Код склада (WH-1 / WH-2)')
    name = models.CharField(max_length=150, verbose_name='Наименование склада')
    warehouse_type = models.CharField(max_length=30, choices=WarehouseType.choices, verbose_name='Тип склада')
    address = models.CharField(max_length=255, blank=True, verbose_name='Адрес помещения')
    description = models.TextField(blank=True, verbose_name='Описание и назначение')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Склад'
        verbose_name_plural = 'Склады'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} — {self.name}'


class StockBalance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='balances', verbose_name='Склад')
    material = models.ForeignKey(
        'materials.Material',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='warehouse_balances',
        verbose_name='Сырьевой материал (для WH-1)',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='warehouse_balances',
        verbose_name='Готовая мебель (для WH-2)',
    )
    current_stock = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name='Текущий физический остаток',
    )
    reserved_stock = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name='Зарезервировано под клиентов',
    )
    min_stock_level = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name='Минимальный буфер',
    )
    last_counted_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата последней инвентаризации')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Остаток на складе'
        verbose_name_plural = 'Остатки на складах'
        unique_together = [('warehouse', 'material'), ('warehouse', 'product')]

    def __str__(self):
        item_name = self.material.name if self.material else (self.product.name if self.product else '—')
        return f'{self.warehouse.code} | {item_name}: {self.current_stock}'

    @property
    def available_stock(self) -> Decimal:
        return max(Decimal('0.000'), self.current_stock - self.reserved_stock)

    @property
    def is_low_stock(self) -> bool:
        return self.current_stock <= self.min_stock_level


class WarehouseDocumentType(models.TextChoices):
    RECEIPT            = 'RECEIPT',            _('Приходная накладная (WH-1)')
    PRODUCTION_ISSUE   = 'PRODUCTION_ISSUE',   _('Требование-накладная на отпуск в цех')
    PRODUCTION_RETURN  = 'PRODUCTION_RETURN',  _('Возврат материалов из производства (WH-1)')
    FINISHED_RECEIPT   = 'FINISHED_RECEIPT',   _('Приёмка готовой продукции из цеха (WH-2)')
    RESERVATION        = 'RESERVATION',        _('Резервирование под клиентский заказ (WH-2)')
    UNRESERVATION      = 'UNRESERVATION',      _('Снятие с резерва (WH-2)')
    SHIPMENT           = 'SHIPMENT',           _('Расходная накладная на отгрузку клиенту (WH-2)')
    CUSTOMER_RETURN    = 'CUSTOMER_RETURN',    _('Возврат готового изделия от клиента (WH-2)')
    INVENTORY          = 'INVENTORY',          _('Акт инвентаризации')


class DocumentStatus(models.TextChoices):
    DRAFT     = 'DRAFT',     _('Черновик')
    POSTED    = 'POSTED',    _('Проведён')
    CANCELLED = 'CANCELLED', _('Отменён')


class WarehouseDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doc_number = models.CharField(max_length=50, unique=True, verbose_name='Номер документа')
    doc_type = models.CharField(
        max_length=40, choices=WarehouseDocumentType.choices, verbose_name='Тип документа'
    )
    status = models.CharField(
        max_length=20, choices=DocumentStatus.choices, default=DocumentStatus.DRAFT, verbose_name='Статус'
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='documents', verbose_name='Склад')
    doc_date = models.DateField(default=timezone.localdate, verbose_name='Дата документа')
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_warehouse_docs', verbose_name='Автор документа'
    )
    posted_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='posted_warehouse_docs', verbose_name='Кто провёл'
    )
    posted_at = models.DateTimeField(null=True, blank=True, verbose_name='Время проведения')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Время отмены')
    supplier = models.ForeignKey(
        'suppliers.Supplier', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouse_documents', verbose_name='Поставщик сырья'
    )
    customer = models.ForeignKey(
        'sales.Customer', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouse_documents', verbose_name='Клиент'
    )
    sales_order = models.ForeignKey(
        'sales.SalesOrder', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouse_documents', verbose_name='Заказ покупателя'
    )
    production_order = models.ForeignKey(
        'production.ProductionOrder', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='warehouse_documents', verbose_name='Производственный заказ'
    )
    total_amount_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='Итоговая сумма (KZT)'
    )
    notes = models.TextField(blank=True, verbose_name='Комментарии и основание')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Складской документ'
        verbose_name_plural = 'Складские документы'
        ordering = ['-doc_date', '-created_at']

    def __str__(self):
        return f'{self.doc_number} ({self.get_doc_type_display()}) — {self.get_status_display()}'

    @property
    def is_posted(self) -> bool:
        return self.status == DocumentStatus.POSTED

    @property
    def is_draft(self) -> bool:
        return self.status == DocumentStatus.DRAFT

    @property
    def is_cancelled(self) -> bool:
        return self.status == DocumentStatus.CANCELLED


class WarehouseDocumentItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        WarehouseDocument, on_delete=models.CASCADE, related_name='items', verbose_name='Документ'
    )
    material = models.ForeignKey(
        'materials.Material', on_delete=models.PROTECT, null=True, blank=True, verbose_name='Материал'
    )
    product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT, null=True, blank=True, verbose_name='Изделие'
    )
    quantity = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal('1.000'), verbose_name='Количество'
    )
    unit = models.CharField(max_length=30, default='шт', verbose_name='Единица')
    unit_cost_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='Цена за ед. (KZT)'
    )
    total_cost_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='Сумма (KZT)'
    )
    # Поля для инвентаризации:
    actual_quantity = models.DecimalField(
        max_digits=14, decimal_places=3, null=True, blank=True, verbose_name='Фактическое количество'
    )
    discrepancy_quantity = models.DecimalField(
        max_digits=14, decimal_places=3, null=True, blank=True, verbose_name='Расхождение (Факт - Учёт)'
    )
    notes = models.CharField(max_length=255, blank=True, verbose_name='Примечание к позиции')

    class Meta:
        verbose_name = 'Строка складского документа'
        verbose_name_plural = 'Строки складских документов'

    def __str__(self):
        item_title = self.material.name if self.material else (self.product.name if self.product else '—')
        return f'{self.document.doc_number}: {item_title} × {self.quantity} {self.unit}'


class MovementType(models.TextChoices):
    RECEIPT           = 'RECEIPT',           _('Поступление на склад')
    ISSUE             = 'ISSUE',             _('Отпуск сырья в цех')
    PRODUCTION_RETURN = 'PRODUCTION_RETURN', _('Возврат из производства')
    FINISHED_RECEIPT  = 'FINISHED_RECEIPT',  _('Приёмка готовой продукции')
    TRANSFER          = 'TRANSFER',          _('Внутрискладское перемещение')
    ADJUSTMENT        = 'ADJUSTMENT',        _('Акт инвентаризации / корректировка')
    RESERVATION       = 'RESERVATION',       _('Резервирование под клиентский заказ')
    UNRESERVATION     = 'UNRESERVATION',     _('Снятие с резерва')
    SHIPMENT          = 'SHIPMENT',          _('Отгрузка клиенту')
    CUSTOMER_RETURN   = 'CUSTOMER_RETURN',   _('Возврат от клиента')


class StockMovement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    movement_number = models.CharField(max_length=50, unique=True, verbose_name='Номер документа (MOV-...)')
    movement_type = models.CharField(max_length=30, choices=MovementType.choices, verbose_name='Тип движения')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='movements', verbose_name='Склад')
    document = models.ForeignKey(
        WarehouseDocument, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='movements', verbose_name='Первичный складской документ'
    )
    material = models.ForeignKey('materials.Material', on_delete=models.PROTECT, null=True, blank=True, verbose_name='Материал')
    product = models.ForeignKey('products.Product', on_delete=models.PROTECT, null=True, blank=True, verbose_name='Изделие')
    quantity = models.DecimalField(max_digits=14, decimal_places=3, verbose_name='Количество')
    unit = models.CharField(max_length=30, default='шт', verbose_name='Единица')
    unit_cost_kzt = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='Учетная цена за ед. (KZT)')
    total_cost_kzt = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='Сумма операции (KZT)')
    reference_number = models.CharField(max_length=100, blank=True, verbose_name='Накладная / Основание')
    notes = models.TextField(blank=True, verbose_name='Комментарий')
    performed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Исполнитель',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата проводки')

    class Meta:
        verbose_name = 'Складское движение'
        verbose_name_plural = 'Журнал складских движений'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.movement_number} ({self.get_movement_type_display()})'
