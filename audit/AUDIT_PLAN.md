# my_finances — Full Repository Audit Plan

**Date:** 2026-07-09  
**Approach:** 12 specialist agents run in parallel → 1 coordinator produces the consolidated report  
**Design spec:** `docs/superpowers/specs/2026-07-09-audit-plan-design.md`  
**Output:** `audit/CONSOLIDATED_AUDIT_REPORT.md`

---

## How to Run

1. Read `CLAUDE.md` before dispatching any agent.
2. Use the `superpowers:dispatching-parallel-agents` skill to launch agents 1–12 simultaneously.
3. Each agent writes its findings to `audit/sections/<NN>_<name>.md` using the section schema below.
4. Once all 12 section files exist, run the coordinator agent (agent 13).

---

## Section File Schema

Every specialist agent must use this exact structure:

```markdown
## [Agent Name] Findings

### Critical
<!-- Issues that must be fixed before trusting any output -->

### High
<!-- Significant bugs, security risks, or calculation errors -->

### Medium
<!-- Code quality, UX, or maintainability issues -->

### Low
<!-- Minor polish, naming, or cosmetic issues -->

### Positive Observations
<!-- What is working well and should be preserved -->
```

---

## Agent Prompts

### Agent 1 — Cybersecurity

**Output file:** `audit/sections/01_cybersecurity.md`  
**Skill:** `security-review`

```
You are a cybersecurity auditor reviewing the my_finances personal finance repository.

Read CLAUDE.md first for full context. Then audit all files under src/ and the root config files.

Focus on:
- File path handling: are paths constructed safely? Any traversal risks?
- Sensitive data exposure: CSV files contain personal financial data — are they written to
  predictable, non-web-accessible locations? Any risk of accidental exposure?
- API key handling: ALPHA_VANTAGE_API_KEY is read from env — is it ever logged or written to disk?
- Environment variable usage: any secrets hardcoded? Any use of os.system or subprocess?
- pdfplumber usage: any risk from malformed or malicious PDFs?
- Dependency hygiene: check pyproject.toml for unpinned dependencies that could introduce
  supply-chain risk.

Write your findings to audit/sections/01_cybersecurity.md using the section schema in
audit/AUDIT_PLAN.md. Do not modify any source files.
```

---

### Agent 2 — Frontend Design

**Output file:** `audit/sections/02_frontend_design.md`  
**Skill:** `code-review`

```
You are a frontend design auditor reviewing the my_finances Streamlit dashboard.

Read CLAUDE.md first. Then read src/dashboard/app.py in full.

Focus on:
- Layout hierarchy: is the sidebar well-organized? Are filters logically grouped?
- Tab organization: do the 5 tabs (Overview, Spending, Reports, Budget, Transactions) flow logically?
- KPI cards: are important numbers prominent and readable? Is there visual clutter?
- Filter UX: are date range, bank, account, category filters easy to use and understand?
- Narrow-viewport behavior: does the layout degrade gracefully at smaller widths?
- User-facing labels: are column names, chart titles, and metric labels clear to a non-technical user?
- Consistency: are similar elements styled/labeled consistently across tabs?

Note: the plots and data content are already decided. This audit is about presentation clarity,
not about changing what information is shown.

Write your findings to audit/sections/02_frontend_design.md using the section schema in
audit/AUDIT_PLAN.md. Do not modify any source files.
```

---

### Agent 3 — Backend Design

**Output file:** `audit/sections/03_backend_design.md`  
**Skill:** `code-review`

```
You are a backend design auditor reviewing the my_finances extraction pipeline.

Read CLAUDE.md first. Then read these files in order:
- src/my_finances/data_extractor/base.py
- src/my_finances/data_extractor/registry.py
- src/my_finances/data_extractor/pipeline.py
- src/my_finances/_cli/_extract_all.py
- src/my_finances/_cli/_shared.py
- src/dashboard/data_loader.py

Focus on:
- Pipeline architecture: is the extract → transform → write flow clean and consistent?
- CLI design: are entrypoints thin? Any business logic leaking into CLI modules?
- Data loading contracts: does data_loader.py have clear input expectations?
- Error handling: what happens when a PDF is malformed, empty, or missing?
- Caching strategy: how does @st.cache_data interact with the extraction pipeline?
- BankConfig/BankExportResult design: are these typed contracts well-defined and stable?
- Active vs. inactive banks: is Bancolombia clearly separated from the active pipeline?

Also check test coverage gaps for the backend (complement agent 11 — Test Coverage).

Write your findings to audit/sections/03_backend_design.md using the section schema in
audit/AUDIT_PLAN.md. Do not modify any source files.
```

