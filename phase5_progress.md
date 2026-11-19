# Phase 5 progress

## Existing state discovered

- Finance models, three migrations, services, dashboard, payment/account/debt/cost views, templates, PDF receipts, and Excel exports were already present.
- Finance migrations 0001–0003 were applied before this continuation; `phase5_implementation_plan.md` is not present.
- Existing Finance acceptance coverage is `tests/test_phase5_finance_costing.py` (16 tests); before this continuation it passed.
- The worktree already contained changes in sales, suppliers, production, warehouses, dashboards, documentation, and tests. Those changes are preserved and are not part of this Finance work.

## Work already present at continuation

- Added idempotency key fields to customer/supplier payments, transfers, expenses, and general income.
- Added Decimal-safe amount parsing and validation, account currency/active checks, stricter order-party linkage, and replay checks in Finance services.
- Added general income CRUD/storno routes and templates, transfer storno handling, date filters, report export routes, and new Excel report types.
- Added production-cost figures and order profitability display to the finance dashboard; costing reads posted WH-1 issues and returns without creating warehouse movements.
- Added read-only Finance admin registrations and Cyrillic font availability validation for PDF output.

## Current continuation changes

- Added the missing summary PDF export view required by the already registered route.
- Added this progress record.

## Remaining work

- Generate and apply a migration for the idempotency fields; verify migration state.
- Run and fix Finance, integration, and full pytest suites.
- Add targeted tests for idempotent retries, general-income storno, transfer storno, posted returns, dashboard/report outputs, and PDF export.
- Review/report any Finance gaps that cannot be completed safely, especially historical opening balances, due dates (not modeled), and production-cost allocation limitations.
- Complete `phase5_finance_report.md` after checks and record accurate results.
- Do not perform project cleanup until Finance has been verified; preserve all existing non-Finance modifications.
