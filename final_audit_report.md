# FurniCore ERP — Final Audit & Safe Cleanup

**Audit date:** 2026-11-20  
**Branch:** `python-django`  
**Commit created:** No

## Scope and starting state

Reviewed the branch and full working-tree change set before editing. The pending Finance work from the previous session was preserved. The requested Finance migrations `0001`–`0005` are applied. `.gitignore` was reviewed; `.env`, backups, uploads, generated static assets, logs, virtual environments, and build artifacts were left untouched.

## Finance audit

The table below records the earlier Phase 5 audit checkpoint. Phase 5.1 subsequently added due-date aging, shipment costing, customer returns/refunds, and finance read-access checks; see `phase5_1_finance_completion_report.md` for current behavior.

| Area | Audit result |
|---|---|
| Customer payments | Supports partial/multiple payments tied to the SalesOrder/customer and updates the linked account transactionally. Overpayments are rejected. Storno is recorded instead of deleting the payment. |
| Supplier payments | Supports partial/full payments and supplier/order linkage, prevents overpayment and insufficient account balance, and records storno. |
| Income and expenses | Uses Decimal amounts, categories, dates, responsible user, and comments. An expense without an account represents an unpaid expense. |
| Accounts and transfers | Cash/bank/Kaspi account balances are updated by service operations. Transfers lock accounts in stable ID order and are excluded from income/expense totals. Negative outgoing balances are rejected. |
| Debts | Receivable/payable balances derive from existing SalesOrder/PurchaseOrder payment properties. Date filtering is available; no due-date aging is modeled. |
| Production costing | Reads existing posted WH-1 issues and production returns, BOM plan values, labor/stage records, overhead, and recorded waste. It does not create warehouse movements or rewrite history. |
| PDF/Excel | Finance PDF routes resolve to existing views; ReportLab PDF and openpyxl workbooks are covered by tests. Cyrillic font availability is explicitly checked. Excel monetary cells retain Decimal input values. |
| RBAC | Mutation and storno endpoints check the existing Owner/Admin/Accountant policy; finance services record AuditLog events for financial operations. Finance read/list/report views require login but are not limited to those roles. Confirm before production whether detailed financial read access should remain available to every authenticated employee. |
| Transactions/idempotency | Financial write services use atomic transactions and row locks where needed. Unique idempotency-key fields protect repeated requests; same-parameter payment retries without a key also have a short duplicate guard. Existing database uniqueness prevents duplicate keys from being committed if simultaneous requests race. The duplicate guard can reject an intentional identical payment submitted within its short window. |

### Error corrected during this audit

Expenses without a linked account are presented by the UI as unpaid, but the prior cashflow KPI included them in cash outflow. The service now computes paid expenses separately for cashflow while retaining all non-storno expenses in accrual expense/profit totals. Dashboard breakdown and Excel cashflow use the paid amount; the expense list and Excel transaction report label account-less expenses as unpaid. A regression test verifies this behavior.

### Limitations at the time of this audit

The following describes the state before the Phase 5.1 continuation in `phase5_1_finance_completion_report.md`; that report supersedes these three findings:

1. SalesOrder and PurchaseOrder had no payment due dates or overdue-debt aging.
2. Finished-goods stock valuation and COGS allocation to shipments were incomplete.
3. Customer returns were not integrated with WH-2 stock and account refunds.

Other limits at that point included incomplete actual cost ledgers for electricity/equipment/packaging, no detailed PDF for every report type, and no fully featured account opening-balance management workflow.

## Safe cleanup outcome

No files were deleted. The candidate review and evidence are in `cleanup_report.md`. No unused dependency, CSS/JS asset, implementation duplicate, or temporary file was proven safe and necessary to remove. Empty Python `__init__.py` files are package markers and were retained. `furnicore_ts_backup/` compares equal by path/content to the active tree, but is a protected backup and was left untouched.

## Files changed and commit preparation

Files in the current change set:

- `apps/finance/models.py`
- `apps/finance/migrations/0005_alter_expense_category.py` (new; applied)
- `apps/finance/reports.py`
- `apps/finance/services.py`
- `templates/finance/expenses/expense_form.html`
- `templates/finance/expenses/expense_list.html`
- `templates/finance/index.html`
- `tests/test_phase5_finance_costing.py`
- `phase5_progress.md`
- `phase5_finance_report.md`
- `final_audit_report.md` (new)
- `cleanup_report.md` (new)

The full content of the pending diffs was reviewed. No commit was made.

## Verification results

| Check | Result |
|---|---|
| `.venv/bin/python manage.py check` | Passed; no issues. |
| `.venv/bin/python manage.py makemigrations --check --dry-run` | Passed; no changes detected. |
| `.venv/bin/python manage.py showmigrations finance` | Finance migrations `0001`–`0005` all applied. |
| Finance / Phase 5.5 integration / route tests | 32 passed in 15.90 seconds. |
| URL resolver smoke check | Dashboard, payment forms, accounts, receivables, payables, costing, PDF, and Excel routes resolved to their expected views. |
| PDF/Excel checks | Finance test coverage passed, including PDF response and supported workbook types. |
| Full pytest (`.venv/bin/pytest -q`) | **141 passed in 219.62 seconds.** The server needed by E2E tests was available at `localhost:8099`; it was stopped after testing. |
| `compileall` for Finance/tests | Passed. |
| `git diff --check` | Passed after the final audit/report updates. |

The previous full-suite baseline was 140 passed. This run collected 141 because the audit added one regression test, and all 141 passed.

## Recommendations before real operation

- Confirm Finance read-access policy for ordinary employee roles and add role-specific access tests if reports should be restricted.
- Review orders with no payment_due_date and backfill only from verified contractual records.
- Reconcile opening WH-2 quantities/costs and validate FIFO layers against physical inventory before relying on COGS as statutory accounting.
- Verify opening account balances and reconciliation procedures against bank/cash statements.
- Deploy with controlled credentials, HTTPS, database backups, monitoring, and an explicitly configured Cyrillic PDF font.

Phase 6 was not started.
