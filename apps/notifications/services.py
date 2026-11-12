import logging
from django.utils import timezone
from apps.accounts.models import User, UserRole
from apps.notifications.models import Notification, NotificationType

logger = logging.getLogger(__name__)


def create_notification(user: User, notification_type: str, title: str, message: str, link: str = '') -> Notification:
    """Создает персональное уведомление для пользователя."""
    return Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message,
        link=link,
    )


def notify_role(role: str, notification_type: str, title: str, message: str, link: str = ''):
    """Отправляет уведомление всем пользователям с определенной ролью (или администраторам)."""
    users = User.objects.filter(role__in=[role, UserRole.ADMIN], is_active=True)
    created_count = 0
    for u in users:
        Notification.objects.create(
            user=u,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
        )
        created_count += 1
    return created_count


def notify_all_managers(notification_type: str, title: str, message: str, link: str = ''):
    """Отправляет уведомление ключевым руководителям (Владелец, Админ, Нач. производства, Снабжение/Склад, Менеджер)."""
    roles = [UserRole.OWNER, UserRole.ADMIN, UserRole.PRODUCTION_MANAGER, UserRole.WAREHOUSE_MANAGER, UserRole.SALES_MANAGER]
    users = User.objects.filter(role__in=roles, is_active=True).distinct()
    for u in users:
        Notification.objects.create(
            user=u,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
        )


def notify_low_stock(material, warehouse, current_stock, min_limit):
    """Уведомление о дефиците материала на складе сырья."""
    title = f'⚠️ Дефицит сырья: {material.name}'
    message = (
        f'На складе "{warehouse.name}" фактический остаток ({current_stock} {material.unit}) '
        f'опустился ниже критического уровня ({min_limit} {material.unit}). Рекомендуется оформить заказ поставщику.'
    )
    notify_role(
        role=UserRole.WAREHOUSE_MANAGER,
        notification_type=NotificationType.LOW_STOCK,
        title=title,
        message=message,
        link=f'/materials/?q={material.sku}',
    )


def notify_supplier_receipt(purchase_order, doc):
    """Уведомление о поступлении сырья от поставщика."""
    title = f'📦 Поступление сырья: {purchase_order.order_number}'
    message = (
        f'По накладной {doc.doc_number} от поставщика "{purchase_order.supplier.name}" '
        f'оприходованы материалы на склад WH-1 на сумму {doc.total_amount_kzt:,.2f} ₸.'
    )
    notify_all_managers(
        notification_type=NotificationType.ORDER_STATUS,
        title=title,
        message=message,
        link=f'/suppliers/orders/{purchase_order.id}/',
    )


def notify_new_sales_order(sales_order):
    """Уведомление о новом заказе клиента."""
    title = f'💼 Новый заказ покупателя: {sales_order.order_number}'
    message = (
        f'Клиент "{sales_order.customer}" оформил заказ на сумму {sales_order.total_amount_kzt:,.2f} ₸. '
        f'Требуется проверка резерва готовой мебели.'
    )
    notify_role(
        role=UserRole.SALES_MANAGER,
        notification_type=NotificationType.ORDER_STATUS,
        title=title,
        message=message,
        link=f'/sales/{sales_order.id}/',
    )


def notify_waiting_production(sales_order, deficit_summary=''):
    """Уведомление: заказ покупателя ожидает запуска в производство."""
    title = f'⚙️ Требуется производство: {sales_order.order_number}'
    message = (
        f'По заказу клиента "{sales_order.customer}" обнаружен дефицит готовой мебели на складе WH-2. '
        f'{deficit_summary} Необходимо сформировать производственный заказ.'
    )
    notify_role(
        role=UserRole.PRODUCTION_MANAGER,
        notification_type=NotificationType.PRODUCTION,
        title=title,
        message=message,
        link=f'/sales/{sales_order.id}/',
    )


def notify_production_complete(production_order):
    """Уведомление: производственный заказ выполнен и передан на WH-2."""
    title = f'✅ Изделия готовы: {production_order.order_number}'
    message = (
        f'Заказ на производство изделия "{production_order.product.name}" успешно выполнен ({production_order.quantity_produced} шт.) '
        f'и оприходован на склад готовой продукции WH-2.'
    )
    notify_all_managers(
        notification_type=NotificationType.PRODUCTION,
        title=title,
        message=message,
        link=f'/production/{production_order.id}/',
    )


def notify_qc_failed(production_order, failed_reasons: str = ''):
    """Уведомление: изделие не прошло контроль качества (ОТК)."""
    title = f'🚫 Брак ОТК: {production_order.order_number}'
    message = (
        f'Партия изделия "{production_order.product.name}" не прошла инспекцию ОТК. '
        f'Замечания: {failed_reasons or "Несоответствие критериям качества"}. Требуется доработка.'
    )
    notify_role(
        role=UserRole.PRODUCTION_MANAGER,
        notification_type=NotificationType.PRODUCTION,
        title=title,
        message=message,
        link=f'/production/{production_order.id}/',
    )


def notify_ready_for_shipment(sales_order):
    """Уведомление: заказ покупателя полностью укомплектован и готов к отгрузке."""
    title = f'🚚 Готов к отгрузке: {sales_order.order_number}'
    message = (
        f'Вся продукция по заказу клиента "{sales_order.customer}" укомплектована и зарезервирована на WH-2. '
        f'Можно оформлять отгрузочную накладную.'
    )
    notify_role(
        role=UserRole.WAREHOUSE_MANAGER,
        notification_type=NotificationType.ORDER_STATUS,
        title=title,
        message=message,
        link=f'/sales/{sales_order.id}/',
    )
