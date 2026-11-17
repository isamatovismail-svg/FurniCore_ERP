import io
import os
from decimal import Decimal
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Register Cyrillic-compatible fonts
FONT_REGULAR = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'
try:
    font_paths = [
        ('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'),
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    ]
    for reg_path, bold_path in font_paths:
        if os.path.exists(reg_path) and os.path.exists(bold_path):
            pdfmetrics.registerFont(TTFont('CyrillicFont', reg_path))
            pdfmetrics.registerFont(TTFont('CyrillicFont-Bold', bold_path))
            FONT_REGULAR = 'CyrillicFont'
            FONT_BOLD = 'CyrillicFont-Bold'
            break
except Exception:
    pass


def generate_customer_payment_pdf(payment) -> bytes:
    """
    Generates a PDF payment receipt for a CustomerPayment.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName=FONT_BOLD,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#173B35'),
        alignment=1,
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontName=FONT_REGULAR,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#4A5568'),
        alignment=1,
    )
    cell_label_style = ParagraphStyle(
        'CellLabel',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#252D29')
    )
    cell_val_style = ParagraphStyle(
        'CellVal',
        parent=styles['Normal'],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#252D29')
    )

    elements = []

    # Header
    elements.append(Paragraph("ТОО «FurniCore» — Мебельная фабрика", subtitle_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"КВИТАНЦИЯ ОБ ОПЛАТЕ № {payment.payment_number}", title_style))
    elements.append(Paragraph(f"Дата операции: {payment.payment_date.strftime('%d.%m.%Y')}", subtitle_style))
    elements.append(Spacer(1, 16))

    # Payment info table
    customer_name = payment.customer.name if payment.customer else (payment.sales_order.customer.name if payment.sales_order and payment.sales_order.customer else '—')
    customer_phone = payment.customer.phone if payment.customer else (payment.sales_order.customer.phone if payment.sales_order and payment.sales_order.customer else '—')
    order_ref = payment.sales_order.order_number if payment.sales_order else 'Без привязки к заказу'
    account_name = payment.account.name if payment.account else 'Основная касса'
    status_label = payment.get_status_display()

    data = [
        [Paragraph("Плательщик / Клиент:", cell_label_style), Paragraph(f"{customer_name} ({customer_phone})", cell_val_style)],
        [Paragraph("Заказ покупателя:", cell_label_style), Paragraph(order_ref, cell_val_style)],
        [Paragraph("Финансовый счёт / Касса:", cell_label_style), Paragraph(account_name, cell_val_style)],
        [Paragraph("Способ оплаты:", cell_label_style), Paragraph(payment.get_payment_method_display(), cell_val_style)],
        [Paragraph("Статус платежа:", cell_label_style), Paragraph(status_label, cell_val_style)],
        [Paragraph("Кассир / Оператор:", cell_label_style), Paragraph((payment.created_by.get_full_name() or payment.created_by.username) if payment.created_by else 'Система', cell_val_style)],
        [Paragraph("Назначение / Комментарий:", cell_label_style), Paragraph(payment.notes or 'Оплата по заказу мебели', cell_val_style)],
    ]

    t = Table(data, colWidths=[160, 360])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 16))

    # Big Total Box
    amount_str = f"{payment.amount_kzt:,.2f}".replace(',', ' ') + " ₸"
    amount_data = [
        [Paragraph("ИТОГО ПРИНЯТО К ОПЛАТЕ:", ParagraphStyle('AmtLbl', fontName=FONT_BOLD, fontSize=12, textColor=colors.white)),
         Paragraph(amount_str, ParagraphStyle('AmtVal', fontName=FONT_BOLD, fontSize=14, textColor=colors.white, alignment=2))]
    ]
    t_amount = Table(amount_data, colWidths=[260, 260])
    t_amount.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#173B35')),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_amount)

    # Order Balance Summary if order attached
    if payment.sales_order:
        elements.append(Spacer(1, 14))
        order = payment.sales_order
        order_total = f"{order.total_amount_kzt:,.2f}".replace(',', ' ') + " ₸"
        order_paid = f"{order.paid_amount_kzt:,.2f}".replace(',', ' ') + " ₸"
        order_rest = f"{order.remaining_debt_kzt:,.2f}".replace(',', ' ') + " ₸"
        bal_data = [
            [Paragraph("Сумма заказа:", cell_label_style), Paragraph(order_total, cell_val_style)],
            [Paragraph("Всего оплачено по заказу:", cell_label_style), Paragraph(order_paid, cell_val_style)],
            [Paragraph("Остаток задолженности:", cell_label_style), Paragraph(order_rest, cell_val_style)],
        ]
        t_bal = Table(bal_data, colWidths=[200, 320])
        t_bal.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(t_bal)

    # Signatures
    elements.append(Spacer(1, 30))
    sig_data = [
        [Paragraph("Принял (Кассир): ____________________", cell_val_style),
         Paragraph("Плательщик: ____________________", cell_val_style)],
        [Paragraph("М.П.", cell_val_style), Paragraph("", cell_val_style)]
    ]
    t_sig = Table(sig_data, colWidths=[260, 260])
    elements.append(t_sig)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def generate_supplier_payment_pdf(payment) -> bytes:
    """
    Generates a PDF payment order for a SupplierPayment.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName=FONT_BOLD,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#173B35'),
        alignment=1,
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontName=FONT_REGULAR,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#4A5568'),
        alignment=1,
    )
    cell_label_style = ParagraphStyle(
        'CellLabel',
        parent=styles['Normal'],
        fontName=FONT_BOLD,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#252D29')
    )
    cell_val_style = ParagraphStyle(
        'CellVal',
        parent=styles['Normal'],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#252D29')
    )

    elements = []

    # Header
    elements.append(Paragraph("ТОО «FurniCore» — Мебельная фабрика", subtitle_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"РАСХОДНЫЙ ОРДЕР / ПЛАТЁЖ ПОСТАВЩИКУ № {payment.payment_number}", title_style))
    elements.append(Paragraph(f"Дата операции: {payment.payment_date.strftime('%d.%m.%Y')}", subtitle_style))
    elements.append(Spacer(1, 16))

    supplier_name = payment.supplier.name if payment.supplier else (payment.purchase_order.supplier.name if payment.purchase_order else '—')
    po_ref = payment.purchase_order.order_number if payment.purchase_order else 'Без привязки к заказу закупки'
    account_name = payment.account.name if payment.account else 'Основной расчётный счёт'

    data = [
        [Paragraph("Получатель / Поставщик:", cell_label_style), Paragraph(supplier_name, cell_val_style)],
        [Paragraph("Заказ закупки (Спецификация):", cell_label_style), Paragraph(po_ref, cell_val_style)],
        [Paragraph("Счёт списания:", cell_label_style), Paragraph(account_name, cell_val_style)],
        [Paragraph("Способ оплаты:", cell_label_style), Paragraph(payment.get_payment_method_display(), cell_val_style)],
        [Paragraph("Статус платежа:", cell_label_style), Paragraph(payment.get_status_display(), cell_val_style)],
        [Paragraph("Ответственный бухгалтер:", cell_label_style), Paragraph((payment.created_by.get_full_name() or payment.created_by.username) if payment.created_by else 'Бухгалтерия', cell_val_style)],
        [Paragraph("Назначение платежа:", cell_label_style), Paragraph(payment.notes or 'Оплата поставщику за материалы и фурнитуру', cell_val_style)],
    ]

    t = Table(data, colWidths=[170, 350])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 16))

    # Big Total Box
    amount_str = f"{payment.amount_kzt:,.2f}".replace(',', ' ') + " ₸"
    amount_data = [
        [Paragraph("ИТОГО ВЫПЛАЧЕНО:", ParagraphStyle('AmtLbl', fontName=FONT_BOLD, fontSize=12, textColor=colors.white)),
         Paragraph(amount_str, ParagraphStyle('AmtVal', fontName=FONT_BOLD, fontSize=14, textColor=colors.white, alignment=2))]
    ]
    t_amount = Table(amount_data, colWidths=[260, 260])
    t_amount.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#B45309')),  # warm amber/bronze for outgoing
        ('PADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_amount)

    # PO Balance Summary if PO attached
    if payment.purchase_order:
        elements.append(Spacer(1, 14))
        po = payment.purchase_order
        po_total = f"{po.total_amount_kzt:,.2f}".replace(',', ' ') + " ₸"
        po_paid = f"{po.paid_amount_kzt:,.2f}".replace(',', ' ') + " ₸"
        po_rest = f"{po.remaining_debt_kzt:,.2f}".replace(',', ' ') + " ₸"
        bal_data = [
            [Paragraph("Общая сумма закупки:", cell_label_style), Paragraph(po_total, cell_val_style)],
            [Paragraph("Выплачено по заказу закупки:", cell_label_style), Paragraph(po_paid, cell_val_style)],
            [Paragraph("Остаток задолженности фабрики:", cell_label_style), Paragraph(po_rest, cell_val_style)],
        ]
        t_bal = Table(bal_data, colWidths=[200, 320])
        t_bal.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF3C7')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FDE68A')),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(t_bal)

    # Signatures
    elements.append(Spacer(1, 30))
    sig_data = [
        [Paragraph("Главный бухгалтер: ____________________", cell_val_style),
         Paragraph("Директор: ____________________", cell_val_style)],
        [Paragraph("М.П.", cell_val_style), Paragraph("", cell_val_style)]
    ]
    t_sig = Table(sig_data, colWidths=[260, 260])
    elements.append(t_sig)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# -------------------------------------------------------------
