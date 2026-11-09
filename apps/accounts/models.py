import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

class UserRole(models.TextChoices):
    OWNER = 'OWNER', _('Владелец бизнеса')
    ADMIN = 'ADMIN', _('Системный администратор')
    ACCOUNTANT = 'ACCOUNTANT', _('Главный бухгалтер')
    PRODUCTION_MANAGER = 'PRODUCTION_MANAGER', _('Начальник производства')
    WAREHOUSE_MANAGER = 'WAREHOUSE_MANAGER', _('Заведующий складом')
    SALES_MANAGER = 'SALES_MANAGER', _('Менеджер по продажам')
    WORKER = 'WORKER', _('Мастер цеха / Станочник')

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(
        max_length=30,
        choices=UserRole.choices,
        default=UserRole.WORKER,
        verbose_name='Роль в системе',
    )
    phone = models.CharField(max_length=30, blank=True, verbose_name='Телефон')
    patronymic = models.CharField(max_length=150, blank=True, verbose_name='Отчество')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['last_name', 'first_name']

    def get_full_name_ru(self) -> str:
        parts = [self.last_name, self.first_name, self.patronymic]
        full = ' '.join(p for p in parts if p)
        return full or self.username

    @property
    def is_owner(self) -> bool:
        return self.role == UserRole.OWNER or self.is_superuser

    @property
    def is_production_manager(self) -> bool:
        return self.role in [UserRole.OWNER, UserRole.ADMIN, UserRole.PRODUCTION_MANAGER]

    @property
    def is_warehouse_manager(self) -> bool:
        return self.role in [UserRole.OWNER, UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER]

    @property
    def is_accountant(self) -> bool:
        return self.role in [UserRole.OWNER, UserRole.ADMIN, UserRole.ACCOUNTANT]

    @property
    def is_sales_manager(self) -> bool:
        return self.role in [UserRole.OWNER, UserRole.ADMIN, UserRole.SALES_MANAGER]

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name='Пользователь',
    )
    action = models.CharField(max_length=100, verbose_name='Действие')
    entity_type = models.CharField(max_length=100, verbose_name='Сущность')
    entity_id = models.CharField(max_length=100, verbose_name='Идентификатор объекта')
    details = models.JSONField(default=dict, blank=True, verbose_name='Параметры и изменения')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP адрес')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Время фиксации')

    class Meta:
        verbose_name = 'Запись аудита'
        verbose_name_plural = 'Журнал аудита'
        ordering = ['-created_at']

    def __str__(self):
        user_name = self.user.username if self.user else 'Система'
        return f"{self.created_at.strftime('%Y-%m-%d %H:%M:%S')} | {user_name} | {self.action} ({self.entity_type})"
