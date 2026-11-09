import uuid
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _


class ExpenseCategory(models.TextChoices):
    MATERIALS  = 'MATERIALS',   _('Закупка сырья и комплектующих')
    ELECTRICITY= 'ELECTRICITY', _('Электроэнергия')
    GAS        = 'GAS',         _('Отопление и газ')
    WATER      = 'WATER',       _('Водоснабжение')
    RENT       = 'RENT',        _('Аренда помещений')
    PAYROLL    = 'PAYROLL',     _('Фонд оплаты труда')
    TRANSPORT  = 'TRANSPORT',   _('Транспорт и логистика')
    REPAIRS    = 'REPAIRS',     _('Техобслуживание оборудования')
    EQUIPMENT  = 'EQUIPMENT',   _('Инструмент и оснастка')
    MARKETING  = 'MARKETING',   _('Реклама и маркетинг')
    OTHER      = 'OTHER',       _('Прочее')


class Expense(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(
        max_length=50,
        choices=ExpenseCategory.choices,
        verbose_name='Статья расходов',
    )
    amount_kzt = models.DecimalField(
        max_digits=16, decimal_places=2,
        verbose_name='Сумма расхода (KZT)',
    )
    payment_date = models.DateField(verbose_name='Дата платежа')
    description = models.CharField(max_length=255, verbose_name='Назначение платежа')
    payee = models.CharField(max_length=200, blank=True, verbose_name='Получатель / Контрагент')
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

    def __str__(self):
        return f'{self.get_category_display()}: {self.amount_kzt} ₸ ({self.payment_date})'
