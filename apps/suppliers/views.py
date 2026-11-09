from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from apps.suppliers.models import Supplier


@login_required
def index(request):
    q = request.GET.get('q', '').strip()
    suppliers = Supplier.objects.prefetch_related('materials').all()
    if q:
        suppliers = suppliers.filter(
            Q(name__icontains=q) |
            Q(contact_person__icontains=q) |
            Q(phone__icontains=q) |
            Q(address__icontains=q)
        )
    suppliers = suppliers.order_by('name')

    context = {
        'page_title': 'Поставщики',
        'suppliers': suppliers,
        'q': q,
        'total_suppliers': Supplier.objects.count(),
    }
    return render(request, 'suppliers/index.html', context)
