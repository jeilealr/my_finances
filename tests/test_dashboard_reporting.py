from __future__ import annotations

import argparse
import inspect

import pandas as pd
import pytest

from dashboard import app as dashboard_app
from dashboard.analytics import (
    DashboardFilters,
    build_fixed_budget_report,
    build_grouped_expense_detail,
    build_grouped_monthly_expense_report,
    build_monthly_extra_transaction_summary,
    build_monthly_movement_summary,
    build_monthly_report,
    build_monthly_spending_totals,
    build_net_worth_snapshots,
    build_payback_debt_summary,
    build_paycheck_budget_report,
    build_report_excluded_movement_summary,
    build_report_group_component_summary,
    build_selected_month_expense_groups,
    build_spending_transactions,
    filter_transactions,
)
from dashboard.app import (
    NO_SELECTION_SENTINEL,
    _default_analysis_period_bounds,
    _normalize_checkbox_filter_selection,
    _prepare_spending_transactions,
)
from dashboard.categories import enrich_transactions
from dashboard.charts import (
    budget_monthly_chart,
    monthly_cashflow_chart,
    monthly_grouped_expense_chart,
    net_worth_chart,
    paycheck_allocation_chart,
    report_group_component_chart,
    report_expense_pie_chart,
)
from dashboard.data_loader import load_dashboard_datasets
from dashboard.investments import (
    KLARNA_INTEREST_START_DATE,
    build_etf_holdings,
    calculate_klarna_accrued_interest,
    fetch_boerse_frankfurt_quote,
    fetch_yahoo_chart_prices,
    load_or_fetch_market_prices,
    parse_investment_order,
    value_etf_holdings,
)
from my_finances.data_extractor.revolut import (
    calculate_revolut_subaccount_balances_from_csv,
)
from my_finances._cli import _dashboard


def _dashboard_transactions() -> pd.DataFrame:
    raw = pd.DataFrame(
        [
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2025-12-29",
                "value_date": None,
                "description": "UEBERWEISUNG VON Helmholtz-Zentrum",
                "amount": 3000.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Lohn/Gehalt 00042194/202512",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-01",
                "value_date": None,
                "description": "HELMHOLTZ-ZENTRUM salary",
                "amount": 1000.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-03-02",
                "value_date": None,
                "description": "REWE LEIPZIG",
                "amount": -200.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "revolut",
                "account": "current_account",
                "subaccount": "Main Account",
                "date": "2026-03-03",
                "value_date": None,
                "description": "To Instant Access Savings",
                "amount": -100.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "revolut",
                "account": "deposit",
                "subaccount": "Instant Access Savings",
                "date": "2026-03-03",
                "value_date": None,
                "description": "To Instant Access Savings",
                "amount": 100.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "revolut",
                "account": "deposit",
                "subaccount": "Instant Access Savings",
                "date": "2026-03-04",
                "value_date": None,
                "description": (
                    "Net Interest Paid to 'Instant Access Savings' for 4 Mar 2026"
                ),
                "amount": 0.5,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-05",
                "value_date": None,
                "description": (
                    "ISIN IE00BK5BQT80 DEPOT 20969100570608 KAUF 3,7674 ZUM"
                ),
                "amount": -600.85,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-06",
                "value_date": None,
                "description": "ECHTZEIT-UEBERWEISUNG AN Jei Klarna",
                "amount": -6000.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-07",
                "value_date": None,
                "description": "ECHTZEIT-UEBERWEISUNG AN TransferWise Europe SA",
                "amount": -500.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "revolut",
                "account": "deposit",
                "subaccount": "Instant Access Savings",
                "date": "2026-03-08",
                "value_date": None,
                "description": "From Instant Access Savings",
                "amount": -20.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-03-09",
                "value_date": None,
                "description": "ZAHLUNG/ÜBERWEISUNG ERHALTEN BESTEN DANK",
                "amount": 150.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-10",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON AMERICAN EXPRESS EUROPE S.A.",
                "amount": -150.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-04-01",
                "value_date": None,
                "description": "REWE LEIPZIG",
                "amount": -50.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
        ]
    )
    raw["date"] = pd.to_datetime(raw["date"])
    raw["value_date"] = pd.to_datetime(raw["value_date"], errors="coerce")
    return enrich_transactions(raw)


def _budget_fixture_transactions() -> pd.DataFrame:
    raw = pd.DataFrame(
        [
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2025-12-29",
                "value_date": None,
                "description": "UEBERWEISUNG VON Helmholtz-Zentrum",
                "amount": 3000.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Lohn/Gehalt 00042194/202512",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-01-02",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON Schwarzer Haus- und",
                "amount": -600.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Miete lfd. Monat",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-01-03",
                "value_date": None,
                "description": "ISIN IE00BK5BQT80 DEPOT 20969100570608 KAUF",
                "amount": -600.85,
                "currency": "EUR",
                "balance": None,
                "notes": "ORDER-NR. 000001",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-01-04",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON DB Vertrieb GmbH",
                "amount": -63.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Abo 279993076 zum 01.01.2026",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-01-05",
                "value_date": None,
                "description": "AJET - ajet.com AMSTERD Amsterdam",
                "amount": -125.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-01-06",
                "value_date": None,
                "description": "ECHTZEIT-UEBERWEISUNG AN Leipziger Stadtwerke",
                "amount": -51.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-01-07",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON FIT/One GmbH",
                "amount": -21.80,
                "currency": "EUR",
                "balance": None,
                "notes": "Fitness First RED ALL-IN",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-01-21",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON FIT/One GmbH",
                "amount": -21.80,
                "currency": "EUR",
                "balance": None,
                "notes": "Fitness First RED ALL-IN",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-01-08",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON Baileo Edler & Gonzalez GbR",
                "amount": -95.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Baileo Tanzschule",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-01-09",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON Drillisch Online GmbH",
                "amount": -16.0,
                "currency": "EUR",
                "balance": None,
                "notes": "handyvertrag.de",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-01-10",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON Vodafone GmbH",
                "amount": -23.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Vodafone sagt Danke",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-01-29",
                "value_date": None,
                "description": "UEBERWEISUNG VON Helmholtz-Zentrum",
                "amount": 3200.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Lohn/Gehalt 00042194/202601",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-02-02",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON Schwarzer Haus- und",
                "amount": -600.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Miete lfd. Monat",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-02-05",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON Rundfunk ARD, ZDF, DRadio",
                "amount": -55.08,
                "currency": "EUR",
                "balance": None,
                "notes": "Rundfunk 02.2026 - 04.2026",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-02-27",
                "value_date": None,
                "description": "UEBERWEISUNG VON Helmholtz-Zentrum",
                "amount": 3400.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Lohn/Gehalt 00042194/202602",
                "page": None,
                "source_file": "statement.pdf",
            },
        ]
    )
    raw["date"] = pd.to_datetime(raw["date"])
    raw["value_date"] = pd.to_datetime(raw["value_date"], errors="coerce")
    return enrich_transactions(raw)


