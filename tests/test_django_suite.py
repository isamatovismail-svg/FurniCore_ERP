from django.test import TestCase, Client
from django.core.management import call_command
from apps.accounts.models import User
from apps.products.models import Product
from apps.production.models import ProductionOrder


class FurniCoreERPTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo')

    def setUp(self):
        self.client = Client()
        self.user = User.objects.get(username='owner')
        self.client.force_login(self.user)

    def test_routes_status_codes(self):
        urls = [
            '/',
            '/warehouses/',
            '/warehouses/wh-1/',
            '/warehouses/wh-2/',
            '/materials/',
            '/products/',
            '/production/',
            '/employees/',
            '/sales/',
            '/sales/customers/',
            '/suppliers/',
            '/quality/',
            '/finance/',
            '/analytics/',
            '/ai/',
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"URL {url} returned {response.status_code}")

    def test_product_detail(self):
        prod = Product.objects.first()
        self.assertIsNotNone(prod)
        res = self.client.get(f'/products/{prod.pk}/')
        self.assertEqual(res.status_code, 200)

    def test_production_detail(self):
        order = ProductionOrder.objects.first()
        self.assertIsNotNone(order)
        res = self.client.get(f'/production/{order.pk}/')
        self.assertEqual(res.status_code, 200)

    def test_unauthenticated_access(self):
        anon_client = Client()
        res = anon_client.get('/')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/accounts/login/', res.headers.get('Location', ''))
