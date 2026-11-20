# FurniCore ERP — Phase 5.1 Finance Completion Report

## Result

Phase 5.1 was continued on branch `python-django` without resetting or replacing the existing work. Finance, Sales, Suppliers, and Warehouse changes were reviewed in place. Migrations were applied and verified. No commit was created, no files were deleted, and Phase 6 work was not started.

## Completed workflows

- **Payment due dates and aging:** SalesOrder and PurchaseOrder now store payment due dates. Receivable/payable views and Excel reports show remaining debt, overdue days, and aging buckets; both registers support counterparty filtering.
- **Finished-goods costing and gross profit:** Shipment lines retain their sales-order item, sale price, cost, and costing basis. WH-2 shipment costing allocates FIFO layers from posted finished-goods movements. Order profitability derives revenue from shipped quantities/prices and subtracts posted returns and returned COGS. Initial stock without movement history is explicitly valued at the product's standard production cost.
- **Customer returns:** A return is linked to its SalesOrder and posted WH-2 shipment, validates returned quantities, and creates a `CUSTOMER_RETURN` document through the existing warehouse `post_document` service. The service posts a cash refund only up to net completed customer payments, protects the operation with row locks and a required idempotency key, and records AuditLog entries. Storno reverses the WH-2 movement through the warehouse cancellation service and restores the account balance; it fails atomically if the returned stock has already left the warehouse.
- **Cashflow and P&L:** Posted customer refunds reduce accrual revenue and are included in cash outflow. Internal account transfers remain excluded from income and expenses.
- **Access and exports:** Finance write operations require the existing OWNER/ADMIN/ACCOUNTANT policy; DEMO_VIEWER is read-only. PDF and Excel export endpoints and payment PDF routes are covered for permitted and denied roles.
- **Return UI:** The form now supports selecting an order and shipment before entering return quantities. Invalid, non-finite, or negative quantities are surfaced rather than silently ignored.

## Migrations

These migrations were already present in the working changeset, were applied, and are all marked applied:

| App | Migration |
|---|---|
| finance | `0005_alter_expense_category` |
| finance | `0006_customerreturn_customerreturnitem` |
| sales | `0004_salesorder_payment_due_date` |
| suppliers | `0003_purchaseorder_payment_due_date` |
| warehouses | `0004_warehousedocumentitem_costing_method_and_more` |

No additional migration was needed after the final code changes.

## Files changed or created

Changes preserved from the previous Phase 5.1 session and this continuation:

- Finance: `apps/finance/admin.py`, `apps/finance/models.py`, `apps/finance/reports.py`, `apps/finance/services.py`, `apps/finance/urls.py`, `apps/finance/views.py`
- Sales: `apps/sales/models.py`, `apps/sales/services.py`, `apps/sales/views.py`
- Suppliers: `apps/suppliers/models.py`, `apps/suppliers/services.py`, `apps/suppliers/views.py`
- Warehouses: `apps/warehouses/models.py`, `apps/warehouses/services.py`
- Templates: `templates/finance/debts/payables.html`, `templates/finance/debts/receivables.html`, `templates/finance/expenses/expense_form.html`, `templates/finance/expenses/expense_list.html`, `templates/finance/index.html`, `templates/finance/returns/return_form.html`, `templates/finance/returns/return_list.html`, `templates/sales/create.html`, `templates/suppliers/orders/create.html`
- Tests and tracking: `tests/test_phase5_finance_costing.py`, `phase5_progress.md`
- Migrations: the five files listed above
- Reports: `phase5_1_finance_completion_report.md` (new), `phase5_finance_report.md`, `final_audit_report.md`

`cleanup_report.md` remains unchanged. No cleanup deletions were made.

## Verification performed

| Check | Result |
|---|---|
| `.venv/bin/python manage.py check` | Passed; no issues. |
| `.venv/bin/python manage.py makemigrations --check --dry-run` | Passed; no changes detected. |
| `showmigrations finance sales suppliers warehouses` | All listed migrations applied. |
| Finance / warehouse / sales / RBAC / routes / acceptance selection | 65 passed. |
| Finance costing tests | 27 passed. |
| `.venv/bin/python -m compileall -q apps/finance apps/sales apps/suppliers apps/warehouses tests/test_phase5_finance_costing.py` | Passed. |
| `git diff --check` | Passed. |
| Final `.venv/bin/pytest -q` | **147 passed in 348.61 seconds**, including browser E2E tests. |

An earlier full-suite run had two intermittent browser-login timeouts (144 passed, 2 failed); both tests passed when retried in isolation, and the final full-suite run passed all 147 tests. The E2E server was stopped after testing.

## Remaining limitations

- Due dates are stored on orders, not separate invoice records. Legacy orders without a verified due date remain in the `no_due_date` category; do not backfill dates without source records.
- Historical WH-2 opening stock with no costed movement history uses the product's standard production cost. Reconcile opening quantities and costs against source records before treating COGS as statutory accounting.
- The project still lacks dedicated actual-cost ledgers for electricity, equipment depreciation, and packaging. Detailed report-specific PDF documents are also not implemented; existing Excel reports and summary/payment PDFs remain available.

## Reproduction

From the project root:

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/pytest -q tests/test_phase5_finance_costing.py tests/test_warehouse_phase2.py tests/test_phase4_procurement_sales.py tests/test_demo_viewer_rbac.py tests/test_all_routes.py tests/test_phase5_5_acceptance.py
.venv/bin/python manage.py runserver 127.0.0.1:8099 --noreload
.venv/bin/pytest -q
```

The browser E2E tests require the local server to be available at `localhost:8099`. Stop it after the suite completes.
