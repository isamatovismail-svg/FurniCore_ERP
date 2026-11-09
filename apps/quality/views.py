from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.quality.models import QualityCheck, QCResult
from apps.production.models import ProductionOrder, ProductionOrderStatus


@login_required
def index(request):
    checks = QualityCheck.objects.select_related('production_order', 'checked_by').order_by('-checked_at')
    orders_in_qc = ProductionOrder.objects.filter(
        status__in=[ProductionOrderStatus.QC_CHECK, ProductionOrderStatus.COMPLETED]
    ).select_related('product')

    pass_count = QualityCheck.objects.filter(result=QCResult.PASS).count()
    defect_count = QualityCheck.objects.filter(result=QCResult.FAIL).count()
    rework_count = QualityCheck.objects.filter(result=QCResult.REWORK).count()

    context = {
        'page_title': 'Контроль качества (ОТК)',
        'checks': checks,
        'orders_in_qc': orders_in_qc,
        'pass_count': pass_count,
        'defect_count': defect_count,
        'rework_count': rework_count,
        'total_checks': QualityCheck.objects.count(),
    }
    return render(request, 'quality/index.html', context)
