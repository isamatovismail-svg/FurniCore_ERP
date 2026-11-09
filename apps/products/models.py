import uuid
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _

class ProductCategory(models.TextChoices):
    WARDROBE = 'WARDROBE', _('Шкафы')
    TABLE = 'TABLE', _('Столы')
    BED = 'BED', _('Кровати')
    KITCHEN = 'KITCHEN', _('Кухни')
    SOFA = 'SOFA', _('Диваны')
    OTHER = 'OTHER', _('Прочая мебель')

class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=50, unique=True, verbose_name='Артикул изделия')
    barcode = models.CharField(max_length=100, blank=True, verbose_name='Штрихкод / EAN')
    name = models.CharField(max_length=200, verbose_name='Наименование модели')
    category = models.CharField(
        max_length=50,
        choices=ProductCategory.choices,
        default=ProductCategory.WARDROBE,
        verbose_name='Категория мебели',
    )
    dimensions = models.CharField(max_length=100, blank=True, verbose_name='Габариты (ДxШxВ)')
    description = models.TextField(blank=True, verbose_name='Техническое описание')
    production_cost_kzt = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Себестоимость изготовления (KZT)',
    )
    sale_price_kzt = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Розничная цена (KZT)',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активно в каталоге')
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name='Фото')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата заведения')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Мебельное изделие'
        verbose_name_plural = 'Каталог изделий'
        ordering = ['name']

    def __str__(self):
        return f'{self.sku} — {self.name}'

    @property
    def margin_kzt(self) -> Decimal:
        return self.sale_price_kzt - self.production_cost_kzt

    @property
    def margin_percent(self) -> float:
        if self.production_cost_kzt > Decimal('0'):
            return round(float(self.margin_kzt / self.production_cost_kzt) * 100, 1)
        return 0.0

    @property
    def effective_barcode(self) -> str:
        return self.barcode or f"FC-PRD-{self.sku}"


class ProductVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants', verbose_name='Базовое изделие')
    sku = models.CharField(max_length=60, unique=True, verbose_name='Артикул модификации')
    name = models.CharField(max_length=150, verbose_name='Наименование модификации')
    color = models.CharField(max_length=100, blank=True, verbose_name='Цвет / Текстура')
    dimensions = models.CharField(max_length=100, blank=True, verbose_name='Размеры модификации')
    extra_price_kzt = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), verbose_name='Надбавка к цене (KZT)')

    class Meta:
        verbose_name = 'Модификация изделия'
        verbose_name_plural = 'Модификации изделий'

    def __str__(self):
        return f'{self.product.name} ({self.name})'