def _spending_income_fixture_transactions() -> pd.DataFrame:
    raw = pd.DataFrame(
        [
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-01",
                "value_date": None,
                "description": "UEBERWEISUNG VON Helmholtz-Zentrum",
                "amount": 1000.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Lohn/Gehalt 00042194/202603",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-02",
                "value_date": None,
                "description": "UEBERWEISUNG VON Finanzamt Leipzig I",
                "amount": 600.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Tax refund",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-03",
                "value_date": None,
                "description": "UEBERWEISUNG VON Maria Travel reimbursement",
                "amount": 250.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "revolut",
                "account": "deposit",
                "subaccount": "Instant Access Savings",
                "date": "2026-03-04",
                "value_date": None,
                "description": (
                    "Net Interest Paid to 'Instant Access Savings' for 4 Mar 2026"
                ),
                "amount": 0.5,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "revolut",
                "account": "current_account",
                "subaccount": "Main Account",
                "date": "2026-03-05",
                "value_date": None,
                "description": "H & M LEIPZIG REFUND",
                "amount": 39.99,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-03-06",
                "value_date": None,
                "description": "ZAHLUNG/ÜBERWEISUNG ERHALTEN BESTEN DANK",
                "amount": 150.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "revolut",
                "account": "current_account",
                "subaccount": "Main Account",
                "date": "2026-03-07",
                "value_date": None,
                "description": "Top-up by *8240",
                "amount": 300.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "revolut",
                "account": "deposit",
                "subaccount": "Instant Access Savings",
                "date": "2026-03-08",
                "value_date": None,
                "description": "To Instant Access Savings",
                "amount": 100.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-09",
                "value_date": None,
                "description": "ECHTZEIT-UEBERWEISUNG AN Jei Klarna",
                "amount": -6000.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-10",
                "value_date": None,
                "description": (
                    "ISIN IE00BK5BQT80 DEPOT 20969100570608 KAUF 3,7674 ZUM"
                ),
                "amount": -600.85,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-11",
                "value_date": None,
                "description": "ECHTZEIT-UEBERWEISUNG AN TransferWise Europe SA",
                "amount": -500.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-03-12",
                "value_date": None,
                "description": "REWE LEIPZIG",
                "amount": -200.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-03-13",
                "value_date": None,
                "description": "HOTEL HOLIDAY INN BUCARAMANGA",
                "amount": -90.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
        ]
    )
    raw["date"] = pd.to_datetime(raw["date"])
    raw["value_date"] = pd.to_datetime(raw["value_date"], errors="coerce")
    return enrich_transactions(raw)


def _paycheck_budget_fixture_transactions() -> pd.DataFrame:
    raw = pd.DataFrame(
        [
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-05-28",
                "value_date": None,
                "description": "UEBERWEISUNG VON Helmholtz-Zentrum",
                "amount": 3341.78,
                "currency": "EUR",
                "balance": None,
                "notes": "Lohn/Gehalt 00042194/202605",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-06-02",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON Schwarzer Haus- und",
                "amount": -600.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Miete lfd. Monat",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-06-03",
                "value_date": None,
                "description": "ECHTZEIT-UEBERWEISUNG AN Leipziger Stadtwerke",
                "amount": -51.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-06-04",
                "value_date": None,
                "description": "REWE LEIPZIG",
                "amount": -200.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-06-05",
                "value_date": None,
                "description": "DEUTSCHE LUFTHANSA AG Koeln",
                "amount": -100.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-06-06",
                "value_date": None,
                "description": "H & M LEIPZIG",
                "amount": -50.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-06-07",
                "value_date": None,
                "description": "ECHTZEIT-UEBERWEISUNG AN Irakli Patsatsia",
                "amount": -30.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "revolut",
                "account": "current_account",
                "subaccount": "Main Account",
                "date": "2026-06-08",
                "value_date": None,
                "description": "Konfetti",
                "amount": -70.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-06-09",
                "value_date": None,
                "description": "ISIN IE00BK5BQT80 DEPOT 20969100570608 KAUF",
                "amount": -600.85,
                "currency": "EUR",
                "balance": None,
                "notes": "ORDER-NR. 000001",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-06-12",
                "value_date": None,
                "description": "UEBERWEISUNG VON Helmholtz-Zentrum",
                "amount": 1221.61,
                "currency": "EUR",
                "balance": None,
                "notes": "0000247059 -- 6000236104",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-06-29",
                "value_date": None,
                "description": "UEBERWEISUNG VON Helmholtz-Zentrum",
                "amount": 3400.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Lohn/Gehalt 00042194/202606",
                "page": None,
                "source_file": "statement.pdf",
            },
        ]
    )
    raw["date"] = pd.to_datetime(raw["date"])
    raw["value_date"] = pd.to_datetime(raw["value_date"], errors="coerce")
    return enrich_transactions(raw)


