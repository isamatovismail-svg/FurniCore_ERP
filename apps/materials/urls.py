from django.urls import path
from . import views

app_name = 'materials'

urlpatterns = [
    path('', views.index, name='index'),
    path('create/', views.material_create, name='create'),
    path('<uuid:pk>/edit/', views.material_edit, name='edit'),
    path('<uuid:pk>/archive/', views.material_archive, name='archive'),
]
