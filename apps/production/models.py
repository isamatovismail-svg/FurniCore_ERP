import uuid
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _


class ProductionOrderStatus(models.TextChoices):
    DRAFT               = 'DRAFT',               _('Черновик')
    WAITING             = 'WAITING',             _('Ожидает запуска')
    CHECKING_MATERIALS  = 'CHECKING_MATERIALS',  _('Проверка материалов')
    MATERIALS_RESERVED  = 'MATERIALS_RESERVED',  _('Материалы выданы в цех')
    IN_PROGRESS         = 'IN_PROGRESS',         _('В производстве')
    QC_CHECK            = 'QC_CHECK',            _('На контроле качества (ОТК)')
    REWORK              = 'REWORK',              _('На доработке')
    READY               = 'READY',               _('Готов к передаче на склад')
    COMPLETED           = 'COMPLETED',           _('Завершён (принят на WH-2)')
    CANCELLED           = 'CANCELLED',           _('Отменён')


class OrderPriority(models.TextChoices):
    LOW    = 'LOW',    _('Низкий')
    NORMAL = 'NORMAL', _('Обычный')
    HIGH   = 'HIGH',   _('Высокий')
    URGENT = 'URGENT', _('Срочный / VIP')


class StageStatus(models.TextChoices):
    PENDING     = 'PENDING',     _('Ожидает')
    IN_PROGRESS = 'IN_PROGRESS', _('В работе')
    DONE        = 'DONE',        _('Выполнен')
    REWORK      = 'REWORK',      _('На исправлении')
    SKIPPED     = 'SKIPPED',     _('Пропущен')


class RoutingTemplate(models.Model):
    """Шаблон технологического маршрута для категории мебели."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, verbose_name='Название маршрута')
    category = models.CharField(
        max_length=50,
        choices=[
            ('WARDROBE', 'Шкафы'),
            ('TABLE', 'Столы'),
            ('BED', 'Кровати'),
            ('KITCHEN', 'Кухни'),
            ('SOFA', 'Диваны'),
            ('OTHER', 'Прочая мебель'),
        ],
        default='WARDROBE',
        verbose_name='Категория мебели'
    )
    description = models.TextField(blank=True, verbose_name='Описание операций')
    is_default = models.BooleanField(default=True, verbose_name='По умолчанию для категории')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Технологический маршрут'
        verbose_name_plural = 'Технологические маршруты'
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_category_display()})'


class RoutingStage(models.Model):
    """Шаг в шаблоне маршрута."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(RoutingTemplate, on_delete=models.CASCADE, related_name='stages', verbose_name='Маршрут')
    sequence = models.PositiveSmallIntegerField(default=1, verbose_name='Порядок операции')
    name = models.CharField(max_length=120, verbose_name='Название участка / операции')
    workstation = models.CharField(max_length=100, blank=True, verbose_name='Участок / Станок')
    standard_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('2.00'), verbose_name='Нормо-часы')

    class Meta:
        verbose_name = 'Шаг маршрута'
        verbose_name_plural = 'Шаги маршрута'
        ordering = ['template', 'sequence']

    def __str__(self):
        return f'{self.sequence}. {self.name} ({self.standard_hours} ч)'


