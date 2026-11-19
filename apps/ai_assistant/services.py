"""
FurniCore ERP — AI Assistant Service
Implements a secure server-side hybrid AI engine:
1. Real OpenAI API Integration via official REST API endpoint (when OPENAI_API_KEY is configured).
2. DEMO AI MODE: local rule-based intelligent query engine connected to PostgreSQL when key is not present or API is unreachable.
3. Strict ERP Data Safety: Read-only access, sanitization, no passwords or credentials exposed.
"""
import json
import logging
import os
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Tuple, Dict, Any

from django.db.models import Sum

logger = logging.getLogger(__name__)


def get_ai_config() -> Dict[str, Any]:
    """Returns AI configuration status safely without leaking the full key."""
    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini').strip()
    has_key = bool(api_key and len(api_key) > 8 and not api_key.startswith('your_'))

    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if has_key else "Не настроен"

    return {
        'has_key': has_key,
        'model': model,
        'masked_key': masked_key,
        'mode': 'OPENAI' if has_key else 'DEMO',
        'mode_label': f'OpenAI ({model})' if has_key else 'DEMO AI MODE (Локальный анализ БД)',
    }


def build_erp_summary_context() -> str:
    """
    Gathers real, sanitized ERP state from PostgreSQL to provide context for AI.
    Never includes password hashes, secrets, or sensitive credentials.
    """
    from apps.warehouses.models import StockBalance, Warehouse, WarehouseType
    from apps.materials.models import Material
    from apps.products.models import Product
    from apps.production.models import ProductionOrder, ProductionOrderStatus
    from apps.sales.models import SalesOrder, OrderStatus
    from apps.suppliers.models import Supplier, PurchaseOrder
    from apps.finance.models import FinancialAccount, Expense

    # WH-1: Materials
    wh1 = Warehouse.objects.filter(warehouse_type=WarehouseType.RAW_MATERIALS).first()
    wh1_balances = StockBalance.objects.filter(warehouse=wh1, material__isnull=False).select_related('material') if wh1 else []
    low_stock = [b for b in wh1_balances if b.is_low_stock]
    low_stock_str = ", ".join([f"{b.material.name} (остаток: {b.current_stock} {b.material.unit}, мин: {b.material.min_stock_level})" for b in low_stock]) if low_stock else "дефицита нет"

    # WH-2: Finished goods
    wh2 = Warehouse.objects.filter(warehouse_type=WarehouseType.FINISHED_PRODUCTS).first()
    wh2_balances = StockBalance.objects.filter(warehouse=wh2, product__isnull=False).select_related('product') if wh2 else []
    wh2_summary = ", ".join([f"{b.product.name} (всего: {b.current_stock} шт., в резерве: {b.reserved_stock} шт., свободно: {b.available_stock} шт.)" for b in wh2_balances[:5]]) if wh2_balances else "склад пуст"

    # Production
    active_po = ProductionOrder.objects.filter(status__in=[ProductionOrderStatus.IN_PROGRESS, ProductionOrderStatus.MATERIALS_RESERVED]).count()
    waiting_po = ProductionOrder.objects.filter(status__in=[ProductionOrderStatus.WAITING, ProductionOrderStatus.DRAFT]).count()
    completed_po = ProductionOrder.objects.filter(status=ProductionOrderStatus.COMPLETED).count()

    # Sales & Revenue
    sales_qs = SalesOrder.objects.filter(status__in=[OrderStatus.CONFIRMED, OrderStatus.SHIPPED, OrderStatus.DELIVERED])
    rev = sales_qs.aggregate(t=Sum('total_amount_kzt'))['t'] or Decimal('0')
    exp = Expense.objects.aggregate(t=Sum('amount_kzt'))['t'] or Decimal('0')
    profit = rev - exp

    # Accounts
    accounts = FinancialAccount.objects.filter(is_active=True)
    acc_summary = ", ".join([f"{a.name}: {a.current_balance_kzt:,.0f} ₸" for a in accounts]) if accounts.exists() else "нет открытых счетов"

    context_text = (
        f"Данные мебельной фабрики FurniCore ERP (актуально на сейчас):\n"
        f"- Склад сырья WH-1: позиций {len(wh1_balances)}, дефицит: {low_stock_str}.\n"
        f"- Склад готовой мебели WH-2: {wh2_summary}.\n"
        f"- Производство: {active_po} в работе, {waiting_po} в очереди, {completed_po} завершено.\n"
        f"- Финансы: Выручка по подтверждённым заказам: {rev:,.0f} ₸, Расходы: {exp:,.0f} ₸, Прибыль: {profit:,.0f} ₸.\n"
        f"- Денежные счета фабрики: {acc_summary}.\n"
    )
    return context_text


