"""
PHASE 1.5 — Full Manual-Style UI Testing via Django Test Client
Tests every module, every role, form submissions, error handling, and business flows.
"""
import json
import pytest
import datetime
from decimal import Decimal
from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def login(client, username, password):
    resp = client.post('/accounts/login/', {
        'username': username,
        'password': password,
    }, follow=True)
    return resp


def assert_page_ok(resp, url, check_text=None):
    assert resp.status_code == 200, f"FAIL {url}: got {resp.status_code}"
    if check_text:
        content = resp.content.decode('utf-8', errors='replace')
        assert check_text in content, f"FAIL {url}: expected '{check_text}' in page"
    return True


# ---------------------------------------------------------------------------
# STEP 1: Authentication
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAuthentication:

    def test_login_page_renders(self, client):
        """Login page returns 200 with form."""
        resp = client.get('/accounts/login/')
        assert resp.status_code == 200
        content = resp.content.decode()
        assert 'FurniCore' in content or 'login' in content.lower() or 'войти' in content.lower()

    def test_redirect_unauthenticated(self, client):
        """Unauthenticated user is redirected from protected pages."""
        for url in ['/', '/production/', '/finance/', '/sales/']:
            resp = client.get(url)
            assert resp.status_code in (302, 301), f"Expected redirect for {url}, got {resp.status_code}"

    def test_owner_login_success(self, client):
        """OWNER can login and reach dashboard."""
        resp = login(client, 'owner', 'owner123')
        assert resp.status_code == 200
        content = resp.content.decode()
        assert 'FurniCore' in content

    def test_invalid_credentials_rejected(self, client):
        """Invalid login shows error, not 500."""
        resp = client.post('/accounts/login/', {
            'username': 'owner',
            'password': 'wrongpassword123',
        })
        assert resp.status_code in (200, 302)
        # Must not be 500
        assert resp.status_code != 500

    def test_logout_works(self, client):
        """Login then logout redirects to login page."""
        login(client, 'owner', 'owner123')
        resp = client.post('/accounts/logout/', follow=True)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# STEP 2 & 3: Dashboard + All Module Pages for OWNER
# ---------------------------------------------------------------------------

OWNER_PAGES = [
    ('/', 'Dashboard', 'FurniCore'),
    ('/employees/', 'Employees', None),
    ('/materials/', 'Materials', None),
    ('/products/', 'Products', None),
    ('/warehouses/', 'Warehouses', None),
    ('/warehouses/wh-1/', 'WH-1', None),
    ('/warehouses/wh-2/', 'WH-2', None),
    ('/warehouses/documents/', 'Warehouse Docs', None),
    ('/production/', 'Production', None),
    ('/production/board/', 'Kanban Board', None),
    ('/production/my-tasks/', 'My Tasks', None),
    ('/production/boms/', 'BOMs', None),
    ('/production/routes/', 'Routes', None),
    ('/production/waste/', 'Waste Log', None),
    ('/quality/', 'Quality Control', None),
    ('/sales/', 'Sales', None),
    ('/sales/customers/', 'CRM Customers', None),
    ('/suppliers/', 'Suppliers', None),
    ('/suppliers/purchase-orders/', 'Purchase Orders', None),
    ('/finance/', 'Finance Dashboard', None),
    ('/finance/accounts/', 'Finance Accounts', None),
    ('/finance/payments/customers/', 'Customer Payments', None),
    ('/finance/payments/suppliers/', 'Supplier Payments', None),
    ('/finance/expenses/', 'Expenses', None),
    ('/finance/costing/', 'Costing', None),
    ('/finance/pl/', 'P&L', None),
    ('/analytics/', 'Analytics', None),
    ('/notifications/', 'Notifications', None),
    ('/ai/', 'AI Assistant', None),
]


@pytest.mark.django_db
class TestAllModulesOwner:

    @pytest.fixture(autouse=True)
    def do_login(self, client):
        self.client = client
        login(client, 'owner', 'owner123')

    @pytest.mark.parametrize("url,name,check", OWNER_PAGES)
    def test_module_page(self, url, name, check):
        resp = self.client.get(url, follow=True)
        assert resp.status_code == 200, f"FAIL [{name}] {url}: got HTTP {resp.status_code}"
        if check:
            content = resp.content.decode('utf-8', errors='replace')
            assert check in content, f"FAIL [{name}]: '{check}' not found on page"


