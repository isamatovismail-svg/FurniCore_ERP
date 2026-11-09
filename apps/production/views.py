import json
from decimal import Decimal
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Sum, Count, Q, Avg, F
from django.utils import timezone
from apps.accounts.models import UserRole
from apps.production.models import (
    ProductionOrder,
    ProductionOrderStatus,
    OrderPriority,
    ProductionStage,
    StageStatus,
    BOM,
    BOMItem,
    MaterialConsumption,
    ProductionWaste,
    WasteType,
    RoutingTemplate,
    RoutingStage,
)
from apps.products.models import Product, ProductCategory
from apps.materials.models import Material
from apps.employees.models import Employee, Department
from apps.sales.models import SalesOrder
from apps.quality.models import QualityCheck, QCResult
from apps.production.forms import (
    ProductionOrderForm,
    BOMForm,
    QualityCheckForm,
    ProductionWasteForm,
)
from apps.production.services import (
    check_materials_availability,
    issue_materials_for_production,
    launch_production_order,
    advance_stage,
    register_waste_or_defect,
    submit_quality_check,
    complete_and_transfer_to_warehouse,
    recalculate_order_costs,
    ensure_default_routing_templates,
)


def can_manage_production(user) -> bool:
    return user.is_authenticated and (
        user.is_superuser or
        user.role in [UserRole.OWNER, UserRole.ADMIN, UserRole.PRODUCTION_MANAGER]
    )


def generate_po_number() -> str:
    year = timezone.now().year
    count = ProductionOrder.objects.filter(order_number__startswith=f'PO-{year}').count() + 1
    return f'PO-{year}-{count:03d}'


# ==============================================================================
# 1. ПРОИЗВОДСТВЕННЫЙ DASHBOARD
# ==============================================================================

