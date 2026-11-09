from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('', include('apps.dashboard.urls', namespace='dashboard')),
    path('warehouses/', include('apps.warehouses.urls', namespace='warehouses')),
    path('materials/', include('apps.materials.urls', namespace='materials')),
    path('products/', include('apps.products.urls', namespace='products')),
    path('production/', include('apps.production.urls', namespace='production')),
    path('quality/', include('apps.quality.urls', namespace='quality')),
    path('employees/', include('apps.employees.urls', namespace='employees')),
    path('sales/', include('apps.sales.urls', namespace='sales')),
    path('suppliers/', include('apps.suppliers.urls', namespace='suppliers')),
    path('finance/', include('apps.finance.urls', namespace='finance')),
    path('analytics/', include('apps.analytics.urls', namespace='analytics')),
    path('notifications/', include('apps.notifications.urls', namespace='notifications')),
    path('ai/', include('apps.ai_assistant.urls', namespace='ai_assistant')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