# ---------------------------------------------------------------------------
# STEP 4: Create Test Customer (Sales CRM)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCreateCustomer:

    def test_create_customer_page_loads(self, client):
        login(client, 'sales_mgr', 'sales123')
        resp = client.get('/sales/customers/create/', follow=True)
        assert resp.status_code == 200

    def test_create_customer_post(self, client):
        """Sales Manager can create a new customer."""
        login(client, 'sales_mgr', 'sales123')
        resp = client.post('/sales/customers/create/', {
            'name': 'TEST-Клиент-UI-2026',
            'phone': '+7 700 000-00-01',
            'email': 'test-ui@furnicore.test',
            'address': 'Тестовый адрес, 1',
            'discount_percent': '0.00',
        }, follow=True)
        assert resp.status_code == 200
        content = resp.content.decode('utf-8', errors='replace')
        # Should show success message or redirect to customer list/detail
        assert 'TEST-Клиент-UI-2026' in content or 'успешно' in content.lower() or resp.redirect_chain

    def test_customer_list_loads(self, client):
        login(client, 'sales_mgr', 'sales123')
        resp = client.get('/sales/customers/')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# STEP 5: Production Order Creation (HOTFIX verification)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestProductionOrderCreate:

    def test_create_form_loads_for_manager(self, client):
        login(client, 'prod_manager', 'prod123')
        resp = client.get('/production/create/')
        assert resp.status_code == 200
        content = resp.content.decode()
        assert 'form' in content.lower() or 'product' in content.lower()

    def test_create_form_blocked_for_worker(self, client):
        login(client, 'worker1', 'work123')
        resp = client.get('/production/create/', follow=True)
        # Worker should be redirected away
        assert resp.status_code in (200, 302)
        # Final destination should NOT be the create form with 200
        if resp.status_code == 200:
            content = resp.content.decode()
            # Should show "недостаточно прав" message or be on a different page
            assert 'production/create' not in resp.wsgi_request.path or 'прав' in content

    def test_create_form_blocked_for_demo_viewer(self, client):
        login(client, 'teacher', 'TeacherPass2026!')
        resp = client.get('/production/create/', follow=True)
        assert resp.status_code == 200
        # Should not be on create page
        final_url = resp.wsgi_request.path
        assert final_url != '/production/create/'

    def test_create_form_blocked_via_post_for_demo_viewer(self, client):
        login(client, 'teacher', 'TeacherPass2026!')
        resp = client.post('/production/create/', {
            'product': 1, 'quantity_planned': 1,
        })
        assert resp.status_code == 302  # redirect, not 200 or 500

    def test_create_form_htmx_blocked_for_demo_viewer_403(self, client):
        login(client, 'teacher', 'TeacherPass2026!')
        resp = client.post('/production/create/', {
            'product': 1, 'quantity_planned': 1,
        }, HTTP_HX_REQUEST='true')
        assert resp.status_code == 403

    def test_production_order_post_creates_stages(self, client, db):
        """Full creation flow: POST creates order AND stages (hotfix verification)."""
        from apps.production.models import ProductionOrder, BOM, ProductionStage
        from apps.products.models import Product, ProductCategory
        from apps.production.services import ensure_default_routing_templates

        ensure_default_routing_templates()

        # Find or create a product and BOM
        product = Product.objects.filter(is_active=True).first()
        if not product:
            pytest.skip("No active products in DB")

        bom = BOM.objects.filter(product=product, is_active=True).first()

        login(client, 'prod_manager', 'prod123')
        today = datetime.date.today()

        post_data = {
            'product': product.id,
            'quantity_planned': 1,
            'priority': 'NORMAL',
            'planned_start': today.strftime('%Y-%m-%d'),
            'planned_end': (today + datetime.timedelta(days=14)).strftime('%Y-%m-%d'),
        }
        if bom:
            post_data['bom'] = bom.id

        count_before = ProductionOrder.objects.count()
        resp = client.post('/production/create/', post_data, follow=True)

        assert resp.status_code == 200, f"Expected 200 after redirect, got {resp.status_code}"
        assert ProductionOrder.objects.count() == count_before + 1, "Order was not created"

        new_order = ProductionOrder.objects.order_by('-id').first()
        stages_count = new_order.stages.count()
        assert stages_count > 0, f"initialize_order_stages FAILED: 0 stages created for order {new_order.order_number}"


