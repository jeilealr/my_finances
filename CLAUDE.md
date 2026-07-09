# CLAUDE.md — my_finances Agent Playbook

Fast-consumption reference for any agent or developer working in this repository.
Read this before touching any file.

---

## 1. Project Purpose

Personal finance toolkit for one person (EUR-only).

- Extracts transactions from PDF/CSV bank statements (Santander, Revolut, Payback)
- Normalizes them into CSV outputs
- Presents them in a local Streamlit dashboard with 5 tabs

**Primary question the dashboard answers:** how much came in, how much was spent, where did it go, what debt remains, what is the total tracked wealth?

---

## 2. Active Banks

| Bank | Role | Format |
|------|------|--------|
| Santander | Main account, salary source | PDF |
| Revolut | Current + pockets + savings | PDF |
| Payback | Credit-card style debt | CSV |

**Bancolombia** — extractor exists but is excluded from the active pipeline and from all dashboard logic. Do not add it to the dashboard. COP/EUR mixing degrades usefulness.

**N26** — removed. Do not reintroduce.

---

## 3. Repository Map

```
src/
├── dashboard/
│   ├── app.py            — Streamlit layout and interaction ONLY
│   ├── analytics.py      — calculations and business logic
│   ├── categories.py     — category and flow classification
│   ├── charts.py         — Plotly chart construction
│   ├── cli.py            — dashboard CLI entry
│   ├── data_loader.py    — reads normalized CSV outputs
│   └── investments.py    — ETF price loading, valuation, Klarna interest
└── my_finances/
    ├── _cli/             — thin CLI entrypoints only
    │   ├── _main.py
    │   ├── _dashboard.py
    │   ├── _extract_all.py
    │   ├── _santander.py
    │   ├── _payback.py
    │   ├── _revolut.py
    │   ├── _bancolombia.py
    │   └── _shared.py
    ├── common/
    │   ├── paths.py      — WorkspacePaths, env var overrides
    │   ├── logger.py     — logging setup
    │   └── utils.py      — shared helpers
    └── data_extractor/
        ├── base.py       — BankConfig, BankExportResult, TRANSACTION_OUTPUT_COLUMNS
        ├── pipeline.py   — extract_all_data, export_bank_statements
        ├── registry.py   — BANK_CONFIGS, ACTIVE_BANK_ORDER
        ├── santander.py
        ├── revolut.py
        ├── payback.py
        └── bancolombia.py
```

**Do NOT recreate** `src/my_finances/data_extractor/common/` — it was deleted intentionally. Shared helpers belong in `src/my_finances/common/`.

---

## 4. Environment & Commands

```bash
# Activate environment
conda activate finances

# Extract all statements
my_finances extract_all_data

# Launch dashboard (with prior extraction)
my_finances dashboard --update

# Launch dashboard only
my_finances dashboard

# Forward Streamlit flags
my_finances dashboard --update -- --server.headless true

# From automated agent sessions (conda activate may not persist)
conda run -n finances my_finances extract_all_data
```

### Path overrides via environment variables

| Variable | Default |
|----------|---------|
| `MY_FINANCES_WORKSPACE_ROOT` | parent of repo root |
| `MY_FINANCES_STATEMENTS_ROOT` | `workspace/pdf_statements` |
| `MY_FINANCES_OUTPUT_ROOT` | `workspace/outputs` |
| `ALPHA_VANTAGE_API_KEY` | unset (ETF prices fall back to cache) |

---

## 5. Validation Gate

Run these three commands before claiming any change is complete:

```bash
conda run -n finances ruff check src tests
conda run -n finances python -m pytest
conda run -n finances python -c "from streamlit.testing.v1 import AppTest; app = AppTest.from_file('src/dashboard/app.py'); app.run(timeout=30); print(f'exceptions={len(app.exception)} errors={len(app.error)}')"
```

If a command cannot run, say so explicitly and explain why.

---

## 6. Financial Model

Agents must use these exact definitions. Do not reinterpret them.

| Term | Definition |
|------|-----------|
| **Income** | Positive rows from Santander/Revolut — salary, interest, reimbursements. Excludes Payback credits, transfers, savings movements. |
| **Expenses** | Negative rows excluding internal transfers, savings transfers, investments, card repayments, Colombia transfers, blocked-account movements. |
| **Money Left** | `Income − Expenses` per month per currency |
| **Savings movement** | Principal moved into/out of Revolut Instant Access Savings — not an expense |
| **Investments** | Santander ETF purchase principal — not an expense |
| **Investment Fees** | `0.85 EUR` per ETF order — IS an expense |
| **Card Repayment** | Santander AmEx debits + Payback repayment rows — excluded from income and expenses |
| **Colombia Transfer** | Wise/TransferWise to Colombia — extra transaction, not expense |
| **Blocked Account** | Klarna blocked-account deposits — excluded from spending. Principal: 6,000 EUR at 2.79% p.a. from 2026-03-11, simple daily interest |
| **Payback Known Debt** | Known purchases − repayments/credits, clipped at zero after each month; last known value carries forward |
| **Total Net Worth** | Santander + Revolut Account + Revolut Savings + Klarna Principal − Payback Known Debt |
| **Tracked Wealth** | Total Net Worth + ETF Market Value + Klarna Accrued Interest |
| **ETF Gain/Loss** | ETF Market Value − ETF PDF-derived Cost Basis |
| **Budget paycheck** | Recurring UFZ/Helmholtz `Lohn/Gehalt` rows only. Salary from month `n−1` funds budget month `n`. |

