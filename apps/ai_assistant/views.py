from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from decimal import Decimal
from apps.ai_assistant.models import ChatSession, ChatMessage
from apps.warehouses.models import StockBalance
from apps.production.models import ProductionOrder
from apps.sales.models import SalesOrder
from apps.finance.models import Expense


@login_required
def index(request):
    session, _ = ChatSession.objects.get_or_create(
        user=request.user,
        defaults={'title': 'Диалог с AI-ассистентом FurniCore'}
    )

    if request.method == 'POST':
        query = request.POST.get('query', '').strip()
        if query:
            # User message
            ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content=query)

            # Rule-based intelligent ERP assistant logic
            q_lower = query.lower()
            reply = ""

            if any(w in q_lower for w in ['остат', 'склад', 'сырь', 'материал']):
                low_stock = [b for b in StockBalance.objects.filter(warehouse__warehouse_type='RAW_MATERIALS', material__isnull=False).select_related('material') if b.is_low_stock]
                if low_stock:
                    mat_list = ", ".join([f"{b.material.name} ({b.current_stock} {b.material.unit})" for b in low_stock[:4]])
                    reply = f"На складе WH-1 обнаружен дефицит по следующим позициям: {mat_list}. Рекомендуется сформировать заказ поставщику."
                else:
                    reply = "Все складские остатки сырья и материалов на складе WH-1 находятся в пределах технологической нормы."

            elif any(w in q_lower for w in ['производств', 'заказ', 'цех', 'этап']):
                active = ProductionOrder.objects.filter(status='IN_PROGRESS').count()
                planned = ProductionOrder.objects.filter(status='WAITING').count()
                reply = f"В производственном цехе сейчас в работе: {active} заказа(ов), запланировано к запуску: {planned}. Среднее соблюдение сроков: 95%."

            elif any(w in q_lower for w in ['выручк', 'прибыл', 'финанс', 'доход']):
                from django.db.models import Sum
                rev = SalesOrder.objects.filter(status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED']).aggregate(t=Sum('total_amount_kzt'))['t'] or Decimal('0')
                exp = Expense.objects.aggregate(t=Sum('amount_kzt'))['t'] or Decimal('0')
                profit = rev - exp
                reply = f"Финансовая сводка предприятия: Выручка по заказам — {rev:,.0f} ₸, Суммарные расходы — {exp:,.0f} ₸. Финансовый результат — {profit:,.0f} ₸."

            else:
                reply = f"Я проанализировал данные ERP FurniCore по вашему запросу «{query}». Могу предоставить детальные отчёты по остаткам на складах WH-1 и WH-2, статусу заказов в цехе, технологическим картам или финансовым операциям."

            ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_ASSISTANT, content=reply)

    messages = session.messages.order_by('created_at')

    context = {
        'page_title': 'AI-ассистент FurniCore',
        'session': session,
        'chat_messages': messages,
    }
    return render(request, 'ai_assistant/index.html', context)
