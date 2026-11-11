from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    # Заказы покупателей
    path('', views.index, name='index'),
    path('create/', views.order_create, name='order_create'),
    path('<uuid:pk>/', views.order_detail, name='order_detail'),
    path('<uuid:pk>/reserve/', views.order_reserve, name='order_reserve'),
    path('<uuid:pk>/create-production/', views.order_create_production, name='order_create_production'),
    path('<uuid:pk>/ship/', views.order_ship, name='order_ship'),
    path('<uuid:pk>/cancel/', views.order_cancel, name='order_cancel'),
    path('<uuid:pk>/pdf/', views.order_pdf, name='order_pdf'),

    # Клиенты (CRM)
    path('customers/', views.customers_list, name='customers'),
    path('customers/create/', views.customer_create, name='customer_create'),
    path('customers/<uuid:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('customers/<uuid:pk>/archive/', views.customer_archive, name='customer_archive'),
]
