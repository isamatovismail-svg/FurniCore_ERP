import datetime
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Sum, Q, Count
from apps.accounts.models import UserRole
from apps.accounts.decorators import deny_demo_viewer
from apps.products.models import Product
from apps.sales.models import SalesOrder, OrderStatus, Customer
from apps.sales.services import (
    create_sales_order,
    check_sales_order_stock,
    confirm_and_reserve_sales_order,
    create_production_orders_for_sales_order,
    ship_sales_order,
    cancel_sales_order,
)
from apps.sales.reports import generate_sales_order_pdf


def can_manage_sales(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.role in [
        UserRole.OWNER,
        UserRole.ADMIN,
        UserRole.SALES_MANAGER,
        UserRole.PRODUCTION_MANAGER,
        UserRole.ACCOUNTANT,
    ] or user.is_superuser


# ==============================================================================
# ЗАКАЗЫ КЛИЕНТОВ (SALES ORDERS)
# ==============================================================================

@login_required
def index(request):
    """Список заказов покупателей с поиском, фильтрацией по статусам и KPI."""
    status_filter = request.GET.get('status', '')
    q = request.GET.get('q', '').strip()

    orders = SalesOrder.objects.select_related('customer', 'created_by').prefetch_related('items__product')
    if status_filter:
        orders = orders.filter(status=status_filter)
    if q:
        orders = orders.filter(
            Q(order_number__icontains=q) |
            Q(customer__full_name__icontains=q) |
            Q(customer__company_name__icontains=q) |
            Q(notes__icontains=q)
        )
    orders = orders.order_by('-created_at')

    # Метрики
    total_orders = SalesOrder.objects.count()
    draft_orders = SalesOrder.objects.filter(status__in=[OrderStatus.DRAFT, OrderStatus.NEW]).count()
    waiting_prod = SalesOrder.objects.filter(status__in=[OrderStatus.WAITING_PRODUCTION, OrderStatus.IN_PRODUCTION]).count()
    ready_to_ship = SalesOrder.objects.filter(status=OrderStatus.READY).count()
    completed_orders = SalesOrder.objects.filter(status__in=[OrderStatus.SHIPPED, OrderStatus.DELIVERED]).count()

    total_revenue = SalesOrder.objects.filter(
        status__in=[OrderStatus.CONFIRMED, OrderStatus.READY, OrderStatus.PARTIALLY_SHIPPED, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    ).aggregate(total=Sum('total_amount_kzt'))['total'] or Decimal('0.00')

    context = {
        'page_title': 'Заказы покупателей',
        'orders': orders,
        'statuses': OrderStatus.choices,
        'status_filter': status_filter,
        'q': q,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'draft_orders': draft_orders,
        'waiting_prod': waiting_prod,
        'ready_to_ship': ready_to_ship,
        'completed_orders': completed_orders,
        'can_manage': can_manage_sales(request.user),
    }
    return render(request, 'sales/index.html', context)


@login_required
@deny_demo_viewer
def order_create(request):
    """Создание нового клиентского заказа со спецификацией изделий."""
    if not can_manage_sales(request.user):
        messages.error(request, 'У вас недостаточно прав для создания клиентских заказов.')
        return redirect('sales:index')

    customers = Customer.objects.filter(is_active=True).order_by('full_name')
    products = Product.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        delivery_date_str = request.POST.get('planned_delivery_date')
        delivery_address = request.POST.get('delivery_address', '').strip()
        notes = request.POST.get('notes', '').strip()
        discount_percent = Decimal(str(request.POST.get('discount_percent') or '0.00'))
        deposit_amount_kzt = Decimal(str(request.POST.get('deposit_amount_kzt') or '0.00'))

        customer = get_object_or_404(Customer, pk=customer_id)
        planned_delivery_date = None
        if delivery_date_str:
            try:
                planned_delivery_date = datetime.date.fromisoformat(delivery_date_str)
            except ValueError:
                pass

        # Динамические строки товаров: product_id[], quantity[], unit_price[], item_discount[]
        prod_ids = request.POST.getlist('product_id[]')
        quantities = request.POST.getlist('quantity[]')
        prices = request.POST.getlist('unit_price[]')
        discounts = request.POST.getlist('item_discount[]')

        items_data = []
        for pid, q_val, p_val, d_val in zip(prod_ids, quantities, prices, discounts):
            if not pid:
                continue
            try:
                prod = Product.objects.get(pk=pid)
                qty = Decimal(str(q_val))
                price = Decimal(str(p_val)) if p_val else prod.sale_price_kzt
                disc = Decimal(str(d_val or '0.00'))
                if qty > Decimal('0'):
                    items_data.append({
                        'product': prod,
                        'quantity': qty,
                        'unit_price_kzt': price,
                        'discount_percent': disc,
                    })
            except Exception:
                continue

        if not items_data:
            messages.error(request, 'Добавьте хотя бы одно изделие с положительным количеством.')
        else:
            so = create_sales_order(
                customer=customer,
                created_by=request.user,
                items_data=items_data,
                planned_delivery_date=planned_delivery_date,
                delivery_address=delivery_address,
                notes=notes,
                discount_percent=discount_percent,
                deposit_amount_kzt=deposit_amount_kzt,
            )
            messages.success(request, f'Заказ клиента {so.order_number} успешно сформирован.')
            return redirect('sales:order_detail', pk=so.id)

    return render(request, 'sales/create.html', {
        'page_title': 'Новый заказ покупателя',
        'customers': customers,
        'products': products,
        'today': datetime.date.today().isoformat(),
    })


@login_required
def order_detail(request, pk):
    """Детальная карточка заказа клиента: анализ остатков WH-2, резервы, производство и отгрузка."""
    so = get_object_or_404(
        SalesOrder.objects.select_related('customer', 'created_by')
        .prefetch_related('items__product', 'warehouse_documents', 'production_orders'),
        pk=pk,
    )

    stock_check = check_sales_order_stock(so)

    context = {
        'page_title': f'Заказ {so.order_number}',
        'order': so,
        'items': so.items.select_related('product').all(),
        'stock_check': stock_check,
        'warehouse_docs': so.warehouse_documents.order_by('-doc_date', '-created_at'),
        'production_orders': so.production_orders.order_by('-created_at'),
        'can_manage': can_manage_sales(request.user),
    }
    return render(request, 'sales/detail.html', context)


@login_required
@deny_demo_viewer
def order_reserve(request, pk):
    """Подтверждение заказа и резервирование мебели на WH-2."""
    if not can_manage_sales(request.user):
        messages.error(request, 'У вас недостаточно прав.')
        return redirect('sales:index')

    so = get_object_or_404(SalesOrder, pk=pk)
    try:
        updated_so, res_doc = confirm_and_reserve_sales_order(so, user=request.user)
        if res_doc:
            messages.success(request, f'Мебель зарезервирована на WH-2 (документ {res_doc.doc_number}). Статус: {updated_so.get_status_display()}.')
        else:
            messages.warning(request, f'На складе WH-2 нет свободных остатков мебели. Статус заказа: {updated_so.get_status_display()}.')
    except Exception as e:
        messages.error(request, f'Ошибка резервирования: {e}')

    return redirect('sales:order_detail', pk=so.id)


@login_required
@deny_demo_viewer
def order_create_production(request, pk):
    """Создание производственных заказов под дефицит мебели по клиентскому заказу."""
    if not can_manage_sales(request.user):
        messages.error(request, 'У вас недостаточно прав.')
        return redirect('sales:index')

    so = get_object_or_404(SalesOrder, pk=pk)
    try:
        created_pos = create_production_orders_for_sales_order(so, user=request.user)
        if created_pos:
            numbers = ", ".join(o.order_number for o in created_pos)
            messages.success(request, f'В цех переданы производственные заказы: {numbers}. Статус заказа изменён на «В производстве».')
        else:
            messages.info(request, 'Дефицита продукции не обнаружено либо производственные заказы уже были запущены.')
    except Exception as e:
        messages.error(request, f'Ошибка создания производственных заказов: {e}')

    return redirect('sales:order_detail', pk=so.id)


@login_required
@deny_demo_viewer
def order_ship(request, pk):
    """Отгрузка готовой мебели клиенту со склада WH-2 (частичная или полная)."""
    if not can_manage_sales(request.user):
        messages.error(request, 'У вас недостаточно прав.')
        return redirect('sales:index')

    so = get_object_or_404(SalesOrder, pk=pk)

    if request.method == 'POST':
        notes = request.POST.get('doc_notes', '').strip()
        shipped_map = {}

        for it in so.items.all():
            val = request.POST.get(f'qty_{it.id}')
            if val:
                try:
                    q = Decimal(str(val))
                    if q > Decimal('0'):
                        shipped_map[it.id] = q
                except Exception:
                    pass

        try:
            doc = ship_sales_order(
                sales_order=so,
                shipped_items_map=shipped_map,
                user=request.user,
                doc_notes=notes,
            )
            messages.success(request, f'Отгрузка клиенту успешно оформлена по накладной {doc.doc_number}.')
        except Exception as e:
            messages.error(request, f'Ошибка при отгрузке: {e}')

    return redirect('sales:order_detail', pk=so.id)


@login_required
@deny_demo_viewer
def order_cancel(request, pk):
    """Отмена клиентского заказа со снятием резервов с WH-2."""
    if not can_manage_sales(request.user):
        messages.error(request, 'У вас недостаточно прав.')
        return redirect('sales:index')

    so = get_object_or_404(SalesOrder, pk=pk)
    try:
        cancel_sales_order(so, user=request.user)
        messages.success(request, f'Заказ {so.order_number} отменён. Все связанные резервы на WH-2 аннулированы.')
    except Exception as e:
        messages.error(request, f'Ошибка отмены заказа: {e}')

    return redirect('sales:order_detail', pk=so.id)


@login_required
def order_pdf(request, pk):
    """Скачать / просмотреть спецификацию и бланк клиентского заказа в PDF."""
    so = get_object_or_404(SalesOrder, pk=pk)
    pdf_bytes = generate_sales_order_pdf(so)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"{so.order_number}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


# ==============================================================================
# КЛИЕНТЫ / CRM (CRUD)
# ==============================================================================

@login_required
def customers_list(request):
    """Справочник клиентов с фильтром по архиву и поиском."""
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'active')

    customers = Customer.objects.annotate(order_count=Count('orders')).all()

    if status_filter == 'active':
        customers = customers.filter(is_active=True)
    elif status_filter == 'archived':
        customers = customers.filter(is_active=False)

    if q:
        customers = customers.filter(
            Q(full_name__icontains=q) |
            Q(company_name__icontains=q) |
            Q(phone__icontains=q) |
            Q(city__icontains=q) |
            Q(email__icontains=q)
        )
    customers = customers.order_by('full_name')

    total_active = Customer.objects.filter(is_active=True).count()
    total_archived = Customer.objects.filter(is_active=False).count()

    context = {
        'page_title': 'Клиенты (CRM)',
        'customers': customers,
        'q': q,
        'status_filter': status_filter,
        'total_active': total_active,
        'total_archived': total_archived,
        'can_manage': can_manage_sales(request.user),
    }
    return render(request, 'sales/customers.html', context)


@login_required
@deny_demo_viewer
def customer_create(request):
    """Добавление нового клиента."""
    if not can_manage_sales(request.user):
        messages.error(request, 'У вас недостаточно прав.')
        return redirect('sales:customers')

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        company_name = request.POST.get('company_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        city = request.POST.get('city', '').strip()
        address = request.POST.get('address', '').strip()
        notes = request.POST.get('notes', '').strip()

        if not full_name and not company_name:
            messages.error(request, 'Укажите ФИО или наименование компании клиента.')
        else:
            cust = Customer.objects.create(
                full_name=full_name or company_name,
                company_name=company_name,
                phone=phone,
                email=email,
                city=city,
                address=address,
                notes=notes,
            )
            messages.success(request, f'Клиент «{cust.name}» успешно зарегистрирован.')
            return redirect('sales:customers')

    return render(request, 'sales/customer_form.html', {
        'page_title': 'Новый клиент',
        'customer': None,
    })


@login_required
@deny_demo_viewer
def customer_edit(request, pk):
    """Редактирование профиля клиента."""
    if not can_manage_sales(request.user):
        messages.error(request, 'У вас недостаточно прав.')
        return redirect('sales:customers')

    cust = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        cust.full_name = request.POST.get('full_name', '').strip()
        cust.company_name = request.POST.get('company_name', '').strip()
        cust.phone = request.POST.get('phone', '').strip()
        cust.email = request.POST.get('email', '').strip()
        cust.city = request.POST.get('city', '').strip()
        cust.address = request.POST.get('address', '').strip()
        cust.notes = request.POST.get('notes', '').strip()

        if not cust.full_name and not cust.company_name:
            messages.error(request, 'Укажите ФИО или наименование компании клиента.')
        else:
            cust.save()
            messages.success(request, f'Данные клиента «{cust.name}» обновлены.')
            return redirect('sales:customers')

    return render(request, 'sales/customer_form.html', {
        'page_title': f'Редактирование: {cust.name}',
        'customer': cust,
    })


@login_required
@deny_demo_viewer
def customer_archive(request, pk):
    """Архивирование клиента без потери связей с заказами."""
    if not can_manage_sales(request.user):
        messages.error(request, 'У вас недостаточно прав.')
        return redirect('sales:customers')

    cust = get_object_or_404(Customer, pk=pk)
    cust.is_active = not cust.is_active
    cust.save(update_fields=['is_active'])

    action_word = 'активирован' if cust.is_active else 'перенесён в архив'
    messages.success(request, f'Клиент «{cust.name}» {action_word}.')
    return redirect('sales:customers')
