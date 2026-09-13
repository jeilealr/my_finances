"""Streamlit application for exploring personal finance data."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.analytics import (
    DashboardFilters,
    build_category_summary,
    build_grouped_expense_detail,
    build_grouped_monthly_expense_report,
    build_monthly_extra_transaction_summary,
    build_monthly_spending_totals,
    build_monthly_summary,
    build_net_worth_snapshots,
    build_payback_debt_summary,
    build_paycheck_budget_report,
    build_report_excluded_movement_summary,
    build_report_group_component_summary,
    build_selected_month_expense_groups,
    build_spending_transactions,
    build_top_expense_table,
    filter_statement_balances,
    filter_transactions,
)
from dashboard.categories import enrich_transactions
from dashboard.charts import (
    category_bar_chart,
    category_donut_chart,
    monthly_grouped_expense_chart,
    monthly_cashflow_chart,
    net_worth_chart,
    payback_debt_chart,
    paycheck_allocation_chart,
    report_group_component_chart,
    report_expense_pie_chart,
    statement_balance_chart,
)
from dashboard.data_loader import build_dashboard_paths, load_dashboard_datasets
from dashboard.investments import (
    build_etf_holdings,
    load_or_fetch_market_prices,
    market_price_cache_dir,
)

DEFAULT_ANALYSIS_START_DATE = pd.Timestamp("2026-01-01")


def _default_output_root() -> str:
    """Return the default output root shown in the sidebar."""
    return os.environ.get(
        "MY_FINANCES_OUTPUT_ROOT",
        str(build_dashboard_paths().output_root),
    )


@st.cache_data(show_spinner=False, ttl=300)
def _load_data(output_root: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load dashboard datasets and derive analysis fields."""
    transactions, statement_balances, revolut_balances = load_dashboard_datasets(
        output_root=output_root
    )
    return enrich_transactions(transactions), statement_balances, revolut_balances


