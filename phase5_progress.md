# FurniCore ERP — Phase 5.1 Progress

## Starting state and preservation

- Continued on the existing `python-django` branch; retained the existing uncommitted Finance/Sales/Suppliers/Warehouse changes and reviewed their full diff before editing.
- The prior implementation-plan file is not present. Existing Phase 5 models, services, templates, reports, audit logging, idempotency fields, and tests were kept and extended.
- The working tree includes earlier work beyond this continuation. No unrelated changes were reverted, no commit was made, and no files or data were deleted.
- `.env` is ignored by `.gitignore`; backups, uploads, migrations, and `furnicore_ts_backup/` were preserved.

## Completed

- Added due dates to sales and purchase orders, plus receivable/payable aging buckets and counterparty filtering.
- Added WH-2 finished-goods FIFO cost allocation from existing stock movements and recorded shipment sales values; gross profit now uses shipped revenue and net posted returns.
- Added customer return documents linked to their source order and shipment. Returns go through the existing WH-2 `CUSTOMER_RETURN` / `post_document` workflow, refund only completed payments, and support transactional storno, audit logging, locking, and exact-payload idempotency.
- Updated the return form selection workflow and reject invalid or negative quantities explicitly.
- Included customer refunds in cash outflow and net accrual revenue; transfers between accounts remain excluded from P&L/cashflow.
- Added tests for due-date aging, shipment costing and gross profit, paid-amount refund limits, partial returns, idempotent retries and key reuse, WH-2 stock reversal, refund reporting, exports, and Finance RBAC.
- Updated `phase5_finance_report.md` and the historical limitation/recommendation text in `final_audit_report.md`. Full details are in `phase5_1_finance_completion_report.md`.

## Migrations

Created/applied migrations already present in the continued changes:

- `apps/finance/migrations/0005_alter_expense_category.py`
- `apps/finance/migrations/0006_customerreturn_customerreturnitem.py`
- `apps/sales/migrations/0004_salesorder_payment_due_date.py`
- `apps/suppliers/migrations/0003_purchaseorder_payment_due_date.py`
- `apps/warehouses/migrations/0004_warehousedocumentitem_costing_method_and_more.py`

All five are applied. `makemigrations --check --dry-run` reports no model changes.

## Verification

- `manage.py check`: passed.
- `makemigrations --check --dry-run`: passed, no changes detected.
- Finance/warehouse/sales/RBAC/routes/acceptance selection: 65 passed.
- Finance costing tests: 27 passed.
- Compileall for changed Python apps/tests: passed.
- `git diff --check`: passed.
- Final full pytest: **147 passed in 348.61 seconds**, including E2E tests. An earlier full run had two intermittent E2E login timeouts; both passed in isolation and the final full run passed.

## Remaining work / limitations

- Legacy orders may have no verified due date and remain unaged until authoritative dates are available; due dates currently belong to orders, not separate invoice records.
- Opening WH-2 stock without costed movement history uses the product's standard production cost. Reconcile this inventory before treating COGS as statutory accounting.
- Separate actual-cost ledgers for electricity, equipment depreciation, and packaging are not modeled; report-specific detailed PDF exports are not implemented.
- No cleanup deletions were made. Phase 6 has not started.

See `phase5_1_finance_completion_report.md` for the file list and exact test commands/results.