def test_dashboard_update_runs_extraction_before_launch(monkeypatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake_extract_all_data() -> None:
        calls.append(("extract", []))

    def fake_run_dashboard(args: list[str]) -> int:
        calls.append(("dashboard", args))
        return 0

    monkeypatch.setattr(_dashboard, "extract_all_data", fake_extract_all_data)
    monkeypatch.setattr(_dashboard, "run_dashboard", fake_run_dashboard)

    parser = argparse.ArgumentParser()
    _dashboard.add_args(parser)
    args = parser.parse_args(["--update", "--", "--server.headless", "true"])

    assert _dashboard.run(args) == 0
    assert calls == [
        ("extract", []),
        ("dashboard", ["--server.headless", "true"]),
    ]


def test_checkbox_filter_selection_contract() -> None:
    options = ["Santander", "Revolut"]

    assert (
        _normalize_checkbox_filter_selection(
            options,
            select_all=True,
            selected_options=[],
        )
        == tuple()
    )
    assert _normalize_checkbox_filter_selection(
        options,
        select_all=False,
        selected_options=["Revolut"],
    ) == ("Revolut",)
    assert _normalize_checkbox_filter_selection(
        options,
        select_all=False,
        selected_options=[],
    ) == (NO_SELECTION_SENTINEL,)


def test_date_period_filter_replaces_month_filtering() -> None:
    transactions = _dashboard_transactions()
    filters = DashboardFilters(
        start_date=pd.Timestamp("2026-03-01"),
        end_date=pd.Timestamp("2026-03-31"),
        months=tuple(),
        banks=tuple(),
        accounts=tuple(),
        subaccounts=tuple(),
        categories=tuple(),
        currencies=tuple(),
        include_transfers=True,
    )

    filtered = filter_transactions(transactions, filters)

    assert filtered["month_label"].unique().tolist() == ["2026-03"]


def test_default_analysis_period_starts_on_january_first_2026() -> None:
    start_date, end_date = _default_analysis_period_bounds(
        pd.Timestamp("2025-05-01"),
        pd.Timestamp("2026-06-30"),
    )

    assert start_date == pd.Timestamp("2026-01-01")
    assert end_date == pd.Timestamp("2026-06-30")


def test_default_analysis_period_clamps_when_2026_is_unavailable() -> None:
    start_date, end_date = _default_analysis_period_bounds(
        pd.Timestamp("2025-05-01"),
        pd.Timestamp("2025-12-31"),
    )

    assert start_date == pd.Timestamp("2025-12-31")
    assert end_date == pd.Timestamp("2025-12-31")


def test_dashboard_tabs_replace_accounts_with_budget() -> None:
    source = inspect.getsource(dashboard_app.main)

    assert '"Budget"' in source
    assert '"Accounts"' not in source


def test_fixed_budget_report_tracks_recurring_items_and_money_left() -> None:
    monthly_budget, budget_detail = build_fixed_budget_report(
        _budget_fixture_transactions(),
        start_date=pd.Timestamp("2026-01-01"),
        end_date=pd.Timestamp("2026-02-28"),
    )

    january = monthly_budget.loc[monthly_budget["month_label"].eq("2026-01")].iloc[0]
    february = monthly_budget.loc[monthly_budget["month_label"].eq("2026-02")].iloc[0]
    january_items = budget_detail.loc[budget_detail["month_label"].eq("2026-01")]
    february_items = budget_detail.loc[budget_detail["month_label"].eq("2026-02")]
    january_amounts = dict(
        zip(january_items["budget_item"], january_items["actual_amount"])
    )
    february_budgeted = dict(
        zip(february_items["budget_item"], february_items["budgeted_amount"])
    )

    assert january_amounts["Rent"] == 600.0
    assert january_amounts["Investment"] == 600.85
    assert january_amounts["Deutschland Ticket"] == 63.0
    assert january_amounts["Electricity"] == 51.0
    assert january_amounts["Fitness"] == 43.6
    assert january_amounts["Baileo"] == 95.0
    assert january_amounts["Phone & Internet"] == 39.0
    assert january_amounts["Rundfunk"] == 0.0
    assert february_budgeted["Investment"] == 600.85
    assert february_budgeted["Rundfunk"] == 55.08
    assert january["salary"] == 3000.0
    assert february["salary"] == 3200.0
    assert january["fixed_commitments"] == pytest.approx(1492.45)
    assert january["money_left"] == pytest.approx(1507.55)
    assert february["money_left"] == pytest.approx(1652.47)


def test_budget_report_does_not_treat_all_transport_as_fixed_ticket() -> None:
    _, budget_detail = build_fixed_budget_report(
        _budget_fixture_transactions(),
        start_date=pd.Timestamp("2026-01-01"),
        end_date=pd.Timestamp("2026-01-31"),
    )
    january_ticket = budget_detail.loc[
        budget_detail["month_label"].eq("2026-01")
        & budget_detail["budget_item"].eq("Deutschland Ticket")
    ].iloc[0]

    assert january_ticket["actual_amount"] == 63.0


def test_budget_monthly_chart_shows_salary_fixed_commitments_and_money_left() -> None:
    monthly_budget, _ = build_fixed_budget_report(
        _budget_fixture_transactions(),
        start_date=pd.Timestamp("2026-01-01"),
        end_date=pd.Timestamp("2026-02-28"),
    )

    figure = budget_monthly_chart(monthly_budget)

    assert {trace.name for trace in figure.data} == {
        "Salary",
        "Fixed Commitments",
        "Money Left",
    }


def test_paycheck_budget_uses_only_lohn_gehalt_paychecks_and_shifts_months() -> None:
    monthly_budget, _ = build_paycheck_budget_report(
        _paycheck_budget_fixture_transactions(),
        start_date=pd.Timestamp("2026-06-01"),
        end_date=pd.Timestamp("2026-07-31"),
    )
    june = monthly_budget.loc[monthly_budget["month_label"].eq("2026-06")].iloc[0]
    july = monthly_budget.loc[monthly_budget["month_label"].eq("2026-07")].iloc[0]

    assert june["paycheck"] == 3341.78
    assert july["paycheck"] == 3400.0


def test_paycheck_budget_limits_and_remaining_target() -> None:
    monthly_budget, detail = build_paycheck_budget_report(
        _paycheck_budget_fixture_transactions(),
        start_date=pd.Timestamp("2026-06-01"),
        end_date=pd.Timestamp("2026-06-30"),
    )
    june = monthly_budget.iloc[0]
    june_detail = detail.loc[detail["month_label"].eq("2026-06")]
    limits = dict(zip(june_detail["budget_bucket"], june_detail["limit_amount"]))

    assert limits["Housing & Utilities"] == pytest.approx(1069.3696)
    assert limits["Grocery"] == pytest.approx(400.0)
    assert limits["Other Spending Groups"] == pytest.approx(334.178)
    assert limits["Investment"] == pytest.approx(601.5204)
    assert june["budgeted_limits"] == pytest.approx(2405.068)
    assert june["remaining_target_percent"] == pytest.approx(0.20)
    assert june["remaining_target_amount"] == pytest.approx(668.356)


def test_paycheck_budget_groups_other_spending_and_investment_principal() -> None:
    monthly_budget, detail = build_paycheck_budget_report(
        _paycheck_budget_fixture_transactions(),
        start_date=pd.Timestamp("2026-06-01"),
        end_date=pd.Timestamp("2026-06-30"),
    )
    june = monthly_budget.iloc[0]
    actuals = dict(zip(detail["budget_bucket"], detail["actual_amount"]))

    assert actuals["Housing & Utilities"] == 651.0
    assert actuals["Grocery"] == 200.0
    assert actuals["Other Spending Groups"] == 250.85
    assert actuals["Investment"] == 600.0
    assert june["actual_used"] == pytest.approx(1701.85)
    assert june["paycheck_remaining"] == pytest.approx(1639.93)


def test_paycheck_budget_keeps_spending_context_separate() -> None:
    monthly_budget, _ = build_paycheck_budget_report(
        _paycheck_budget_fixture_transactions(),
        start_date=pd.Timestamp("2026-06-01"),
        end_date=pd.Timestamp("2026-06-30"),
    )
    june = monthly_budget.iloc[0]

    assert june["paycheck"] == 3341.78
    assert june["total_income"] == pytest.approx(4621.61)
    assert june["total_expenses"] == pytest.approx(1101.85)
    assert june["spending_money_left"] == pytest.approx(3519.76)
    assert june["spending_money_left"] != june["paycheck_remaining"]


def test_paycheck_allocation_chart_includes_remaining_paycheck() -> None:
    allocation = pd.DataFrame(
        {
            "bucket": ["Housing & Utilities", "Grocery", "Remaining Paycheck"],
            "amount": [651.0, 200.0, 1639.93],
        }
    )

    figure = paycheck_allocation_chart(allocation)

    assert set(figure.data[0].labels) == {
        "Housing & Utilities",
        "Grocery",
        "Remaining Paycheck",
    }


def test_savings_transfers_are_not_spending_and_interest_is_income() -> None:
    transactions = _dashboard_transactions()

    interest = transactions.loc[
        transactions["description"].str.contains("Net Interest", case=False)
    ].iloc[0]
    savings = transactions.loc[
        transactions["description"].eq("To Instant Access Savings")
    ]
    spending = _prepare_spending_transactions(transactions)

    assert interest["category"] == "Interest Income"
    assert interest["flow_group"] == "Income"
    assert savings["flow_group"].eq("Transfer").all()
    assert "Savings" not in spending["category"].tolist()


def test_monthly_spending_totals_include_real_income_only() -> None:
    transactions = _spending_income_fixture_transactions()
    spending = build_spending_transactions(transactions)

    totals = build_monthly_spending_totals(spending, transactions)
    march = totals.loc[totals["month_label"].eq("2026-03")].iloc[0]

    assert march["income"] == pytest.approx(1890.49)
    assert march["expenses"] == pytest.approx(290.85)
    assert march["money_left"] == pytest.approx(1599.64)
    assert march["transactions"] == 3


def test_monthly_spending_totals_exclude_transfers_and_payback_credits() -> None:
    transactions = _spending_income_fixture_transactions()
    income_rows = transactions.loc[transactions["flow_group"].eq("Income")]
    income_descriptions = set(income_rows["description"])

    totals = build_monthly_spending_totals(
        build_spending_transactions(transactions),
        transactions,
    )
    march = totals.loc[totals["month_label"].eq("2026-03")].iloc[0]

    assert "ZAHLUNG/ÜBERWEISUNG ERHALTEN BESTEN DANK" not in income_descriptions
    assert "Top-up by *8240" not in income_descriptions
    assert "To Instant Access Savings" not in income_descriptions
    assert march["income"] == pytest.approx(1890.49)


def test_monthly_spending_totals_keep_income_when_expense_focus_changes() -> None:
    transactions = _spending_income_fixture_transactions()
    spending = build_spending_transactions(transactions)
    grocery_spending = spending.loc[spending["category"].eq("Grocery Shopping")]

    all_totals = build_monthly_spending_totals(spending, transactions)
    focused_totals = build_monthly_spending_totals(grocery_spending, transactions)
    all_march = all_totals.loc[all_totals["month_label"].eq("2026-03")].iloc[0]
    focused_march = focused_totals.loc[
        focused_totals["month_label"].eq("2026-03")
    ].iloc[0]

    assert focused_march["income"] == all_march["income"]
    assert focused_march["expenses"] == pytest.approx(200.0)
    assert focused_march["expenses"] < all_march["expenses"]
    assert focused_march["money_left"] == pytest.approx(1690.49)


def test_non_expense_movements_are_excluded_from_spending() -> None:
    transactions = _dashboard_transactions()
    movement_categories = {
        "Blocked Account",
        "Card Repayment",
        "Colombia Transfer",
        "Investments",
        "Savings",
    }
    movements = transactions.loc[transactions["category"].isin(movement_categories)]
    spending = _prepare_spending_transactions(transactions)

    assert not movements.empty
    assert movements["flow_group"].eq("Transfer").all()
    assert movements["expense_amount"].eq(0).all()
    assert movement_categories.isdisjoint(set(spending["category"]))
    assert "Investment Fees" in spending["category"].tolist()


def test_monthly_report_separates_expenses_and_savings_movement() -> None:
    report = build_monthly_report(_dashboard_transactions())
    march_rows = report.loc[
        report["month_label"].eq("2026-03") & report["currency"].eq("EUR")
    ]
    grocery_row = march_rows.loc[march_rows["category"].eq("Grocery Shopping")].iloc[0]

    assert grocery_row["category_expenses"] == 200.0
    assert grocery_row["income"] == 1000.5
    assert grocery_row["expenses"] == 200.85
    assert grocery_row["money_left"] == 799.65
    assert grocery_row["savings_transfer_in"] == 100.0
    assert grocery_row["savings_transfer_out"] == 20.0
    assert grocery_row["net_savings_movement"] == 80.0


def test_monthly_movement_summary_keeps_context_out_of_expenses() -> None:
    movement_summary = build_monthly_movement_summary(_dashboard_transactions())
    march = movement_summary.loc[
        movement_summary["month_label"].eq("2026-03")
        & movement_summary["currency"].eq("EUR")
    ]
    amounts = dict(zip(march["category"], march["movement_amount"]))

    assert amounts["Investments"] == 600.85
    assert amounts["Blocked Account"] == 6000.0
    assert amounts["Colombia Transfer"] == 500.0
    assert amounts["Savings"] == 120.0
    assert amounts["Card Repayment"] == 150.0


def test_payback_debt_summary_uses_purchases_and_repayments() -> None:
    debt_summary = build_payback_debt_summary(_dashboard_transactions())

    march = debt_summary.loc[debt_summary["month_label"].eq("2026-03")].iloc[0]
    april = debt_summary.loc[debt_summary["month_label"].eq("2026-04")].iloc[0]

    assert march["purchases"] == 200.0
    assert march["repayments"] == 150.0
    assert march["outstanding_debt"] == 50.0
    assert april["purchases"] == 50.0
    assert april["repayments"] == 0.0
    assert april["outstanding_debt"] == 100.0


def test_payback_debt_counts_all_positive_credits_and_clips_recursively() -> None:
    raw = pd.DataFrame(
        [
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-01-01",
                "value_date": None,
                "description": "LIDL LEIPZIG",
                "amount": -100.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-01-02",
                "value_date": None,
                "description": "Merchant refund",
                "amount": 20.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-01-03",
                "value_date": None,
                "description": "ZAHLUNG/ÜBERWEISUNG ERHALTEN BESTEN DANK",
                "amount": 90.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-02-01",
                "value_date": None,
                "description": "REWE LEIPZIG",
                "amount": -50.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
        ]
    )
    raw["date"] = pd.to_datetime(raw["date"])
    raw["value_date"] = pd.to_datetime(raw["value_date"], errors="coerce")
    debt_summary = build_payback_debt_summary(enrich_transactions(raw))

    january = debt_summary.loc[debt_summary["month_label"].eq("2026-01")].iloc[0]
    february = debt_summary.loc[debt_summary["month_label"].eq("2026-02")].iloc[0]

    assert january["purchases"] == 100.0
    assert january["repayments"] == 110.0
    assert january["outstanding_debt"] == 0.0
    assert february["outstanding_debt"] == 50.0


def test_card_repayments_are_not_report_expense_categories() -> None:
    transactions = _dashboard_transactions()
    report = build_monthly_report(transactions)
    card_rows = transactions.loc[transactions["category"].eq("Card Repayment")]

    assert not card_rows.empty
    assert card_rows["flow_group"].eq("Transfer").all()
    assert "American Express Debt" not in report["category"].tolist()
    assert "Card Repayment" not in report["category"].tolist()


def test_investment_order_fees_are_spending_without_counting_principal() -> None:
    transactions = _dashboard_transactions()
    spending = build_spending_transactions(transactions)
    report = build_monthly_report(transactions)

    fee_rows = spending.loc[spending["category"].eq("Investment Fees")]
    report_fee_rows = report.loc[report["category"].eq("Investment Fees")]

    assert fee_rows["expense_amount"].sum() == 0.85
    assert report_fee_rows["category_expenses"].sum() == 0.85
    assert "Investments" not in spending["category"].tolist()


def _reports_fixture_transactions() -> pd.DataFrame:
    raw = pd.DataFrame(
        [
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-05-01",
                "value_date": None,
                "description": "HELMHOLTZ-ZENTRUM salary",
                "amount": 3000.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "santander.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-05-02",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON Leipziger Stadtwerke",
                "amount": -50.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "santander.pdf",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-05-03",
                "value_date": None,
                "description": "HERZ-APOTHEKE LEIPZIG",
                "amount": -20.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "revolut",
                "account": "current_account",
                "subaccount": "Main Account",
                "date": "2026-05-04",
                "value_date": None,
                "description": "RB Brot Markt",
                "amount": -10.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "revolut",
                "account": "current_account",
                "subaccount": "Main Account",
                "date": "2026-05-05",
                "value_date": None,
                "description": "Niiko Asia Streetfood",
                "amount": -15.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "revolut",
                "account": "current_account",
                "subaccount": "Main Account",
                "date": "2026-05-06",
                "value_date": None,
                "description": "Vapiano Dresden",
                "amount": -25.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-05-07",
                "value_date": None,
                "description": "DEUTSCHE LUFTHANSA AG Koeln",
                "amount": -120.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-05-08",
                "value_date": None,
                "description": "FLIXBUS.COM MUNICH",
                "amount": -30.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-05-09",
                "value_date": None,
                "description": "H & M LEIPZIG",
                "amount": -40.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "revolut",
                "account": "current_account",
                "subaccount": "Main Account",
                "date": "2026-05-10",
                "value_date": None,
                "description": "Konfetti",
                "amount": -35.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "revolut",
                "account": "current_account",
                "subaccount": "Main Account",
                "date": "2026-05-11",
                "value_date": None,
                "description": "ticket.io",
                "amount": -12.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "revolut",
                "account": "pockets",
                "subaccount": "Holidays",
                "date": "2026-05-12",
                "value_date": None,
                "description": "Unknown beach merchant",
                "amount": -60.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "revolut.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-05-13",
                "value_date": None,
                "description": "ECHTZEIT-UEBERWEISUNG AN TransferWise Europe SA",
                "amount": -500.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "santander.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-05-14",
                "value_date": None,
                "description": "ECHTZEIT-UEBERWEISUNG AN Jei Klarna",
                "amount": -6000.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "santander.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-05-15",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON AMERICAN EXPRESS EUROPE S.A.",
                "amount": -150.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "santander.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-05-16",
                "value_date": None,
                "description": "ECHTZEIT-UEBERWEISUNG AN Irakli Patsatsia",
                "amount": -45.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "santander.pdf",
            },
        ]
    )
    raw["date"] = pd.to_datetime(raw["date"])
    raw["value_date"] = pd.to_datetime(raw["value_date"], errors="coerce")
    return enrich_transactions(raw)


