from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.index, name='index'),
    path('create/', views.product_create, name='create'),
    path('<uuid:pk>/', views.detail, name='detail'),
    path('<uuid:pk>/edit/', views.product_edit, name='edit'),
    path('<uuid:pk>/archive/', views.product_archive, name='archive'),
]
