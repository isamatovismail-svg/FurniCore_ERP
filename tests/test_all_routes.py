import pytest
from django.test import Client
from django.core.management import call_command
from apps.accounts.models import User
from apps.products.models import Product
from apps.production.models import ProductionOrder


@pytest.fixture
def auth_client(db):
    call_command('seed_demo')
    client = Client()
    user = User.objects.get(username='owner')
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_all_primary_routes(auth_client):
    routes = [
        ('/', 200),
        ('/warehouses/', 200),
        ('/warehouses/wh-1/', 200),
        ('/warehouses/wh-2/', 200),
        ('/materials/', 200),
        ('/products/', 200),
        ('/production/', 200),
        ('/employees/', 200),
        ('/sales/', 200),
        ('/sales/customers/', 200),
        ('/suppliers/', 200),
        ('/quality/', 200),
        ('/finance/', 200),
        ('/analytics/', 200),
        ('/ai/', 200),
    ]

    for url, expected_status in routes:
        response = auth_client.get(url)
        assert response.status_code == expected_status, f"Route {url} returned {response.status_code}"


@pytest.mark.django_db
def test_details_pages(auth_client):
    prod = Product.objects.first()
    assert prod is not None
    res_prod = auth_client.get(f'/products/{prod.pk}/')
    assert res_prod.status_code == 200
    assert prod.name in res_prod.content.decode('utf-8')

    order = ProductionOrder.objects.first()
    assert order is not None
    res_po = auth_client.get(f'/production/{order.pk}/')
    assert res_po.status_code == 200
    assert order.order_number in res_po.content.decode('utf-8')


@pytest.mark.django_db
def test_search_and_filters(auth_client):
    # Material search
    res = auth_client.get('/materials/?q=ЛДСП')
    assert res.status_code == 200
    assert 'ЛДСП' in res.content.decode('utf-8')

    # Product search
    res_p = auth_client.get('/products/?category=WARDROBE')
    assert res_p.status_code == 200
    assert 'Шкаф' in res_p.content.decode('utf-8')

    # Warehouse WH-1 low stock filter
    res_wh1 = auth_client.get('/warehouses/wh-1/?low=1')
    assert res_wh1.status_code == 200

    # Finance category filter
    res_fin = auth_client.get('/finance/?category=RENT')
    assert res_fin.status_code == 200
    assert 'Аренда' in res_fin.content.decode('utf-8')


@pytest.mark.django_db
def test_unauthenticated_redirect():
    client = Client()
    routes = [
        '/',
        '/warehouses/',
        '/warehouses/wh-1/',
        '/warehouses/wh-2/',
        '/materials/',
        '/products/',
        '/production/',
        '/employees/',
        '/sales/',
        '/finance/',
    ]
    for url in routes:
        response = client.get(url)
        assert response.status_code == 302
        assert '/accounts/login/' in response.headers.get('Location', '')


@pytest.mark.django_db
def test_login_page_renders():
    client = Client()
    response = client.get('/accounts/login/')
    assert response.status_code == 200
    assert 'FurniCore' in response.content.decode('utf-8')


@pytest.mark.django_db
def test_auth_login_and_logout(db):
    call_command('seed_demo')
    client = Client()
    login_res = client.post('/accounts/login/', {
        'username': 'owner',
        'password': 'furnicore123',
    }, follow=True)
    assert login_res.status_code == 200
    assert 'Дашборд' in login_res.content.decode('utf-8')

    logout_res = client.get('/accounts/logout/', follow=True)
    assert logout_res.status_code == 200
    assert 'Вход в систему' in logout_res.content.decode('utf-8')
