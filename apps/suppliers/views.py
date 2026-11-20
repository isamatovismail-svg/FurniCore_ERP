import datetime
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q, Sum
from apps.accounts.models import UserRole
from apps.accounts.decorators import deny_demo_viewer
from apps.materials.models import Material
from apps.suppliers.models import (
    Supplier,
    PurchaseOrder,
    PurchaseOrderStatus,
)
from apps.suppliers.services import (
    create_purchase_order,
    confirm_purchase_order,
    receive_purchase_order_items,
    cancel_purchase_order,
)
from apps.suppliers.reports import generate_purchase_order_pdf


def can_manage_procurement(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.role in [
        UserRole.OWNER,
        UserRole.ADMIN,
        UserRole.PRODUCTION_MANAGER,
        UserRole.WAREHOUSE_MANAGER,
        UserRole.ACCOUNTANT,
    ] or user.is_superuser


# ==============================================================================
# СПРАВОЧНИК ПОСТАВЩИКОВ (CRUD)
# ==============================================================================

@login_required
def index(request):
    """Список поставщиков с поиском и фильтром по активности."""
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'active')

    suppliers = Supplier.objects.prefetch_related('materials', 'purchase_orders').all()

    if status_filter == 'active':
        suppliers = suppliers.filter(is_active=True)
    elif status_filter == 'archived':
        suppliers = suppliers.filter(is_active=False)

    if q:
        suppliers = suppliers.filter(
            Q(name__icontains=q) |
            Q(contact_person__icontains=q) |
            Q(phone__icontains=q) |
            Q(address__icontains=q) |
            Q(email__icontains=q)
        )
    suppliers = suppliers.order_by('name')

    total_active = Supplier.objects.filter(is_active=True).count()
    total_archived = Supplier.objects.filter(is_active=False).count()

    context = {
        'page_title': 'Поставщики сырья и комплектующих',
        'suppliers': suppliers,
        'q': q,
        'status_filter': status_filter,
        'total_active': total_active,
        'total_archived': total_archived,
        'can_manage': can_manage_procurement(request.user),
    }
    return render(request, 'suppliers/index.html', context)