@login_required
def index(request):
    ensure_default_routing_templates()

    tab = request.GET.get('tab', 'dashboard')
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    q = request.GET.get('q', '').strip()

    orders_qs = ProductionOrder.objects.select_related(
        'product', 'variant', 'bom', 'created_by', 'assigned_master', 'sales_order'
    ).prefetch_related('stages', 'stages__assigned_employee')

    if status_filter:
        orders_qs = orders_qs.filter(status=status_filter)
    if priority_filter:
        orders_qs = orders_qs.filter(priority=priority_filter)
    if q:
        orders_qs = orders_qs.filter(
            Q(order_number__icontains=q) |
            Q(product__name__icontains=q) |
            Q(product__sku__icontains=q) |
            Q(notes__icontains=q)
        )

    all_orders = list(orders_qs.order_by('-created_at'))

    today = timezone.localdate()
    # Сводные показатели
    total_orders = ProductionOrder.objects.count()
    active_orders = ProductionOrder.objects.filter(
        status__in=[
            ProductionOrderStatus.MATERIALS_RESERVED,
            ProductionOrderStatus.IN_PROGRESS,
            ProductionOrderStatus.QC_CHECK,
            ProductionOrderStatus.REWORK,
            ProductionOrderStatus.READY,
        ]
    ).count()

    waiting_orders = ProductionOrder.objects.filter(
        status__in=[ProductionOrderStatus.DRAFT, ProductionOrderStatus.WAITING, ProductionOrderStatus.CHECKING_MATERIALS]
    ).count()

    in_progress_orders = ProductionOrder.objects.filter(status=ProductionOrderStatus.IN_PROGRESS).count()
    qc_orders = ProductionOrder.objects.filter(status=ProductionOrderStatus.QC_CHECK).count()
    rework_orders = ProductionOrder.objects.filter(status=ProductionOrderStatus.REWORK).count()
    completed_orders = ProductionOrder.objects.filter(status=ProductionOrderStatus.COMPLETED).count()

    # Просроченные заказы (плановая дата окончания прошла, а заказ не завершён)
    overdue_orders = ProductionOrder.objects.filter(
        planned_end__lt=today
    ).exclude(status__in=[ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CANCELLED]).count()

    # Выпущено готовой мебели
    total_produced_items = ProductionOrder.objects.filter(
        status=ProductionOrderStatus.COMPLETED
    ).aggregate(total=Sum('quantity_produced'))['total'] or Decimal('0.00')

    # Процент выполнения плана
    total_planned_items = ProductionOrder.objects.exclude(
        status=ProductionOrderStatus.CANCELLED
    ).aggregate(total=Sum('quantity_planned'))['total'] or Decimal('1.00')

    plan_completion_pct = int(round((total_produced_items / total_planned_items) * 100)) if total_planned_items > 0 else 0

    # Загрузка мастеров цеха
    production_employees = Employee.objects.filter(department=Department.PRODUCTION).select_related('user')
    employees_load = []
    for emp in production_employees:
        active_tasks = ProductionStage.objects.filter(
            assigned_employee=emp,
            status=StageStatus.IN_PROGRESS
        ).count()
        pending_tasks = ProductionStage.objects.filter(
            assigned_employee=emp,
            status=StageStatus.PENDING
        ).count()
        employees_load.append({
            'employee': emp,
            'active_tasks': active_tasks,
            'pending_tasks': pending_tasks,
            'total_assigned': active_tasks + pending_tasks,
        })

    # Графики: 1. Выпуск по категориям мебели
    category_labels = []
    category_counts = []
    for cat_code, cat_name in ProductCategory.choices:
        cnt = ProductionOrder.objects.filter(
            product__category=cat_code,
            status=ProductionOrderStatus.COMPLETED
        ).aggregate(total=Sum('quantity_produced'))['total'] or 0
        category_labels.append(str(cat_name))
        category_counts.append(float(cnt))

    # 2. Выпуск по дням (последние 7 дней)
    day_labels = []
    day_counts = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_str = day.strftime('%d.%m')
        cnt = ProductionOrder.objects.filter(
            actual_end=day,
            status=ProductionOrderStatus.COMPLETED
        ).aggregate(total=Sum('quantity_produced'))['total'] or 0
        day_labels.append(day_str)
        day_counts.append(float(cnt))

    # 3. Загруженность производственных участков
    workstation_stages = ProductionStage.objects.filter(
        status=StageStatus.IN_PROGRESS
    ).values('workstation').annotate(count=Count('id')).order_by('-count')[:6]

    ws_labels = [w['workstation'] or 'Сборочный участок' for w in workstation_stages]
    ws_counts = [w['count'] for w in workstation_stages]
    if not ws_labels:
        ws_labels = ['Раскрой ЧПУ', 'Кромление', 'Сборка каркаса', 'Обивка', 'ОТК']
        ws_counts = [3, 2, 4, 1, 2]

    context = {
        'page_title': 'Управление производством',
        'tab': tab,
        'orders': all_orders,
        'statuses': ProductionOrderStatus.choices,
        'priorities': OrderPriority.choices,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'q': q,

        # Метрики
        'total_orders': total_orders,
        'active_orders': active_orders,
        'waiting_orders': waiting_orders,
        'in_progress_orders': in_progress_orders,
        'qc_orders': qc_orders,
        'rework_orders': rework_orders,
        'completed_orders': completed_orders,
        'overdue_orders': overdue_orders,
        'total_produced_items': total_produced_items,
        'plan_completion_pct': plan_completion_pct,
        'employees_load': employees_load,

        # Графики JSON для Chart.js
        'chart_categories_json': json.dumps({'labels': category_labels, 'data': category_counts}),
        'chart_days_json': json.dumps({'labels': day_labels, 'data': day_counts}),
        'chart_workstations_json': json.dumps({'labels': ws_labels, 'data': ws_counts}),

        'can_manage': can_manage_production(request.user),
    }
    return render(request, 'production/index.html', context)


