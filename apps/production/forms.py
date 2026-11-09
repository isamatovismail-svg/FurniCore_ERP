from django import forms
from decimal import Decimal
from apps.production.models import (
    ProductionOrder,
    BOM,
    BOMItem,
    ProductionWaste,
    WasteType,
    OrderPriority,
    ProductionOrderStatus,
    RoutingTemplate,
)
from apps.products.models import Product, ProductVariant
from apps.employees.models import Employee, Department
from apps.sales.models import SalesOrder
from apps.materials.models import Material
from apps.quality.models import QualityCheck, QCResult


class ProductionOrderForm(forms.ModelForm):
    class Meta:
        model = ProductionOrder
        fields = [
            'product',
            'variant',
            'bom',
            'quantity_planned',
            'priority',
            'planned_start',
            'planned_end',
            'assigned_master',
            'sales_order',
            'notes',
        ]
        widgets = {
            'product': forms.Select(attrs={'class': 'fc-input text-xs font-medium', 'required': 'true'}),
            'variant': forms.Select(attrs={'class': 'fc-input text-xs'}),
            'bom': forms.Select(attrs={'class': 'fc-input text-xs'}),
            'quantity_planned': forms.NumberInput(attrs={'class': 'fc-input text-xs font-bold', 'min': '1', 'step': '1'}),
            'priority': forms.Select(attrs={'class': 'fc-input text-xs font-medium'}),
            'planned_start': forms.DateInput(attrs={'class': 'fc-input text-xs', 'type': 'date'}),
            'planned_end': forms.DateInput(attrs={'class': 'fc-input text-xs', 'type': 'date'}),
            'assigned_master': forms.Select(attrs={'class': 'fc-input text-xs'}),
            'sales_order': forms.Select(attrs={'class': 'fc-input text-xs'}),
            'notes': forms.Textarea(attrs={'class': 'fc-input text-xs', 'rows': 2, 'placeholder': 'Особые пожелания заказчика, чертежи или комплектация'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['variant'].required = False
        self.fields['bom'].required = False
        self.fields['assigned_master'].required = False
        self.fields['sales_order'].required = False
        self.fields['assigned_master'].queryset = Employee.objects.filter(department=Department.PRODUCTION).order_by('last_name')


class BOMForm(forms.ModelForm):
    class Meta:
        model = BOM
        fields = [
            'product',
            'variant',
            'name',
            'version',
            'routing_template',
            'standard_labor_hours',
            'labor_rate_hourly_kzt',
            'overhead_rate_kzt',
            'is_active',
            'description',
        ]
        widgets = {
            'product': forms.Select(attrs={'class': 'fc-input text-xs', 'required': 'true'}),
            'variant': forms.Select(attrs={'class': 'fc-input text-xs'}),
            'name': forms.TextInput(attrs={'class': 'fc-input text-xs', 'placeholder': 'Например: Базовая спецификация (шкаф-купе)'}),
            'version': forms.TextInput(attrs={'class': 'fc-input text-xs font-mono', 'placeholder': '1.0'}),
            'routing_template': forms.Select(attrs={'class': 'fc-input text-xs'}),
            'standard_labor_hours': forms.NumberInput(attrs={'class': 'fc-input text-xs font-bold', 'step': '0.5'}),
            'labor_rate_hourly_kzt': forms.NumberInput(attrs={'class': 'fc-input text-xs', 'step': '100'}),
            'overhead_rate_kzt': forms.NumberInput(attrs={'class': 'fc-input text-xs', 'step': '500'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded text-[#173B35]'}),
            'description': forms.Textarea(attrs={'class': 'fc-input text-xs', 'rows': 2, 'placeholder': 'Описание карты'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['variant'].required = False
        self.fields['routing_template'].required = False


class QualityCheckForm(forms.ModelForm):
    class Meta:
        model = QualityCheck
        fields = [
            'result',
            'quantity_checked',
            'quantity_accepted',
            'quantity_defective',
            'check_dimensions',
            'check_assembly',
            'check_appearance',
            'check_coating',
            'check_completeness',
            'check_mechanisms',
            'check_damage_free',
            'defect_description',
            'rework_instructions',
            'notes',
        ]
        widgets = {
            'result': forms.Select(attrs={'class': 'fc-input text-xs font-bold'}),
            'quantity_checked': forms.NumberInput(attrs={'class': 'fc-input text-xs font-bold', 'min': '1', 'step': '1'}),
            'quantity_accepted': forms.NumberInput(attrs={'class': 'fc-input text-xs font-bold text-emerald-700', 'min': '0', 'step': '1'}),
            'quantity_defective': forms.NumberInput(attrs={'class': 'fc-input text-xs font-bold text-rose-600', 'min': '0', 'step': '1'}),
            'check_dimensions': forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded text-[#173B35]'}),
            'check_assembly': forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded text-[#173B35]'}),
            'check_appearance': forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded text-[#173B35]'}),
            'check_coating': forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded text-[#173B35]'}),
            'check_completeness': forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded text-[#173B35]'}),
            'check_mechanisms': forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded text-[#173B35]'}),
            'check_damage_free': forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded text-[#173B35]'}),
            'defect_description': forms.Textarea(attrs={'class': 'fc-input text-xs', 'rows': 2, 'placeholder': 'Описание дефектов'}),
            'rework_instructions': forms.Textarea(attrs={'class': 'fc-input text-xs', 'rows': 2, 'placeholder': 'Указания по доработке'}),
            'notes': forms.Textarea(attrs={'class': 'fc-input text-xs', 'rows': 1}),
        }


class ProductionWasteForm(forms.ModelForm):
    class Meta:
        model = ProductionWaste
        fields = [
            'waste_type',
            'stage',
            'material',
            'quantity',
            'unit',
            'cost_kzt',
            'reason',
            'decision',
        ]
        widgets = {
            'waste_type': forms.Select(attrs={'class': 'fc-input text-xs font-bold'}),
            'stage': forms.Select(attrs={'class': 'fc-input text-xs'}),
            'material': forms.Select(attrs={'class': 'fc-input text-xs'}),
            'quantity': forms.NumberInput(attrs={'class': 'fc-input text-xs font-bold', 'step': '0.001'}),
            'unit': forms.TextInput(attrs={'class': 'fc-input text-xs font-mono'}),
            'cost_kzt': forms.NumberInput(attrs={'class': 'fc-input text-xs font-bold', 'step': '10'}),
            'reason': forms.TextInput(attrs={'class': 'fc-input text-xs', 'placeholder': 'Причина (скол, ошибка оператора...)'}),
            'decision': forms.Textarea(attrs={'class': 'fc-input text-xs', 'rows': 2, 'placeholder': 'Решение'}),
        }
