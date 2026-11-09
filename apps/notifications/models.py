import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


class NotificationType(models.TextChoices):
    LOW_STOCK = 'LOW_STOCK', _('Низкий остаток материала')
    ORDER_STATUS = 'ORDER_STATUS', _('Изменение статуса заказа')
    PRODUCTION = 'PRODUCTION', _('Производственное событие')
    FINANCE = 'FINANCE', _('Финансовое уведомление')
    SYSTEM = 'SYSTEM', _('Системное уведомление')


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='notifications',
        verbose_name='Пользователь'
    )
    notification_type = models.CharField(
        max_length=20, choices=NotificationType.choices, default=NotificationType.SYSTEM,
        verbose_name='Тип'
    )
    title = models.CharField(max_length=200, verbose_name='Заголовок')
    message = models.TextField(verbose_name='Сообщение')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    link = models.CharField(max_length=255, blank=True, verbose_name='Ссылка')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата')

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} → {self.user.username}'