def test_report_grouping_builds_expense_only_monthly_groups() -> None:
    transactions = _reports_fixture_transactions()
    grouped = build_grouped_monthly_expense_report(transactions)
    may = grouped.loc[grouped["month_label"].eq("2026-05")]
    amounts = dict(zip(may["report_group"], may["expenses"]))

    assert amounts["Housing & Utilities"] == 70.0
    assert amounts["Grocery"] == 50.0
    assert amounts["Travel & Holidays"] == 210.0
    assert amounts["Retail & Online Shopping"] == 40.0
    assert amounts["Entertainment"] == 47.0
    assert amounts["Other"] == 45.0
    assert "Card Repayment" not in may["report_group"].tolist()
    assert "Colombia Transfer" not in may["report_group"].tolist()
    assert "Blocked Account" not in may["report_group"].tolist()


def test_selected_month_expense_groups_are_pie_ready() -> None:
    grouped = build_grouped_monthly_expense_report(_reports_fixture_transactions())
    selected = build_selected_month_expense_groups(grouped, month_label="2026-05")

    assert selected["month_label"].unique().tolist() == ["2026-05"]
    assert set(selected["report_group"]) == {
        "Entertainment",
        "Grocery",
        "Housing & Utilities",
        "Other",
        "Retail & Online Shopping",
        "Travel & Holidays",
    }