# ==============================================================================
# 2. CRUD ПРОИЗВОДСТВЕННЫХ ЗАКАЗОВ
# ==============================================================================

@login_required
def order_create(request):
    if not can_manage_production(request.user):
        messages.error(request, 'У вас недостаточно прав для создания производственных заказов.')
        return redirect('production:index')

    if request.method == 'POST':
        form = ProductionOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.order_number = generate_po_number()
            order.created_by = request.user
            order.status = ProductionOrderStatus.WAITING

            # Если выбран BOM, берем плановую себестоимость
            if order.bom:
                recalculate_order_costs(order)
            else:
                # Находим активный BOM изделия
                default_bom = BOM.objects.filter(product=order.product, is_active=True).first()
                if default_bom:
                    order.bom = default_bom
                    recalculate_order_costs(order)

            order.save()
            form.save_m2m()

            # Инициализация этапов маршрута
            initialize_order_stages(order)

            messages.success(request, f'Производственный заказ {order.order_number} успешно сформирован.')
            return redirect('production:detail', pk=order.id)
    else:
        initial = {
            'planned_start': timezone.localdate(),
            'planned_end': timezone.localdate() + datetime.timedelta(days=14),
            'priority': OrderPriority.NORMAL,
        }
        product_id = request.GET.get('product')
        if product_id:
            initial['product'] = product_id
            default_bom = BOM.objects.filter(product_id=product_id, is_active=True).first()
            if default_bom:
                initial['bom'] = default_bom.id

        form = ProductionOrderForm(initial=initial)

    boms_by_product = {
        str(b.product_id): {'id': str(b.id), 'name': f'{b.name} v{b.version}'}
        for b in BOM.objects.filter(is_active=True)
    }

    context = {
        'page_title': 'Новый производственный заказ',
        'form': form,
        'boms_json': json.dumps(boms_by_product),
    }
    return render(request, 'production/create.html', context)


@login_required
def order_edit(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)

    if not can_manage_production(request.user):
        messages.error(request, 'Недостаточно прав для редактирования заказа.')
        return redirect('production:detail', pk=order.id)

    if order.status in [ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CANCELLED]:
        messages.warning(request, 'Завершённый или отменённый заказ нельзя редактировать.')
        return redirect('production:detail', pk=order.id)

    if request.method == 'POST':
        form = ProductionOrderForm(request.POST, instance=order)
        if form.is_valid():
            updated_order = form.save()
            recalculate_order_costs(updated_order)
            messages.success(request, f'Заказ {updated_order.order_number} обновлён.')
            return redirect('production:detail', pk=order.id)
    else:
        form = ProductionOrderForm(instance=order)

    context = {
        'page_title': f'Редактирование {order.order_number}',
        'order': order,
        'form': form,
    }
    return render(request, 'production/edit.html', context)


@login_required
def detail(request, pk):
    order = get_object_or_404(
        ProductionOrder.objects.select_related(
            'product', 'variant', 'bom', 'created_by', 'assigned_master', 'sales_order'
        ),
        pk=pk
    )

    stages = list(order.stages.select_related('assigned_employee').order_by('sequence'))
    consumptions = order.material_consumptions.select_related('material').all()
    wastes = order.wastes.select_related('material', 'stage', 'reported_by').all()
    quality_checks = order.quality_checks.select_related('checked_by').order_by('-checked_at')

    # Анализ потребности и наличия материалов на складе WH-1
    materials_analysis = check_materials_availability(order)

    can_manage = can_manage_production(request.user)
    is_worker = hasattr(request.user, 'employee_profile') and (
        request.user.employee_profile.department == Department.PRODUCTION
    )

    context = {
        'page_title': f'Производственный заказ {order.order_number}',
        'order': order,
        'stages': stages,
        'consumptions': consumptions,
        'wastes': wastes,
        'quality_checks': quality_checks,
        'materials_analysis': materials_analysis,
        'can_manage': can_manage,
        'is_worker': is_worker,
    }
    return render(request, 'production/detail.html', context)


