from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from apps.ai_assistant.models import ChatSession, ChatMessage
from apps.ai_assistant.services import process_ai_query, get_ai_config


@login_required
def index(request):
    """Main AI Assistant chat interface supporting OpenAI backend and DEMO AI MODE."""
    session, _ = ChatSession.objects.get_or_create(
        user=request.user,
        defaults={'title': 'Диалог с AI-ассистентом FurniCore'}
    )

    ai_config = get_ai_config()

    if request.method == 'POST':
        query = request.POST.get('query', '').strip()
        if query:
            # 1. Store user message
            ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_USER, content=query)

            # 2. Process query via backend AI service (OpenAI or DEMO AI MODE)
            reply, mode = process_ai_query(query)

            # 3. Store assistant response
            ChatMessage.objects.create(session=session, role=ChatMessage.ROLE_ASSISTANT, content=reply)

            if request.headers.get('HX-Request') or request.GET.get('format') == 'json':
                return JsonResponse({
                    'status': 'ok',
                    'reply': reply,
                    'mode': mode
                })

            return redirect('ai_assistant:index')

    messages = session.messages.order_by('created_at')

    context = {
        'page_title': 'AI-ассистент FurniCore',
        'session': session,
        'chat_messages': messages,
        'ai_config': ai_config,
    }
    return render(request, 'ai_assistant/index.html', context)


@login_required
def settings_view(request):
    """Settings and connection guide for OpenAI API integration."""
    ai_config = get_ai_config()
    context = {
        'page_title': 'Настройки AI-ассистента',
        'ai_config': ai_config,
    }
    return render(request, 'ai_assistant/settings.html', context)