def test_report_excluded_movements_stay_outside_the_pie() -> None:
    movements = build_report_excluded_movement_summary(_reports_fixture_transactions())
    amounts = dict(zip(movements["category"], movements["amount"]))

    assert amounts["Colombia Transfer"] == 500.0
    assert amounts["Blocked Account"] == 6000.0
    assert amounts["Card Repayment"] == 150.0


def test_pharmacy_and_merchant_cleanup_categories() -> None:
    transactions = _reports_fixture_transactions()
    categories = dict(zip(transactions["description"], transactions["category"]))

    assert categories["HERZ-APOTHEKE LEIPZIG"] == "Pharmacy"
    assert categories["RB Brot Markt"] == "Grocery Shopping"
    assert categories["Niiko Asia Streetfood"] == "Restaurants & Delivery"
    assert categories["Vapiano Dresden"] == "Restaurants & Delivery"
    assert categories["DEUTSCHE LUFTHANSA AG Koeln"] == "Travel"
    assert categories["FLIXBUS.COM MUNICH"] == "Travel"
    assert categories["H & M LEIPZIG"] == "Retail & Online Shopping"
    assert categories["Konfetti"] == "Entertainment"
    assert categories["ticket.io"] == "Entertainment"
    assert categories["ECHTZEIT-UEBERWEISUNG AN Irakli Patsatsia"] == "Other"


def test_report_charts_use_grouped_expense_fields() -> None:
    grouped = build_grouped_monthly_expense_report(_reports_fixture_transactions())
    selected = build_selected_month_expense_groups(grouped, month_label="2026-05")

    pie = report_expense_pie_chart(selected)
    trend = monthly_grouped_expense_chart(grouped)

    assert "Travel & Holidays" in list(pie.data[0].labels)
    assert {trace.name for trace in trend.data} >= {
        "Grocery",
        "Housing & Utilities",
        "Travel & Holidays",
    }


def test_report_group_component_summary_breaks_down_selected_group() -> None:
    transactions = _reports_fixture_transactions()
    extra_rows = pd.DataFrame(
        [
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-06-02",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON Leipziger Stadtwerke",
                "amount": -51.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "santander.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-06-03",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON DB Vertrieb GmbH",
                "amount": -63.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Deutschlandticket",
                "page": None,
                "source_file": "santander.pdf",
            },
        ]
    )
    extra_rows["date"] = pd.to_datetime(extra_rows["date"])
    extra_rows["value_date"] = pd.to_datetime(
        extra_rows["value_date"],
        errors="coerce",
    )
    transactions = pd.concat(
        [transactions, enrich_transactions(extra_rows)],
        ignore_index=True,
    )
    detail = build_grouped_expense_detail(transactions)

    components = build_report_group_component_summary(
        detail,
        report_group="Housing & Utilities",
    )
    amounts = {
        (row.month_label, row.category): row.expenses
        for row in components.itertuples(index=False)
    }

    assert amounts[("2026-05", "Electricity")] == 50.0
    assert amounts[("2026-05", "Pharmacy")] == 20.0
    assert amounts[("2026-06", "Electricity")] == 51.0
    assert amounts[("2026-06", "Transport")] == 63.0


def test_report_group_component_chart_uses_original_categories() -> None:
    detail = build_grouped_expense_detail(_reports_fixture_transactions())
    components = build_report_group_component_summary(
        detail,
        report_group="Housing & Utilities",
    )

    figure = report_group_component_chart(components)

    assert {trace.name for trace in figure.data} == {"Electricity", "Pharmacy"}


def test_monthly_cashflow_chart_uses_monthly_date_ticks() -> None:
    transactions = _dashboard_transactions()
    visible_transactions = transactions.loc[~transactions["flow_group"].eq("Transfer")]
    monthly_summary = (
        visible_transactions.groupby(
            ["month", "month_label", "currency"],
            dropna=False,
        )
        .agg(
            income=("income_amount", "sum"),
            expenses=("expense_amount", "sum"),
            net=("amount", "sum"),
            transactions=("description", "size"),
        )
        .reset_index()
    )

    figure = monthly_cashflow_chart(
        monthly_summary,
        build_monthly_extra_transaction_summary(transactions),
    )

    assert figure.layout.xaxis.dtick == "M1"
    assert figure.layout.xaxis.tickformat == "%b<br>%Y"
    annotation_trace = next(
        trace
        for trace in figure.data
        if getattr(trace, "mode", None) == "markers+text"
    )
    assert annotation_trace.text[0].startswith("Extra<br>")
    assert "Extra transactions EUR" not in annotation_trace.text[0]
    assert "TransferWise Europe SA" in annotation_trace.customdata[0][0]


def test_investment_order_parser_handles_santander_pdf_text() -> None:
    order = parse_investment_order(
        "ISIN IE00BK5BQT80 DEPOT 20969100570608 KAUF 3,7674 ZUM"
    )

    assert order is not None
    assert order.isin == "IE00BK5BQT80"
    assert order.side == "KAUF"
    assert order.units == 3.7674


def test_etf_holdings_are_aggregated_from_pdf_derived_rows() -> None:
    holdings = build_etf_holdings(
        _dashboard_transactions(),
        as_of_date=pd.Timestamp("2026-03-31"),
    )

    row = holdings.loc[holdings["isin"].eq("IE00BK5BQT80")].iloc[0]

    assert row["symbol"] == "VWCE.DEX"
    assert row["units"] == 3.7674
    assert row["cost_basis"] == 600.0
    assert row["transactions"] == 1