# ==============================================================================
# 3. ОПЕРАТИВНЫЕ ДЕЙСТВИЯ: ВЫДАЧА СЫРЬЯ, ЗАПУСК, ЭТАПЫ, ОТК, ПРИЁМКА НА WH-2
# ==============================================================================

@login_required
@require_POST
def order_issue_materials(request, pk):
    """Выдача материалов со склада WH-1 под заказ."""
    order = get_object_or_404(ProductionOrder, pk=pk)

    if not can_manage_production(request.user):
        messages.error(request, 'У вас недостаточно прав для выдачи материалов.')
        return redirect('production:detail', pk=order.id)

    try:
        doc = issue_materials_for_production(order, user=request.user)
        messages.success(request, f'Материалы успешно списаны с WH-1 по накладной {doc.doc_number}.')
    except Exception as e:
        messages.error(request, f'Ошибка выдачи материалов: {e}')

    return redirect('production:detail', pk=order.id)


@login_required
@require_POST
def order_launch(request, pk):
    """Запуск заказа в производство."""
    order = get_object_or_404(ProductionOrder, pk=pk)

    if not can_manage_production(request.user):
        messages.error(request, 'У вас недостаточно прав для запуска заказа.')
        return redirect('production:detail', pk=order.id)

    try:
        launch_production_order(order, user=request.user)
        messages.success(request, f'Заказ {order.order_number} запущен в работу цеха. Первый этап активирован.')
    except Exception as e:
        messages.error(request, f'Не удалось запустить заказ: {e}')

    return redirect('production:detail', pk=order.id)


@login_required
@require_POST
def stage_advance_action(request, stage_id):
    """Фиксация завершения этапа мастером."""
    stage = get_object_or_404(ProductionStage.objects.select_related('production_order'), pk=stage_id)
    order = stage.production_order

    actual_hours = request.POST.get('actual_hours')
    quantity_processed = request.POST.get('quantity_processed')
    notes = request.POST.get('notes', '').strip()

    try:
        advance_stage(
            stage,
            user=request.user,
            actual_hours=actual_hours,
            quantity_processed=quantity_processed,
            notes=notes
        )
        messages.success(request, f'Этап "{stage.stage_name}" завершён. Прогресс сохранён.')
    except Exception as e:
        messages.error(request, f'Ошибка при завершении этапа: {e}')

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER')
    return redirect(next_url or 'production:detail', pk=order.id)


@login_required
def order_qc_inspect(request, pk):
    """Страница и форма контроля качества (ОТК)."""
    order = get_object_or_404(ProductionOrder, pk=pk)

    if request.method == 'POST':
        form = QualityCheckForm(request.POST)
        if form.is_valid():
            qc = form.save(commit=False)
            submit_quality_check(
                order=order,
                inspector=request.user,
                result=qc.result,
                quantity_checked=qc.quantity_checked,
                quantity_accepted=qc.quantity_accepted,
                quantity_defective=qc.quantity_defective,
                check_dimensions=qc.check_dimensions,
                check_assembly=qc.check_assembly,
                check_appearance=qc.check_appearance,
                check_coating=qc.check_coating,
                check_completeness=qc.check_completeness,
                check_mechanisms=qc.check_mechanisms,
                check_damage_free=qc.check_damage_free,
                defect_description=qc.defect_description,
                rework_instructions=qc.rework_instructions,
                notes=qc.notes,
            )
            messages.success(request, f'Акт ОТК оформлен со статусом: {qc.get_result_display()}.')
            return redirect('production:detail', pk=order.id)
    else:
        form = QualityCheckForm(initial={
            'quantity_checked': order.quantity_planned,
            'quantity_accepted': order.quantity_planned,
            'quantity_defective': Decimal('0.00'),
            'result': QCResult.PASS,
        })

    context = {
        'page_title': f'Контроль качества ОТК — {order.order_number}',
        'order': order,
        'form': form,
    }
    return render(request, 'production/qc_inspect.html', context)