@st.cache_data(show_spinner=False, ttl=3600)
def _load_market_prices(
    output_root: str,
    symbols: tuple[str, ...],
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Load ETF prices from the local cache or Alpha Vantage when configured."""
    return load_or_fetch_market_prices(
        symbols,
        cache_dir=market_price_cache_dir(output_root),
        api_key=os.environ.get("ALPHA_VANTAGE_API_KEY"),
    )


def _inject_styles() -> None:
    """Apply lightweight visual styling to the Streamlit app."""
    st.markdown(
        """
        <style>
        :root {
            --dashboard-bg: #f8f4ed;
            --dashboard-card: #ffffff;
            --dashboard-border: rgba(38, 70, 83, 0.16);
            --dashboard-accent: #d1495b;
            --dashboard-accent-soft: #f4a261;
            --dashboard-ink: #20323a;
            --dashboard-muted: #5f6b73;
            --dashboard-shadow: 0 18px 44px rgba(32, 50, 58, 0.08);
        }
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(244, 162, 97, 0.18), transparent 25%),
                radial-gradient(circle at top left, rgba(31, 157, 120, 0.12), transparent 18%),
                var(--dashboard-bg);
            color: var(--dashboard-ink);
        }
        section[data-testid="stMain"] .block-container {
            max-width: 1460px;
            padding-top: 2.2rem;
            padding-bottom: 3rem;
        }
        section[data-testid="stMain"] h1 {
            color: var(--dashboard-ink);
            font-size: clamp(2.6rem, 4vw, 3.6rem);
            font-weight: 800;
            letter-spacing: -0.04em;
            margin-bottom: 0.35rem;
        }
        section[data-testid="stMain"] h2,
        section[data-testid="stMain"] h3,
        section[data-testid="stMain"] h4 {
            color: var(--dashboard-ink);
            letter-spacing: -0.02em;
        }
        section[data-testid="stMain"] [data-testid="stCaptionContainer"] {
            color: var(--dashboard-muted);
            font-size: 1rem;
        }
        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid var(--dashboard-border);
            border-radius: 20px;
            padding: 1rem 1.1rem;
            box-shadow: var(--dashboard-shadow);
        }
        div[data-testid="stMetricLabel"] p {
            color: var(--dashboard-ink) !important;
            font-size: 0.98rem !important;
            font-weight: 800 !important;
            letter-spacing: 0.01em;
            opacity: 1 !important;
        }
        div[data-testid="stMetricValue"] {
            color: var(--dashboard-ink) !important;
        }
        div[data-testid="stMetricValue"] > div {
            color: var(--dashboard-ink) !important;
            font-weight: 800 !important;
            line-height: 1.1;
        }
        div[data-testid="stMetricDelta"] > div {
            color: var(--dashboard-accent) !important;
        }
        div[data-testid="stAlert"] {
            background: rgba(209, 228, 244, 0.9);
            border: 1px solid rgba(52, 124, 189, 0.22);
            border-radius: 18px;
            box-shadow: 0 10px 28px rgba(52, 124, 189, 0.08);
        }
        div[data-testid="stAlert"] p {
            color: #18486d !important;
            font-weight: 600;
        }
        div[data-testid="stPlotlyChart"] {
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid var(--dashboard-border);
            border-radius: 26px;
            padding: 0.8rem 0.85rem 0.35rem;
            box-shadow: var(--dashboard-shadow);
        }
        div[data-testid="stDataFrame"] {
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid var(--dashboard-border);
            border-radius: 22px;
            padding: 0.45rem;
            box-shadow: var(--dashboard-shadow);
        }
        .dashboard-card {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid var(--dashboard-border);
            border-radius: 24px;
            padding: 1rem 1.15rem;
            margin-bottom: 1rem;
            color: var(--dashboard-ink);
            box-shadow: var(--dashboard-shadow);
            backdrop-filter: blur(8px);
        }
        .dashboard-section-shell {
            background:
                linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(252, 248, 240, 0.95));
            border: 1px solid var(--dashboard-border);
            border-radius: 28px;
            padding: 1rem 1.15rem;
            margin: 0.45rem 0 1rem;
            box-shadow: var(--dashboard-shadow);
        }
        .dashboard-section-title {
            color: var(--dashboard-ink);
            font-size: 1.05rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin-bottom: 0.15rem;
        }
        .dashboard-section-copy {
            color: var(--dashboard-muted);
            font-size: 0.94rem;
            line-height: 1.45;
            margin-bottom: 0.7rem;
        }
        .dashboard-mini-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.28rem 0.72rem;
            border-radius: 999px;
            background: rgba(38, 70, 83, 0.06);
            border: 1px solid rgba(38, 70, 83, 0.08);
            color: var(--dashboard-ink);
            font-size: 0.84rem;
            font-weight: 700;
            margin-right: 0.42rem;
            margin-bottom: 0.32rem;
        }
        .dashboard-currency-banner {
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(38, 70, 83, 0.1);
            border-radius: 22px;
            padding: 0.85rem 1rem;
            margin: 0.2rem 0 0.7rem;
            box-shadow: 0 12px 28px rgba(32, 50, 58, 0.06);
        }
        .dashboard-currency-kicker {
            display: inline-block;
            padding: 0.22rem 0.6rem;
            border-radius: 999px;
            background: rgba(42, 157, 143, 0.13);
            color: #1c6f65;
            font-size: 0.8rem;
            font-weight: 800;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 0.45rem;
        }
        .dashboard-currency-title {
            color: var(--dashboard-ink);
            font-size: 1rem;
            font-weight: 800;
            margin-bottom: 0.12rem;
        }
        .dashboard-currency-meta {
            color: var(--dashboard-muted);
            font-size: 0.9rem;
            line-height: 1.4;
        }
        .dashboard-tag {
            display: inline-block;
            padding: 0.24rem 0.62rem;
            border-radius: 999px;
            background: rgba(209, 73, 91, 0.12);
            color: var(--dashboard-accent);
            border: 1px solid rgba(209, 73, 91, 0.08);
            font-size: 0.85rem;
            font-weight: 700;
            margin-right: 0.4rem;
            margin-bottom: 0.25rem;
        }
        button[data-baseweb="tab"] {
            color: var(--dashboard-muted);
            font-weight: 700;
            border-radius: 999px 999px 0 0;
            padding-left: 0.1rem;
            padding-right: 0.1rem;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: var(--dashboard-accent);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _bank_display_name(bank_name: str) -> str:
    """Return a user-friendly bank label."""
    overrides = {
        "payback": "Payback",
        "revolut": "Revolut",
        "santander": "Santander",
    }
    return overrides.get(bank_name, bank_name.replace("_", " ").title())


BLOCKED_ACCOUNT_NOTE = (
    "Klarna blocked account: 6,000 EUR is excluded from spending calculations "
    "and is expected to remain blocked until 11 March 2029."
)
NO_SELECTION_SENTINEL = "__no_selection__"


def _filter_by_selection(
    dataframe: pd.DataFrame,
    column: str,
    selected_values: tuple[str, ...],
) -> pd.DataFrame:
    """Apply a sidebar checkbox selection to one DataFrame column."""
    if selected_values == (NO_SELECTION_SENTINEL,):
        return dataframe.iloc[0:0].copy()
    if selected_values:
        return dataframe.loc[dataframe[column].isin(selected_values)].copy()
    return dataframe.copy()


def _normalize_checkbox_filter_selection(
    options: list[str],
    *,
    select_all: bool,
    selected_options: list[str],
) -> tuple[str, ...]:
    """Return the filter tuple represented by a checkbox group."""
    if select_all:
        return tuple()

    valid_options = set(options)
    selection = tuple(option for option in selected_options if option in valid_options)
    return selection or (NO_SELECTION_SENTINEL,)


def _normalize_analysis_period(
    date_range: object,
    *,
    min_date: pd.Timestamp,
    max_date: pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return a complete date range from Streamlit's date input value."""
    fallback = (
        st.session_state.get("analysis_period_start", min_date),
        st.session_state.get("analysis_period_end", max_date),
    )
    if date_range is None:
        start_date, end_date = fallback
    elif isinstance(date_range, (tuple, list)):
        if len(date_range) >= 2:
            start_date, end_date = (
                pd.Timestamp(date_range[0]),
                pd.Timestamp(date_range[-1]),
            )
        elif len(date_range) == 1:
            start_date, end_date = pd.Timestamp(date_range[0]), fallback[1]
        else:
            start_date, end_date = fallback
    else:
        start_date = end_date = pd.Timestamp(date_range)

    start_date = max(pd.Timestamp(start_date).normalize(), min_date)
    end_date = min(pd.Timestamp(end_date).normalize(), max_date)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    st.session_state["analysis_period_start"] = start_date
    st.session_state["analysis_period_end"] = end_date
    return start_date, end_date


def _default_analysis_period_bounds(
    min_date: pd.Timestamp,
    max_date: pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return the default dashboard period, starting at Jan 1 2026 when possible."""
    default_start = DEFAULT_ANALYSIS_START_DATE
    start_date = min(max(default_start, min_date), max_date)
    return start_date, max_date


def _render_checkbox_filter_group(
    label: str,
    options: list[str],
    *,
    key_prefix: str,
) -> tuple[str, ...]:
    """Render a compact checkbox filter group inside a sidebar expander."""
    clean_options = sorted(str(option) for option in options if str(option))
    with st.sidebar.expander(label, expanded=False):
        select_all = st.checkbox(
            "All",
            value=True,
            key=f"{key_prefix}_all",
        )
        selected_options = [
            option
            for index, option in enumerate(clean_options)
            if st.checkbox(
                option,
                value=True,
                disabled=select_all,
                key=f"{key_prefix}_{index}",
            )
        ]

        if select_all:
            st.caption(f"All {len(clean_options)} selected")
        else:
            st.caption(f"{len(selected_options)} of {len(clean_options)} selected")

    return _normalize_checkbox_filter_selection(
        clean_options,
        select_all=select_all,
        selected_options=selected_options,
    )


def _render_sidebar(transactions: pd.DataFrame) -> DashboardFilters:
    """Render the dashboard sidebar and return analysis-period filters."""
    st.sidebar.header("Control Panel")

    if transactions.empty:
        empty_date = pd.Timestamp.today().normalize()
        filters = DashboardFilters(
            start_date=empty_date,
            end_date=empty_date,
            months=tuple(),
            banks=tuple(),
            accounts=tuple(),
            subaccounts=tuple(),
            categories=tuple(),
            currencies=tuple(),
            include_transfers=False,
            search_text="",
        )
        return filters

    min_date = transactions["date"].min().normalize()
    max_date = transactions["date"].max().normalize()
    default_start_date, default_end_date = _default_analysis_period_bounds(
        min_date,
        max_date,
    )

    date_range = st.sidebar.date_input(
        "Analysis period",
        value=(default_start_date.date(), default_end_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
        format="YYYY-MM-DD",
        key="analysis_period",
        help=(
            "Dates after the latest loaded transaction are disabled. The year can "
            "still be opened when some dates in that year are available."
        ),
    )
    start_date, end_date = _normalize_analysis_period(
        date_range,
        min_date=min_date,
        max_date=max_date,
    )

    period_transactions = transactions.loc[
        transactions["date"].between(start_date, end_date, inclusive="both")
    ].copy()
    selected_banks = _render_checkbox_filter_group(
        "Banks",
        sorted(period_transactions["bank"].dropna().unique().tolist()),
        key_prefix="banks",
    )

    bank_transactions = _filter_by_selection(
        period_transactions,
        "bank",
        selected_banks,
    )
    selected_accounts = _render_checkbox_filter_group(
        "Accounts",
        sorted(bank_transactions["account"].dropna().unique().tolist()),
        key_prefix="accounts",
    )

    account_transactions = _filter_by_selection(
        bank_transactions,
        "account",
        selected_accounts,
    )
    selected_subaccounts = _render_checkbox_filter_group(
        "Subaccounts",
        sorted(account_transactions["subaccount"].dropna().unique().tolist()),
        key_prefix="subaccounts",
    )

    subaccount_transactions = _filter_by_selection(
        account_transactions,
        "subaccount",
        selected_subaccounts,
    )
    selected_categories = _render_checkbox_filter_group(
        "Categories",
        sorted(subaccount_transactions["category"].dropna().unique().tolist()),
        key_prefix="categories",
    )
    include_transfers = st.sidebar.checkbox(
        "Include internal transfers",
        value=False,
        help="Turn this on if you want account transfers included outside reports.",
    )
    search_text = st.sidebar.text_input(
        "Search description / notes",
        value="",
        help="Filter the dashboard to transactions matching this text.",
    )

    st.sidebar.divider()
    if st.sidebar.button("Refresh data", help="Clear the data cache and reload from disk."):
        st.cache_data.clear()
        st.rerun()

    filters = DashboardFilters(
        start_date=start_date,
        end_date=end_date,
        months=tuple(),
        banks=selected_banks,
        accounts=selected_accounts,
        subaccounts=selected_subaccounts,
        categories=selected_categories,
        currencies=tuple(),
        include_transfers=include_transfers,
        search_text=search_text,
    )
    return filters


def _prepare_spending_transactions(scope_transactions: pd.DataFrame) -> pd.DataFrame:
    """Return expense transactions that should appear in spending views."""
    if scope_transactions.empty:
        return scope_transactions.copy()

    return build_spending_transactions(scope_transactions)


def _render_spending_scope_header(
    scope_transactions: pd.DataFrame,
    focused_transactions: pd.DataFrame,
) -> None:
    """Render a compact scope summary card for the spending view."""
    currencies = sorted(focused_transactions["currency"].dropna().unique().tolist())
    categories = sorted(focused_transactions["category"].dropna().unique().tolist())
    months_visible = focused_transactions["month_label"].nunique()
    notes = [
        f"{len(focused_transactions)} tracked outflows",
        f"{months_visible} visible months",
        f"{len(currencies)} currencies",
        f"{len(categories)} categories",
    ]
    chips = "".join(
        f'<span class="dashboard-mini-chip">{item}</span>' for item in notes
    )
    st.markdown(
        f"""
        <div class="dashboard-section-shell">
            <div class="dashboard-section-title">Spending Lens</div>
            <div class="dashboard-section-copy">
                Transfers between your own accounts are excluded so the chart focuses on real merchant spending.
            </div>
            {chips}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_currency_banner(
    currency: str,
    currency_transactions: pd.DataFrame,
) -> None:
    """Render a small descriptive banner above a currency section."""
    category_count = currency_transactions["category"].nunique()
    month_count = currency_transactions["month_label"].nunique()
    transaction_count = len(currency_transactions)
    st.markdown(
        f"""
        <div class="dashboard-currency-banner">
            <div class="dashboard-currency-kicker">{currency or "Unknown"}</div>
            <div class="dashboard-currency-title">Monthly spending flow</div>
            <div class="dashboard-currency-meta">
                {month_count} months, {category_count} categories, {transaction_count} tracked outflows
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_currency_expense_table(
    currency_transactions: pd.DataFrame,
    income_scope_transactions: pd.DataFrame,
) -> None:
    """Render monthly expense totals with income comparison for one currency."""
    monthly_totals = build_monthly_spending_totals(
        currency_transactions,
        income_scope_transactions,
    )
    if monthly_totals.empty:
        st.info("No monthly totals are available for this currency.")
        return

    expense_table = (
        monthly_totals.sort_values("month", ascending=False)
        .loc[:, ["month_label", "income", "expenses", "money_left", "transactions"]]
        .rename(
            columns={
                "month_label": "Month",
                "income": "Income",
                "expenses": "Expenses",
                "money_left": "Money Left",
                "transactions": "Transactions",
            }
        )
    )
    st.dataframe(expense_table, width="stretch", hide_index=True)


def _render_spending_transaction_details(
    focused_transactions: pd.DataFrame,
    *,
    key_prefix: str,
) -> None:
    """Render transaction-level detail for the current spending scope."""
    st.markdown("#### Transaction Details")
    detail_mode = st.radio(
        "Transaction view",
        options=("All filtered transactions", "Largest transactions"),
        index=0,
        horizontal=True,
        key=f"{key_prefix}_transaction_detail_mode",
        help=(
            "Switch between the complete filtered dataset for this scope and a "
            "shorter list of the largest transactions."
        ),
    )

    if detail_mode == "Largest transactions":
        detail_frame = build_top_expense_table(focused_transactions)
        file_name = f"{key_prefix}_largest_transactions.csv"
    else:
        detail_frame = (
            focused_transactions.sort_values(
                ["date", "amount"], ascending=[False, True]
            )
            .loc[
                :,
                [
                    "date",
                    "bank",
                    "account",
                    "subaccount",
                    "category",
                    "description",
                    "amount",
                    "currency",
                    "notes",
                    "source_file",
                ],
            ]
            .reset_index(drop=True)
        )
        file_name = f"{key_prefix}_filtered_transactions.csv"

    st.caption(
        f"{len(detail_frame)} rows match the current scope, date range, and category focus."
    )
    st.dataframe(detail_frame, width="stretch", hide_index=True)
    st.download_button(
        "Download current transaction detail",
        detail_frame.to_csv(index=False).encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
        key=f"{key_prefix}_transaction_detail_download",
    )


def _render_reports(filtered_transactions: pd.DataFrame) -> None:
    """Render grouped month-by-month expense reports for the active filters."""
    grouped_report = build_grouped_monthly_expense_report(filtered_transactions)
    expense_detail = build_grouped_expense_detail(filtered_transactions)
    excluded_movements = build_report_excluded_movement_summary(filtered_transactions)
    if grouped_report.empty:
        st.info("No grouped expense data is available for the current filter selection.")
        return

    st.markdown("### Monthly Expense Report")
    st.caption(
        "The pie chart is expense-only. Transfers, salary, savings, investments, blocked-account movements, and card repayments stay outside the pie."
    )

    month_options = (
        grouped_report.sort_values("month")["month_label"].drop_duplicates().tolist()
    )
    selected_month = st.selectbox(
        "Report month",
        options=month_options,
        index=len(month_options) - 1,
        help="Choose the month shown in the expense pie chart.",
        key="reports_month_selector",
    )
    selected_pie_data = build_selected_month_expense_groups(
        grouped_report,
        month_label=selected_month,
    )

    selected_month_total = float(selected_pie_data["expenses"].sum())
    selected_currencies = sorted(selected_pie_data["currency"].dropna().unique())
    currency_label = (
        selected_currencies[0] if len(selected_currencies) == 1 else "mixed currencies"
    )
    group_count = selected_pie_data["report_group"].nunique()
    transaction_count = int(
        grouped_report.loc[grouped_report["month_label"].eq(selected_month)][
            "transactions"
        ].sum()
    )
    metric_cols = st.columns(4)
    metric_cols[0].metric("Report Month", selected_month)
    metric_cols[1].metric(
        "Total Pie Expenses",
        f"{selected_month_total:,.2f} {currency_label}",
        help="Total expense amount included in the selected month's pie chart.",
    )
    metric_cols[2].metric(
        "Groups In Pie",
        f"{group_count}",
        help="Number of grouped expense categories visible in the pie chart.",
    )
    metric_cols[3].metric(
        "Expense Transactions",
        f"{transaction_count}",
        help="Number of expense transactions included in the selected month's grouped totals.",
    )

    pie_col, table_col = st.columns((1.15, 1))
    with pie_col:
        st.plotly_chart(
            report_expense_pie_chart(selected_pie_data),
            width="stretch",
            key="reports_grouped_expense_pie_chart",
        )
    with table_col:
        st.markdown("#### Selected Month Groups")
        selected_table = selected_pie_data.rename(
            columns={
                "month_label": "Month",
                "currency": "Currency",
                "report_group": "Expense Group",
                "expenses": "Expenses",
            }
        )
        st.dataframe(
            selected_table.drop(columns=["month"]),
            width="stretch",
            hide_index=True,
        )

    if not excluded_movements.empty:
        month_movements = excluded_movements.loc[
            excluded_movements["month_label"].eq(selected_month)
        ].copy()
        if not month_movements.empty:
            st.markdown("#### Context Outside The Pie")
            st.caption(
                "These movements are shown for awareness but are not counted as expenses in the pie."
            )
            movement_cols = st.columns(min(4, len(month_movements)))
            for index, row in enumerate(month_movements.itertuples(index=False)):
                movement_cols[index % len(movement_cols)].metric(
                    f"Outside Pie: {row.category}",
                    f"{float(row.amount):,.2f} {row.currency}",
                    help=(
                        f"{int(row.transactions)} transfer/context transaction(s) in "
                        f"{selected_month}. This amount is not included in Total Pie Expenses."
                    ),
                )

    st.markdown("#### Month-by-Month Expense Groups")
    st.plotly_chart(
        monthly_grouped_expense_chart(grouped_report),
        width="stretch",
        key="reports_grouped_monthly_expense_chart",
    )

    component_options = (
        grouped_report.sort_values(["report_group"])["report_group"]
        .drop_duplicates()
        .tolist()
    )
    selected_component_group = st.selectbox(
        "Break down expense group",
        options=component_options,
        index=0,
        help=(
            "Choose one high-level Reports group and see the raw categories that "
            "make up that group month by month."
        ),
        key="reports_component_group_selector",
    )
    component_summary = build_report_group_component_summary(
        expense_detail,
        report_group=selected_component_group,
    )
    st.markdown(f"#### {selected_component_group} Components")
    st.caption(
        "This chart breaks the selected group into its original dashboard categories, such as rent, electricity, transport, and pharmacy inside Housing & Utilities."
    )
    st.plotly_chart(
        report_group_component_chart(component_summary),
        width="stretch",
        key="reports_group_component_chart",
    )

    st.markdown("#### Group Detail")
    grouped_table = grouped_report.rename(
        columns={
            "month_label": "Month",
            "currency": "Currency",
            "report_group": "Expense Group",
            "expenses": "Expenses",
            "transactions": "Transactions",
        }
    ).sort_values(["Currency", "Month", "Expenses"], ascending=[True, False, False])
    st.dataframe(grouped_table.drop(columns=["month"]), width="stretch", hide_index=True)

    with st.expander("Transaction detail for grouped expenses", expanded=False):
        detail_table = expense_detail.rename(
            columns={
                "month_label": "Month",
                "bank": "Bank",
                "account": "Account",
                "subaccount": "Subaccount",
                "category": "Original Category",
                "report_group": "Expense Group",
                "description": "Description",
                "amount": "Amount",
                "expense_amount": "Expense Amount",
                "currency": "Currency",
                "notes": "Notes",
                "source_file": "Source File",
            }
        )
        st.dataframe(detail_table, width="stretch", hide_index=True)

    st.download_button(
        "Download grouped expense report",
        grouped_report.to_csv(index=False).encode("utf-8"),
        file_name="grouped_monthly_expense_report.csv",
        mime="text/csv",
        key="grouped_monthly_report_download",
    )
    st.download_button(
        "Download grouped transaction detail",
        expense_detail.to_csv(index=False).encode("utf-8"),
        file_name="grouped_expense_transaction_detail.csv",
        mime="text/csv",
        key="grouped_expense_detail_download",
    )


def _render_bank_monthly_view(
    bank_name: str,
    bank_transactions: pd.DataFrame,
    bank_report_transactions: pd.DataFrame,
) -> None:
    """Render one bank-specific overview section."""
    st.markdown(f"### {_bank_display_name(bank_name)}")
    monthly_summary = build_monthly_summary(bank_transactions)
    extra_summary = build_monthly_extra_transaction_summary(bank_report_transactions)
    st.plotly_chart(
        monthly_cashflow_chart(monthly_summary, extra_summary),
        width="stretch",
        key=f"{bank_name}_monthly_cashflow_chart",
    )


def _render_payback_debt_view(payback_transactions: pd.DataFrame) -> None:
    """Render Payback as a credit-card debt tracker."""
    st.markdown("### Payback")
    debt_summary = build_payback_debt_summary(payback_transactions)
    if debt_summary.empty:
        st.info("No Payback debt activity is available for the current filters.")
        return

    latest = debt_summary.sort_values("month").iloc[-1]
    total_purchases = float(debt_summary["purchases"].sum())
    total_repaid = float(debt_summary["repayments"].sum())
    remaining_debt = float(latest["outstanding_debt"])
    progress_ratio = min(total_repaid / total_purchases, 1.0) if total_purchases else 0

    metric_cols = st.columns(3)
    metric_cols[0].metric("Known Purchases", f"{total_purchases:,.2f} EUR")
    metric_cols[1].metric("Known Credits / Repaid", f"{total_repaid:,.2f} EUR")
    metric_cols[2].metric("Remaining Known Debt", f"{remaining_debt:,.2f} EUR")
    st.progress(
        progress_ratio,
        text=f"{progress_ratio:.1%} of known Payback purchases credited/repaid",
    )

    st.plotly_chart(
        payback_debt_chart(debt_summary),
        width="stretch",
        key="payback_debt_tracker_chart",
    )


def _render_net_worth_snapshot(
    transactions: pd.DataFrame,
    statement_balances: pd.DataFrame,
    revolut_balances: pd.DataFrame,
    filters: DashboardFilters,
    output_root: str,
) -> None:
    """Render the overview net-worth snapshot section."""
    latest_holdings = build_etf_holdings(
        transactions,
        as_of_date=transactions["date"].max(),
    )
    market_symbols = tuple(latest_holdings["symbol"].dropna().astype(str).unique())
    market_prices, market_warnings = _load_market_prices(output_root, market_symbols)
    net_worth = build_net_worth_snapshots(
        transactions,
        statement_balances,
        revolut_balances,
        start_date=filters.start_date,
        end_date=filters.end_date,
        market_prices=market_prices,
    )
    if net_worth.empty:
        st.info("No net-worth snapshot is available for the current period.")
        return

    st.markdown("### Net Worth Snapshot")
    latest_net_worth = build_net_worth_snapshots(
        transactions,
        statement_balances,
        revolut_balances,
        start_date=transactions["date"].min(),
        end_date=transactions["date"].max(),
        market_prices=market_prices,
    )
    latest = latest_net_worth.sort_values("month").iloc[-1]
    selected_period_latest = net_worth.sort_values("month").iloc[-1]
    latest_label = pd.Timestamp(latest["month"]).strftime("%b %Y")
    selected_label = pd.Timestamp(selected_period_latest["month"]).strftime("%b %Y")
    st.caption(
        f"Cards show the latest loaded snapshot ({latest_label}). The chart follows "
        f"the selected analysis period and currently ends at {selected_label}. Total Net Worth "
        "uses account balances, blocked principal, and Payback debt. Tracked Wealth adds ETF "
        "market value and Klarna accrued interest."
    )
    if market_warnings:
        st.warning(
            "ETF market prices are incomplete, so affected investments fall back to "
            f"PDF-derived cost basis. Details: {'; '.join(market_warnings)}"
        )
    metric_cols = st.columns(4)
    metric_cols[0].metric(
        "Latest Total Net Worth",
        f"{latest['total_net_worth']:,.2f} EUR",
        help=(
            f"Latest loaded month: {latest_label}. The line chart can show a different "
            "value when the selected analysis period ends earlier."
        ),
    )
    metric_cols[1].metric("Santander Account", f"{latest['santander_cash']:,.2f} EUR")
    metric_cols[2].metric("Revolut Account", f"{latest['revolut_cash']:,.2f} EUR")
    metric_cols[3].metric("Revolut Savings", f"{latest['revolut_savings']:,.2f} EUR")
    detail_cols = st.columns(4)
    detail_cols[0].metric(
        "Investment",
        f"{latest['investment_market_value']:,.2f} EUR",
        help=(
            "ETF market value from Alpha Vantage/cached prices when available. If prices "
            "are missing, this falls back to the PDF-derived Santander purchase cost basis."
        ),
    )
    detail_cols[1].metric(
        "ETF Gain/Loss",
        f"{latest['investment_gain_loss']:,.2f} EUR",
        help="Investment market value minus PDF-derived ETF cost basis.",
    )
    detail_cols[2].metric(
        "Klarna Interest",
        f"{latest['blocked_interest_accrued']:,.2f} EUR",
        help="Simple daily accrued interest on the 6,000 EUR blocked account at 2.79% annually.",
    )
    detail_cols[3].metric(
        "Tracked Wealth",
        f"{latest['tracked_wealth']:,.2f} EUR",
        help="Total Net Worth plus ETF market value and Klarna accrued interest.",
    )
    liability_cols = st.columns(4)
    liability_cols[0].metric(
        "Blocked Principal",
        f"{latest['blocked_account']:,.2f} EUR",
    )
    liability_cols[1].metric(
        "Payback Known Debt",
        f"{latest['payback_debt']:,.2f} EUR",
        help=(
            "Running known Payback liability from loaded Payback CSVs. If there are no newer "
            "Payback rows, the last known debt is carried forward."
        ),
    )

    st.plotly_chart(
        net_worth_chart(net_worth),
        width="stretch",
        key="net_worth_snapshot_chart",
    )


def _render_overview(
    filtered_transactions: pd.DataFrame,
    filtered_statement_balances: pd.DataFrame,
    report_transactions: pd.DataFrame,
    all_transactions: pd.DataFrame,
    all_statement_balances: pd.DataFrame,
    revolut_balances: pd.DataFrame,
    filters: DashboardFilters,
    output_root: str,
) -> None:
    """Render the top-level dashboard overview."""
    visible_banks = sorted(
        set(filtered_transactions["bank"].dropna().unique().tolist())
        | set(filtered_statement_balances["bank"].dropna().unique().tolist())
    )
    if not visible_banks:
        st.info("No bank data is available for the current filters.")
        return

    _render_net_worth_snapshot(
        all_transactions,
        all_statement_balances,
        revolut_balances,
        filters,
        output_root,
    )

    st.markdown("### Bank-by-Bank Monthly View")
    st.caption(
        "Each bank tab shows monthly cashflow for the visible period."
    )
    bank_tabs = st.tabs([_bank_display_name(bank_name) for bank_name in visible_banks])
    for tab, bank_name in zip(bank_tabs, visible_banks):
        with tab:
            bank_transactions = filtered_transactions.loc[
                filtered_transactions["bank"].eq(bank_name)
            ].copy()
            bank_report_transactions = report_transactions.loc[
                report_transactions["bank"].eq(bank_name)
            ].copy()
            if bank_name == "payback":
                _render_payback_debt_view(bank_report_transactions)
            else:
                _render_bank_monthly_view(
                    bank_name,
                    bank_transactions,
                    bank_report_transactions,
                )

    st.markdown("### Statement Closing Balances")
    st.caption(
        "Each point shows the closing balance reported at a statement's end date. "
        "Use the chart legend to hide or isolate specific banks."
    )
    balance_chart_data = filtered_statement_balances.loc[
        ~filtered_statement_balances["bank"].eq("payback")
    ].copy()
    if balance_chart_data.empty:
        st.info("No statement closing balances are available for the current filters.")
        return

    st.plotly_chart(
        statement_balance_chart(balance_chart_data),
        width="stretch",
    )


def _render_spending(
    transactions: pd.DataFrame,
    filters: DashboardFilters,
) -> None:
    """Render spending-related views."""
    spending_filters = DashboardFilters(
        start_date=filters.start_date,
        end_date=filters.end_date,
        months=filters.months,
        banks=filters.banks,
        accounts=filters.accounts,
        subaccounts=filters.subaccounts,
        categories=filters.categories,
        currencies=filters.currencies,
        include_transfers=True,
        search_text=filters.search_text,
    )
    filtered_transactions = filter_transactions(transactions, spending_filters)
    spending_income_filters = DashboardFilters(
        start_date=filters.start_date,
        end_date=filters.end_date,
        months=filters.months,
        banks=filters.banks,
        accounts=filters.accounts,
        subaccounts=filters.subaccounts,
        categories=tuple(),
        currencies=filters.currencies,
        include_transfers=True,
        search_text=filters.search_text,
    )
    spending_income_scope = filter_transactions(transactions, spending_income_filters)
    if filtered_transactions.empty:
        st.info("No spending data is available for the current filters.")
        return

    def render_spending_scope(
        scope_transactions: pd.DataFrame,
        income_scope_transactions: pd.DataFrame,
        *,
        key_prefix: str,
    ) -> None:
        """Render the spending detail for one scope."""
        scope_expenses = _prepare_spending_transactions(scope_transactions)
        if scope_expenses.empty:
            st.info("No expense transactions are available for this view.")
            return

        category_options = sorted(scope_expenses["category"].dropna().unique().tolist())
        selected_spending_categories = st.multiselect(
            "Focus categories",
            options=category_options,
            default=[],
            key=f"{key_prefix}_spending_category_filter",
            help=(
                "Limit the monthly spending chart, totals table, and expense "
                "breakdowns to specific categories such as Grocery Shopping."
            ),
        )

        if selected_spending_categories:
            focused_expenses = scope_expenses.loc[
                scope_expenses["category"].isin(selected_spending_categories)
            ].copy()
        else:
            focused_expenses = scope_expenses

        if focused_expenses.empty:
            st.info("No transactions remain after applying the category focus.")
            return

        _render_spending_scope_header(scope_expenses, focused_expenses)
        currencies = sorted(focused_expenses["currency"].dropna().unique().tolist())

        st.markdown("#### Monthly Expense Totals")
        for currency in currencies:
            currency_expenses = focused_expenses.loc[
                focused_expenses["currency"].eq(currency)
            ].copy()
            currency_income_scope = income_scope_transactions.loc[
                income_scope_transactions["currency"].eq(currency)
            ].copy()
            _render_currency_banner(currency, currency_expenses)
            _render_currency_expense_table(
                currency_expenses,
                currency_income_scope,
            )

        st.markdown("#### Category Mix by Currency")
        for currency in currencies:
            currency_expenses = focused_expenses.loc[
                focused_expenses["currency"].eq(currency)
            ].copy()
            category_summary = build_category_summary(currency_expenses)
            _render_currency_banner(currency, currency_expenses)

            chart_col1, chart_col2 = st.columns((1.2, 1))
            with chart_col1:
                st.plotly_chart(
                    category_bar_chart(category_summary),
                    width="stretch",
                    key=f"{key_prefix}_{currency}_category_bar_chart",
                )
            with chart_col2:
                st.plotly_chart(
                    category_donut_chart(category_summary),
                    width="stretch",
                    key=f"{key_prefix}_{currency}_category_donut_chart",
                )

        _render_spending_transaction_details(
            focused_expenses,
            key_prefix=key_prefix,
        )

    st.markdown("### Month-by-Month Spending")
    st.caption(
        "This view combines all accounts so Santander transfers to Payback or Revolut do not appear as spending twice. "
        "Payback purchases and Revolut card/account purchases are the itemized expenses."
    )
    render_spending_scope(
        filtered_transactions,
        spending_income_scope,
        key_prefix="all_banks",
    )


def _render_budget(
    filtered_transactions: pd.DataFrame,
    filters: DashboardFilters,
) -> None:
    """Render paycheck-based budget limits and spending context."""
    monthly_budget, budget_detail = build_paycheck_budget_report(
        filtered_transactions,
        start_date=filters.start_date,
        end_date=filters.end_date,
    )
    if monthly_budget.empty:
        st.info("No budget data is available for the current filter selection.")
        return

    st.markdown("### Paycheck Budget")
    st.caption(
        "This view uses only recurring UFZ/Helmholtz paycheck rows as the planning base. "
        "Travel refunds and one-off reimbursements stay out of the paycheck budget, but remain visible in total income context."
    )

    month_options = monthly_budget.sort_values("month")[
        "month_label"
    ].drop_duplicates().tolist()
    selected_month = st.selectbox(
        "Budget month",
        options=month_options,
        index=len(month_options) - 1,
        help="Choose the month shown in the paycheck-limit detail.",
        key="budget_month_selector",
    )
    selected_month_rows = monthly_budget.loc[
        monthly_budget["month_label"].eq(selected_month)
    ].copy()
    selected_budget = selected_month_rows.sort_values("currency").iloc[0]
    selected_currency = str(selected_budget["currency"])
    selected_detail = budget_detail.loc[
        budget_detail["month_label"].eq(selected_month)
        & budget_detail["currency"].eq(selected_currency)
    ].copy()

    top_cols = st.columns(3)
    top_cols[0].metric(
        "Paycheck",
        f"{float(selected_budget['paycheck']):,.2f} {selected_currency}",
        help="Recurring UFZ/Helmholtz paycheck assigned to this budget month.",
    )
    top_cols[1].metric(
        "Budgeted Limits",
        f"{float(selected_budget['budgeted_limits']):,.2f} {selected_currency}",
        help="Sum of the configured percentage limits for this paycheck.",
    )
    top_cols[2].metric(
        "Actual Used",
        f"{float(selected_budget['actual_used']):,.2f} {selected_currency}",
        help="Actual grouped expenses plus Santander ETF investment principal.",
    )

    context_cols = st.columns(3)
    context_cols[0].metric(
        "Paycheck Remaining",
        f"{float(selected_budget['paycheck_remaining']):,.2f} {selected_currency}",
        help="Paycheck minus actual grouped spending and investment principal.",
    )
    context_cols[1].metric(
        "Total Income",
        f"{float(selected_budget['total_income']):,.2f} {selected_currency}",
        help="Actual income received in this calendar month, using the Spending table logic.",
    )
    context_cols[2].metric(
        "Spending Money Left",
        f"{float(selected_budget['spending_money_left']):,.2f} {selected_currency}",
        help="Total income minus total expenses from the Spending table logic.",
    )

    progress_col, chart_col = st.columns((1.1, 1))
    with progress_col:
        st.markdown("#### Limit Usage")
        for row in selected_detail.itertuples(index=False):
            limit_amount = float(row.limit_amount)
            actual_amount = float(row.actual_amount)
            usage_ratio = actual_amount / limit_amount if limit_amount > 0 else 0.0
            usage_percent = usage_ratio * 100.0
            difference = float(row.difference)
            status = (
                f"over by {-difference:,.2f} {row.currency}"
                if difference < 0
                else f"left {difference:,.2f} {row.currency}"
            )
            st.progress(
                min(max(usage_ratio, 0.0), 1.0),
                text=(
                    f"{row.budget_bucket}: {actual_amount:,.2f} / "
                    f"{limit_amount:,.2f} {row.currency} "
                    f"({usage_percent:.1f}%, {status})"
                ),
            )

    with chart_col:
        allocation_rows = selected_detail.loc[
            selected_detail["actual_amount"].gt(0),
            ["budget_bucket", "actual_amount"],
        ].rename(columns={"budget_bucket": "bucket", "actual_amount": "amount"})
        remaining_amount = max(0.0, float(selected_budget["paycheck_remaining"]))
        if remaining_amount > 0:
            allocation_rows = pd.concat(
                [
                    allocation_rows,
                    pd.DataFrame(
                        {
                            "bucket": ["Remaining Paycheck"],
                            "amount": [remaining_amount],
                        }
                    ),
                ],
                ignore_index=True,
            )
        st.plotly_chart(
            paycheck_allocation_chart(allocation_rows),
            width="stretch",
            key="paycheck_allocation_chart",
        )

    detail_table = selected_detail.rename(
        columns={
            "budget_bucket": "Budget Bucket",
            "limit_percent": "Limit %",
            "limit_amount": "Limit Amount",
            "actual_amount": "Actual Amount",
            "usage_percent": "Usage %",
            "difference": "Limit Left",
            "status": "Status",
        }
    )
    st.markdown("#### Selected Month Limits")
    st.dataframe(
        detail_table.drop(columns=["month", "month_label", "currency"]),
        width="stretch",
        hide_index=True,
    )

    actual_pivot = budget_detail.pivot_table(
        index=["month", "month_label", "currency"],
        columns="budget_bucket",
        values="actual_amount",
        aggfunc="sum",
        fill_value=0.0,
    ).add_suffix(" Actual")
    limit_pivot = budget_detail.pivot_table(
        index=["month", "month_label", "currency"],
        columns="budget_bucket",
        values="limit_amount",
        aggfunc="sum",
        fill_value=0.0,
    ).add_suffix(" Limit")
    monthly_table = (
        monthly_budget.set_index(["month", "month_label", "currency"])
        .join(actual_pivot, how="left")
        .join(limit_pivot, how="left")
        .reset_index()
        .fillna(0.0)
        .rename(
            columns={
                "month_label": "Month",
                "currency": "Currency",
                "paycheck": "Paycheck",
                "budgeted_limits": "Budgeted Limits",
                "actual_used": "Actual Used",
                "paycheck_remaining": "Paycheck Remaining",
                "remaining_target_amount": "Remaining Target",
                "total_income": "Total Income",
                "total_expenses": "Total Expenses",
                "spending_money_left": "Spending Money Left",
            }
        )
    )

    with st.expander("All budget months", expanded=False):
        st.dataframe(
            monthly_table.drop(columns=["month", "remaining_target_percent"]),
            width="stretch",
            hide_index=True,
        )

    st.download_button(
        "Download paycheck budget detail",
        budget_detail.to_csv(index=False).encode("utf-8"),
        file_name="paycheck_budget_detail.csv",
        mime="text/csv",
        key="budget_detail_download",
    )


def _render_transactions(filtered_transactions: pd.DataFrame) -> None:
    """Render the raw transaction exploration table."""
    if filtered_transactions.empty:
        st.info("No transactions match the current filter selection.")
        return

    export_frame = filtered_transactions[
        [
            "date",
            "bank",
            "account",
            "subaccount",
            "category",
            "flow_group",
            "description",
            "amount",
            "currency",
            "notes",
            "source_file",
        ]
    ].copy()
    st.dataframe(export_frame, width="stretch", hide_index=True)
    st.download_button(
        "Download filtered transactions",
        export_frame.to_csv(index=False).encode("utf-8"),
        file_name="filtered_financial_transactions.csv",
        mime="text/csv",
    )


def main() -> None:
    """Run the Streamlit dashboard."""
    st.set_page_config(
        page_title="My Finances Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_styles()

    st.title("Interactive Financial Dashboard")
    st.caption(
        "Explore monthly balances, bank-by-bank cashflow, and category spending from the repository's normalized CSV exports."
    )
    st.info(BLOCKED_ACCOUNT_NOTE)

    output_root = _default_output_root()

    try:
        transactions, statement_balances, revolut_balances = _load_data(output_root)
    except FileNotFoundError:
        st.error(
            f"No transactions were found at {Path(output_root) / 'combined' / 'all_transactions.csv'}."
        )
        st.stop()

    filters = _render_sidebar(transactions)

    if transactions.empty:
        st.error(
            f"No transactions were found at {Path(output_root) / 'combined' / 'all_transactions.csv'}."
        )
        st.stop()

    filtered_transactions = filter_transactions(transactions, filters)
    filtered_statement_balances = filter_statement_balances(
        statement_balances,
        filters.banks,
        start_date=filters.start_date,
        end_date=filters.end_date,
        selected_currencies=filters.currencies,
    )
    report_transactions = filter_transactions(
        transactions,
        DashboardFilters(
            start_date=filters.start_date,
            end_date=filters.end_date,
            months=filters.months,
            banks=filters.banks,
            accounts=filters.accounts,
            subaccounts=filters.subaccounts,
            categories=filters.categories,
            currencies=filters.currencies,
            include_transfers=True,
            search_text=filters.search_text,
        ),
    )
    budget_start_date = (
        filters.start_date.to_period("M").to_timestamp() - pd.offsets.MonthBegin(1)
    )
    budget_transactions = filter_transactions(
        transactions,
        DashboardFilters(
            start_date=budget_start_date,
            end_date=filters.end_date,
            months=tuple(),
            banks=filters.banks,
            accounts=filters.accounts,
            subaccounts=filters.subaccounts,
            categories=filters.categories,
            currencies=filters.currencies,
            include_transfers=True,
            search_text=filters.search_text,
        ),
    )

    if filters.categories:
        active_categories = "".join(
            f'<span class="dashboard-tag">{category}</span>'
            for category in filters.categories
        )
    else:
        active_categories = '<span class="dashboard-tag">All Categories</span>'
    if filters.banks:
        active_banks = "".join(
            f'<span class="dashboard-tag">{bank}</span>' for bank in filters.banks
        )
    else:
        active_banks = '<span class="dashboard-tag">All Banks</span>'

    st.markdown(
        f"""
        <div class="dashboard-card">
            <strong>Active Scope</strong><br/>
            {active_banks}
            {active_categories}
            <span class="dashboard-tag">{len(filtered_transactions)} visible transactions</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if filtered_transactions.empty:
        st.warning(
            "No transactions found for the selected filters. "
            "Run `conda activate finances && my_finances extract_all_data` to extract data, "
            "or adjust your date range and filter selections."
        )

    overview_tab, spending_tab, reports_tab, budget_tab, transactions_tab = st.tabs(
        [
            "Overview",
            "Spending",
            "Reports",
            "Budget",
            "Transactions",
        ]
    )

    with overview_tab:
        _render_overview(
            filtered_transactions,
            filtered_statement_balances,
            report_transactions,
            transactions,
            statement_balances,
            revolut_balances,
            filters,
            output_root,
        )
    with spending_tab:
        _render_spending(transactions, filters)
    with reports_tab:
        _render_reports(report_transactions)
    with budget_tab:
        _render_budget(budget_transactions, filters)
    with transactions_tab:
        _render_transactions(filtered_transactions)


if __name__ == "__main__":
    main()