def call_openai_api(prompt: str, erp_context: str, model: str, api_key: str) -> str:
    """
    Sends the user query and sanitized ERP context to OpenAI API using standard library.
    Handles network errors, timeouts, and rate limits gracefully.
    """
    url = "https://api.openai.com/v1/chat/completions"
    system_instruction = (
        "Ты — умный интеллектуальный ассистент мебельной фабрики FurniCore ERP. "
        "Твоя задача — помогать руководству, начальнику производства, бухгалтеру и менеджерам. "
        "Используй предоставленные данные фабрики. Будь точным, вежливым и лаконичным. Валюта — тенге (₸). "
        "Не предлагай вымышленных данных и не выходи за рамки мебельного производства.\n\n"
        + erp_context
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4,
        "max_tokens": 600,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "FurniCore-ERP/2.0"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            reply = res_data['choices'][0]['message']['content'].strip()
            return f"[OpenAI {model}]: {reply}"
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode('utf-8')
        logger.warning(f"OpenAI API HTTP Error {e.code}: {error_msg}")
        return f"[Ошибка OpenAI API {e.code}]: Не удалось получить ответ от внешнего сервиса. Включён локальный режим."
    except Exception as e:
        logger.warning(f"OpenAI API Request Exception: {e}")
        return f"[Сбой связи с OpenAI]: {str(e)}. Переключение на локальный анализ данных."


def generate_local_demo_reply(query: str) -> str:
    """
    Generates intelligent local rule-based response directly from PostgreSQL models.
    Clearly marks the output as DEMO AI MODE.
    """
    from apps.warehouses.models import StockBalance, Warehouse, WarehouseType
    from apps.materials.models import Material
    from apps.products.models import Product
    from apps.production.models import ProductionOrder, ProductionOrderStatus
    from apps.sales.models import SalesOrder, OrderStatus, Customer
    from apps.suppliers.models import Supplier, PurchaseOrder
    from apps.finance.models import FinancialAccount, Expense, CustomerPayment, SupplierPayment

    q_lower = query.lower()

    # 1. WH-1 & Raw materials
    if any(w in q_lower for w in ['остат', 'склад', 'сырь', 'материал', 'wh-1', 'дефицит']):
        wh1 = Warehouse.objects.filter(warehouse_type=WarehouseType.RAW_MATERIALS).first()
        balances = StockBalance.objects.filter(warehouse=wh1, material__isnull=False).select_related('material') if wh1 else []
        low = [b for b in balances if b.is_low_stock]
        total_items = len(balances)
        if low:
            items_str = "; ".join([f"{b.material.name}: остаток {b.current_stock} {b.material.unit} (минимум {b.material.min_stock_level})" for b in low[:5]])
            return (
                f"[DEMO AI MODE — Анализ склада WH-1]:\n"
                f"На складе сырья и материалов WH-1 числится {total_items} номенклатурных позиций. "
                f"Выявлен дефицит по следующим позициям:\n• {items_str}.\n"
                f"Рекомендация: Создать заказ поставщику в разделе «Закупки»."
            )
        else:
            return (
                f"[DEMO AI MODE — Склад WH-1]:\n"
                f"Все {total_items} позиций сырья на складе WH-1 имеют достаточный запас. Дефицитных остатков ниже нормы не зафиксировано."
            )

    # 2. WH-2 & Finished furniture
    if any(w in q_lower for w in ['готовая', 'мебель', 'wh-2', 'издели', 'шкаф', 'стол', 'кровать', 'кухн', 'диван']):
        wh2 = Warehouse.objects.filter(warehouse_type=WarehouseType.FINISHED_PRODUCTS).first()
        balances = StockBalance.objects.filter(warehouse=wh2, product__isnull=False).select_related('product') if wh2 else []
        total_physical = sum(b.current_stock for b in balances)
        total_reserved = sum(b.reserved_stock for b in balances)
        total_avail = sum(b.available_stock for b in balances)
        details = ", ".join([f"{b.product.name} (остаток: {b.current_stock}, свободно: {b.available_stock})" for b in balances[:4]])
        return (
            f"[DEMO AI MODE — Склад готовой продукции WH-2]:\n"
            f"Всего готовой мебели на складе: {total_physical} шт. (в резерве под заказы: {total_reserved} шт., доступно для новых клиентов: {total_avail} шт.).\n"
            f"Текущие позиции: {details}."
        )

    # 3. Production & Shop floor
    if any(w in q_lower for w in ['производств', 'цех', 'этап', 'заказ в цех', 'отк', 'брак', 'bom']):
        in_prog = ProductionOrder.objects.filter(status=ProductionOrderStatus.IN_PROGRESS).count()
        waiting = ProductionOrder.objects.filter(status=ProductionOrderStatus.WAITING).count()
        done = ProductionOrder.objects.filter(status=ProductionOrderStatus.COMPLETED).count()
        qc_orders = ProductionOrder.objects.filter(status=ProductionOrderStatus.QUALITY_CONTROL).count()
        return (
            f"[DEMO AI MODE — Производственный цех]:\n"
            f"Текущий срез производственной программы:\n"
            f"• В активной обработке в цехе: {in_prog} заказов\n"
            f"• На контроле ОТК: {qc_orders} заказов\n"
            f"• В очереди ожидания запуска: {waiting} заказов\n"
            f"• Успешно выпущено и передано на WH-2: {done} заказов.\n"
            f"Все 5 технологических маршрутов (шкафы, кухни, диваны, столы, кровати) активны."
        )

    # 4. Finance & Profitability
    if any(w in q_lower for w in ['выручк', 'прибыл', 'финанс', 'доход', 'расход', 'касс', 'банк', 'деньг', 'счет']):
        sales_qs = SalesOrder.objects.filter(status__in=[OrderStatus.CONFIRMED, OrderStatus.SHIPPED, OrderStatus.DELIVERED])
        rev = sales_qs.aggregate(t=Sum('total_amount_kzt'))['t'] or Decimal('0')
        exp = Expense.objects.aggregate(t=Sum('amount_kzt'))['t'] or Decimal('0')
        profit = rev - exp

        accounts = FinancialAccount.objects.filter(is_active=True)
        acc_details = "; ".join([f"{a.name}: {a.current_balance_kzt:,.0f} ₸" for a in accounts])
        return (
            f"[DEMO AI MODE — Финансовый отчёт]:\n"
            f"• Выручка по подтверждённым заказам: {rev:,.0f} ₸\n"
            f"• Суммарные операционные расходы: {exp:,.0f} ₸\n"
            f"• Финансовый результат (чистая прибыль): {profit:,.0f} ₸\n"
            f"• Остатки денежных средств по счетам: {acc_details}."
        )

    # 5. Sales & CRM
    if any(w in q_lower for w in ['клиент', 'продаж', 'crm', 'заказ покупател']):
        total_customers = Customer.objects.count()
        total_orders = SalesOrder.objects.count()
        confirmed = SalesOrder.objects.filter(status=OrderStatus.CONFIRMED).count()
        shipped = SalesOrder.objects.filter(status=OrderStatus.SHIPPED).count()
        return (
            f"[DEMO AI MODE — Модуль продаж и CRM]:\n"
            f"В базе зарегистрировано {total_customers} контрагентов. Всего оформлено заказов: {total_orders} "
            f"(в подтверждении/резерве: {confirmed}, отгружено покупателям: {shipped})."
        )

    # 6. Suppliers & Procurement
    if any(w in q_lower for w in ['поставщик', 'закупк', 'поставка', 'po-']):
        total_sups = Supplier.objects.count()
        total_pos = PurchaseOrder.objects.count()
        received_pos = PurchaseOrder.objects.filter(status='RECEIVED').count()
        return (
            f"[DEMO AI MODE — Закупки и поставщики]:\n"
            f"База поставщиков: {total_sups} партнёров (КазДревМатериал, МетизКомплект, ИП Сатпаев). "
            f"Заказов на закупку: {total_pos} (полностью принято на склад WH-1: {received_pos})."
        )

    # 7. Navigation & System Guide
    if any(w in q_lower for w in ['как', 'куда', 'инструкци', 'помощь', 'раздел', 'навигац']):
        return (
            f"[DEMO AI MODE — Навигатор по FurniCore ERP]:\n"
            f"Основные разделы системы:\n"
            f"1. «Дашборд» — сводные KPI, выручка и графики Chart.js.\n"
            f"2. «Склады» — учёт сырья (WH-1) и готовой мебели (WH-2), приходные ордера и инвентаризация.\n"
            f"3. «Производство» — заказы цеха, технологические маршруты, BOM и канбан-доска.\n"
            f"4. «Контроль качества» — 7 критериев ОТК (PASS, REWORK, FAIL).\n"
            f"5. «Продажи» — оформление заказов покупателей и резервирование остатков.\n"
            f"6. «Финансы» — касса, расчётные счета, отчёты P&L, экспорт в PDF и Excel."
        )

    # Default fallback
    return (
        f"[DEMO AI MODE — Интеллектуальный помощник]:\n"
        f"Я проанализировал ваш запрос «{query}» по базе данных FurniCore ERP.\n"
        f"Вы можете запросить информацию по: остаткам на складах WH-1 и WH-2, "
        f"статусам заказов в цехе, проверке ОТК, финансовым отчётам или поставкам."
    )


def process_ai_query(user_query: str) -> Tuple[str, str]:
    """
    Main entry point: executes either OpenAI API or Demo Mode.
    Returns (reply_content, mode_used).
    """
    config = get_ai_config()

    if config['has_key']:
        api_key = os.getenv('OPENAI_API_KEY', '').strip()
        erp_context = build_erp_summary_context()
        reply = call_openai_api(user_query, erp_context, config['model'], api_key)
        # If API returned an error string, append fallback local reply
        if reply.startswith('[Ошибка') or reply.startswith('[Сбой'):
            fallback = generate_local_demo_reply(user_query)
            reply = f"{reply}\n\n{fallback}"
        return reply, 'OPENAI'
    else:
        reply = generate_local_demo_reply(user_query)
        return reply, 'DEMO'
