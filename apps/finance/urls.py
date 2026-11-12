from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    # Финансовый дашборд
    path('', views.index, name='index'),

    # Платежи покупателей
    path('payments/customers/', views.customer_payment_list, name='customer_payments'),
    path('payments/customers/create/', views.customer_payment_create, name='customer_payment_create'),
    path('payments/customers/<uuid:pk>/pdf/', views.customer_payment_pdf, name='customer_payment_pdf'),
    path('payments/customers/<uuid:pk>/storno/', views.customer_payment_storno, name='customer_payment_storno'),

    # Оплаты поставщикам
    path('payments/suppliers/', views.supplier_payment_list, name='supplier_payments'),
    path('payments/suppliers/create/', views.supplier_payment_create, name='supplier_payment_create'),
    path('payments/suppliers/<uuid:pk>/pdf/', views.supplier_payment_pdf, name='supplier_payment_pdf'),
    path('payments/suppliers/<uuid:pk>/storno/', views.supplier_payment_storno, name='supplier_payment_storno'),

    # Казначейство: Счета и кассы
    path('accounts/', views.account_list, name='accounts'),
    path('accounts/transfer/', views.account_transfer, name='account_transfer'),

    # Операционные расходы
    path('expenses/', views.expense_list, name='expenses'),
    path('expenses/create/', views.expense_create, name='expense_create'),
    path('expenses/<uuid:pk>/storno/', views.expense_storno, name='expense_storno'),

    # Задолженности
    path('receivables/', views.receivables_list, name='receivables'),
    path('payables/', views.payables_list, name='payables'),

    # Себестоимость производства
    path('costing/', views.cost_accounting_view, name='order_costs'),

    # Экспорт отчётов в Excel
    path('export/excel/', views.export_excel, name='export_excel'),
]