@login_required
@require_POST
def order_transfer_wh2(request, pk):
    """Сдача готовой партии мебели на склад готовой продукции (WH-2)."""
    order = get_object_or_404(ProductionOrder, pk=pk)

    if not can_manage_production(request.user):
        messages.error(request, 'У вас недостаточно прав для сдачи продукции на склад.')
        return redirect('production:detail', pk=order.id)

    try:
        doc = complete_and_transfer_to_warehouse(order, user=request.user)
        messages.success(
            request,
            f'Партия мебели успешно принята на склад WH-2 по накладной {doc.doc_number}. Заказ {order.order_number} завершён!'
        )
    except Exception as e:
        messages.error(request, f'Не удалось передать мебель на склад WH-2: {e}')

    return redirect('production:detail', pk=order.id)


# ==============================================================================
# 4. КАНБАН-ДОСКА ЦЕХА
# ==============================================================================

@login_required
def kanban_board(request):
    """Канбан-доска цеха по этапам производства."""
    cat_filter = request.GET.get('category', '')
    master_filter = request.GET.get('master', '')
    priority_filter = request.GET.get('priority', '')

    orders_qs = ProductionOrder.objects.select_related(
        'product', 'assigned_master', 'created_by'
    ).prefetch_related('stages').exclude(status__in=[ProductionOrderStatus.CANCELLED])

    if cat_filter:
        orders_qs = orders_qs.filter(product__category=cat_filter)
    if master_filter:
        orders_qs = orders_qs.filter(assigned_master_id=master_filter)
    if priority_filter:
        orders_qs = orders_qs.filter(priority=priority_filter)

    orders = list(orders_qs)

    # Распределение заказов по колонкам канбана
    columns = {
        'WAITING':    {'title': 'Ожидает запуска', 'orders': [], 'color': 'border-gray-300'},
        'CUTTING':    {'title': 'Раскрой',         'orders': [], 'color': 'border-amber-400'},
        'PROCESSING': {'title': 'Присадка / Фрез.', 'orders': [], 'color': 'border-blue-400'},
        'EDGING':     {'title': 'Кромление',       'orders': [], 'color': 'border-indigo-400'},
        'ASSEMBLY':   {'title': 'Сборка',          'orders': [], 'color': 'border-purple-400'},
        'FINISHING':  {'title': 'Отделка / Обивка', 'orders': [], 'color': 'border-teal-400'},
        'QC_CHECK':   {'title': 'ОТК (Контроль)',  'orders': [], 'color': 'border-orange-400'},
        'REWORK':     {'title': 'Доработка',       'orders': [], 'color': 'border-rose-400'},
        'READY':      {'title': 'Готово к сдаче',  'orders': [], 'color': 'border-emerald-500'},
    }

    for ord in orders:
        if ord.status in [ProductionOrderStatus.DRAFT, ProductionOrderStatus.WAITING, ProductionOrderStatus.CHECKING_MATERIALS]:
            columns['WAITING']['orders'].append(ord)
        elif ord.status == ProductionOrderStatus.QC_CHECK:
            columns['QC_CHECK']['orders'].append(ord)
        elif ord.status == ProductionOrderStatus.REWORK:
            columns['REWORK']['orders'].append(ord)
        elif ord.status == ProductionOrderStatus.READY:
            columns['READY']['orders'].append(ord)
        elif ord.status == ProductionOrderStatus.COMPLETED:
            # Завершённые можно не показывать на активной доске или в READY
            pass
        else:
            # IN_PROGRESS или MATERIALS_RESERVED -> определяем по текущему активному этапу
            current_stage = ord.stages.filter(status=StageStatus.IN_PROGRESS).first()
            if not current_stage:
                current_stage = ord.stages.filter(status=StageStatus.PENDING).first()

            s_name = (current_stage.stage_name.lower() if current_stage else '')
            if 'раскрой' in s_name:
                columns['CUTTING']['orders'].append(ord)
            elif 'присадк' in s_name or 'фрезер' in s_name or 'шлифов' in s_name:
                columns['PROCESSING']['orders'].append(ord)
            elif 'кром' in s_name:
                columns['EDGING']['orders'].append(ord)
            elif 'сборк' in s_name or 'каркас' in s_name:
                columns['ASSEMBLY']['orders'].append(ord)
            elif 'лак' in s_name or 'окрас' in s_name or 'обивк' in s_name or 'фасад' in s_name:
                columns['FINISHING']['orders'].append(ord)
            else:
                columns['ASSEMBLY']['orders'].append(ord)

    masters = Employee.objects.filter(department=Department.PRODUCTION).order_by('last_name')

    context = {
        'page_title': 'Канбан-доска цеха',
        'columns': columns,
        'categories': ProductCategory.choices,
        'masters': masters,
        'priorities': OrderPriority.choices,
        'selected_cat': cat_filter,
        'selected_master': master_filter,
        'selected_priority': priority_filter,
    }
    return render(request, 'production/board.html', context)


