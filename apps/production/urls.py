from django.urls import path
from . import views

app_name = 'production'

urlpatterns = [
    # Главная страница и Dashboard
    path('', views.index, name='index'),

    # Заказы на производство (CRUD)
    path('create/', views.order_create, name='create'),
    path('<uuid:pk>/', views.detail, name='detail'),
    path('<uuid:pk>/edit/', views.order_edit, name='edit'),

    # Оперативные действия по заказу
    path('<uuid:pk>/issue-materials/', views.order_issue_materials, name='issue_materials'),
    path('<uuid:pk>/launch/', views.order_launch, name='launch'),
    path('stage/<uuid:stage_id>/advance/', views.stage_advance_action, name='stage_advance'),
    path('<uuid:pk>/qc/', views.order_qc_inspect, name='qc_inspect'),
    path('<uuid:pk>/transfer-wh2/', views.order_transfer_wh2, name='transfer_wh2'),

    # Канбан-доска
    path('board/', views.kanban_board, name='board'),

    # Интерфейс мастера
    path('my-tasks/', views.my_tasks, name='my_tasks'),

    # Технологические карты (BOM)
    path('boms/', views.boms_list, name='boms_list'),
    path('boms/create/', views.bom_create, name='bom_create'),
    path('boms/<uuid:pk>/', views.bom_detail, name='bom_detail'),

    # Маршруты производства
    path('routes/', views.routes_list, name='routes_list'),

    # Журнал брака и отходов
    path('waste/', views.waste_list, name='waste_list'),
    path('<uuid:pk>/waste/create/', views.waste_create, name='waste_create'),
]