def test_etf_valuation_uses_market_price_when_available() -> None:
    holdings = pd.DataFrame(
        [
            {
                "isin": "IE00BK5BQT80",
                "symbol": "VWCE.DEX",
                "name": "Vanguard FTSE All-World UCITS ETF",
                "units": 2.0,
                "cost_basis": 100.0,
                "transactions": 1,
                "latest_purchase_date": pd.Timestamp("2026-03-01"),
            }
        ]
    )
    market_prices = pd.DataFrame(
        [
            {
                "symbol": "VWCE.DEX",
                "date": pd.Timestamp("2026-03-31"),
                "close": 70.0,
                "fetched_at": pd.Timestamp("2026-04-01"),
            }
        ]
    )

    valuation = value_etf_holdings(
        holdings,
        market_prices,
        as_of_date=pd.Timestamp("2026-03-31"),
    )
    row = valuation.iloc[0]

    assert row["market_value"] == 140.0
    assert row["gain_loss"] == 40.0
    assert row["valuation_source"] == "market_price"


def test_etf_valuation_falls_back_to_cost_basis_without_prices() -> None:
    holdings = build_etf_holdings(
        _dashboard_transactions(),
        as_of_date=pd.Timestamp("2026-03-31"),
    )

    valuation = value_etf_holdings(
        holdings,
        pd.DataFrame(),
        as_of_date=pd.Timestamp("2026-03-31"),
    )
    row = valuation.loc[valuation["isin"].eq("IE00BK5BQT80")].iloc[0]

    assert row["market_value"] == row["cost_basis"]
    assert row["gain_loss"] == 0.0
    assert row["valuation_source"] == "cost_basis_fallback"


def test_etf_valuation_uses_latest_market_price_when_history_is_unavailable() -> None:
    holdings = build_etf_holdings(
        _dashboard_transactions(),
        as_of_date=pd.Timestamp("2026-03-31"),
    )
    market_prices = pd.DataFrame(
        [
            {
                "symbol": "VWCE.DEX",
                "date": pd.Timestamp("2026-07-06"),
                "close": 166.5,
                "fetched_at": pd.Timestamp("2026-07-06"),
            }
        ]
    )

    valuation = value_etf_holdings(
        holdings,
        market_prices,
        as_of_date=pd.Timestamp("2026-03-31"),
    )
    row = valuation.loc[valuation["isin"].eq("IE00BK5BQT80")].iloc[0]

    assert row["market_value"] == pytest.approx(3.7674 * 166.5)
    assert row["valuation_source"] == "latest_market_price"


def test_alpha_vantage_price_loader_uses_mocked_fetch_and_cache(tmp_path) -> None:
    fetched_at = pd.Timestamp.utcnow().tz_localize(None).isoformat()

    def fake_fetcher(symbol: str, api_key: str) -> pd.DataFrame:
        assert api_key == "test-key"
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "date": pd.Timestamp("2026-03-31"),
                    "close": 70.0,
                    "fetched_at": fetched_at,
                }
            ]
        )

    prices, warnings = load_or_fetch_market_prices(
        ("VWCE.DEX",),
        cache_dir=tmp_path,
        api_key="test-key",
        fetcher=fake_fetcher,
    )
    cached_prices, cached_warnings = load_or_fetch_market_prices(
        ("VWCE.DEX",),
        cache_dir=tmp_path,
        api_key=None,
        fetcher=fake_fetcher,
    )

    assert warnings == tuple()
    assert cached_warnings == tuple()
    assert prices["close"].iloc[0] == 70.0
    assert cached_prices["close"].iloc[0] == 70.0


def test_alpha_vantage_price_loader_warns_without_key_or_cache(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)

    prices, warnings = load_or_fetch_market_prices(
        ("VWCE.DEX",),
        cache_dir=tmp_path,
        api_key=None,
        fallback_fetchers=tuple(),
    )

    assert prices.empty
    assert "ALPHA_VANTAGE_API_KEY" in warnings[0]


def test_yahoo_chart_provider_normalizes_prices(monkeypatch) -> None:
    def fake_read_json_url(url: str) -> dict[str, object]:
        assert "VWCE.DE" in url
        return {
            "chart": {
                "result": [
                    {
                        "timestamp": [1775001600, 1775088000],
                        "indicators": {
                            "quote": [
                                {
                                    "close": [165.1, 166.6],
                                }
                            ]
                        },
                    }
                ],
                "error": None,
            }
        }

    monkeypatch.setattr(
        "dashboard.investments._read_json_url",
        fake_read_json_url,
    )

    prices = fetch_yahoo_chart_prices("VWCE.DEX")

    assert prices["symbol"].unique().tolist() == ["VWCE.DEX"]
    assert prices["close"].tolist() == [165.1, 166.6]


def test_boerse_frankfurt_provider_normalizes_quote(monkeypatch) -> None:
    def fake_read_json_url(url: str) -> dict[str, object]:
        assert "isin=IE00BK5BQT80" in url
        return {
            "lastPrice": 166.5,
            "timestampLastPrice": "2026-07-06T20:40:16+02:00",
        }

    monkeypatch.setattr(
        "dashboard.investments._read_json_url",
        fake_read_json_url,
    )

    prices = fetch_boerse_frankfurt_quote("VWCE.DEX")

    assert prices["symbol"].iloc[0] == "VWCE.DEX"
    assert prices["close"].iloc[0] == 166.5
    assert prices["date"].iloc[0] == pd.Timestamp("2026-07-06")


def test_klarna_accrued_interest_is_daily_simple_interest() -> None:
    first_day = calculate_klarna_accrued_interest(pd.Timestamp("2026-03-11"))
    july_sixth = calculate_klarna_accrued_interest(pd.Timestamp("2026-07-06"))

    assert first_day == pytest.approx(6000.0 * 0.0279 / 365.0)
    assert july_sixth == pytest.approx(6000.0 * 0.0279 * 118 / 365.0)


def test_net_worth_chart_uses_renamed_labels_and_tracked_wealth_line() -> None:
    summary = pd.DataFrame(
        [
            {
                "month": pd.Timestamp("2026-03-01"),
                "month_label": "2026-03",
                "currency": "EUR",
                "santander_cash": 1000.0,
                "revolut_cash": 50.0,
                "revolut_savings": 100.0,
                "blocked_account": 6000.0,
                "payback_debt": 200.0,
                "investment_cost_basis": 600.0,
                "investment_market_value": 650.0,
                "investment_gain_loss": 50.0,
                "total_net_worth": 6950.0,
                "tracked_wealth": 7610.0,
            }
        ]
    )

    figure = net_worth_chart(summary)
    trace_names = {trace.name for trace in figure.data}

    assert "Santander Account" in trace_names
    assert "Revolut Account" in trace_names
    assert "Investment" in trace_names
    assert "Tracked Wealth" in trace_names
    assert "Investment Principal (not in total)" not in trace_names