@login_required
@deny_demo_viewer
def supplier_create(request):
    """Создание нового контрагента-поставщика."""
    if not can_manage_procurement(request.user):
        messages.error(request, 'У вас недостаточно прав для добавления поставщиков.')
        return redirect('suppliers:index')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        contact_person = request.POST.get('contact_person', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        address = request.POST.get('address', '').strip()
        notes = request.POST.get('notes', '').strip()

        if not name:
            messages.error(request, 'Укажите наименование компании поставщика.')
        else:
            supplier = Supplier.objects.create(
                name=name,
                contact_person=contact_person,
                phone=phone,
                email=email,
                address=address,
                notes=notes,
            )
            messages.success(request, f'Поставщик «{supplier.name}» успешно добавлен.')
            return redirect('suppliers:index')

    return render(request, 'suppliers/form.html', {
        'page_title': 'Новый поставщик',
        'supplier': None,
    })


@login_required
@deny_demo_viewer
def supplier_edit(request, pk):
    """Редактирование карточки поставщика."""
    if not can_manage_procurement(request.user):
        messages.error(request, 'У вас недостаточно прав для редактирования поставщиков.')
        return redirect('suppliers:index')

    supplier = get_object_or_404(Supplier, pk=pk)

    if request.method == 'POST':
        supplier.name = request.POST.get('name', '').strip()
        supplier.contact_person = request.POST.get('contact_person', '').strip()
        supplier.phone = request.POST.get('phone', '').strip()
        supplier.email = request.POST.get('email', '').strip()
        supplier.address = request.POST.get('address', '').strip()
        supplier.notes = request.POST.get('notes', '').strip()

        if not supplier.name:
            messages.error(request, 'Укажите наименование компании поставщика.')
        else:
            supplier.save()
            messages.success(request, f'Данные поставщика «{supplier.name}» обновлены.')
            return redirect('suppliers:index')

    return render(request, 'suppliers/form.html', {
        'page_title': f'Редактирование: {supplier.name}',
        'supplier': supplier,
    })


@login_required
@deny_demo_viewer
def supplier_archive(request, pk):
    """Архивирование поставщика (безопасное отключение без удаления истории)."""
    if not can_manage_procurement(request.user):
        messages.error(request, 'У вас недостаточно прав для архивирования.')
        return redirect('suppliers:index')

    supplier = get_object_or_404(Supplier, pk=pk)
    supplier.is_active = not supplier.is_active
    supplier.save(update_fields=['is_active'])

    action_word = 'активирован' if supplier.is_active else 'перенесён в архив'
    messages.success(request, f'Поставщик «{supplier.name}» {action_word}.')
    return redirect('suppliers:index')


# ==============================================================================
# ЗАКАЗЫ ПОСТАВЩИКАМ (PURCHASE ORDERS)
# ==============================================================================

@login_required
def order_list(request):
    """Журнал заказов поставщикам с фильтрами по статусам и поиском."""
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()

    orders = PurchaseOrder.objects.select_related('supplier', 'created_by').prefetch_related('items__material')

    if status_filter:
        orders = orders.filter(status=status_filter)
    if q:
        orders = orders.filter(
            Q(order_number__icontains=q) |
            Q(supplier__name__icontains=q) |
            Q(notes__icontains=q)
        )

    orders = orders.order_by('-created_at')

    # KPI метрики
    total_orders = PurchaseOrder.objects.count()
    draft_orders = PurchaseOrder.objects.filter(status=PurchaseOrderStatus.DRAFT).count()
    active_orders = PurchaseOrder.objects.filter(
        status__in=[PurchaseOrderStatus.SENT, PurchaseOrderStatus.PARTIALLY_RECEIVED]
    ).count()
    received_orders = PurchaseOrder.objects.filter(status=PurchaseOrderStatus.RECEIVED).count()
    total_spent = PurchaseOrder.objects.filter(
        status__in=[PurchaseOrderStatus.PARTIALLY_RECEIVED, PurchaseOrderStatus.RECEIVED]
    ).aggregate(t=Sum('total_amount_kzt'))['t'] or Decimal('0.00')

    context = {
        'page_title': 'Закупки и снабжение',
        'orders': orders,
        'statuses': PurchaseOrderStatus.choices,
        'status_filter': status_filter,
        'q': q,
        'total_orders': total_orders,
        'draft_orders': draft_orders,
        'active_orders': active_orders,
        'received_orders': received_orders,
        'total_spent': total_spent,
        'can_manage': can_manage_procurement(request.user),
    }
    return render(request, 'suppliers/orders/list.html', context)


@login_required
@deny_demo_viewer
def order_create(request):
    """Формирование нового заказа поставщику."""
    if not can_manage_procurement(request.user):
        messages.error(request, 'У вас недостаточно прав для создания заказов на закупку.')
        return redirect('suppliers:order_list')

    materials = Material.objects.filter(is_active=True).order_by('name')
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier')
        delivery_date_str = request.POST.get('planned_delivery_date')
        due_date_str = request.POST.get('payment_due_date')
        notes = request.POST.get('notes', '').strip()

        supplier = get_object_or_404(Supplier, pk=supplier_id)
        planned_delivery_date = None
        if delivery_date_str:
            try:
                planned_delivery_date = datetime.date.fromisoformat(delivery_date_str)
            except ValueError:
                pass
        payment_due_date = None
        if due_date_str:
            try:
                payment_due_date = datetime.date.fromisoformat(due_date_str)
            except ValueError:
                pass

        # Сбор позиций из формы (динамические строки: material_id[], quantity[], price[])
        mat_ids = request.POST.getlist('material_id[]')
        quantities = request.POST.getlist('quantity[]')
        prices = request.POST.getlist('unit_price[]')

        items_data = []
        for mid, q_val, p_val in zip(mat_ids, quantities, prices):
            if not mid:
                continue
            try:
                mat = Material.objects.get(pk=mid)
                qty = Decimal(str(q_val))
                price = Decimal(str(p_val)) if p_val else mat.purchase_cost_kzt
                if qty > Decimal('0'):
                    items_data.append({
                        'material': mat,
                        'quantity': qty,
                        'unit_price_kzt': price,
                    })
            except Exception:
                continue

        if not items_data:
            messages.error(request, 'Добавьте хотя бы один материал в заказ с положительным количеством.')
        else:
            po = create_purchase_order(
                supplier=supplier,
                created_by=request.user,
                planned_delivery_date=planned_delivery_date,
                payment_due_date=payment_due_date,
                notes=notes,
                items_data=items_data,
            )
            messages.success(request, f'Заказ поставщику {po.order_number} успешно сформирован (черновик).')
            return redirect('suppliers:order_detail', pk=po.id)

    return render(request, 'suppliers/orders/create.html', {
        'page_title': 'Новый заказ поставщику',
        'materials': materials,
        'suppliers': suppliers,
        'today': datetime.date.today().isoformat(),
    })


@login_required
def order_detail(request, pk):
    """Детальная карточка заказа поставщику со спецификацией и историей поступлений."""
    po = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'created_by').prefetch_related('items__material', 'warehouse_documents'),
        pk=pk,
    )

    context = {
        'page_title': f'Заказ {po.order_number}',
        'order': po,
        'items': po.items.select_related('material').all(),
        'warehouse_docs': po.warehouse_documents.order_by('-doc_date', '-created_at'),
        'can_manage': can_manage_procurement(request.user),
    }
    return render(request, 'suppliers/orders/detail.html', context)


