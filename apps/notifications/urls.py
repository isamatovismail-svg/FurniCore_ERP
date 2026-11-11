from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.index, name='index'),
    path('<uuid:pk>/read/', views.mark_as_read, name='mark_as_read'),
    path('read-all/', views.mark_all_as_read, name='mark_all_as_read'),
]