class BOM(models.Model):
    """Bill of Materials — Технологическая карта (ТК) изделия с версионированием."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='boms',
        verbose_name='Изделие',
    )
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='boms',
        verbose_name='Модификация (опционально)'
    )
    name = models.CharField(max_length=200, verbose_name='Название ТК')
    version = models.CharField(max_length=20, default='1.0', verbose_name='Версия карты')
    is_active = models.BooleanField(default=True, verbose_name='Активна для запусков')
    routing_template = models.ForeignKey(
        RoutingTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='boms',
        verbose_name='Технологический маршрут'
    )
    standard_labor_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('8.00'), verbose_name='Нормативное время изготовления (ч)'
    )
    labor_rate_hourly_kzt = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('2500.00'), verbose_name='Ставка оплаты мастера (KZT/ч)'
    )
    overhead_rate_kzt = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('5000.00'), verbose_name='Накладные расходы на единицу (KZT)'
    )
    description = models.TextField(blank=True, verbose_name='Технические указания и требования')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Технологическая карта (BOM)'
        verbose_name_plural = 'Технологические карты (BOM)'
        unique_together = [('product', 'version')]
        ordering = ['product', '-version']

    def __str__(self):
        return f'ТК {self.name} v{self.version} — {self.product.name}'

    @property
    def total_materials_cost_kzt(self) -> Decimal:
        """Расчёт нормативной стоимости материалов на 1 ед. изделия."""
        return sum(
            (item.planned_cost_kzt for item in self.items.select_related('material').all()),
            Decimal('0.00')
        )

    @property
    def materials_cost_kzt(self) -> Decimal:
        return self.total_materials_cost_kzt

    @property
    def labor_cost_kzt(self) -> Decimal:
        return (self.standard_labor_hours * self.labor_rate_hourly_kzt).quantize(Decimal('0.01'))

    @property
    def total_planned_cost_kzt(self) -> Decimal:
        return self.planned_unit_cost_kzt

    @property
    def planned_unit_cost_kzt(self) -> Decimal:
        """Нормативная себестоимость 1 изделия (материалы + труд + накладные)."""
        labor = (self.standard_labor_hours * self.labor_rate_hourly_kzt).quantize(Decimal('0.01'))
        return self.total_materials_cost_kzt + labor + self.overhead_rate_kzt


class BOMItem(models.Model):
    """Строка технологической карты — потребность в материале или фурнитуре."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name='items', verbose_name='ТК')
    material = models.ForeignKey(
        'materials.Material',
        on_delete=models.PROTECT,
        verbose_name='Материал / Фурнитура',
    )
    quantity_planned = models.DecimalField(
        max_digits=14, decimal_places=3, verbose_name='Норма расхода на 1 шт'
    )
    unit = models.CharField(max_length=30, default='шт', verbose_name='Единица')
    waste_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('5.00'),
        verbose_name='Нормативный процент отходов (%)',
    )
    notes = models.CharField(max_length=200, blank=True, verbose_name='Примечание / Участок применения')

    class Meta:
        verbose_name = 'Строка технологической карты'
        verbose_name_plural = 'Строки технологических карт'

    def __str__(self):
        return f'{self.material.name} × {self.quantity_planned} {self.unit}'

    @property
    def quantity_with_waste(self) -> Decimal:
        multiplier = Decimal('1.00') + (self.waste_percent / Decimal('100.00'))
        return (self.quantity_planned * multiplier).quantize(Decimal('0.001'))

    @property
    def planned_cost_kzt(self) -> Decimal:
        cost = self.material.purchase_cost_kzt if self.material else Decimal('0.00')
        return (self.quantity_with_waste * cost).quantize(Decimal('0.01'))


class ProductionOrder(models.Model):
    """Производственный заказ на изготовление партии мебели."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=30, unique=True, verbose_name='Номер заказа (PO-...)')
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='production_orders',
        verbose_name='Изделие',
    )
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Модификация'
    )
    bom = models.ForeignKey(
        BOM, on_delete=models.PROTECT, null=True, blank=True,
        related_name='production_orders',
        verbose_name='Зафиксированная технологическая карта (BOM)'
    )
    quantity_planned = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('1.00'), verbose_name='План выпуска (шт)'
    )
    quantity_produced = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Фактически принято ОТК (шт)'
    )
    status = models.CharField(
        max_length=30,
        choices=ProductionOrderStatus.choices,
        default=ProductionOrderStatus.DRAFT,
        verbose_name='Статус производства',
    )
    priority = models.CharField(
        max_length=20,
        choices=OrderPriority.choices,
        default=OrderPriority.NORMAL,
        verbose_name='Приоритет исполнения',
    )
    planned_start = models.DateField(null=True, blank=True, verbose_name='Плановый запуск')
    planned_end = models.DateField(null=True, blank=True, verbose_name='Плановое окончание')
    actual_start = models.DateField(null=True, blank=True, verbose_name='Фактический старт')
    actual_end = models.DateField(null=True, blank=True, verbose_name='Фактическое завершение')

    # Финансовые показатели себестоимости
    planned_materials_cost_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='План: Материалы (KZT)'
    )
    planned_labor_cost_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='План: ФОТ цеха (KZT)'
    )
    overhead_cost_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='План: Накладные цеха (KZT)'
    )
    planned_cost_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='Плановая себестоимость (KZT)'
    )

    actual_materials_cost_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='Факт: Материалы (KZT)'
    )
    actual_labor_cost_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='Факт: ФОТ цеха (KZT)'
    )
    actual_cost_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='Итоговая фактическая себестоимость (KZT)'
    )

    sales_order = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='production_orders',
        verbose_name='Заказ покупателя',
    )
    assigned_master = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='supervised_orders',
        verbose_name='Ответственный мастер смены'
    )
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='production_orders_created', verbose_name='Создал заказ'
    )
    notes = models.TextField(blank=True, verbose_name='Технические примечания')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Производственный заказ'
        verbose_name_plural = 'Производственные заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order_number} — {self.product.name} ({self.quantity_planned} шт)'

    @property
    def total_planned_cost_kzt(self) -> Decimal:
        return self.planned_cost_kzt

    @property
    def total_actual_cost_kzt(self) -> Decimal:
        return self.actual_cost_kzt

    @property
    def unit_planned_cost_kzt(self) -> Decimal:
        if self.quantity_planned > Decimal('0'):
            return (self.planned_cost_kzt / self.quantity_planned).quantize(Decimal('0.01'))
        return Decimal('0.00')

    @property
    def unit_actual_cost_kzt(self) -> Decimal:
        qty = self.quantity_produced if self.quantity_produced > Decimal('0') else self.quantity_planned
        if qty > Decimal('0'):
            return (self.actual_cost_kzt / qty).quantize(Decimal('0.01'))
        return Decimal('0.00')

    @property
    def cost_variance_kzt(self) -> Decimal:
        """Отклонение факта от плана (положительное = перерасход)."""
        return self.actual_cost_kzt - self.planned_cost_kzt

    @property
    def progress_percent(self) -> int:
        stages = list(self.stages.all())
        if not stages:
            if self.status == ProductionOrderStatus.COMPLETED:
                return 100
            return 0
        done_count = sum(1 for s in stages if s.status == StageStatus.DONE)
        return int(round((done_count / len(stages)) * 100))

    @property
    def is_materials_issued(self) -> bool:
        return self.status in [
            ProductionOrderStatus.MATERIALS_RESERVED,
            ProductionOrderStatus.IN_PROGRESS,
            ProductionOrderStatus.QC_CHECK,
            ProductionOrderStatus.REWORK,
            ProductionOrderStatus.READY,
            ProductionOrderStatus.COMPLETED,
        ]


class ProductionStage(models.Model):
    """Этап производственного маршрута конкретного заказа."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production_order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE, related_name='stages', verbose_name='Производственный заказ'
    )
    stage_name = models.CharField(max_length=120, verbose_name='Название этапа / операции')
    sequence = models.PositiveSmallIntegerField(default=1, verbose_name='Порядок')
    status = models.CharField(
        max_length=20, choices=StageStatus.choices, default=StageStatus.PENDING, verbose_name='Статус этапа'
    )
    assigned_employee = models.ForeignKey(
        'employees.Employee', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='production_tasks',
        verbose_name='Исполнитель'
    )
    workstation = models.CharField(max_length=100, blank=True, verbose_name='Участок / Оборудование')
    planned_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0.00'), verbose_name='Норматив (ч)'
    )
    actual_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0.00'), verbose_name='Фактически отработано (ч)'
    )
    quantity_processed = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Обработано деталей/изделий'
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Начало этапа')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='Завершение этапа')
    notes = models.TextField(blank=True, verbose_name='Отметка мастера')

    class Meta:
        verbose_name = 'Этап производства'
        verbose_name_plural = 'Этапы производства'
        ordering = ['production_order', 'sequence']

    def __str__(self):
        return f'{self.production_order.order_number} — Этап {self.sequence}: {self.stage_name}'