def test_net_worth_snapshot_combines_components() -> None:
    raw_transactions = pd.DataFrame(
        [
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-05",
                "value_date": None,
                "description": (
                    "ISIN IE00BK5BQT80 DEPOT 20969100570608 KAUF 1,0000 ZUM"
                ),
                "amount": -100.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "santander.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-06",
                "value_date": None,
                "description": "ECHTZEIT-UEBERWEISUNG AN Jei Klarna",
                "amount": -6000.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "santander.pdf",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-03-07",
                "value_date": None,
                "description": "REWE LEIPZIG",
                "amount": -200.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-03-08",
                "value_date": None,
                "description": "ZAHLUNG/ÜBERWEISUNG ERHALTEN BESTEN DANK",
                "amount": 50.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            {
                "bank": "revolut",
                "account": "current_account",
                "subaccount": "Main Account",
                "date": "2026-03-10",
                "value_date": None,
                "description": "Top-up by card",
                "amount": 30.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "account-statement_2026-03-01_2026-03-31_en-gb.pdf",
            },
            {
                "bank": "revolut",
                "account": "deposit",
                "subaccount": "Instant Access Savings",
                "date": "2026-03-11",
                "value_date": None,
                "description": "To Instant Access Savings",
                "amount": 100.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "account-statement_2026-03-01_2026-03-31_en-gb.pdf",
            },
        ]
    )
    raw_transactions["date"] = pd.to_datetime(raw_transactions["date"])
    raw_transactions["value_date"] = pd.to_datetime(
        raw_transactions["value_date"],
        errors="coerce",
    )
    transactions = enrich_transactions(raw_transactions)
    statement_balances = pd.DataFrame(
        [
            {
                "bank": "santander",
                "source_file": "santander.pdf",
                "statement_start_date": pd.Timestamp("2026-02-01"),
                "statement_end_date": pd.Timestamp("2026-02-28"),
                "opening_balance": 1000.0,
                "closing_balance": 1000.0,
                "currency": "EUR",
                "summary_method": "test",
            }
        ]
    )
    revolut_balances = pd.DataFrame(
        [
            {
                "bank": "revolut",
                "source_file": "account-statement_2026-02-01_2026-02-28_en-gb.pdf",
                "account": "current_account",
                "subaccount": "Main Account",
                "opening_balance": 0.0,
                "closing_balance": 40.0,
                "currency": "EUR",
                "transactions_count": 1,
                "summary_method": "test",
            },
            {
                "bank": "revolut",
                "source_file": "account-statement_2026-02-01_2026-02-28_en-gb.pdf",
                "account": "deposit",
                "subaccount": "Instant Access Savings",
                "opening_balance": 0.0,
                "closing_balance": 40.0,
                "currency": "EUR",
                "transactions_count": 1,
                "summary_method": "test",
            },
            {
                "bank": "revolut",
                "source_file": "account-statement_2026-03-01_2026-03-31_en-gb.pdf",
                "account": "current_account",
                "subaccount": "Main Account",
                "opening_balance": 0.0,
                "closing_balance": 30.0,
                "currency": "EUR",
                "transactions_count": 1,
                "summary_method": "test",
            },
            {
                "bank": "revolut",
                "source_file": "account-statement_2026-03-01_2026-03-31_en-gb.pdf",
                "account": "deposit",
                "subaccount": "Instant Access Savings",
                "opening_balance": 0.0,
                "closing_balance": 100.0,
                "currency": "EUR",
                "transactions_count": 1,
                "summary_method": "test",
            },
        ]
    )
    market_prices = pd.DataFrame(
        [
            {
                "symbol": "VWCE.DEX",
                "date": pd.Timestamp("2026-03-31"),
                "close": 120.0,
                "fetched_at": pd.Timestamp("2026-04-01"),
            }
        ]
    )

    snapshots = build_net_worth_snapshots(
        transactions,
        statement_balances,
        revolut_balances,
        start_date=pd.Timestamp("2026-03-01"),
        end_date=pd.Timestamp("2026-03-31"),
        market_prices=market_prices,
    )
    row = snapshots.iloc[0]
    expected_interest = calculate_klarna_accrued_interest(pd.Timestamp("2026-03-31"))

    assert row["santander_cash"] == -5100.0
    assert row["revolut_cash"] == 30.0
    assert row["revolut_savings"] == 100.0
    assert row["investments"] == 99.15
    assert row["investment_cost_basis"] == 99.15
    assert row["investment_market_value"] == 120.0
    assert row["investment_gain_loss"] == pytest.approx(20.85)
    assert row["blocked_account"] == 6000.0
    assert row["blocked_interest_accrued"] == pytest.approx(expected_interest)
    assert row["payback_debt"] == 150.0
    assert row["total_net_worth"] == 880.0
    assert row["tracked_wealth"] == pytest.approx(1000.0 + expected_interest)


def test_revolut_pocket_balance_summary_uses_aggregate_running_balance(
    tmp_path,
) -> None:
    csv_path = tmp_path / "revolut_transactions.csv"
    pd.DataFrame(
        [
            {
                "source_file": "account-statement_2026-04-01_2026-06-30.pdf",
                "account": "pockets",
                "subaccount": "Main Account",
                "amount": -42.15,
                "balance": 163.54,
                "currency": "EUR",
            },
            {
                "source_file": "account-statement_2026-04-01_2026-06-30.pdf",
                "account": "pockets",
                "subaccount": "Groceries",
                "amount": 13.0,
                "balance": 135.69,
                "currency": "EUR",
            },
            {
                "source_file": "account-statement_2026-04-01_2026-06-30.pdf",
                "account": "pockets",
                "subaccount": "Main Account",
                "amount": -2.99,
                "balance": 1.70,
                "currency": "EUR",
            },
        ]
    ).to_csv(csv_path, index=False)

    summary = calculate_revolut_subaccount_balances_from_csv(csv_path)

    assert len(summary) == 1
    row = summary.iloc[0]
    assert row["account"] == "pockets"
    assert row["subaccount"] == "All Pockets"
    assert row["opening_balance"] == 205.69
    assert row["closing_balance"] == 1.70
    assert row["summary_method"] == "running_balance"


def test_dashboard_loader_excludes_bancolombia(tmp_path) -> None:
    output_root = tmp_path
    combined_dir = output_root / "combined"
    revolut_dir = output_root / "revolut"
    combined_dir.mkdir()
    revolut_dir.mkdir()

    pd.DataFrame(
        [
            {
                "bank": "bancolombia",
                "account": "savings",
                "subaccount": "",
                "date": "2026-03-01",
                "value_date": "",
                "description": "Bancolombia transaction",
                "amount": -1.0,
                "currency": "COP",
                "balance": "",
                "notes": "",
                "page": 1,
                "source_file": "bancolombia.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-03-01",
                "value_date": "",
                "description": "Santander transaction",
                "amount": 1.0,
                "currency": "EUR",
                "balance": "",
                "notes": "",
                "page": 1,
                "source_file": "santander.pdf",
            },
        ]
    ).to_csv(combined_dir / "all_transactions.csv", index=False)
    pd.DataFrame(
        [
            {
                "bank": "bancolombia",
                "source_file": "bancolombia.pdf",
                "statement_start_date": "2026-03-01",
                "statement_end_date": "2026-03-31",
                "opening_balance": 10,
                "closing_balance": 20,
                "currency": "COP",
                "summary_method": "test",
            },
            {
                "bank": "santander",
                "source_file": "santander.pdf",
                "statement_start_date": "2026-03-01",
                "statement_end_date": "2026-03-31",
                "opening_balance": 10,
                "closing_balance": 20,
                "currency": "EUR",
                "summary_method": "test",
            },
        ]
    ).to_csv(output_root / "statement_balance_summary.csv", index=False)
    pd.DataFrame(
        columns=[
            "source_file",
            "account",
            "subaccount",
            "currency",
            "opening_balance",
            "closing_balance",
            "transactions_count",
        ]
    ).to_csv(revolut_dir / "revolut_subaccount_balances.csv", index=False)

    transactions, statement_balances, _ = load_dashboard_datasets(output_root)

    assert transactions["bank"].unique().tolist() == ["santander"]
    assert "bancolombia" not in statement_balances["bank"].tolist()


