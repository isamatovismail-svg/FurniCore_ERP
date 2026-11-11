from django.conf import settings


def furnicore_global_context(request):
    """Global template variables for FurniCore ERP."""
    unread_count = 0
    if request.user.is_authenticated:
        try:
            unread_count = request.user.notifications.filter(is_read=False).count()
        except Exception:
            unread_count = 0

    return {
        'COMPANY_NAME': getattr(settings, 'COMPANY_NAME', 'FurniCore ERP'),
        'CURRENCY_CODE': getattr(settings, 'CURRENCY_CODE', 'KZT'),
        'CURRENCY_SYMBOL': getattr(settings, 'CURRENCY_SYMBOL', '₸'),
        'CURRENT_USER': request.user if request.user.is_authenticated else None,
        'unread_notifications': unread_count,
    }