---

### Agent 4 — Python Architecture

**Output file:** `audit/sections/04_python_architecture.md`  
**Skill:** `impeccable`

```
You are a Python architecture auditor reviewing the my_finances codebase.

Read CLAUDE.md first. Then read all files under src/ systematically.

Focus on:
- Module boundaries: does each file have one clear responsibility? Any boundary violations?
- Import hygiene: any circular imports, star imports, or unnecessary cross-layer imports?
- Type annotations: are public functions and dataclasses fully annotated?
- Dataclass usage: are frozen dataclasses used where immutability is expected?
- Separation of concerns: does app.py contain any business logic? Does analytics.py
  contain any Streamlit calls?
- AGENTS.md compliance: are the code organization rules in AGENTS.md being followed?
- Dead code: any imports, functions, or modules that are never called?

Write your findings to audit/sections/04_python_architecture.md using the section schema in
audit/AUDIT_PLAN.md. Do not modify any source files.
```

---

### Agent 5 — Graphical Design

**Output file:** `audit/sections/05_graphical_design.md`  
**Skill:** `ui-ux-pro-max`

```
You are a graphical design auditor reviewing the my_finances Streamlit dashboard.

Read CLAUDE.md first. Then read src/dashboard/charts.py and src/dashboard/app.py.

Focus on visual presentation only — do not change what data is shown or what charts exist.

Focus on:
- Color palette: is the palette (INCOME_COLOR, EXPENSE_COLOR, NET_COLOR, etc.) consistent
  and appropriate for a financial dashboard? Any colors that are too similar or confusing?
- Chart typography: are font sizes readable? Are chart titles, axis labels, and legends clear?
- Spacing and layout: is whitespace used well? Are charts cramped or too spread out?
- Visual consistency: do all 5 tabs feel like the same application? Any mismatched styles?
- Chart type appropriateness: does each chart type match its question? (e.g., bar for
  monthly comparison, pie for composition)
- Color-blind safety: are the income/expense colors distinguishable without relying on
  red/green alone?

This audit is about how the existing content is presented, not about adding or removing features.

Write your findings to audit/sections/05_graphical_design.md using the section schema in
audit/AUDIT_PLAN.md. Do not modify any source files.
```

---

### Agent 6 — Statistical / Math

**Output file:** `audit/sections/06_statistical_math.md`  
**Skill:** `code-review`

```
You are a statistical and mathematical correctness auditor reviewing the my_finances dashboard.

Read CLAUDE.md first (especially section 6, Financial Model). Then read:
- src/dashboard/analytics.py (in full)
- src/dashboard/investments.py (in full)

For each formula, verify it matches the definition in CLAUDE.md and AGENTS.md.

Check specifically:
- Net Worth: Santander + Revolut Account + Revolut Savings + Klarna Principal − Payback Debt
- Tracked Wealth: Net Worth + ETF Market Value + Klarna Accrued Interest
- ETF Gain/Loss: Market Value − PDF-derived Cost Basis
- Klarna interest: simple daily interest on 6,000 EUR at 2.79% p.a. from 2026-03-11
  (not compound — verify it is simple daily: principal × rate × days / 365)
- Payback debt: known purchases − repayments/credits, clipped at zero, carry-forward logic
- Budget calculations: limit = paycheck × %, usage = actual / limit, difference = limit − actual
- Money Left: income − expenses (check signs are correct and transfers are excluded)
- Budget paycheck base: only Lohn/Gehalt rows, salary from month n−1 funds month n

Flag any formula where the implementation deviates from the documented definition, even slightly.

Write your findings to audit/sections/06_statistical_math.md using the section schema in
audit/AUDIT_PLAN.md. Do not modify any source files.
```

---

### Agent 7 — Finance Expert

**Output file:** `audit/sections/07_finance_expert.md`  
**Skill:** `code-review`