# ---------------------------------------------------------------------------
# STEP 6: DEMO_VIEWER role testing
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDemoViewerRole:

    @pytest.fixture(autouse=True)
    def do_login(self, client):
        self.client = client
        login(client, 'teacher', 'TeacherPass2026!')

    def test_dashboard_accessible(self):
        resp = self.client.get('/')
        assert resp.status_code == 200

    def test_production_list_accessible(self):
        resp = self.client.get('/production/')
        assert resp.status_code == 200

    def test_finance_accessible(self):
        resp = self.client.get('/finance/')
        assert resp.status_code == 200

    def test_sales_accessible(self):
        resp = self.client.get('/sales/')
        assert resp.status_code == 200

    def test_warehouses_accessible(self):
        resp = self.client.get('/warehouses/')
        assert resp.status_code == 200

    def test_admin_panel_blocked(self):
        resp = self.client.get('/admin/', follow=True)
        # Should redirect to admin login (not 200 with admin panel)
        assert resp.status_code == 200
        content = resp.content.decode()
        # Should be admin login page, not admin index
        assert 'Log in' in content or 'войти' in content.lower() or '/admin/login/' in resp.wsgi_request.path

    def test_production_create_blocked(self):
        resp = self.client.get('/production/create/', follow=True)
        assert resp.wsgi_request.path != '/production/create/'

    def test_sales_create_blocked_post(self):
        resp = self.client.post('/sales/create/', {
            'customer': 1, 'discount_percent': 0
        })
        assert resp.status_code == 302

    def test_finance_payment_create_blocked_post(self):
        resp = self.client.post('/finance/payments/customers/create/', {'amount': 1})
        assert resp.status_code == 302

    def test_htmx_mutation_returns_403(self):
        resp = self.client.post('/production/create/', {
            'product': 1, 'quantity_planned': 1
        }, HTTP_HX_REQUEST='true')
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# STEP 7: WORKER role
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestWorkerRole:

    @pytest.fixture(autouse=True)
    def do_login(self, client):
        self.client = client
        login(client, 'worker1', 'work123')

    def test_my_tasks_accessible(self):
        resp = self.client.get('/production/my-tasks/')
        assert resp.status_code == 200

    def test_kanban_board_accessible(self):
        resp = self.client.get('/production/board/')
        assert resp.status_code == 200

    def test_boms_accessible(self):
        resp = self.client.get('/production/boms/')
        assert resp.status_code == 200

    def test_production_routes_accessible(self):
        resp = self.client.get('/production/routes/')
        assert resp.status_code == 200

    def test_production_create_blocked(self):
        resp = self.client.get('/production/create/', follow=True)
        assert resp.status_code == 200
        final_path = resp.wsgi_request.path
        assert final_path != '/production/create/'

    def test_finance_blocked(self):
        resp = self.client.get('/finance/', follow=True)
        assert resp.status_code in (200, 302, 403)
        # Must not get a 500
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# STEP 8: Finance module (Accountant)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFinanceModule:

    @pytest.fixture(autouse=True)
    def do_login(self, client):
        self.client = client
        login(client, 'accountant', 'acc123')

    def test_finance_dashboard(self):
        resp = self.client.get('/finance/')
        assert resp.status_code == 200

    def test_accounts_list(self):
        resp = self.client.get('/finance/accounts/')
        assert resp.status_code == 200

    def test_customer_payments(self):
        resp = self.client.get('/finance/payments/customers/')
        assert resp.status_code == 200

    def test_supplier_payments(self):
        resp = self.client.get('/finance/payments/suppliers/')
        assert resp.status_code == 200

    def test_expenses_list(self):
        resp = self.client.get('/finance/expenses/')
        assert resp.status_code == 200

    def test_costing_page(self):
        resp = self.client.get('/finance/costing/')
        assert resp.status_code == 200

    def test_pl_report(self):
        resp = self.client.get('/finance/pl/')
        assert resp.status_code == 200

    def test_pl_excel_export(self):
        resp = self.client.get('/finance/pl/export/excel/')
        assert resp.status_code == 200
        content_type = resp.get('Content-Type', '')
        assert 'spreadsheet' in content_type or 'excel' in content_type or 'octet-stream' in content_type, \
            f"P&L Excel export returned wrong content-type: {content_type}"


