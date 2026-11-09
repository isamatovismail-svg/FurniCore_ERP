from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, AuditLog

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'get_full_name_ru', 'role', 'phone', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Служебные данные FurniCore', {'fields': ('role', 'phone', 'patronymic')}),
    )

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'entity_type', 'entity_id', 'ip_address')
    list_filter = ('action', 'entity_type', 'created_at')
    search_fields = ('entity_id', 'action', 'user__username')
    readonly_fields = ('created_at',)