# ==============================================================================
# 5. ПЕРСОНАЛЬНЫЙ ИНТЕРФЕЙС МАСТЕРА
# ==============================================================================

@login_required
def my_tasks(request):
    """Персональный терминал задач рабочего/мастера."""
    user = request.user
    emp_profile = getattr(user, 'employee_profile', None)

    tasks_qs = ProductionStage.objects.select_related(
        'production_order', 'production_order__product', 'assigned_employee'
    ).exclude(status__in=[StageStatus.DONE, StageStatus.SKIPPED])

    if emp_profile:
        tasks_qs = tasks_qs.filter(assigned_employee=emp_profile)
    elif not can_manage_production(user):
        tasks_qs = tasks_qs.none()

    my_active_tasks = list(tasks_qs.filter(status=StageStatus.IN_PROGRESS).order_by('production_order__planned_end'))
    my_pending_tasks = list(tasks_qs.filter(status__in=[StageStatus.PENDING, StageStatus.REWORK]).order_by('sequence'))

    recent_completed = ProductionStage.objects.filter(
        assigned_employee=emp_profile,
        status=StageStatus.DONE
    ).select_related('production_order', 'production_order__product').order_by('-finished_at')[:8] if emp_profile else []

    context = {
        'page_title': 'Мои задания в цехе',
        'employee': emp_profile,
        'active_tasks': my_active_tasks,
        'pending_tasks': my_pending_tasks,
        'recent_completed': recent_completed,
    }
    return render(request, 'production/my_tasks.html', context)


# ==============================================================================
# 6. ТЕХНОЛОГИЧЕСКИЕ КАРТЫ — BOM (BILL OF MATERIALS)
# ==============================================================================

@login_required
def boms_list(request):
    boms = BOM.objects.select_related('product', 'variant', 'routing_template').prefetch_related(
        'items', 'items__material'
    ).order_by('product__name', '-version')

    context = {
        'page_title': 'Технологические карты (BOM)',
        'boms': boms,
        'can_manage': can_manage_production(request.user),
    }
    return render(request, 'production/boms/list.html', context)


@login_required
def bom_detail(request, pk):
    bom = get_object_or_404(
        BOM.objects.select_related('product', 'variant', 'routing_template'),
        pk=pk
    )
    items = bom.items.select_related('material').all()
    route_stages = bom.routing_template.stages.order_by('sequence') if bom.routing_template else []

    context = {
        'page_title': f'{bom.name} v{bom.version}',
        'bom': bom,
        'items': items,
        'route_stages': route_stages,
        'can_manage': can_manage_production(request.user),
    }
    return render(request, 'production/boms/detail.html', context)