def test_payback_debt_carry_forward_with_zero_row_month() -> None:
    """Month 2 with no Payback rows must not reset the running debt to zero.

    The carry-forward works because ``build_payback_debt_summary`` only
    produces rows for months that have Payback transactions.  The running-debt
    loop therefore skips Month 2 entirely and Month 3 correctly inherits the
    Month 1 debt in its starting balance.
    """
    raw = pd.DataFrame(
        [
            # Month 1 — 100 EUR purchase, no repayment → 100 EUR debt
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-01-15",
                "value_date": None,
                "description": "REWE LEIPZIG",
                "amount": -100.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
            # Month 2 — intentionally empty (no rows inserted here)
            # Month 3 — 40 EUR new purchase → total debt 140 EUR
            {
                "bank": "payback",
                "account": "payback_card",
                "subaccount": "",
                "date": "2026-03-10",
                "value_date": None,
                "description": "LIDL LEIPZIG",
                "amount": -40.0,
                "currency": "EUR",
                "balance": None,
                "notes": "",
                "page": None,
                "source_file": "activity.csv",
            },
        ]
    )
    raw["date"] = pd.to_datetime(raw["date"])
    raw["value_date"] = pd.to_datetime(raw["value_date"], errors="coerce")
    debt_summary = build_payback_debt_summary(enrich_transactions(raw))

    january = debt_summary.loc[debt_summary["month_label"].eq("2026-01")].iloc[0]
    march = debt_summary.loc[debt_summary["month_label"].eq("2026-03")].iloc[0]

    # Month 2 has no rows so it does not appear in the summary at all
    assert "2026-02" not in debt_summary["month_label"].tolist()
    # Month 1 builds up 100 EUR of debt
    assert january["purchases"] == 100.0
    assert january["outstanding_debt"] == 100.0
    # Month 3 carries forward the 100 EUR and adds 40 EUR — NOT starting from 0
    assert march["purchases"] == 40.0
    assert march["outstanding_debt"] == 140.0


def test_paycheck_budget_difference_is_limit_minus_actual() -> None:
    """``difference`` in the paycheck budget detail must equal limit − actual.

    A positive value means headroom; a negative value means over budget.
    Per CLAUDE.md §6: difference = limit − actual.
    """
    # Use the existing paycheck fixture — June 2026 has well-known values
    monthly_budget, detail = build_paycheck_budget_report(
        _paycheck_budget_fixture_transactions(),
        start_date=pd.Timestamp("2026-06-01"),
        end_date=pd.Timestamp("2026-06-30"),
    )
    june_detail = detail.loc[detail["month_label"].eq("2026-06")]
    row_by_bucket = {
        row.budget_bucket: row
        for row in june_detail.itertuples(index=False)
    }

    housing = row_by_bucket["Housing & Utilities"]
    grocery = row_by_bucket["Grocery"]

    # Housing limit ≈ 1069.37, actual = 651.0 → under budget, difference > 0
    assert housing.difference == pytest.approx(
        housing.limit_amount - housing.actual_amount
    )
    assert housing.difference > 0.0

    # Grocery limit ≈ 668.36, actual = 200.0 → under budget, difference > 0
    assert grocery.difference == pytest.approx(
        grocery.limit_amount - grocery.actual_amount
    )
    assert grocery.difference > 0.0

    # Verify the sign convention directly with a computed over-budget case:
    # inject a tiny paycheck so Investment limit < actual cost
    tiny_paycheck_raw = pd.DataFrame(
        [
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-04-28",
                "value_date": None,
                "description": "UEBERWEISUNG VON Helmholtz-Zentrum",
                "amount": 500.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Lohn/Gehalt 00042194/202604",
                "page": None,
                "source_file": "statement.pdf",
            },
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-05-10",
                "value_date": None,
                "description": "ISIN IE00BK5BQT80 DEPOT 20969100570608 KAUF",
                "amount": -600.85,
                "currency": "EUR",
                "balance": None,
                "notes": "ORDER-NR. 000001",
                "page": None,
                "source_file": "statement.pdf",
            },
        ]
    )
    tiny_paycheck_raw["date"] = pd.to_datetime(tiny_paycheck_raw["date"])
    tiny_paycheck_raw["value_date"] = pd.to_datetime(
        tiny_paycheck_raw["value_date"], errors="coerce"
    )
    _, tiny_detail = build_paycheck_budget_report(
        enrich_transactions(tiny_paycheck_raw),
        start_date=pd.Timestamp("2026-05-01"),
        end_date=pd.Timestamp("2026-05-31"),
    )
    may_detail = tiny_detail.loc[tiny_detail["month_label"].eq("2026-05")]
    investment_row = may_detail.loc[
        may_detail["budget_bucket"].eq("Investment")
    ].iloc[0]

    # paycheck=500, investment limit = 500*0.18 = 90 EUR, actual = 600 EUR
    # difference = 90 - 600 = -510 (over budget) → must be negative
    assert investment_row.limit_amount == pytest.approx(500.0 * 0.18)
    assert investment_row.actual_amount == 600.0
    assert investment_row.difference == pytest.approx(
        investment_row.limit_amount - investment_row.actual_amount
    )
    assert investment_row.difference < 0.0


def test_fixed_budget_money_left_when_over_committed() -> None:
    """When fixed commitments exceed salary, money_left must be negative."""
    raw = pd.DataFrame(
        [
            # Salary 1000 EUR arriving in December, budgeted for January
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2025-12-29",
                "value_date": None,
                "description": "UEBERWEISUNG VON Helmholtz-Zentrum",
                "amount": 1000.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Lohn/Gehalt 00042194/202512",
                "page": None,
                "source_file": "statement.pdf",
            },
            # Rent 700 EUR
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-01-02",
                "value_date": None,
                "description": "SEPA-LASTSCHRIFT VON Schwarzer Haus- und",
                "amount": -700.0,
                "currency": "EUR",
                "balance": None,
                "notes": "Miete lfd. Monat",
                "page": None,
                "source_file": "statement.pdf",
            },
            # Investment 600 EUR
            {
                "bank": "santander",
                "account": "girokonto",
                "subaccount": "",
                "date": "2026-01-03",
                "value_date": None,
                "description": "ISIN IE00BK5BQT80 DEPOT 20969100570608 KAUF",
                "amount": -600.85,
                "currency": "EUR",
                "balance": None,
                "notes": "ORDER-NR. 000001",
                "page": None,
                "source_file": "statement.pdf",
            },
        ]
    )
    raw["date"] = pd.to_datetime(raw["date"])
    raw["value_date"] = pd.to_datetime(raw["value_date"], errors="coerce")
    monthly_budget, _ = build_fixed_budget_report(
        enrich_transactions(raw),
        start_date=pd.Timestamp("2026-01-01"),
        end_date=pd.Timestamp("2026-01-31"),
    )

    january = monthly_budget.loc[
        monthly_budget["month_label"].eq("2026-01")
    ].iloc[0]

    # salary=1000, fixed_commitments = rent(700) + investment(600.85) = 1300.85
    # money_left = 1000 - 1300.85 = -300.85 → must be negative
    assert january["salary"] == 1000.0
    assert january["fixed_commitments"] > january["salary"]
    assert january["money_left"] < 0.0
    assert january["money_left"] == pytest.approx(
        january["salary"] - january["fixed_commitments"]
    )


def test_klarna_interest_before_start_date() -> None:
    """A date before KLARNA_INTEREST_START_DATE must return 0.0 interest."""
    day_before = KLARNA_INTEREST_START_DATE - pd.Timedelta(days=1)

    interest = calculate_klarna_accrued_interest(day_before)

    assert interest == 0.0


def test_klarna_interest_on_start_date() -> None:
    """Klarna interest accrues on the deposit date itself (inclusive start).

    On 2026-03-11 (deposit date): 1 day of interest.
    On 2026-03-12 (day after): 2 days of interest.
    """
    interest_on_start = calculate_klarna_accrued_interest(KLARNA_INTEREST_START_DATE)
    interest_day_after = calculate_klarna_accrued_interest(
        KLARNA_INTEREST_START_DATE + pd.Timedelta(days=1)
    )

    assert interest_on_start == pytest.approx(6000.0 * 0.0279 / 365.0)
    assert interest_day_after == pytest.approx(6000.0 * 0.0279 * 2 / 365.0)
