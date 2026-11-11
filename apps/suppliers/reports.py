import io
import os
import qrcode
from decimal import Decimal
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from apps.suppliers.models import PurchaseOrder

_FONT_INITIALIZED = False


def init_fonts():
    global _FONT_INITIALIZED
    if _FONT_INITIALIZED:
        return

    font_path_regular = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    font_path_bold = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

    if os.path.exists(font_path_regular):
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path_regular))
    if os.path.exists(font_path_bold):
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_path_bold))

    _FONT_INITIALIZED = True


def generate_purchase_order_pdf(order: PurchaseOrder) -> bytes:
    init_fonts()
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    primary_color = colors.HexColor('#173B35')
    secondary_color = colors.HexColor('#285F4D')
    bg_light = colors.HexColor('#F4F6F3')

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='DejaVuSans-Bold',
        fontSize=15,
        leading=18,
        textColor=primary_color,
    )
    meta_style = ParagraphStyle(
        'Meta',
        parent=styles['Normal'],
        fontName='DejaVuSans',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#252D29'),
    )
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='DejaVuSans-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='DejaVuSans',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#252D29'),
    )
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='DejaVuSans-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#252D29'),
    )

    elements = []

    # Header block
    header_data = [
        [
            Paragraph("<b>FURNICORE ERP</b> — Мебельное производство<br/><font size=8 color='#666'>Отдел материально-технического снабжения</font>", meta_style),
            Paragraph(f"<b>ЗАКАЗ ПОСТАВЩИКУ</b><br/><font size=12 color='#173B35'><b>№ {order.order_number}</b></font>", title_style),
        ]
    ]
    header_table = Table(header_data, colWidths=[100 * mm, 80 * mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 4 * mm))

    # Order details
    order_info = [
        [
            Paragraph(f"<b>Поставщик:</b> {order.supplier.name}", meta_style),
            Paragraph(f"<b>Дата заказа:</b> {order.order_date.strftime('%d.%m.%Y')}", meta_style),
        ],
        [
            Paragraph(f"<b>Контактное лицо:</b> {order.supplier.contact_person or '—'}", meta_style),
            Paragraph(f"<b>Срок поставки:</b> {order.planned_delivery_date.strftime('%d.%m.%Y') if order.planned_delivery_date else 'По согласованию'}", meta_style),
        ],
        [
            Paragraph(f"<b>Телефон:</b> {order.supplier.phone or '—'}", meta_style),
            Paragraph(f"<b>Статус заказа:</b> {order.get_status_display()}", meta_style),
        ],
        [
            Paragraph(f"<b>Адрес поставки:</b> Склад сырья WH-1 (г. Алматы)", meta_style),
            Paragraph(f"<b>Создал заказ:</b> {order.created_by.get_full_name() if order.created_by else 'ERP System'}", meta_style),
        ],
    ]
    info_table = Table(order_info, colWidths=[100 * mm, 80 * mm])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg_light),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 5 * mm))

    # Items table
    items_rows = [
        [
            Paragraph("№", table_header_style),
            Paragraph("Артикул", table_header_style),
            Paragraph("Наименование материала", table_header_style),
            Paragraph("Кол-во", table_header_style),
            Paragraph("Принято", table_header_style),
            Paragraph("Цена (₸)", table_header_style),
            Paragraph("Сумма (₸)", table_header_style),
        ]
    ]

    for idx, it in enumerate(order.items.select_related('material').all(), 1):
        items_rows.append([
            Paragraph(str(idx), table_cell_style),
            Paragraph(it.material.sku, table_cell_style),
            Paragraph(it.material.name, table_cell_style),
            Paragraph(f"{it.quantity} {it.material.unit}", table_cell_style),
            Paragraph(f"{it.received_quantity} {it.material.unit}", table_cell_style),
            Paragraph(f"{it.unit_price_kzt:,.2f}", table_cell_style),
            Paragraph(f"{it.total_price_kzt:,.2f}", table_cell_bold),
        ])

    items_table = Table(
        items_rows,
        colWidths=[8 * mm, 24 * mm, 62 * mm, 22 * mm, 22 * mm, 20 * mm, 22 * mm],
    )
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 4 * mm))

    # Total amount
    total_data = [
        [
            Paragraph(f"<b>Примечания:</b> {order.notes or 'Без дополнительных условий'}", meta_style),
            Paragraph(f"<b>ИТОГО К ОПЛАТЕ:</b>", table_cell_bold),
            Paragraph(f"<b>{order.total_amount_kzt:,.2f} ₸</b>", title_style),
        ]
    ]
    total_table = Table(total_data, colWidths=[100 * mm, 38 * mm, 42 * mm])
    total_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (-1, 0), 'RIGHT'),
    ]))
    elements.append(total_table)
    elements.append(Spacer(1, 10 * mm))

    # Signature block
    sign_data = [
        [
            Paragraph("<b>Ответственный за заказ:</b> ___________________", meta_style),
            Paragraph("<b>Поставщик принял заказ:</b> ___________________", meta_style),
        ],
        [
            Paragraph("М.П.                          Дата: _____________", meta_style),
            Paragraph("М.П.                          Дата: _____________", meta_style),
        ],
    ]
    sign_table = Table(sign_data, colWidths=[90 * mm, 90 * mm])
    sign_table.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 4)]))
    elements.append(KeepTogether(sign_table))

    doc.build(elements)
    return buffer.getvalue()
