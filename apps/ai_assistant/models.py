import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


class ChatSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='chat_sessions',
        verbose_name='Пользователь'
    )
    title = models.CharField(max_length=200, default='Новый сеанс', verbose_name='Тема сеанса')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Сеанс AI-ассистента'
        verbose_name_plural = 'Сеансы AI-ассистента'
        ordering = ['-updated_at']

    def __str__(self):
        return f'Сеанс {self.id} — {self.user.username}'


class ChatMessage(models.Model):
    ROLE_USER = 'user'
    ROLE_ASSISTANT = 'assistant'
    ROLE_CHOICES = [
        (ROLE_USER, _('Пользователь')),
        (ROLE_ASSISTANT, _('Ассистент')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ChatSession, on_delete=models.CASCADE, related_name='messages', verbose_name='Сеанс'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='Роль')
    content = models.TextField(verbose_name='Текст сообщения')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Сообщение AI-чата'
        verbose_name_plural = 'Сообщения AI-чата'
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.role}] {self.content[:60]}'