```
You are a personal finance expert auditing the my_finances dashboard for financial correctness.

Read CLAUDE.md first (especially sections 6 and 7). Then read:
- src/dashboard/categories.py (in full)
- src/dashboard/analytics.py (in full)
- AGENTS.md sections: Financial Model, Dashboard Tabs, Category Rules

Focus on:
- Category classification: do Revolut savings interest rows go to Income, not Savings?
  Do Santander AmEx debits go to Card Repayment, not Expenses?
- Double-counting risks: could a Payback repayment appear as both a Payback credit and
  a Santander expense?
- Investment separation: is ETF principal cleanly separated from ETF fees in calculations?
- Budget vs. Spending separation: does the Budget tab use only Lohn/Gehalt for its paycheck
  base, while Spending uses all actual income?
- Payback Known Debt carry-forward: if no new Payback CSV rows exist for a month, does
  the last known debt carry forward correctly?
- Revolut Holidays pocket: are future Holidays-pocket expenses reported under
  Travel & Holidays, not their raw merchant category?
- Financial definitions: do all user-facing labels in the dashboard match the definitions
  in CLAUDE.md and AGENTS.md exactly?

Write your findings to audit/sections/07_finance_expert.md using the section schema in
audit/AUDIT_PLAN.md. Do not modify any source files.
```

---

### Agent 8 — Impeccable (Code Polish)

**Output file:** `audit/sections/08_impeccable.md`  
**Skill:** `impeccable`

```
You are a code polish auditor reviewing the my_finances codebase for quality and consistency.

Read CLAUDE.md first. Then run the impeccable skill across src/ and tests/.

Focus on:
- Naming conventions: are functions, variables, and constants named clearly and consistently?
- Dead code: any unreachable code, commented-out blocks, or unused imports?
- Magic numbers: any hardcoded numeric literals that should be named constants?
  (e.g., 0.85 EUR fee, 6000 EUR Klarna principal, 2.79% rate, 32%/20%/10%/18% budget limits)
- Docstring quality: are module, class, and function docstrings present and accurate?
- Pattern consistency: are similar operations handled consistently across different bank
  extractors and dashboard modules?
- String literals: are user-facing strings consistent in capitalization and phrasing?

Write your findings to audit/sections/08_impeccable.md using the section schema in
audit/AUDIT_PLAN.md. Do not modify any source files.
```

---

### Agent 9 — Ponytail (Technical Debt)

**Output file:** `audit/sections/09_ponytail.md`  
**Skill:** `ponytail`

```
You are a technical debt auditor reviewing the my_finances codebase.

Read CLAUDE.md first. Then run the ponytail skill across the repository.

Focus on:
- N26/Bancolombia remnants: any dead references, imports, or CLI flags for removed banks?
- Outdated patterns: any Python 2-style code, deprecated stdlib usage, or patterns superseded
  by the current architecture (e.g., anything that should use BankConfig but doesn't)?
- Dependency hygiene: any unpinned or conflicting dependencies in pyproject.toml or
  environment.yml? Any packages that are imported but not listed as dependencies?
- Long-term maintainability: any modules that are growing too large or doing too many things?
- Git state: any untracked files or uncommitted changes that represent in-progress work?
  (check git status output context)
- Migration risks: any code that would make adding a future bank extractor difficult?

Write your findings to audit/sections/09_ponytail.md using the section schema in
audit/AUDIT_PLAN.md. Do not modify any source files.
```

---

### Agent 10 — Accessibility

**Output file:** `audit/sections/10_accessibility.md`  
**Skill:** `code-review`

```
You are an accessibility auditor reviewing the my_finances Streamlit dashboard.

Read CLAUDE.md first. Then read src/dashboard/charts.py and src/dashboard/app.py.

Focus on WCAG AA compliance for a local desktop financial dashboard:
- Color contrast: check the color palette constants in charts.py against WCAG AA ratio (4.5:1
  for normal text, 3:1 for large text). Flag any color pairs used together that fail.
  Key pairs to check: INCOME_COLOR on BACKGROUND_COLOR, EXPENSE_COLOR on BACKGROUND_COLOR,
  FONT_COLOR on BACKGROUND_COLOR.
- Color-only information: are income (green) and expense (red) ever distinguished ONLY by
  color, with no label, icon, or pattern? If so, flag it.
- Text sizing: are any chart labels, axis ticks, or metric values too small to read at
  standard display resolution?
- Screen-reader / alt text: Streamlit does not natively support alt text on Plotly charts —
  flag any chart that conveys unique information not readable via the surrounding UI.
- Keyboard navigation: can a user navigate all tabs and filters without a mouse in Streamlit?
- Chart legends: are all chart legends descriptive enough to understand without color?

Write your findings to audit/sections/10_accessibility.md using the section schema in
audit/AUDIT_PLAN.md. Do not modify any source files.
```

---

### Agent 11 — Test Coverage

**Output file:** `audit/sections/11_test_coverage.md`  
**Skill:** `code-review`

