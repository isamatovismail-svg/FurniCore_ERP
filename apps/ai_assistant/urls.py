from django.urls import path
from . import views

app_name = 'ai_assistant'

urlpatterns = [
    path('', views.index, name='index'),
    path('settings/', views.settings_view, name='settings'),
]
