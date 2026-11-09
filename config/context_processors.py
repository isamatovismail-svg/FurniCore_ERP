from django.conf import settings

def furnicore_global_context(request):
    """Global template variables for FurniCore ERP."""
    return {
        'COMPANY_NAME': getattr(settings, 'COMPANY_NAME', 'FurniCore ERP'),
        'CURRENCY_CODE': getattr(settings, 'CURRENCY_CODE', 'KZT'),
        'CURRENCY_SYMBOL': getattr(settings, 'CURRENCY_SYMBOL', '₸'),
        'CURRENT_USER': request.user if request.user.is_authenticated else None,
    }