# Excel Reports Generator using openpyxl
# -------------------------------------------------------------

def export_financial_excel(report_type: str, start_date=None, end_date=None) -> bytes:
    """
    Exports clean, styled Excel workbook for:
    - 'pandl': Profit & Loss (Отчёт о прибылях и убытках)
    - 'cashflow': Движение денежных средств (ДДС)
    - 'receivables': Дебиторская задолженность (клиенты)
    - 'payables': Кредиторская задолженность (поставщики)
    - 'costing': Себестоимость заказов и мебели
    """
    from apps.finance.models import CustomerPayment, SupplierPayment, Expense, ExpenseCategory, FinancialAccount
    from apps.sales.models import SalesOrder, Customer
    from apps.suppliers.models import PurchaseOrder, Supplier
    from apps.production.models import ProductionOrder
    from apps.finance.services import get_financial_dashboard_kpis, calculate_production_order_actual_cost

    wb = openpyxl.Workbook()
    ws = wb.active

    # Styling helper
    header_fill = PatternFill(start_color="173B35", end_color="173B35", fill_type="solid")
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Arial", size=14, bold=True, color="173B35")
    bold_font = Font(name="Arial", size=10, bold=True)
    normal_font = Font(name="Arial", size=10)
    border_thin = Border(
        left=Side(style='thin', color='E0E0E0'),
        right=Side(style='thin', color='E0E0E0'),
        top=Side(style='thin', color='E0E0E0'),
        bottom=Side(style='thin', color='E0E0E0')
    )

    now_str = timezone.now().strftime("%d.%m.%Y %H:%M")

    if report_type == 'pandl':
        ws.title = "Отчёт P&L"
        kpis = get_financial_dashboard_kpis(start_date=start_date, end_date=end_date)

        ws.append(["FurniCore ERP — Отчёт о прибылях и убытках (P&L)"])
        ws.append([f"Сформирован: {now_str}"])
        ws.append([])

        headers = ["Статья отчёта", "Значение (KZT)", "Примечание"]
        ws.append(headers)

        rows = [
            ("Выручка от продаж (Метод начисления)", float(kpis['accrual_revenue_kzt']), "По подтверждённым и отгруженным заказам"),
            ("Фактические поступления денег", float(kpis['cash_inflow_kzt']), "Оплаты от клиентов (ДДС)"),
            ("Расходы на закупки сырья", float(kpis['purchases_total_kzt']), "Оплачено поставщикам сырья и фурнитуры"),
            ("Операционные расходы фабрики", float(kpis['cash_expenses_kzt']), "Аренда, зарплата, логистика и т.д."),
            ("Общие подтверждённые затраты", float(kpis['cash_outflow_kzt']), "Всего выплачено средств"),
            ("Чистая операционная прибыль (P&L)", float(kpis['net_profit_kzt']), "Выручка минус расходы"),
        ]
        for r in rows:
            ws.append(list(r))

        ws.append([])
        ws.append(["Детализация расходов по статьям:"])
        for cat in kpis['expenses_breakdown']:
            ws.append([str(cat['label']), float(cat['total']), f"{cat['percent']}% от общих расходов"])

    elif report_type == 'cashflow':
        ws.title = "Отчёт ДДС"
        kpis = get_financial_dashboard_kpis(start_date=start_date, end_date=end_date)

        ws.append(["FurniCore ERP — Движение денежных средств (Cash Flow)"])
        ws.append([f"Сформирован: {now_str}"])
        ws.append([])

        ws.append(["Показатель ДДС", "Сумма (KZT)", "Комментарий"])
        ws.append(["Поступления (Cash Inflow)", float(kpis['cash_inflow_kzt']), "Платежи клиентов и прочие доходы"])
        ws.append(["Выплаты поставщикам", float(kpis['purchases_total_kzt']), "Оплата счетов за материалы"])
        ws.append(["Операционные выплаты", float(kpis['cash_expenses_kzt']), "ФОТ, аренда, налоги, логистика"])
        ws.append(["Всего выплат (Cash Outflow)", float(kpis['cash_outflow_kzt']), "Суммарный отток средств"])
        ws.append(["Чистый денежный поток (Net Cash Flow)", float(kpis['net_cash_flow_kzt']), "Поступления минус выплаты"])

        ws.append([])
        ws.append(["Остатки на счетах и в кассах:"])
        for acc in kpis['accounts']:
            name = acc.name if hasattr(acc, 'name') else acc.get('name', '—')
            bal = float(acc.current_balance_kzt) if hasattr(acc, 'current_balance_kzt') else float(acc.get('balance_kzt', 0.0))
            t_label = acc.type_label if hasattr(acc, 'type_label') else acc.get('type_label', '')
            ws.append([name, bal, str(t_label)])

    elif report_type == 'receivables':
        ws.title = "Дебиторка"
        ws.append(["FurniCore ERP — Реестр дебиторской задолженности покупателей"])
        ws.append([f"Сформирован: {now_str}"])
        ws.append([])

        headers = ["Клиент", "Телефон", "Номер заказа", "Дата заказа", "Сумма заказа (₸)", "Оплачено (₸)", "Долг (₸)", "Статус оплаты"]
        ws.append(headers)

        active_orders = SalesOrder.objects.exclude(status='CANCELLED').select_related('customer').order_by('-created_at')
        orders = [o for o in active_orders if o.remaining_debt_kzt > Decimal('0.00')]
        for o in orders:
            ws.append([
                o.customer.name if o.customer else "—",
                o.customer.phone if o.customer else "—",
                o.order_number,
                o.created_at.strftime("%d.%m.%Y"),
                float(o.total_amount_kzt),
                float(o.paid_amount_kzt),
                float(o.remaining_debt_kzt),
                str(getattr(o, 'payment_status_display', o.payment_status))
            ])

    elif report_type == 'payables':
        ws.title = "Кредиторка"
        ws.append(["FurniCore ERP — Реестр кредиторской задолженности перед поставщиками"])
        ws.append([f"Сформирован: {now_str}"])
        ws.append([])

        headers = ["Поставщик", "Контакты", "Заказ закупки", "Дата", "Сумма закупки (₸)", "Выплачено (₸)", "Долг фабрики (₸)", "Статус"]
        ws.append(headers)

        active_pos = PurchaseOrder.objects.exclude(status='CANCELLED').select_related('supplier').order_by('-order_date')
        pos = [p for p in active_pos if p.remaining_debt_kzt > Decimal('0.00')]
        for p in pos:
            ws.append([
                p.supplier.name if p.supplier else "—",
                p.supplier.contact_person if p.supplier else "—",
                p.order_number,
                p.order_date.strftime("%d.%m.%Y"),
                float(p.total_amount_kzt),
                float(p.paid_amount_kzt),
                float(p.remaining_debt_kzt),
                str(getattr(p, 'payment_status_display', p.payment_status))
            ])

    elif report_type == 'costing':
        ws.title = "Себестоимость"
        ws.append(["FurniCore ERP — Расчёт себестоимости производственных заказов"])
        ws.append([f"Сформирован: {now_str}"])
        ws.append([])

        headers = [
            "Заказ пр-ва", "Изделие", "Кол-во", "Статус",
            "План. мат-лы (₸)", "Факт. мат-лы (₸)", "ФОТ и цех (₸)",
            "Итого себестоимость (₸)", "Себестоимость ед. (₸)", "Отклонение от плана (₸)"
        ]
        ws.append(headers)

        p_orders = ProductionOrder.objects.select_related('product').all().order_by('-created_at')[:50]
        for po in p_orders:
            cost_info = calculate_production_order_actual_cost(po)
            ws.append([
                po.order_number,
                po.product.name if po.product else "—",
                float(po.quantity_planned),
                str(po.get_status_display()),
                float(cost_info['planned_materials_cost_kzt']),
                float(cost_info['actual_materials_cost_kzt']),
                float(cost_info['labor_and_overhead_cost_kzt']),
                float(cost_info['total_actual_cost_kzt']),
                float(cost_info['actual_unit_cost_kzt']),
                float(cost_info['cost_variance_kzt']),
            ])

    # Styling sheet
    ws['A1'].font = title_font
    ws['A2'].font = Font(name="Arial", size=9, italic=True, color="666666")

    # Find the header row (row 4)
    if ws.max_row >= 4:
        for col_idx in range(1, ws.max_column + 1):
            cell = ws.cell(row=4, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    # Borders and styling for data cells
    for row in ws.iter_rows(min_row=5, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            cell.font = normal_font
            cell.border = border_thin
            if isinstance(cell.value, float):
                cell.number_format = '#,##0.00'

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or '')
            if len(val_str) > max_len and len(val_str) < 60:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 14)

    buffer = io.BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()
    buffer.close()
    return excel_bytes