class MaterialConsumption(models.Model):
    """Спецификация фактического расхода материалов на производственный заказ."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production_order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE, related_name='material_consumptions',
        verbose_name='Производственный заказ'
    )
    material = models.ForeignKey(
        'materials.Material', on_delete=models.PROTECT, verbose_name='Материал'
    )
    quantity_planned = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal('0.000'), verbose_name='Норма расхода (план)'
    )
    quantity_actual = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal('0.000'), verbose_name='Фактически выдано/списано'
    )
    unit = models.CharField(max_length=30, default='шт', verbose_name='Единица')
    unit_cost_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='Цена за единицу (KZT)'
    )
    cost_kzt = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='Итоговая стоимость (KZT)'
    )

    class Meta:
        verbose_name = 'Строка списания материалов'
        verbose_name_plural = 'Журнал расхода материалов'

    def __str__(self):
        return f'{self.material.name} (план {self.quantity_planned} / факт {self.quantity_actual} {self.unit})'


class WasteType(models.TextChoices):
    TECHNOLOGICAL_WASTE = 'TECHNOLOGICAL_WASTE', _('Технологические отходы (стружка, обрезки)')
    REWORKABLE_DEFECT   = 'REWORKABLE_DEFECT',   _('Исправимый брак (доработка)')
    IRREPARABLE_DEFECT  = 'IRREPARABLE_DEFECT',  _('Неисправимый брак (списание)')


class ProductionWaste(models.Model):
    """Регистрация отходов, брака и дефектов в производстве."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production_order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE, related_name='wastes',
        verbose_name='Производственный заказ'
    )
    waste_type = models.CharField(
        max_length=30, choices=WasteType.choices, default=WasteType.TECHNOLOGICAL_WASTE,
        verbose_name='Тип отхода / брака'
    )
    stage = models.ForeignKey(
        ProductionStage, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reported_wastes',
        verbose_name='Производственный участок'
    )
    material = models.ForeignKey(
        'materials.Material', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Повреждённый / израсходованный материал'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='Количество')
    unit = models.CharField(max_length=30, default='шт', verbose_name='Единица')
    cost_kzt = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'), verbose_name='Стоимость ущерба (KZT)'
    )
    reason = models.CharField(max_length=255, verbose_name='Причина дефекта / отхода')
    decision = models.TextField(blank=True, verbose_name='Принятое решение (доработка / утилизация)')
    reported_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Кто зафиксировал'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Время фиксации')

    class Meta:
        verbose_name = 'Запись об отходах и браке'
        verbose_name_plural = 'Журнал отходов и брака'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.production_order.order_number} — {self.get_waste_type_display()} ({self.quantity} {self.unit})'
