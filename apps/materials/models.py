import uuid
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _

class MaterialCategory(models.TextChoices):
    WOOD = 'WOOD', _('Массив дерева')
    MDF = 'MDF', _('МДФ панели')
    CHIPBOARD = 'CHIPBOARD', _('ЛДСП')
    PLYWOOD = 'PLYWOOD', _('Фанера березовая')
    HARDWARE_SCREWS = 'HARDWARE_SCREWS', _('Крепеж и конфирматы')
    HARDWARE_HINGES = 'HARDWARE_HINGES', _('Петли мебельные')
    HARDWARE_HANDLES = 'HARDWARE_HANDLES', _('Ручки мебельные')
    HARDWARE_RAILS = 'HARDWARE_RAILS', _('Направляющие ящиков')
    GLUE = 'GLUE', _('Клей столярный')
    PAINT = 'PAINT', _('Краска и эмаль')
    VARNISH = 'VARNISH', _('Лак мебельный')
    FABRIC = 'FABRIC', _('Обивочный текстиль/велюр')
    FOAM = 'FOAM', _('Поролон (ППУ)')
    OTHER = 'OTHER', _('Прочие материалы')

class Material(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=50, unique=True, verbose_name='Артикул / SKU')
    barcode = models.CharField(max_length=100, blank=True, verbose_name='Штрихкод / EAN')
    name = models.CharField(max_length=200, verbose_name='Наименование сырья')
    description = models.TextField(blank=True, verbose_name='Техническое описание')
    category = models.CharField(
        max_length=50,
        choices=MaterialCategory.choices,
        default=MaterialCategory.OTHER,
        verbose_name='Категория',
    )
    unit = models.CharField(max_length=30, default='шт', verbose_name='Единица измерения')
    purchase_cost_kzt = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Учетная цена закупки (KZT)',
    )
    min_stock_level = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name='Минимальный буферный остаток',
    )
    location = models.CharField(max_length=100, blank=True, verbose_name='Ячейка на Складе №1')
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='materials',
        verbose_name='Основной поставщик',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата заведения')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата изменения')

    class Meta:
        verbose_name = 'Сырье / Материал'
        verbose_name_plural = 'Материалы и сырье'
        ordering = ['name']

    def __str__(self):
        return f'{self.sku} — {self.name}'

    @property
    def effective_barcode(self) -> str:
        return self.barcode or f"FC-MAT-{self.sku}"
