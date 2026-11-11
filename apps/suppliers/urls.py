from django.urls import path
from . import views

app_name = 'suppliers'

urlpatterns = [
    # Каталог поставщиков
    path('', views.index, name='index'),
    path('create/', views.supplier_create, name='supplier_create'),
    path('<uuid:pk>/edit/', views.supplier_edit, name='supplier_edit'),
    path('<uuid:pk>/archive/', views.supplier_archive, name='supplier_archive'),

    # Заказы поставщикам
    path('orders/', views.order_list, name='order_list'),
    path('orders/create/', views.order_create, name='order_create'),
    path('orders/<uuid:pk>/', views.order_detail, name='order_detail'),
    path('orders/<uuid:pk>/send/', views.order_send, name='order_send'),
    path('orders/<uuid:pk>/receive/', views.order_receive, name='order_receive'),
    path('orders/<uuid:pk>/cancel/', views.order_cancel, name='order_cancel'),
    path('orders/<uuid:pk>/pdf/', views.order_pdf, name='order_pdf'),
]