```
You are a test coverage auditor reviewing the my_finances test suite.

Read CLAUDE.md first. Then read all files under tests/ and the source files they target.

Existing test files:
- tests/test_dashboard_reporting.py
- tests/test_extractor_base.py
- tests/test_logger.py
- tests/test_paths.py

For each of the following critical paths, determine whether a test exists and whether
it covers edge cases:

1. Net worth calculation (Total Net Worth, Tracked Wealth)
2. Budget percentage calculations (limit, usage, difference, paycheck remaining)
3. Money Left = Income − Expenses (correct sign, correct exclusions)
4. Payback Known Debt carry-forward when no new rows exist
5. ETF valuation fallback to cost basis when no market price is available
6. Klarna simple daily interest accrual
7. Santander AmEx debit classified as Card Repayment (not Expenses)
8. Revolut savings interest classified as Income (not Savings)
9. TRANSACTION_OUTPUT_COLUMNS schema enforced in pipeline output
10. Category enrichment (enrich_transactions) for key merchant rules

For each gap, describe what the test should verify. Prioritize by financial risk of a silent error.

Write your findings to audit/sections/11_test_coverage.md using the section schema in
audit/AUDIT_PLAN.md. Do not modify any source files.
```

---

### Agent 12 — Data Schema Validation

**Output file:** `audit/sections/12_data_schema.md`  
**Skill:** `code-review`

```
You are a data schema validation auditor reviewing the my_finances extraction pipeline.

Read CLAUDE.md first (especially the TRANSACTION_OUTPUT_COLUMNS contract in section 10).
Then read:
- src/my_finances/data_extractor/base.py
- src/my_finances/data_extractor/pipeline.py
- src/my_finances/data_extractor/santander.py
- src/my_finances/data_extractor/revolut.py
- src/my_finances/data_extractor/payback.py
- src/dashboard/data_loader.py

Focus on:
- Column contract: does every extractor produce exactly TRANSACTION_OUTPUT_COLUMNS?
  Any extra or missing columns?
- Dtype stability: are date columns parsed as datetime? Are amount/balance columns float?
  Are text columns string? Check prepare_transaction_frame() in base.py.
- Null/missing handling: what happens when a PDF row has no amount, no date, or no description?
  Is it silently dropped, filled, or does it propagate as NaN into the dashboard?
- Schema drift: does data_loader.py make any assumptions about columns that could break
  if an extractor changes its output?
- Revolut subaccount balances: does revolut_subaccount_balances.csv have a stable schema?
  What columns does data_loader.py expect from it?
- Statement balance schema: does statement_balance_summary.csv match STATEMENT_BALANCE_COLUMNS
  in data_loader.py across all banks?

Write your findings to audit/sections/12_data_schema.md using the section schema in
audit/AUDIT_PLAN.md. Do not modify any source files.
```

---

### Agent 13 — Coordinator (Run after all 12 sections exist)

**Output file:** `audit/CONSOLIDATED_AUDIT_REPORT.md`

```
You are the audit coordinator for the my_finances repository.

Read CLAUDE.md first. Then read all 12 section files under audit/sections/ in order.

Your job is to produce a single consolidated audit report at audit/CONSOLIDATED_AUDIT_REPORT.md.

Structure the report as follows:

## Executive Summary
- Top-level verdict per domain: pass / needs attention / critical
- Top 3 most critical findings across all agents
- Top 3 strengths observed across all agents

## Findings by Severity

For each severity level (Critical → High → Medium → Low):
- Finding title
- Source agent(s)
- Affected file(s) and line(s) where known
- Recommended fix (one to three sentences)
- If two agents flagged the same issue differently, note both perspectives

## Domain Summaries
One paragraph per agent domain (12 total) summarizing overall health.

## Positive Observations
Bullet list of what is working well and must be preserved.

## Prioritized Action Checklist
Grouped by effort level:

### Quick Wins (< 1 hour each)
- [ ] ...

### Medium Effort (1–4 hours each)
- [ ] ...

### Long-term Improvements (> 4 hours or requires design decision)
- [ ] ...

Important rules:
- If two agents contradict each other, flag the contradiction explicitly — do not silently resolve it.
- Do not invent findings not present in the section files.
- Preserve the "Positive Observations" from each agent — do not only report negatives.
- Keep the tone constructive and specific.
```

---

## Completion Checklist

- [ ] All 12 section files written to `audit/sections/`
- [ ] Coordinator has read all 12 sections
- [ ] `audit/CONSOLIDATED_AUDIT_REPORT.md` written
- [ ] All findings files committed to git