@login_required
@deny_demo_viewer
def order_send(request, pk):
    """Отправка заказа поставщику (переход в статус SENT)."""
    if not can_manage_procurement(request.user):
        messages.error(request, 'У вас недостаточно прав.')
        return redirect('suppliers:order_list')

    po = get_object_or_404(PurchaseOrder, pk=pk)
    try:
        confirm_purchase_order(po, user=request.user)
        messages.success(request, f'Заказ {po.order_number} подтвержден и отправлен поставщику.')
    except Exception as e:
        messages.error(request, f'Ошибка отправки заказа: {e}')
    return redirect('suppliers:order_detail', pk=po.id)


@login_required
@deny_demo_viewer
def order_receive(request, pk):
    """Приемка поступивших материалов на склад WH-1 (полная или частичная)."""
    if not can_manage_procurement(request.user):
        messages.error(request, 'У вас недостаточно прав для приемки сырья.')
        return redirect('suppliers:order_list')

    po = get_object_or_404(PurchaseOrder, pk=pk)

    if request.method == 'POST':
        notes = request.POST.get('doc_notes', '').strip()
        received_map = {}

        for it in po.items.all():
            field_name = f'qty_{it.id}'
            val = request.POST.get(field_name)
            if val:
                try:
                    q_dec = Decimal(str(val))
                    if q_dec > Decimal('0'):
                        received_map[it.id] = q_dec
                except Exception:
                    pass

        try:
            doc = receive_purchase_order_items(
                purchase_order=po,
                received_items_map=received_map,
                user=request.user,
                doc_notes=notes,
            )
            messages.success(request, f'Сырье успешно оприходовано на WH-1 по накладной {doc.doc_number}.')
        except Exception as e:
            messages.error(request, f'Ошибка при приемке: {e}')

        return redirect('suppliers:order_detail', pk=po.id)

    return redirect('suppliers:order_detail', pk=po.id)


@login_required
@deny_demo_viewer
def order_cancel(request, pk):
    """Отмена заказа поставщику."""
    if not can_manage_procurement(request.user):
        messages.error(request, 'У вас недостаточно прав.')
        return redirect('suppliers:order_list')

    po = get_object_or_404(PurchaseOrder, pk=pk)
    try:
        cancel_purchase_order(po, user=request.user)
        messages.success(request, f'Заказ {po.order_number} отменен.')
    except Exception as e:
        messages.error(request, f'Ошибка отмены: {e}')
    return redirect('suppliers:order_detail', pk=po.id)


@login_required
def order_pdf(request, pk):
    """Скачать / просмотреть официальный PDF-бланк заказа поставщику."""
    po = get_object_or_404(PurchaseOrder, pk=pk)
    pdf_bytes = generate_purchase_order_pdf(po)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"{po.order_number}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
