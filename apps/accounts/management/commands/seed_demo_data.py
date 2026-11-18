"""
seed_demo_data.py — Safe, idempotent management command to populate FurniCore ERP with DEMO data.

Ensures complete business demonstration coverage:
- Warehouses (WH-1 Materials & WH-2 Finished Goods)
- Materials, Products, BOMs, and 5 Production Routes
- Production Orders with stages and QC
- Suppliers, Purchase Orders, and WH-1 Receipts
- Customers, Sales Orders, Reservations, and WH-2 Shipments
- Financial Accounts (Cash, Bank, Kaspi), Payments, Expenses, and P&L

Usage:
    python manage.py seed_demo_data
    python manage.py seed_demo_data --clear  # explicitly clears demo data before re-seeding
"""
import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = 'Безопасно и идемпотентно наполняет FurniCore ERP демонстрационными данными (DEMO).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            default=False,
            help='Явное удаление существующих демонстрационных данных перед повторным заполнением',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            '\n==================================================\n'
            '  FURNICORE ERP — НАПОЛНЕНИЕ ДЕМО-ДАННЫМИ (DEMO)\n'
            '=================================================='
        ))

        # 1. Reuse existing base seed logic
        from apps.accounts.management.commands.seed_demo import Command as BaseSeedCommand
        base_cmd = BaseSeedCommand()
        base_cmd.stdout = self.stdout
        base_cmd.style = self.style

        # Run base seed command
        base_cmd.handle(*args, **options)

        # 2. Ensure Phase 4 & Phase 5 Financial and Procurement data are fully initialized
        self.stdout.write('\nПроверка и дополнение финансовых счетов и операций (Фаза 5)...')
        from apps.finance.services import ensure_default_accounts
        from apps.finance.models import FinancialAccount, CustomerPayment, SupplierPayment, PaymentStatus
        from apps.suppliers.models import Supplier, PurchaseOrder, PurchaseOrderItem
        from apps.sales.models import Customer, SalesOrder, OrderStatus
        from apps.accounts.models import User
        from apps.materials.models import Material

        accounts = ensure_default_accounts()
        self.stdout.write(f'  ✓ Финансовые счета активны: {[a.name for a in accounts]}')

        accountant = User.objects.filter(username='accountant').first() or User.objects.filter(is_superuser=True).first()

        # Ensure Purchase Orders exist
        sup1 = Supplier.objects.first()
        mat1 = Material.objects.first()
        if sup1 and mat1 and not PurchaseOrder.objects.filter(order_number='PO-2026-DEMO1').exists():
            today = timezone.localdate()
            po = PurchaseOrder.objects.create(
                order_number='PO-2026-DEMO1',
                supplier=sup1,
                status='RECEIVED',
                order_date=today - datetime.timedelta(days=7),
                planned_delivery_date=today - datetime.timedelta(days=2),
                created_by=accountant,
                total_amount_kzt=Decimal('350000.00'),
                notes='(DEMO) Поставка массива сосны для цеха',
            )
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                material=mat1,
                quantity=Decimal('5.000'),
                received_quantity=Decimal('5.000'),
                unit_price_kzt=Decimal('70000.00'),
                total_price_kzt=Decimal('350000.00'),
            )
            self.stdout.write(f'  ✓ Заказ на закупку: {po.order_number}')

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Идемпотентное наполнение FurniCore ERP завершено успешно!\n'
            '   База данных готова к показу преподавателю.\n'
        ))