@login_required
def bom_create(request):
    if not can_manage_production(request.user):
        messages.error(request, 'Недостаточно прав для создания спецификаций BOM.')
        return redirect('production:boms_list')

    if request.method == 'POST':
        form = BOMForm(request.POST)
        if form.is_valid():
            bom = form.save()

            # Сохранение строк материалов
            mat_ids = request.POST.getlist('material_id[]')
            quantities = request.POST.getlist('quantity_planned[]')
            units = request.POST.getlist('unit[]')
            wastes = request.POST.getlist('waste_percent[]')
            notes = request.POST.getlist('notes[]')

            for i in range(len(mat_ids)):
                m_id = mat_ids[i] if i < len(mat_ids) else None
                if not m_id:
                    continue
                try:
                    qty = Decimal(str(quantities[i]))
                except Exception:
                    qty = Decimal('1.000')

                u = units[i] if i < len(units) else 'шт'
                try:
                    w = Decimal(str(wastes[i]))
                except Exception:
                    w = Decimal('5.00')

                n = notes[i] if i < len(notes) else ''

                BOMItem.objects.create(
                    bom=bom,
                    material_id=m_id,
                    quantity_planned=qty,
                    unit=u,
                    waste_percent=w,
                    notes=n,
                )

            messages.success(request, f'Технологическая карта {bom.name} v{bom.version} создана.')
            return redirect('production:bom_detail', pk=bom.id)
    else:
        form = BOMForm()

    materials = Material.objects.order_by('name')
    context = {
        'page_title': 'Новая технологическая карта (BOM)',
        'form': form,
        'materials': materials,
    }
    return render(request, 'production/boms/create.html', context)


# ==============================================================================
# 7. МАРШРУТЫ ПРОИЗВОДСТВА
# ==============================================================================

@login_required
def routes_list(request):
    ensure_default_routing_templates()
    templates = RoutingTemplate.objects.prefetch_related('stages').order_by('category')

    context = {
        'page_title': 'Маршруты производства мебели',
        'templates': templates,
    }
    return render(request, 'production/routes/list.html', context)


# ==============================================================================
# 8. ЖУРНАЛ БРАКА И ОТХОДОВ
# ==============================================================================

@login_required
def waste_list(request):
    wastes = ProductionWaste.objects.select_related(
        'production_order', 'production_order__product', 'material', 'stage', 'reported_by'
    ).order_by('-created_at')

    total_damage_kzt = sum((w.cost_kzt for w in wastes), Decimal('0.00'))
    total_incidents = wastes.count()

    context = {
        'page_title': 'Журнал производственного брака и отходов',
        'wastes': wastes,
        'total_damage_kzt': total_damage_kzt,
        'total_incidents': total_incidents,
        'waste_types': WasteType.choices,
    }
    return render(request, 'production/waste/list.html', context)


@login_required
def waste_create(request, pk):
    order = get_object_or_404(ProductionOrder, pk=pk)

    if request.method == 'POST':
        form = ProductionWasteForm(request.POST)
        if form.is_valid():
            waste = form.save(commit=False)
            waste.production_order = order
            waste.reported_by = request.user
            waste.save()

            if waste.waste_type == WasteType.REWORKABLE_DEFECT:
                order.status = ProductionOrderStatus.REWORK
                order.save(update_fields=['status'])

            recalculate_order_costs(order)
            messages.success(request, f'Запись о браке/отходе зафиксирована для заказа {order.order_number}.')
            return redirect('production:detail', pk=order.id)
    else:
        form = ProductionWasteForm()
        form.fields['stage'].queryset = order.stages.all()

    context = {
        'page_title': f'Фиксация брака / отходов — {order.order_number}',
        'order': order,
        'form': form,
    }
    return render(request, 'production/waste/create.html', context)
