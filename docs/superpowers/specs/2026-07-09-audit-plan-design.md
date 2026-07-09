# Audit Plan Design — my_finances
**Date:** 2026-07-09  
**Status:** Approved  
**Author:** Jeisson Leal + Claude

---

## Goal

Perform a full multi-agent audit of the `my_finances` repository and Streamlit dashboard. The audit produces a single consolidated report (`audit/CONSOLIDATED_AUDIT_REPORT.md`) with severity-ranked findings and a prioritized action checklist.

Scope: all Python source under `src/`, the test suite under `tests/`, `AGENTS.md`, `README.md`, `pyproject.toml`, and `environment.yml`.

---

## Approach

**Option A — Parallel dispatch + coordinator** (selected).

12 specialist agents run simultaneously. Each writes its findings to a structured section file under `audit/sections/`. A 13th coordinator agent reads all 12 section files, deduplicates overlapping findings, scores severity, and writes the single consolidated report.

Execution is triggered via the `superpowers:dispatching-parallel-agents` skill.

---

## Agent Roster

| # | Agent | Audit Focus | Plugin / Skill |
|---|-------|-------------|----------------|
| 1 | Cybersecurity | File path handling, sensitive data exposure (CSV with personal finances, API keys, env vars), safe subprocess/env usage, no hardcoded secrets | `security-review` |
| 2 | Frontend Design | Streamlit layout hierarchy, sidebar usability, tab organization, filter UX, KPI card clarity, narrow-viewport degradation | `code-review` |
| 3 | Backend Design | Extraction pipeline architecture, CLI entrypoint design, data loading contracts, error handling, caching strategy (`@st.cache_data`) | `code-review` |
| 4 | Python Architecture | Module boundaries, import hygiene, type annotations, dataclass usage, separation of concerns per AGENTS.md rules, no recreation of `data_extractor/common/` | `impeccable` |
| 5 | Graphical Design | Color palette consistency, chart typography, spacing, visual coherence across 5 dashboard tabs, chart type vs. question fit | `ui-ux-pro-max` |
| 6 | Statistical / Math | Formula correctness: net worth, budget percentages, money left, ETF gain/loss, Klarna simple daily interest, Payback debt carry-forward, multi-currency guards | `code-review` |
| 7 | Finance Expert | Financial definitions vs. AGENTS.md, category classification correctness, double-counting risks (card repayments, savings, investments), budget vs. spending logic separation | `code-review` |
| 8 | Impeccable | Code polish: naming conventions, dead code, magic numbers, docstring quality, pattern consistency across files | `impeccable` |
| 9 | Ponytail | Technical debt: N26/Bancolombia remnants, outdated patterns, long-term maintainability risks, dependency hygiene | `ponytail` |
| 10 | Accessibility | WCAG AA color contrast on financial charts (income green vs. expense red palette), chart readability without color alone, text sizing, screen-reader labels in Streamlit | `code-review` |
| 11 | Test Coverage | Gap analysis of 4 existing test files vs. critical analytics paths; missing edge cases for budget logic, net worth, ETF valuation fallback, Payback carry-forward | `code-review` |
| 12 | Data Schema Validation | CSV output column contracts (`TRANSACTION_OUTPUT_COLUMNS`), dtype stability, null/missing value handling, schema consistency across extraction pipeline | `code-review` |
| 13 | **Coordinator** | Reads all 12 section files, deduplicates, scores severity (Critical / High / Medium / Low), writes `CONSOLIDATED_AUDIT_REPORT.md` | — |

---

## Output Structure

```
my_finances/
├── CLAUDE.md                                        ← agent playbook (created in plan phase)
├── audit/
│   ├── AUDIT_PLAN.md                               ← execution guide (created in plan phase)
│   ├── sections/                                   ← written at execution time
│   │   ├── 01_cybersecurity.md
│   │   ├── 02_frontend_design.md
│   │   ├── 03_backend_design.md
│   │   ├── 04_python_architecture.md
│   │   ├── 05_graphical_design.md
│   │   ├── 06_statistical_math.md
│   │   ├── 07_finance_expert.md
│   │   ├── 08_impeccable.md
│   │   ├── 09_ponytail.md
│   │   ├── 10_accessibility.md
│   │   ├── 11_test_coverage.md
│   │   └── 12_data_schema.md
│   └── CONSOLIDATED_AUDIT_REPORT.md               ← final deliverable
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-07-09-audit-plan-design.md    ← this file
```

---

## Section File Schema

Every specialist agent writes its section file using this exact structure so the coordinator can parse consistently:

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

## CLAUDE.md Design

`CLAUDE.md` is the fast-consumption agent playbook. It is terse and imperative. It covers:

1. **Project purpose** — personal finance toolkit, EUR-only, Santander + Revolut + Payback, local Streamlit dashboard
2. **Repository map** — file responsibilities verified against actual current structure
3. **Environment & commands** — conda activate, extract, dashboard, validation (`ruff`, `pytest`, Streamlit AppTest)
4. **Financial model** — key definitions agents must not reinterpret (income, expenses, money left, net worth, tracked wealth, budget)
5. **Dashboard tabs** — what each of the 5 tabs does, what data it uses, what it must never inflate
6. **Category rules** — conservative classification; agents must not invent new categories
7. **What NOT to do** — no `data_extractor/common/`, no Bancolombia in dashboard, no COP/EUR mixing, no UI complexity without financial clarity gain
8. **Agent review lenses** — the 12 audit agents mapped to the 10 review roles from AGENTS.md
9. **Validation gate** — three commands every agent runs before claiming completion
10. **Installed plugins** — caveman, ui-ux-pro-max, impeccable, ponytail, superpowers — when each applies

---

## Consolidated Report Structure

The coordinator writes `CONSOLIDATED_AUDIT_REPORT.md` with:

1. **Executive Summary** — top-level verdict per domain (pass / needs attention / critical), top 3 critical findings, top 3 strengths
2. **Findings by Severity** — Critical → High → Medium → Low, each with: finding, agent source, affected file(s), recommended fix
3. **Domain Summaries** — one paragraph per agent domain
4. **Positive Observations** — what is working and must be preserved
5. **Prioritized Action Checklist** — ordered list of recommended fixes, grouped by effort (Quick Wins / Medium Effort / Long-term)

---

## Constraints

- `ui-ux-pro-max` (Graphical Design agent) is a presentation layer concern. It must not override or rewrite dashboard content, data definitions, or chart data. It audits visual presentation only.
- No agent writes code. All agents write audit findings only.
- Agents do not modify `AGENTS.md` or `CLAUDE.md` during the audit run.
- The coordinator must flag when two agents contradict each other rather than silently picking one.

---

## Implementation Plan Inputs

The `writing-plans` skill will produce tasks for:

1. Create `CLAUDE.md`
2. Create `audit/AUDIT_PLAN.md` with prompts for all 13 agents
3. Execute 12 specialist agents in parallel (via `dispatching-parallel-agents`)
4. Execute coordinator agent to produce `CONSOLIDATED_AUDIT_REPORT.md`
5. Commit all files
