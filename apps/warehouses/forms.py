from django import forms
from decimal import Decimal
from apps.warehouses.models import (
    Warehouse,
    WarehouseType,
    WarehouseDocument,
    WarehouseDocumentItem,
    WarehouseDocumentType,
    DocumentStatus,
)
from apps.materials.models import Material
from apps.products.models import Product
from apps.suppliers.models import Supplier
from apps.sales.models import Customer, SalesOrder
from apps.production.models import ProductionOrder


class WarehouseDocumentForm(forms.ModelForm):
    class Meta:
        model = WarehouseDocument
        fields = [
            'warehouse',
            'doc_type',
            'doc_date',
            'supplier',
            'customer',
            'sales_order',
            'production_order',
            'notes',
        ]
        widgets = {
            'warehouse': forms.Select(attrs={'class': 'fc-input'}),
            'doc_type': forms.Select(attrs={'class': 'fc-input'}),
            'doc_date': forms.DateInput(attrs={'class': 'fc-input', 'type': 'date'}),
            'supplier': forms.Select(attrs={'class': 'fc-input'}),
            'customer': forms.Select(attrs={'class': 'fc-input'}),
            'sales_order': forms.Select(attrs={'class': 'fc-input'}),
            'production_order': forms.Select(attrs={'class': 'fc-input'}),
            'notes': forms.Textarea(attrs={'class': 'fc-input', 'rows': 2, 'placeholder': 'Основание, номер договора или комментарий'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].required = False
        self.fields['customer'].required = False
        self.fields['sales_order'].required = False
        self.fields['production_order'].required = False
