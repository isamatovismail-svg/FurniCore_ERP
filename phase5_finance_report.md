# FurniCore ERP — Phase 5 Finance report

## Existing state and preserved work

At the start of this continuation, the worktree was clean at commit `2f6720c`; the earlier Phase 5 implementation was already committed and was not reverted. The Finance module already included its payment/account models and services, dashboard and operation views, templates, PDF/Excel report functions, and migrations `0001`–`0004`. The requested `phase5_implementation_plan.md` was not present. Migration `0004` existed but was unapplied at the beginning of this continuation; it has since been applied. Migration `0005` was added in this continuation.

The committed Phase 5 work includes customer and supplier payment flows, transfers, income/expense registers, operation reversals, idempotency keys, dashboard costing/profitability, PDF and Excel exports, and Finance RBAC integration. PDF routing and its view were present; no duplicate view or route was added.

## Changes in this continuation

| File | Change |
|---|---|
| `apps/finance/models.py` | Restored the existing `OFFICE` expense category. |
| `apps/finance/migrations/0005_alter_expense_category.py` | Added and applied the category migration. |
| `apps/finance/services.py` | Preserved duplicate-payment protection for rapid repeated submissions; allowed an expense to be recorded without a cash account until payment; improved plan/actual production-cost calculations using existing BOM, posted warehouse issue/return movements, recorded labor, and existing waste data. No warehouse movement is created or edited by Finance. |
| `apps/finance/reports.py` | Kept monetary values as `Decimal` in Excel output rather than converting to binary floats. |
| `templates/finance/expenses/expense_form.html` | Made account selection optional for an expense not yet paid. |
| `tests/test_phase5_finance_costing.py` | Added regression coverage for idempotent submission, storno, production returns, PDF output, and Excel exports. |
| `phase5_progress.md` | Updated the progress record and remaining limitations. |
| `phase5_finance_report.md` | Added this report. |

## Implemented behavior and limits

- Customer and supplier payments support partial/full payments, multiple payments, order linkage, and outstanding balances. Persisted idempotency keys protect retries; a short-window duplicate guard remains for identical payment requests without keys.
- Cash/bank account transactions are performed transactionally with account locking and balance checks. Transfers are not treated as income or expense. Posted operations are reversed through storno rather than deletion.
- Income and expense records support categories, dates, comments, accounts, and responsible users. An unpaid/uncategorized-by-account expense can be recorded without an account; posting a disbursement still checks the account balance.
- Finance dashboard and reports include income/expense and receivable/payable balances, payment history, order profit estimates, and production costing. Production costing reads existing posted WH-1 issues and production returns; Finance does not create fictitious warehouse movements or change historical movements.
- PDF endpoints use ReportLab and a Cyrillic-capable system font. Excel reports use openpyxl and monetary Decimal values. PDF and workbook responses were tested.
- RBAC is integrated with existing application permissions; audit logging follows the existing Finance service patterns.

This report records the Phase 5 state before the Phase 5.1 continuation. The subsequently added order due dates and debt aging, finished-goods shipment costing, and WH-2/customer-refund workflow are documented in `phase5_1_finance_completion_report.md`. Production overhead remains limited to data represented in current models; separate actual electricity, equipment-depreciation, and packaging ledgers are not available. There is no separate detailed PDF for every report type; detailed report exports are available in Excel. Initial balance administration remains limited by the existing account-management UI.

## Migrations

- Finance migrations `0001` through `0005` are applied on the configured database, including existing idempotency migration `0004` and `0005_alter_expense_category`.
- `makemigrations --check --dry-run` reported no model changes needing migration.

## Verification actually run

| Command/check | Result |
|---|---|
| `python manage.py check` | Passed. |
| `python manage.py makemigrations --check --dry-run` | Passed; no changes detected. |
| Finance migration status (`showmigrations finance`) | `0001`–`0005` applied. |
| Finance, RBAC, and Phase 5.5 acceptance tests at Phase 5 completion | 31 passed. |
| Finance, integration, and route tests in final audit | 32 passed in 15.90 seconds. |
| Full pytest suite, first attempt without the required E2E server | 81 passed; 59 browser E2E tests failed to connect to `localhost:8099`. |
| Full pytest suite, rerun with the local server available at `localhost:8099` | 140 passed in 204.32 seconds. |
| `git diff --check` | Passed after the final audit/report updates. |

The first full-suite failures were environment-dependent connection failures; the rerun with the expected server running passed. The server was stopped after testing. No cleanup or file deletion was performed.

## Final audit follow-up

The subsequent final audit found and corrected a cashflow classification issue: an expense without a linked account is recorded as unpaid, so it remains in accrual expense/profit totals but must not be reported as a cash outflow. Cash KPIs, the dashboard breakdown, and Excel cashflow now distinguish expenses linked to an account (paid) from those without one (unpaid). The expense register and income/expense workbook show the unpaid state. A regression test covers this distinction. The final full suite passed 141 tests; see `final_audit_report.md`.

## Run instructions

From the repository root, activate the project environment and run:

```sh
python manage.py check
python manage.py showmigrations finance
python manage.py makemigrations --check --dry-run
pytest
```

The browser E2E tests require their configured local application endpoint to be available at `localhost:8099`.

Phase 5 remains in progress for the limitations listed above. Phase 6 was not started.
