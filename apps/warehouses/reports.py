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
from apps.warehouses.models import WarehouseDocument, WarehouseDocumentType


# Регистрация кириллических шрифтов DejaVuSans
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


def generate_qr_png_bytes(data: str, box_size: int = 8, border: int = 2) -> bytes:
    """Генерация PNG байтов QR-кода."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#173B35", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def generate_document_pdf(document: WarehouseDocument) -> bytes:
    """
    Генерация официального печатного PDF-документа складской накладной / акта
    с полным русскоязычным оформлением, табличной частью, QR-кодом и подписями.
    """
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

    styles = getSampleStyleSheet()

    # Стили с поддержкой кириллицы
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='DejaVuSans-Bold' if 'DejaVuSans-Bold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#173B35'),
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#6B7280'),
    )
    normal_style = ParagraphStyle(
        'DocNormal',
        parent=styles['Normal'],
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#252D29'),
    )
    bold_style = ParagraphStyle(
        'DocBold',
        parent=styles['Normal'],
        fontName='DejaVuSans-Bold' if 'DejaVuSans-Bold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#173B35'),
    )
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='DejaVuSans-Bold' if 'DejaVuSans-Bold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1,  # Center
    )
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
        fontSize=8,
        leading=11,
    )
    table_cell_right = ParagraphStyle(
        'TableCellRight',
        parent=styles['Normal'],
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
        fontSize=8,
        leading=11,
        alignment=2,  # Right
    )

    story = []

    # Шапка: Логотип/название компании + QR код документа
    qr_bytes = generate_qr_png_bytes(f"FURNICORE:{document.doc_number}:{document.warehouse.code}", box_size=4, border=1)
    qr_img = RLImage(io.BytesIO(qr_bytes), width=24 * mm, height=24 * mm)

    header_table_data = [
        [
            Paragraph("<b>ТОО «FurniCore Manufacturing»</b><br/>Мебельная фабрика полного цикла<br/>Республика Казахстан, г. Алматы", subtitle_style),
            qr_img
        ]
    ]
    header_table = Table(header_table_data, colWidths=[140 * mm, 35 * mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4 * mm))

    # Заголовок документа
    title_text = f"{document.get_doc_type_display().upper()}<br/>№ {document.doc_number}"
    story.append(Paragraph(title_text, title_style))
    story.append(Paragraph(f"Дата составления: {document.doc_date.strftime('%d.%m.%Y')} г. | Статус: {document.get_status_display()}", subtitle_style))
    story.append(Spacer(1, 4 * mm))

    # Реквизиты документа
    meta_info = [
        [
            Paragraph("<b>Склад:</b>", bold_style),
            Paragraph(f"{document.warehouse.code} — {document.warehouse.name}", normal_style),
            Paragraph("<b>Основание / Заказ:</b>", bold_style),
            Paragraph(
                document.sales_order.order_number if document.sales_order
                else (document.production_order.order_number if document.production_order else "—"),
                normal_style
            ),
        ],
        [
            Paragraph("<b>Контрагент:</b>", bold_style),
            Paragraph(
                document.supplier.name if document.supplier
                else (document.customer.full_name if document.customer else "Внутреннее перемещение"),
                normal_style
            ),
            Paragraph("<b>Ответственный:</b>", bold_style),
            Paragraph(document.created_by.get_full_name_ru() if document.created_by else "Система", normal_style),
        ]
    ]
    meta_table = Table(meta_info, colWidths=[35 * mm, 55 * mm, 45 * mm, 45 * mm])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 4 * mm))

    # Таблица позиций
    items = list(document.items.select_related('material', 'product').all())
    is_inventory = (document.doc_type == WarehouseDocumentType.INVENTORY)

    if is_inventory:
        table_headers = [
            Paragraph("№", table_header_style),
            Paragraph("Наименование ТМЦ", table_header_style),
            Paragraph("Артикул", table_header_style),
            Paragraph("Учёт", table_header_style),
            Paragraph("Факт", table_header_style),
            Paragraph("Разница", table_header_style),
            Paragraph("Ед.", table_header_style),
        ]
        table_col_widths = [10 * mm, 70 * mm, 30 * mm, 20 * mm, 20 * mm, 20 * mm, 10 * mm]
    else:
        table_headers = [
            Paragraph("№", table_header_style),
            Paragraph("Наименование номенклатуры", table_header_style),
            Paragraph("Артикул / Код", table_header_style),
            Paragraph("Кол-во", table_header_style),
            Paragraph("Ед.", table_header_style),
            Paragraph("Цена, ₸", table_header_style),
            Paragraph("Сумма, ₸", table_header_style),
        ]
        table_col_widths = [10 * mm, 65 * mm, 25 * mm, 20 * mm, 15 * mm, 22 * mm, 23 * mm]

    table_rows = [table_headers]

    for idx, item in enumerate(items, start=1):
        name = item.material.name if item.material else (item.product.name if item.product else '—')
        sku = item.material.sku if item.material else (item.product.sku if item.product else '—')

        if is_inventory:
            table_rows.append([
                Paragraph(str(idx), table_cell_style),
                Paragraph(name, table_cell_style),
                Paragraph(sku, table_cell_style),
                Paragraph(f"{item.quantity:.3f}", table_cell_right),
                Paragraph(f"{(item.actual_quantity or 0):.3f}", table_cell_right),
                Paragraph(f"{(item.discrepancy_quantity or 0):+.3f}", table_cell_right),
                Paragraph(item.unit, table_cell_style),
            ])
        else:
            table_rows.append([
                Paragraph(str(idx), table_cell_style),
                Paragraph(name, table_cell_style),
                Paragraph(sku, table_cell_style),
                Paragraph(f"{item.quantity:.3f}", table_cell_right),
                Paragraph(item.unit, table_cell_style),
                Paragraph(f"{item.unit_cost_kzt:,.2f}".replace(',', ' '), table_cell_right),
                Paragraph(f"{item.total_cost_kzt:,.2f}".replace(',', ' '), table_cell_right),
            ])

    items_table = Table(table_rows, colWidths=table_col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#173B35')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#173B35')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5 * mm),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 4 * mm))

    # Итог
    if not is_inventory:
        total_p = Paragraph(f"<b>ИТОГО К ОПЛАТЕ / УЧЁТУ:</b> {document.total_amount_kzt:,.2f} KZT (тенге)".replace(',', ' '), bold_style)
        story.append(total_p)
        story.append(Spacer(1, 4 * mm))

    # Примечания
    if document.notes:
        story.append(Paragraph(f"<b>Особые отметки:</b> {document.notes}", subtitle_style))
        story.append(Spacer(1, 6 * mm))

    # Блок подписей сторон
    signatures_data = [
        [
            Paragraph("<b>Отпустил (Сдал):</b><br/><br/>______________________ / ________________ /<br/>М.П.", normal_style),
            Paragraph("<b>Принял (Получил):</b><br/><br/>______________________ / ________________ /<br/>М.П.", normal_style),
        ]
    ]
    sig_table = Table(signatures_data, colWidths=[90 * mm, 90 * mm])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6 * mm),
    ]))
    story.append(KeepTogether(sig_table))

    doc.build(story)
    return buffer.getvalue()


def generate_item_label_pdf(item_type: str, item_obj) -> bytes:
    """
    Генерация термоэтикетки (размер 58x40 мм или 80x50 мм) с артикулом, штрихкодом,
    наименованием и QR-кодом для наклейки на сырье или коробку готовой мебели.
    """
    init_fonts()
    buffer = io.BytesIO()

    # Размер этикетки: 58mm x 40mm
    label_width = 58 * mm
    label_height = 40 * mm

    doc = SimpleDocTemplate(
        buffer,
        pagesize=(label_width, label_height),
        leftMargin=3 * mm,
        rightMargin=3 * mm,
        topMargin=2 * mm,
        bottomMargin=2 * mm,
    )

    name = item_obj.name[:35]
    sku = item_obj.sku
    barcode = getattr(item_obj, 'effective_barcode', sku)

    # Генерация QR
    qr_data = f"FURNICORE:{item_type.upper()}:{sku}:{barcode}"
    qr_bytes = generate_qr_png_bytes(qr_data, box_size=3, border=0)
    qr_img = RLImage(io.BytesIO(qr_bytes), width=18 * mm, height=18 * mm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'LabelTitle',
        parent=styles['Normal'],
        fontName='DejaVuSans-Bold' if 'DejaVuSans-Bold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold',
        fontSize=7,
        leading=8,
        textColor=colors.HexColor('#173B35'),
    )
    desc_style = ParagraphStyle(
        'LabelDesc',
        parent=styles['Normal'],
        fontName='DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
        fontSize=6,
        leading=7,
        textColor=colors.HexColor('#252D29'),
    )
    code_style = ParagraphStyle(
        'LabelCode',
        parent=styles['Normal'],
        fontName='DejaVuSans-Bold' if 'DejaVuSans-Bold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold',
        fontSize=8,
        leading=9,
        textColor=colors.HexColor('#173B35'),
    )

    story = [
        Paragraph("<b>FurniCore ERP</b> | Контроль ТМЦ", desc_style),
        Spacer(1, 1 * mm),
        Paragraph(name, title_style),
        Spacer(1, 1 * mm),
    ]

    label_table_data = [
        [
            [
                Paragraph(f"<b>АРТ:</b> {sku}", code_style),
                Spacer(1, 1 * mm),
                Paragraph(f"<b>ШК:</b> {barcode}", desc_style),
                Spacer(1, 1 * mm),
                Paragraph("Склад: " + ("WH-1 Сырьё" if item_type == 'material' else "WH-2 Продукция"), desc_style),
            ],
            qr_img
        ]
    ]
    t = Table(label_table_data, colWidths=[33 * mm, 19 * mm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(t)

    doc.build(story)
    return buffer.getvalue()
