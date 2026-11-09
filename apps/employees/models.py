import uuid
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _


class Department(models.TextChoices):
    PRODUCTION = 'PRODUCTION', _('Производственный цех')
    WAREHOUSE = 'WAREHOUSE', _('Складской отдел')
    SALES = 'SALES', _('Отдел продаж')
    ACCOUNTING = 'ACCOUNTING', _('Бухгалтерия')
    MANAGEMENT = 'MANAGEMENT', _('Руководство')
    OTHER = 'OTHER', _('Прочее')


class EmployeeStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', _('Работает')
    ON_LEAVE = 'ON_LEAVE', _('В отпуске')
    SICK = 'SICK', _('На больничном')
    DISMISSED = 'DISMISSED', _('Уволен')


class Employee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee_profile',
        verbose_name='Учётная запись',
    )
    employee_number = models.CharField(max_length=20, unique=True, verbose_name='Табельный номер')
    last_name = models.CharField(max_length=150, verbose_name='Фамилия')
    first_name = models.CharField(max_length=150, verbose_name='Имя')
    patronymic = models.CharField(max_length=150, blank=True, verbose_name='Отчество')
    department = models.CharField(
        max_length=30,
        choices=Department.choices,
        default=Department.PRODUCTION,
        verbose_name='Отдел',
    )
    position = models.CharField(max_length=150, verbose_name='Должность')
    status = models.CharField(
        max_length=20,
        choices=EmployeeStatus.choices,
        default=EmployeeStatus.ACTIVE,
        verbose_name='Статус',
    )
    hire_date = models.DateField(verbose_name='Дата приёма на работу')
    salary_kzt = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Оклад (KZT)',
    )
    phone = models.CharField(max_length=30, blank=True, verbose_name='Телефон')
    notes = models.TextField(blank=True, verbose_name='Примечания')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.employee_number} — {self.last_name} {self.first_name}'

    def get_full_name(self):
        parts = [self.last_name, self.first_name, self.patronymic]
        return ' '.join(p for p in parts if p)