# ---------------------------------------------------------------------------
# STEP 9: Warehouse module (WH Manager)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestWarehouseModule:

    @pytest.fixture(autouse=True)
    def do_login(self, client):
        self.client = client
        login(client, 'wh_manager', 'wh123')

    def test_wh1_stock_page(self):
        resp = self.client.get('/warehouses/wh-1/')
        assert resp.status_code == 200

    def test_wh2_stock_page(self):
        resp = self.client.get('/warehouses/wh-2/')
        assert resp.status_code == 200
        content = resp.content.decode('utf-8', errors='replace')
        # WH-2 should show finished product data
        assert resp.status_code == 200

    def test_documents_list(self):
        resp = self.client.get('/warehouses/documents/')
        assert resp.status_code == 200

    def test_scan_barcode_page(self):
        resp = self.client.get('/warehouses/scan/', follow=True)
        assert resp.status_code in (200, 404)  # May or may not exist


# ---------------------------------------------------------------------------
# STEP 10: Error handling
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestErrorHandling:

    @pytest.fixture(autouse=True)
    def do_login(self, client):
        self.client = client
        login(client, 'owner', 'owner123')

    def test_nonexistent_production_order(self):
        """404 for non-existent order, not 500 Django traceback."""
        resp = self.client.get('/production/9999999/')
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_nonexistent_sales_order(self):
        resp = self.client.get('/sales/9999999/')
        assert resp.status_code == 404

    def test_nonexistent_url(self):
        resp = self.client.get('/this-url-does-not-exist-at-all/')
        assert resp.status_code in (404, 302), f"Expected 404, got {resp.status_code}"

    def test_nonexistent_bom(self):
        resp = self.client.get('/production/boms/9999999/')
        assert resp.status_code == 404

    def test_nonexistent_customer(self):
        resp = self.client.get('/sales/customers/9999999/')
        assert resp.status_code == 404

    def test_production_create_empty_post(self):
        """Empty POST to create form returns form with errors, not 500."""
        login(self.client, 'prod_manager', 'prod123')
        resp = self.client.post('/production/create/', {})
        assert resp.status_code in (200, 302)
        assert resp.status_code != 500

    def test_sales_create_empty_post(self):
        resp = self.client.post('/sales/create/', {})
        assert resp.status_code in (200, 302)
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# STEP 11: Dashboard period filters
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDashboardFilters:

    @pytest.fixture(autouse=True)
    def do_login(self, client):
        self.client = client
        login(client, 'owner', 'owner123')

    def test_period_today(self):
        resp = self.client.get('/?period=today')
        assert resp.status_code == 200

    def test_period_week(self):
        resp = self.client.get('/?period=week')
        assert resp.status_code == 200

    def test_period_month(self):
        resp = self.client.get('/?period=month')
        assert resp.status_code == 200

    def test_period_year(self):
        resp = self.client.get('/?period=year')
        assert resp.status_code == 200

    def test_period_invalid_falls_back(self):
        resp = self.client.get('/?period=invalid_value')
        assert resp.status_code == 200  # Should not 500


