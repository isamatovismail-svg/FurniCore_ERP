import uuid
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _


class QCResult(models.TextChoices):
    PASS   = 'PASS',   _('Принято (ОТК пройден)')
    FAIL   = 'FAIL',   _('Отклонено (Брак)')
    REWORK = 'REWORK', _('Отправлено на доработку')


class QualityCheck(models.Model):
    """Акт проверки качества готовой мебели перед приёмкой на WH-2."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production_order = models.ForeignKey(
        'production.ProductionOrder',
        on_delete=models.CASCADE,
        related_name='quality_checks',
        verbose_name='Производственный заказ',
    )
    checked_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Инспектор ОТК'
    )
    result = models.CharField(
        max_length=15, choices=QCResult.choices, default=QCResult.PASS, verbose_name='Заключение ОТК'
    )
    quantity_checked = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('1.00'), verbose_name='Проверено (шт)'
    )
    quantity_accepted = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Принято годно (шт)'
    )
    quantity_defective = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Выявлен брак (шт)'
    )

    # 7 обязательных чек-листов контроля качества
    check_dimensions = models.BooleanField(default=True, verbose_name='1. Соответствие габаритным размерам и чертежам')
    check_assembly = models.BooleanField(default=True, verbose_name='2. Качество сборки, соосность и жесткость каркаса')
    check_appearance = models.BooleanField(default=True, verbose_name='3. Внешний вид, совпадение текстур и цвета')
    check_coating = models.BooleanField(default=True, verbose_name='4. Качество покрытия, кромления и окраски/лакировки')
    check_completeness = models.BooleanField(default=True, verbose_name='5. Комплектность крепежа, ручек и полок')
    check_mechanisms = models.BooleanField(default=True, verbose_name='6. Плавность работы петель, доводчиков и направляющих')
    check_damage_free = models.BooleanField(default=True, verbose_name='7. Отсутствие сколов, царапин и пятен клея')

    defect_description = models.TextField(blank=True, verbose_name='Описание дефектов / замечания ОТК')
    rework_instructions = models.TextField(blank=True, verbose_name='Предписания по доработке для цеха')
    checked_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время контроля')
    notes = models.TextField(blank=True, verbose_name='Примечания')

    class Meta:
        verbose_name = 'Акт контроля качества (ОТК)'
        verbose_name_plural = 'Журнал контроля качества (ОТК)'
        ordering = ['-checked_at']

    def __str__(self):
        return f'ОТК {self.production_order.order_number} — {self.get_result_display()}'

    @property
    def is_passed(self) -> bool:
        return self.result == QCResult.PASS
