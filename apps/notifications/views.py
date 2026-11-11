from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.notifications.models import Notification, NotificationType


@login_required
def index(request):
    """Центр уведомлений пользователя с фильтрами по статусу и типу."""
    type_filter = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')

    notifications = request.user.notifications.all()

    if type_filter:
        notifications = notifications.filter(notification_type=type_filter)
    if status_filter == 'unread':
        notifications = notifications.filter(is_read=False)
    elif status_filter == 'read':
        notifications = notifications.filter(is_read=True)

    notifications = notifications.order_by('-created_at')[:100]

    unread_count = request.user.notifications.filter(is_read=False).count()
    total_count = request.user.notifications.count()

    context = {
        'page_title': 'Уведомления',
        'notifications': notifications,
        'types': NotificationType.choices,
        'selected_type': type_filter,
        'status_filter': status_filter,
        'unread_count': unread_count,
        'total_count': total_count,
    }
    return render(request, 'notifications/index.html', context)


@login_required
def mark_as_read(request, pk):
    """Пометить уведомление как прочитанное и перейти по ссылке (если есть)."""
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])

    if notif.link:
        return redirect(notif.link)
    return redirect('notifications:index')


@login_required
def mark_all_as_read(request):
    """Пометить все уведомления текущего пользователя как прочитанные."""
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, 'Все уведомления отмечены как прочитанные.')
    return redirect('notifications:index')
