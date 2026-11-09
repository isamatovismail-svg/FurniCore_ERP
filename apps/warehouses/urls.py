from django.urls import path
from . import views

app_name = 'warehouses'

urlpatterns = [
    path('', views.index, name='index'),
    path('wh-1/', views.wh1_view, name='wh1'),
    path('wh-2/', views.wh2_view, name='wh2'),

    # Документы складского учета
    path('documents/', views.document_list, name='document_list'),
    path('documents/create/', views.document_create, name='document_create'),
    path('documents/<uuid:pk>/', views.document_detail, name='document_detail'),
    path('documents/<uuid:pk>/post/', views.document_post, name='document_post'),
    path('documents/<uuid:pk>/cancel/', views.document_cancel, name='document_cancel'),
    path('documents/<uuid:pk>/pdf/', views.document_pdf, name='document_pdf'),

    # Инвентаризация
    path('inventory/', views.inventory_list, name='inventory_list'),
    path('inventory/create/', views.inventory_create, name='inventory_create'),
    path('inventory/<uuid:pk>/', views.inventory_detail, name='inventory_detail'),

    # QR, штрихкоды и печать термоэтикеток
    path('qr/<str:sku>/', views.qr_image_view, name='qr_image'),
    path('label/<str:item_type>/<uuid:item_id>/', views.item_label_pdf_view, name='item_label_pdf'),

    # Терминал сканирования
    path('scan/', views.scanner_view, name='scanner'),
    path('scan/lookup/', views.scanner_lookup, name='scanner_lookup'),
]