---

## 7. Dashboard Tabs

| Tab | Purpose | Must NOT do |
|-----|---------|-------------|
| **Overview** | Net worth, cashflow by bank, extra transactions, Payback debt, statement balances | Inflate expenses with transfers or savings |
| **Spending** | Monthly income vs. expenses vs. money left | Narrow income with expense focus filters; include Payback credits as income |
| **Reports** | Expense-only grouped pie + bar by month | Include salary, transfers, savings, investments in pie |
| **Budget** | Paycheck-based limits and actuals | Mix reimbursements into paycheck base; use total income instead of salary |
| **Transactions** | Full filtered table for auditing | Hide rows; this is the audit trail |

---

## 8. Category Rules

These rules are conservative. Do not infer personal transfers into detailed categories without an explicit rule.

- **Housing & Utilities**: Rent, Electricity, Phone & Internet, Transport, Pharmacy, ATM Withdrawal, Bank Fees
- **Grocery**: Grocery Shopping + Restaurants & Delivery (REWE, LIDL, ALDI, NETTO, KAUFLAND, Lieferando, etc.)
- **Entertainment**: Dance, Fitness, and identified leisure merchants
- **Travel & Holidays**: Travel + Revolut Holidays-pocket expenses
- **Retail & Online Shopping**: retail and online purchases
- **Other**: remaining after conservative classification
- `Insurance & Health` was renamed to `Pharmacy` — use the newer name only

Report pie excludes: Salary, Income, Internal transfers, Savings, Investments, Card repayments, Colombia transfers, Blocked-account movements.

---

## 9. What NOT to Do

- Do not add Bancolombia to any dashboard tab or calculation
- Do not recreate `src/my_finances/data_extractor/common/`
- Do not mix COP and EUR in any calculation
- Do not add UI complexity that does not improve a financial decision
- Do not widen CLI entrypoints with business logic — keep them thin
- Do not infer categories without explicit rules
- Do not count Payback credits as income
- Do not count savings principal as expenses
- Do not count ETF principal as expenses (fees are expenses)
- Do not use `data_extractor/common` path — it does not exist

---

## 10. Output Files

| File | Description |
|------|-------------|
| `outputs/combined/all_transactions.csv` | Full merged transaction table |
| `outputs/extraction_summary.csv` | Per-bank extraction row counts |
| `outputs/statement_balance_summary.csv` | Statement opening/closing balances |
| `outputs/santander/santander_statement_balances.csv` | Santander balance history |
| `outputs/revolut/revolut_subaccount_balances.csv` | Revolut pocket/savings balances |
| `outputs/market_prices/` | ETF price cache (Alpha Vantage / Yahoo / Boerse Frankfurt) |

Transaction column contract (`TRANSACTION_OUTPUT_COLUMNS`):
`bank, account, subaccount, date, value_date, description, amount, currency, balance, notes, page, source_file`

---

## 11. Agent Review Lenses

When making non-trivial changes, apply these perspectives in order:

1. **Coordinator** — does this match the product goal?
2. **Backend** — extraction, loading, typing, testability
3. **Financial Advisor** — formulas, signs, transfers, debt, savings
4. **Plotting/Interactivity** — hover text, legends, filters, chart type
5. **Frontend** — layout, visual hierarchy, readable numbers
6. **Digital Designer** — color, spacing, typography, consistency
7. **Marketing** — do labels explain value to a human?
8. **Coherence** — terms used uniformly across tabs, docs, tests
9. **Proofreading** — spelling, grammar, user-facing copy
10. **Senior Developer** — maintainability, duplication, edge cases

---

## 12. Installed Plugins

| Plugin | When to use |
|--------|-------------|
| `superpowers` | Planning, brainstorming, parallel agent dispatch, writing plans |
| `caveman` | Terse commit messages, code review comments |
| `ui-ux-pro-max` | Visual/graphical design review — presentation layer only, not data |
| `impeccable` | Code polish: naming, dead code, magic numbers, docstring quality |
| `ponytail` | Technical debt: outdated patterns, unused code, maintainability |

---

## 13. Audit Agents

A 12-agent parallel audit is defined in `audit/AUDIT_PLAN.md`. Results land in `audit/sections/`. The coordinator produces `audit/CONSOLIDATED_AUDIT_REPORT.md`.
