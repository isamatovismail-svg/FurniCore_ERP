from django.contrib import admin

from .models import (
    AccountTransfer,
    CustomerPayment,
    Expense,
    FinancialAccount,
    GeneralIncome,
    SupplierPayment,
)


class ReadOnlyFinanceAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FinancialAccount)
class FinancialAccountAdmin(ReadOnlyFinanceAdmin):
    list_display = ('name', 'account_type', 'currency', 'initial_balance_kzt', 'current_balance_kzt', 'is_active')
    list_filter = ('account_type', 'currency', 'is_active')
    search_fields = ('name', 'account_number')


@admin.register(CustomerPayment)
class CustomerPaymentAdmin(ReadOnlyFinanceAdmin):
    list_display = ('payment_number', 'payment_date', 'customer', 'sales_order', 'amount_kzt', 'account', 'status')
    list_filter = ('status', 'payment_method', 'payment_date')
    search_fields = ('payment_number', 'reference_number', 'customer__full_name', 'sales_order__order_number')


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(ReadOnlyFinanceAdmin):
    list_display = ('payment_number', 'payment_date', 'supplier', 'purchase_order', 'amount_kzt', 'account', 'status')
    list_filter = ('status', 'payment_method', 'payment_date')
    search_fields = ('payment_number', 'reference_number', 'supplier__name', 'purchase_order__order_number')


@admin.register(AccountTransfer)
class AccountTransferAdmin(ReadOnlyFinanceAdmin):
    list_display = ('transfer_number', 'transfer_date', 'from_account', 'to_account', 'amount_kzt', 'status')
    list_filter = ('status', 'transfer_date')
    search_fields = ('transfer_number',)


@admin.register(Expense)
class ExpenseAdmin(ReadOnlyFinanceAdmin):
    list_display = ('expense_number', 'payment_date', 'category', 'description', 'amount_kzt', 'account', 'is_storno')
    list_filter = ('category', 'is_storno', 'payment_date')
    search_fields = ('expense_number', 'description', 'payee')


@admin.register(GeneralIncome)
class GeneralIncomeAdmin(ReadOnlyFinanceAdmin):
    list_display = ('income_number', 'income_date', 'category', 'payer', 'amount_kzt', 'account', 'is_storno')
    list_filter = ('category', 'is_storno', 'income_date')
    search_fields = ('income_number', 'payer', 'description')