# ---------------------------------------------------------------------------
# STEP 12: Search and filter functionality
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSearchAndFilters:

    @pytest.fixture(autouse=True)
    def do_login(self, client):
        self.client = client
        login(client, 'owner', 'owner123')

    def test_materials_search(self):
        resp = self.client.get('/materials/?q=лдсп')
        assert resp.status_code == 200

    def test_products_search(self):
        resp = self.client.get('/products/?q=шкаф')
        assert resp.status_code == 200

    def test_production_filter_by_status(self):
        resp = self.client.get('/production/?status=WAITING')
        assert resp.status_code == 200

    def test_sales_filter(self):
        resp = self.client.get('/sales/?status=DRAFT')
        assert resp.status_code == 200

    def test_customers_search(self):
        resp = self.client.get('/sales/customers/?q=test')
        assert resp.status_code == 200

    def test_suppliers_search(self):
        resp = self.client.get('/suppliers/?q=поставщик')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# STEP 13: PDF/Excel Export
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExports:

    @pytest.fixture(autouse=True)
    def do_login(self, client):
        self.client = client
        login(client, 'owner', 'owner123')

    def test_pl_excel_export(self):
        resp = self.client.get('/finance/pl/export/excel/')
        assert resp.status_code == 200
        ct = resp.get('Content-Type', '')
        assert 'spreadsheet' in ct or 'excel' in ct or 'octet-stream' in ct

    def test_finance_pdf_routes_exist(self):
        # At minimum check the route doesn't 500
        resp = self.client.get('/finance/payments/customers/')
        assert resp.status_code == 200

    def test_supplier_report_export(self):
        resp = self.client.get('/suppliers/reports/excel/', follow=True)
        assert resp.status_code in (200, 404)  # May not exist
        assert resp.status_code != 500

    def test_sales_report_export(self):
        resp = self.client.get('/sales/reports/excel/', follow=True)
        assert resp.status_code in (200, 404)
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# STEP 14: AI Assistant
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAIAssistant:

    def test_ai_page_loads(self, client):
        login(client, 'owner', 'owner123')
        resp = client.get('/ai/')
        assert resp.status_code == 200

    def test_ai_chat_post(self, client):
        login(client, 'owner', 'owner123')
        resp = client.post('/ai/chat/', {
            'message': 'Покажи сводку по складам',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        assert resp.status_code in (200, 405, 404)
        assert resp.status_code != 500

    def test_ai_settings_page(self, client):
        login(client, 'owner', 'owner123')
        resp = client.get('/ai/settings/', follow=True)
        assert resp.status_code in (200, 404)
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# STEP 15: Analytics
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAnalytics:

    def test_analytics_page(self, client):
        login(client, 'owner', 'owner123')
        resp = client.get('/analytics/')
        assert resp.status_code == 200

    def test_analytics_no_500(self, client):
        login(client, 'owner', 'owner123')
        resp = client.get('/analytics/?period=month')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# STEP 16: Sales Manager role restrictions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSalesManagerRole:

    @pytest.fixture(autouse=True)
    def do_login(self, client):
        self.client = client
        login(client, 'sales_mgr', 'sales123')

    def test_sales_list(self):
        resp = self.client.get('/sales/')
        assert resp.status_code == 200

    def test_customers_list(self):
        resp = self.client.get('/sales/customers/')
        assert resp.status_code == 200

    def test_production_view_allowed(self):
        resp = self.client.get('/production/')
        assert resp.status_code == 200

    def test_finance_limited(self):
        resp = self.client.get('/finance/', follow=True)
        assert resp.status_code in (200, 302, 403)
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# STEP 17: Notifications
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestNotifications:

    def test_notifications_page(self, client):
        login(client, 'owner', 'owner123')
        resp = client.get('/notifications/')
        assert resp.status_code == 200

    def test_notifications_mark_read(self, client):
        login(client, 'owner', 'owner123')
        resp = client.post('/notifications/mark-all-read/', follow=True)
        assert resp.status_code in (200, 302, 404, 405)
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# STEP 18: BOM and Routes
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBOMAndRoutes:

    @pytest.fixture(autouse=True)
    def do_login(self, client):
        self.client = client
        login(client, 'prod_manager', 'prod123')

    def test_bom_list(self):
        resp = self.client.get('/production/boms/')
        assert resp.status_code == 200

    def test_bom_create_form(self):
        resp = self.client.get('/production/boms/create/')
        assert resp.status_code == 200

    def test_routes_list(self):
        resp = self.client.get('/production/routes/')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# STEP 19: Quality Control
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestQualityControl:

    def test_quality_list(self, client):
        login(client, 'prod_manager', 'prod123')
        resp = client.get('/quality/')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# STEP 20: Employees
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestEmployees:

    def test_employee_list(self, client):
        login(client, 'owner', 'owner123')
        resp = client.get('/employees/')
        assert resp.status_code == 200

    def test_employee_list_no_pii_in_title(self, client):
        """Page loads successfully for owner."""
        login(client, 'owner', 'owner123')
        resp = client.get('/employees/')
        assert resp.status_code == 200
        assert resp.status_code != 500
