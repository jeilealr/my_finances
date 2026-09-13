"""Business logic for the interactive dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from dashboard.data_loader import _parse_revolut_statement_dates
from dashboard.investments import (
    INVESTMENT_ORDER_FEE,
    build_etf_holdings,
    calculate_klarna_accrued_interest,
    value_etf_holdings,
)

MOVEMENT_CATEGORIES = (
    "Blocked Account",
    "Card Repayment",
    "Colombia Transfer",
    "Investments",
    "Savings",
)
PAYBACK_BANK_NAME = "payback"
REVOLUT_BANK_NAME = "revolut"
SANTANDER_BANK_NAME = "santander"
SPENDING_INCOME_BANKS = (SANTANDER_BANK_NAME, REVOLUT_BANK_NAME)
INVESTMENT_FEE_CATEGORY = "Investment Fees"
REPORT_EXPENSE_GROUPS = {
    "ATM Withdrawal": "Housing & Utilities",
    "Bank Fees": "Housing & Utilities",
    "Electricity": "Housing & Utilities",
    "Phone & Internet": "Housing & Utilities",
    "Pharmacy": "Housing & Utilities",
    "Rent": "Housing & Utilities",
    "Transport": "Housing & Utilities",
    "Utilities": "Housing & Utilities",
    "Grocery Shopping": "Grocery",
    "Restaurants & Delivery": "Grocery",
    "Dance": "Entertainment",
    "Entertainment": "Entertainment",
    "Fitness": "Entertainment",
    "Travel": "Travel & Holidays",
    "Retail & Online Shopping": "Retail & Online Shopping",
    "Other": "Other",
}
REPORT_EXCLUDED_MOVEMENT_CATEGORIES = (
    "Blocked Account",
    "Card Repayment",
    "Colombia Transfer",
    "Internal Transfer",
    "Investments",
    "Savings",
)
BUDGET_ITEM_ORDER = (
    "Rent",
    "Investment",
    "Deutschland Ticket",
    "Electricity",
    "Fitness",
    "Baileo",
    "Phone & Internet",
    "Rundfunk",
)
ACTUAL_ONLY_BUDGET_ITEMS = {"Rundfunk"}
PAYCHECK_BUDGET_LIMITS = {
    "Housing & Utilities": 0.32,
    "Grocery": 0.20,
    "Other Spending Groups": 0.10,
    "Investment": 0.18,
}
# Fixed EUR limits override the percentage-based limit for specific buckets.
PAYCHECK_BUDGET_FIXED_EUR: dict[str, float] = {
    "Grocery": 400.0,
}
PAYCHECK_BUDGET_BUCKETS = tuple(PAYCHECK_BUDGET_LIMITS)
OTHER_SPENDING_REPORT_GROUPS = (
    "Entertainment",
    "Travel & Holidays",
    "Retail & Online Shopping",
    "Other",
)


@dataclass(frozen=True)
class DashboardFilters:
    """Interactive dashboard filters selected by the user."""

    start_date: pd.Timestamp
    end_date: pd.Timestamp
    months: tuple[str, ...]
    banks: tuple[str, ...]
    accounts: tuple[str, ...]
    subaccounts: tuple[str, ...]
    categories: tuple[str, ...]
    currencies: tuple[str, ...]
    include_transfers: bool
    search_text: str = ""


def available_months(transactions: pd.DataFrame) -> list[str]:
    """Return sorted available month labels."""
    if transactions.empty:
        return []
    return sorted(transactions["month_label"].dropna().unique().tolist())


def filter_transactions(
    transactions: pd.DataFrame,
    filters: DashboardFilters,
) -> pd.DataFrame:
    """Apply interactive dashboard filters to the transaction data."""
    if transactions.empty:
        return transactions.copy()

    filtered = transactions.copy()
    filtered = filtered.loc[
        filtered["date"].between(filters.start_date, filters.end_date, inclusive="both")
    ]

    if filters.months:
        filtered = filtered.loc[filtered["month_label"].isin(filters.months)]
    if filters.banks:
        filtered = filtered.loc[filtered["bank"].isin(filters.banks)]
    if filters.accounts:
        filtered = filtered.loc[filtered["account"].isin(filters.accounts)]
    if filters.subaccounts:
        filtered = filtered.loc[filtered["subaccount"].isin(filters.subaccounts)]
    if filters.categories:
        filtered = filtered.loc[filtered["category"].isin(filters.categories)]
    if filters.currencies:
        filtered = filtered.loc[filtered["currency"].isin(filters.currencies)]
    if not filters.include_transfers:
        filtered = filtered.loc[~filtered["flow_group"].eq("Transfer")]
    if filters.search_text:
        search_mask = filtered["description"].str.contains(
            filters.search_text, case=False, na=False
        ) | filtered["notes"].str.contains(filters.search_text, case=False, na=False)
        filtered = filtered.loc[search_mask]

    return filtered.reset_index(drop=True)


def build_monthly_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    """Aggregate transactions into monthly income, expense, and net totals."""
    if transactions.empty:
        return pd.DataFrame(
            columns=[
                "month",
                "month_label",
                "currency",
                "income",
                "expenses",
                "net",
                "transactions",
                "savings_rate",
            ]
        )

    summary = (
        transactions.groupby(["month", "month_label", "currency"], dropna=False)
        .agg(
            income=("income_amount", "sum"),
            expenses=("expense_amount", "sum"),
            net=("amount", "sum"),
            transactions=("description", "size"),
        )
        .reset_index()
        .sort_values(["currency", "month"])
    )
    summary["savings_rate"] = summary.apply(
        lambda row: (((row["income"] - row["expenses"]) / row["income"]) * 100.0)
        if row["income"] > 0
        else None,
        axis=1,
    )
    return summary


def build_extra_transaction_rows(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return transfer-style rows that should be shown as extra context."""
    columns = [
        "date",
        "month",
        "month_label",
        "bank",
        "account",
        "subaccount",
        "category",
        "description",
        "amount",
        "extra_amount",
        "currency",
        "source_file",
    ]
    if transactions.empty:
        return pd.DataFrame(columns=columns)

    extra_rows = transactions.loc[
        transactions["category"].isin(MOVEMENT_CATEGORIES)
    ].copy()
    if extra_rows.empty:
        return pd.DataFrame(columns=columns)

    savings_mask = extra_rows["category"].eq("Savings")
    extra_rows = extra_rows.loc[
        ~savings_mask | _is_savings_account_row(extra_rows)
    ].copy()
    if extra_rows.empty:
        return pd.DataFrame(columns=columns)

    extra_rows["extra_amount"] = extra_rows["amount"].abs()
    extra_rows = extra_rows.loc[extra_rows["extra_amount"].gt(0)].copy()
    card_rows = extra_rows.loc[extra_rows["category"].eq("Card Repayment")].copy()
    if not card_rows.empty:
        canonical_card_rows = card_rows.loc[
            card_rows["bank"].eq(PAYBACK_BANK_NAME) & card_rows["amount"].gt(0)
        ].copy()
        canonical_keys = set(
            zip(
                canonical_card_rows["month"],
                canonical_card_rows["currency"],
                strict=False,
            )
        )
        fallback_card_rows = card_rows.loc[
            ~card_rows.apply(
                lambda row: (row["month"], row["currency"]) in canonical_keys,
                axis=1,
            )
        ].copy()
        extra_rows = pd.concat(
            [
                extra_rows.loc[~extra_rows["category"].eq("Card Repayment")],
                canonical_card_rows,
                fallback_card_rows,
            ],
            ignore_index=True,
        )
    return extra_rows.loc[:, columns].sort_values(["currency", "date", "category"])


def _format_extra_transaction_detail(row: pd.Series) -> str:
    """Return a concise hover line for one extra transaction."""
    date_label = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
    amount = float(row["amount"])
    description = str(row["description"])
    if len(description) > 58:
        description = f"{description[:55]}..."
    return (
        f"{date_label} | {row['bank']} | {row['category']} | "
        f"{amount:,.2f} {row['currency']} | {description}"
    )


def build_monthly_extra_transaction_summary(
    transactions: pd.DataFrame,
) -> pd.DataFrame:
    """Return monthly extra transaction totals with hover detail text."""
    columns = [
        "month",
        "month_label",
        "currency",
        "extra_amount",
        "transactions",
        "detail_text",
    ]
    extra_rows = build_extra_transaction_rows(transactions)
    if extra_rows.empty:
        return pd.DataFrame(columns=columns)

    extra_rows["detail_line"] = extra_rows.apply(
        _format_extra_transaction_detail,
        axis=1,
    )
    return (
        extra_rows.groupby(["month", "month_label", "currency"], dropna=False)
        .agg(
            extra_amount=("extra_amount", "sum"),
            transactions=("category", "size"),
            detail_text=("detail_line", lambda values: "<br>".join(values)),
        )
        .reset_index()
        .sort_values(["currency", "month"])
    )


def build_monthly_movement_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    """Aggregate extra financial movements that are not expenses.

    These amounts are useful context for the monthly charts, but they should not
    inflate expense totals. Savings uses only the savings-account side of the
    Revolut transfer so the same movement is not counted twice.
    """
    columns = [
        "month",
        "month_label",
        "currency",
        "category",
        "movement_amount",
        "transactions",
    ]
    movement_rows = build_extra_transaction_rows(transactions)
    if movement_rows.empty:
        return pd.DataFrame(columns=columns)

    return (
        movement_rows.groupby(
            ["month", "month_label", "currency", "category"],
            dropna=False,
        )
        .agg(
            movement_amount=("extra_amount", "sum"),
            transactions=("category", "size"),
        )
        .reset_index()
        .sort_values(["currency", "month", "category"])
    )


def build_payback_debt_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return monthly Payback purchases, credits, and known outstanding debt.

    Payback is a credit-card account in this repo. Negative Payback rows are
    itemized purchases; positive Payback rows are credits such as repayments or
    refunds. Debt is clipped after every month so repayments from before the
    loaded history do not offset future purchases incorrectly.
    """
    columns = [
        "month",
        "month_label",
        "currency",
        "purchases",
        "repayments",
        "outstanding_debt",
        "purchase_transactions",
        "repayment_transactions",
    ]
    payback_rows = transactions.loc[transactions["bank"].eq(PAYBACK_BANK_NAME)].copy()
    if payback_rows.empty:
        return pd.DataFrame(columns=columns)

    payback_rows["purchases"] = payback_rows["amount"].where(
        payback_rows["amount"].lt(0),
        0.0,
    ).abs()
    payback_rows["repayments"] = payback_rows["amount"].where(
        payback_rows["amount"].gt(0),
        0.0,
    )
    payback_rows["purchase_transactions"] = payback_rows["purchases"].gt(0).astype(int)
    payback_rows["repayment_transactions"] = (
        payback_rows["repayments"].gt(0).astype(int)
    )
    monthly = (
        payback_rows.groupby(["month", "month_label", "currency"], dropna=False)
        .agg(
            purchases=("purchases", "sum"),
            repayments=("repayments", "sum"),
            purchase_transactions=("purchase_transactions", "sum"),
            repayment_transactions=("repayment_transactions", "sum"),
        )
        .reset_index()
        .sort_values(["currency", "month"])
    )
    debt_frames = []
    for _, group in monthly.groupby("currency", dropna=False):
        group = group.copy()
        running_debt = 0.0
        outstanding_debt: list[float] = []
        for row in group.itertuples(index=False):
            running_debt = max(
                0.0,
                running_debt + float(row.purchases) - float(row.repayments),
            )
            outstanding_debt.append(running_debt)
        group["outstanding_debt"] = outstanding_debt
        debt_frames.append(group)
    monthly = pd.concat(debt_frames, ignore_index=True)
    return monthly.loc[:, columns]


def _month_starts_between(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DatetimeIndex:
    """Return calendar month starts covering the selected analysis period."""
    start_month = pd.Timestamp(start_date).to_period("M").to_timestamp()
    end_month = pd.Timestamp(end_date).to_period("M").to_timestamp()
    return pd.date_range(start_month, end_month, freq="MS")


def _normalized_budget_text(transactions: pd.DataFrame) -> pd.Series:
    """Return normalized text used for recurring budget item matching."""
    description = transactions["description"].fillna("").astype(str)
    notes = transactions["notes"].fillna("").astype(str)
    return (description + " " + notes).str.upper()


def _budget_item_mask(transactions: pd.DataFrame, item: str) -> pd.Series:
    """Return rows that belong to one recurring budget item."""
    text = _normalized_budget_text(transactions)
    is_outflow = transactions["amount"].lt(0)
    if item == "Rent":
        return is_outflow & transactions["category"].eq("Rent")
    if item == "Investment":
        return is_outflow & transactions["category"].eq("Investments")
    if item == "Deutschland Ticket":
        return (
            is_outflow
            & transactions["category"].eq("Transport")
            & text.str.contains(
                r"DB VERTRIEB|DEUTSCHLANDTICKET|BAHN\.DE/ABOPORTAL|ABO\s+279",
                regex=True,
                na=False,
            )
        )
    if item == "Electricity":
        return is_outflow & transactions["category"].eq("Electricity")
    if item == "Fitness":
        return is_outflow & transactions["category"].eq("Fitness")
    if item == "Baileo":
        return (
            is_outflow
            & transactions["category"].eq("Dance")
            & text.str.contains(r"BAILEO", regex=True, na=False)
        )
    if item == "Phone & Internet":
        return (
            is_outflow
            & transactions["category"].eq("Phone & Internet")
            & ~text.str.contains(r"RUNDFUNK", regex=True, na=False)
        )
    if item == "Rundfunk":
        return (
            is_outflow
            & transactions["category"].eq("Phone & Internet")
            & text.str.contains(r"RUNDFUNK", regex=True, na=False)
        )
    return pd.Series(False, index=transactions.index)


def _budget_item_transaction_rows(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return transaction rows matched to recurring budget items."""
    columns = [
        "month",
        "month_label",
        "currency",
        "budget_item",
        "actual_amount",
        "transaction_count",
        "last_transaction_date",
    ]
    if transactions.empty:
        return pd.DataFrame(columns=columns)

    item_frames = []
    for item in BUDGET_ITEM_ORDER:
        item_rows = transactions.loc[_budget_item_mask(transactions, item)].copy()
        if item_rows.empty:
            continue
        item_rows["budget_item"] = item
        item_rows["actual_amount"] = item_rows["amount"].abs()
        item_frames.append(item_rows)

    if not item_frames:
        return pd.DataFrame(columns=columns)

    budget_rows = pd.concat(item_frames, ignore_index=True)
    return (
        budget_rows.groupby(
            ["month", "month_label", "currency", "budget_item"],
            dropna=False,
        )
        .agg(
            actual_amount=("actual_amount", "sum"),
            transaction_count=("budget_item", "size"),
            last_transaction_date=("date", "max"),
        )
        .reset_index()
        .sort_values(["currency", "month", "budget_item"])
    )


def _budget_status(
    *,
    item: str,
    actual_amount: float,
    expected_amount: float,
    budgeted_amount: float,
) -> str:
    """Return a user-facing status for one budget item/month."""
    if item in ACTUAL_ONLY_BUDGET_ITEMS:
        return "Recorded" if actual_amount > 0 else "Not due / not seen"
    if actual_amount <= 0 and expected_amount <= 0:
        return "No history"
    if actual_amount <= 0 and budgeted_amount > 0:
        return "Planned"
    if actual_amount < budgeted_amount:
        return "Partial / planned"
    return "Paid"


def _salary_rows_by_budget_month(
    transactions: pd.DataFrame,
    *,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Return salary rows assigned to the month they are intended to fund."""
    columns = ["month", "month_label", "currency", "salary"]
    salary_rows = transactions.loc[
        _is_monthly_paycheck_row(transactions)
    ].copy()
    if salary_rows.empty:
        return pd.DataFrame(columns=columns)

    salary_rows["month"] = (
        salary_rows["date"].dt.to_period("M") + 1
    ).dt.to_timestamp()
    salary_rows["month_label"] = salary_rows["month"].dt.strftime("%Y-%m")
    start_month = pd.Timestamp(start_date).to_period("M").to_timestamp()
    end_month = pd.Timestamp(end_date).to_period("M").to_timestamp()
    salary_rows = salary_rows.loc[
        salary_rows["month"].between(start_month, end_month, inclusive="both")
    ]
    if salary_rows.empty:
        return pd.DataFrame(columns=columns)

    return (
        salary_rows.groupby(["month", "month_label", "currency"], dropna=False)
        .agg(salary=("amount", "sum"))
        .reset_index()
    )


def _is_monthly_paycheck_row(transactions: pd.DataFrame) -> pd.Series:
    """Return recurring UFZ/Helmholtz paycheck rows, excluding reimbursements."""
    if transactions.empty:
        return pd.Series(False, index=transactions.index)
    text = _normalized_budget_text(transactions)
    return (
        transactions["bank"].eq(SANTANDER_BANK_NAME)
        & transactions["category"].eq("Salary")
        & transactions["amount"].gt(0)
        & text.str.contains(r"HELMHOLTZ-ZENTRUM", regex=True, na=False)
        & text.str.contains(r"LOHN/GEHALT", regex=True, na=False)
    )


def _monthly_investment_principal(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return monthly Santander ETF principal, excluding embedded order fees."""
    columns = ["month", "month_label", "currency", "investment_actual"]
    investment_rows = transactions.loc[
        transactions["category"].eq("Investments") & transactions["amount"].lt(0)
    ].copy()
    if investment_rows.empty:
        return pd.DataFrame(columns=columns)

    investment_rows["investment_actual"] = (
        investment_rows["amount"].abs() - INVESTMENT_ORDER_FEE
    ).clip(lower=0.0)
    return (
        investment_rows.groupby(["month", "month_label", "currency"], dropna=False)
        .agg(investment_actual=("investment_actual", "sum"))
        .reset_index()
        .loc[:, columns]
        .sort_values(["currency", "month"])
    )


def _monthly_spending_context(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return actual income/expense context using Spending-tab definitions."""
    columns = [
        "month",
        "month_label",
        "currency",
        "total_income",
        "total_expenses",
        "spending_money_left",
    ]
    if transactions.empty:
        return pd.DataFrame(columns=columns)

    group_columns = ["month", "month_label", "currency"]
    income_rows = transactions.loc[
        transactions["bank"].isin(SPENDING_INCOME_BANKS)
        & transactions["flow_group"].eq("Income")
        & transactions["amount"].gt(0)
    ].copy()
    if income_rows.empty:
        income_totals = pd.DataFrame(columns=[*group_columns, "total_income"])
    else:
        income_totals = (
            income_rows.groupby(group_columns, dropna=False)
            .agg(total_income=("income_amount", "sum"))
            .reset_index()
        )

    expense_rows = build_spending_transactions(transactions)
    if expense_rows.empty:
        expense_totals = pd.DataFrame(columns=[*group_columns, "total_expenses"])
    else:
        expense_totals = (
            expense_rows.groupby(group_columns, dropna=False)
            .agg(total_expenses=("expense_amount", "sum"))
            .reset_index()
        )

    month_keys = pd.concat(
        [
            income_totals.loc[:, group_columns],
            expense_totals.loc[:, group_columns],
        ],
        ignore_index=True,
    ).drop_duplicates()
    if month_keys.empty:
        return pd.DataFrame(columns=columns)

    context = (
        month_keys.merge(income_totals, on=group_columns, how="left")
        .merge(expense_totals, on=group_columns, how="left")
        .fillna({"total_income": 0.0, "total_expenses": 0.0})
    )
    context["spending_money_left"] = (
        context["total_income"] - context["total_expenses"]
    )
    return context.loc[:, columns].sort_values(["currency", "month"])


def build_paycheck_budget_report(
    transactions: pd.DataFrame,
    *,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return paycheck-based budget summary and bucket detail tables."""
    monthly_columns = [
        "month",
        "month_label",
        "currency",
        "paycheck",
        "budgeted_limits",
        "actual_used",
        "paycheck_remaining",
        "remaining_target_percent",
        "remaining_target_amount",
        "total_income",
        "total_expenses",
        "spending_money_left",
    ]
    detail_columns = [
        "month",
        "month_label",
        "currency",
        "budget_bucket",
        "limit_percent",
        "limit_amount",
        "actual_amount",
        "usage_percent",
        "difference",
        "status",
    ]
    if transactions.empty:
        return (
            pd.DataFrame(columns=monthly_columns),
            pd.DataFrame(columns=detail_columns),
        )

    start_date = pd.Timestamp(start_date).normalize()
    end_date = pd.Timestamp(end_date).normalize()
    scoped_transactions = transactions.loc[
        transactions["date"].between(start_date, end_date, inclusive="both")
    ].copy()
    paycheck_totals = _salary_rows_by_budget_month(
        transactions,
        start_date=start_date,
        end_date=end_date,
    ).rename(columns={"salary": "paycheck"})
    grouped_report = build_grouped_monthly_expense_report(scoped_transactions)
    investment_principal = _monthly_investment_principal(scoped_transactions)
    spending_context = _monthly_spending_context(scoped_transactions)

    currencies = sorted(
        set(scoped_transactions["currency"].dropna().unique().tolist())
        | set(paycheck_totals["currency"].dropna().unique().tolist())
        | set(spending_context["currency"].dropna().unique().tolist())
    )
    if not currencies:
        return (
            pd.DataFrame(columns=monthly_columns),
            pd.DataFrame(columns=detail_columns),
        )

    month_grid = pd.DataFrame(
        [
            {
                "month": pd.Timestamp(month),
                "month_label": pd.Timestamp(month).strftime("%Y-%m"),
                "currency": currency,
            }
            for currency in currencies
            for month in _month_starts_between(start_date, end_date)
        ]
    )
    group_columns = ["month", "month_label", "currency"]

    if grouped_report.empty:
        report_actuals = pd.DataFrame(columns=[*group_columns, "budget_bucket", "actual_amount"])
    else:
        direct_groups = grouped_report.loc[
            grouped_report["report_group"].isin(("Housing & Utilities", "Grocery"))
        ].copy()
        direct_groups["budget_bucket"] = direct_groups["report_group"]
        other_groups = grouped_report.loc[
            grouped_report["report_group"].isin(OTHER_SPENDING_REPORT_GROUPS)
        ].copy()
        if other_groups.empty:
            other_actuals = pd.DataFrame(
                columns=[*group_columns, "budget_bucket", "actual_amount"]
            )
        else:
            other_actuals = (
                other_groups.groupby(group_columns, dropna=False)
                .agg(actual_amount=("expenses", "sum"))
                .reset_index()
            )
            other_actuals["budget_bucket"] = "Other Spending Groups"
        report_actuals = pd.concat(
            [
                direct_groups.rename(columns={"expenses": "actual_amount"}).loc[
                    :, [*group_columns, "budget_bucket", "actual_amount"]
                ],
                other_actuals.loc[
                    :, [*group_columns, "budget_bucket", "actual_amount"]
                ],
            ],
            ignore_index=True,
        )

    if investment_principal.empty:
        investment_actuals = pd.DataFrame(
            columns=[*group_columns, "budget_bucket", "actual_amount"]
        )
    else:
        investment_actuals = investment_principal.rename(
            columns={"investment_actual": "actual_amount"}
        )
        investment_actuals["budget_bucket"] = "Investment"
        investment_actuals = investment_actuals.loc[
            :, [*group_columns, "budget_bucket", "actual_amount"]
        ]

    bucket_actuals = pd.concat(
        [report_actuals, investment_actuals],
        ignore_index=True,
    )
    if bucket_actuals.empty:
        bucket_actuals = pd.DataFrame(
            columns=[*group_columns, "budget_bucket", "actual_amount"]
        )

    monthly_base = (
        month_grid.merge(paycheck_totals, on=group_columns, how="left")
        .merge(spending_context, on=group_columns, how="left")
        .fillna(
            {
                "paycheck": 0.0,
                "total_income": 0.0,
                "total_expenses": 0.0,
                "spending_money_left": 0.0,
            }
        )
    )

    detail_rows: list[dict[str, object]] = []
    for month_row in monthly_base.itertuples(index=False):
        paycheck = float(month_row.paycheck)
        for bucket, limit_percent in PAYCHECK_BUDGET_LIMITS.items():
            actual_rows = bucket_actuals.loc[
                bucket_actuals["month"].eq(month_row.month)
                & bucket_actuals["currency"].eq(month_row.currency)
                & bucket_actuals["budget_bucket"].eq(bucket)
            ]
            actual_amount = (
                float(actual_rows["actual_amount"].sum())
                if not actual_rows.empty
                else 0.0
            )
            limit_amount = PAYCHECK_BUDGET_FIXED_EUR.get(bucket, paycheck * limit_percent)
            usage_percent = (
                (actual_amount / limit_amount) * 100.0 if limit_amount > 0 else 0.0
            )
            difference = limit_amount - actual_amount
            if paycheck <= 0:
                status = "No Paycheck"
            elif difference < 0:
                status = "Over Limit"
            else:
                status = "Within Limit"
            detail_rows.append(
                {
                    "month": month_row.month,
                    "month_label": month_row.month_label,
                    "currency": month_row.currency,
                    "budget_bucket": bucket,
                    "limit_percent": limit_percent,
                    "limit_amount": limit_amount,
                    "actual_amount": actual_amount,
                    "usage_percent": usage_percent,
                    "difference": difference,
                    "status": status,
                }
            )

    detail = pd.DataFrame(detail_rows, columns=detail_columns)
    detail_totals = (
        detail.groupby(group_columns, dropna=False)
        .agg(
            budgeted_limits=("limit_amount", "sum"),
            actual_used=("actual_amount", "sum"),
        )
        .reset_index()
    )
    monthly = monthly_base.merge(detail_totals, on=group_columns, how="left").fillna(
        {"budgeted_limits": 0.0, "actual_used": 0.0}
    )
    remaining_target_percent = max(0.0, 1.0 - sum(PAYCHECK_BUDGET_LIMITS.values()))
    monthly["paycheck_remaining"] = monthly["paycheck"] - monthly["actual_used"]
    monthly["remaining_target_percent"] = remaining_target_percent
    monthly["remaining_target_amount"] = (
        monthly["paycheck"] * monthly["remaining_target_percent"]
    )
    return (
        monthly.loc[:, monthly_columns].sort_values(["currency", "month"]),
        detail.loc[:, detail_columns].sort_values(
            ["currency", "month", "budget_bucket"]
        ),
    )


def build_fixed_budget_report(
    transactions: pd.DataFrame,
    *,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return monthly budget summary and fixed-item detail tables.

    Fixed commitments use a hybrid model: actual payments are used when a full
    month is available, while the latest observed recurring amount is carried
    forward when a later month is missing or incomplete.
    """
    monthly_columns = [
        "month",
        "month_label",
        "currency",
        "salary",
        "fixed_commitments",
        "actual_fixed_paid",
        "money_left",
        "actual_money_left",
        "fixed_items_tracked",
    ]
    detail_columns = [
        "month",
        "month_label",
        "currency",
        "budget_item",
        "expected_amount",
        "actual_amount",
        "budgeted_amount",
        "difference",
        "status",
        "transaction_count",
        "last_transaction_date",
    ]
    if transactions.empty:
        return (
            pd.DataFrame(columns=monthly_columns),
            pd.DataFrame(columns=detail_columns),
        )

    start_date = pd.Timestamp(start_date).normalize()
    end_date = pd.Timestamp(end_date).normalize()
    month_starts = _month_starts_between(start_date, end_date)
    scoped_transactions = transactions.loc[
        transactions["date"].between(start_date, end_date, inclusive="both")
    ].copy()
    if scoped_transactions.empty:
        return (
            pd.DataFrame(columns=monthly_columns),
            pd.DataFrame(columns=detail_columns),
        )

    data_max_date = scoped_transactions["date"].max().normalize()
    item_actuals = _budget_item_transaction_rows(scoped_transactions)
    salary_monthly = _salary_rows_by_budget_month(
        transactions,
        start_date=start_date,
        end_date=end_date,
    )
    currencies = sorted(
        set(scoped_transactions["currency"].dropna().unique().tolist())
        | set(salary_monthly["currency"].dropna().unique().tolist())
    )

    detail_rows: list[dict[str, object]] = []
    for currency in currencies:
        for item in BUDGET_ITEM_ORDER:
            last_expected: float | None = None
            item_rows = scoped_transactions.loc[
                scoped_transactions["currency"].eq(currency)
                & _budget_item_mask(scoped_transactions, item)
            ]
            item_data_max_date = (
                item_rows["date"].max().normalize()
                if not item_rows.empty
                else data_max_date
            )
            item_data_cutoff = min(data_max_date, item_data_max_date)
            for month in month_starts:
                month = pd.Timestamp(month)
                month_label = month.strftime("%Y-%m")
                month_end = month + pd.offsets.MonthEnd(0)
                is_incomplete_month = (
                    month_end > item_data_cutoff or pd.Timestamp(end_date) < month_end
                )
                actual_match = item_actuals.loc[
                    item_actuals["currency"].eq(currency)
                    & item_actuals["budget_item"].eq(item)
                    & item_actuals["month"].eq(month)
                ]
                if actual_match.empty:
                    actual_amount = 0.0
                    transaction_count = 0
                    last_transaction_date = pd.NaT
                else:
                    actual = actual_match.iloc[0]
                    actual_amount = float(actual["actual_amount"])
                    transaction_count = int(actual["transaction_count"])
                    last_transaction_date = actual["last_transaction_date"]

                if item in ACTUAL_ONLY_BUDGET_ITEMS:
                    expected_amount = actual_amount
                    budgeted_amount = actual_amount
                else:
                    if actual_amount > 0 and not is_incomplete_month:
                        last_expected = actual_amount
                    elif actual_amount > 0 and last_expected is None:
                        last_expected = actual_amount
                    expected_amount = float(last_expected or 0.0)
                    if actual_amount > 0 and not is_incomplete_month:
                        budgeted_amount = actual_amount
                    else:
                        budgeted_amount = max(actual_amount, expected_amount)

                detail_rows.append(
                    {
                        "month": month,
                        "month_label": month_label,
                        "currency": currency,
                        "budget_item": item,
                        "expected_amount": expected_amount,
                        "actual_amount": actual_amount,
                        "budgeted_amount": budgeted_amount,
                        "difference": expected_amount - actual_amount,
                        "status": _budget_status(
                            item=item,
                            actual_amount=actual_amount,
                            expected_amount=expected_amount,
                            budgeted_amount=budgeted_amount,
                        ),
                        "transaction_count": transaction_count,
                        "last_transaction_date": last_transaction_date,
                    }
                )

    detail = pd.DataFrame(detail_rows, columns=detail_columns)
    commitment_summary = (
        detail.groupby(["month", "month_label", "currency"], dropna=False)
        .agg(
            fixed_commitments=("budgeted_amount", "sum"),
            actual_fixed_paid=("actual_amount", "sum"),
            fixed_items_tracked=(
                "budgeted_amount",
                lambda values: int((values > 0).sum()),
            ),
        )
        .reset_index()
    )
    month_grid = pd.DataFrame(
        [
            {
                "month": pd.Timestamp(month),
                "month_label": pd.Timestamp(month).strftime("%Y-%m"),
                "currency": currency,
            }
            for currency in currencies
            for month in month_starts
        ]
    )
    monthly = (
        month_grid.merge(
            salary_monthly,
            on=["month", "month_label", "currency"],
            how="left",
        )
        .merge(
            commitment_summary,
            on=["month", "month_label", "currency"],
            how="left",
        )
        .fillna(
            {
                "salary": 0.0,
                "fixed_commitments": 0.0,
                "actual_fixed_paid": 0.0,
                "fixed_items_tracked": 0,
            }
        )
    )
    monthly["money_left"] = monthly["salary"] - monthly["fixed_commitments"]
    monthly["actual_money_left"] = monthly["salary"] - monthly["actual_fixed_paid"]
    monthly["fixed_items_tracked"] = monthly["fixed_items_tracked"].astype(int)
    return (
        monthly.loc[:, monthly_columns].sort_values(["currency", "month"]),
        detail.loc[:, detail_columns].sort_values(
            ["currency", "month", "budget_item"]
        ),
    )


def _latest_payback_debt(
    payback_debt: pd.DataFrame,
    as_of_date: pd.Timestamp,
    currency: str,
) -> float:
    """Return the latest known Payback debt as of one month."""
    if payback_debt.empty:
        return 0.0

    month = pd.Timestamp(as_of_date).to_period("M").to_timestamp()
    debt_rows = payback_debt.loc[
        payback_debt["currency"].eq(currency) & payback_debt["month"].le(month)
    ]
    if debt_rows.empty:
        return 0.0
    return float(debt_rows.sort_values("month").iloc[-1]["outstanding_debt"])


def _payback_debt_as_of(
    transactions: pd.DataFrame,
    *,
    as_of_date: pd.Timestamp,
    currency: str,
) -> float:
    """Return Payback debt using only transactions known by the snapshot date."""
    debt_summary = build_payback_debt_summary(
        transactions.loc[transactions["date"].le(as_of_date)].copy()
    )
    return _latest_payback_debt(debt_summary, as_of_date, currency)


def _cumulative_principal(
    transactions: pd.DataFrame,
    *,
    category: str,
    as_of_date: pd.Timestamp,
    currency: str,
) -> float:
    """Return cumulative principal moved into an asset-style category."""
    rows = transactions.loc[
        transactions["category"].eq(category)
        & transactions["currency"].eq(currency)
        & transactions["date"].le(as_of_date)
    ]
    if rows.empty:
        return 0.0
    principal = float((-rows["amount"]).sum())
    if category == "Investments":
        principal -= INVESTMENT_ORDER_FEE * len(rows)
    return max(0.0, principal)


def _investment_fee_rows(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return synthetic expense rows for embedded Santander ETF order fees."""
    if transactions.empty:
        return transactions.copy()

    investment_rows = transactions.loc[
        transactions["category"].eq("Investments") & transactions["amount"].lt(0)
    ].copy()
    if investment_rows.empty:
        return investment_rows

    investment_rows["category"] = INVESTMENT_FEE_CATEGORY
    investment_rows["flow_group"] = "Expense"
    investment_rows["amount"] = -INVESTMENT_ORDER_FEE
    investment_rows["expense_amount"] = INVESTMENT_ORDER_FEE
    investment_rows["income_amount"] = 0.0
    investment_rows["description"] = (
        "Investment order fee extracted from Santander ETF purchase"
    )
    if "notes" not in investment_rows.columns:
        investment_rows["notes"] = ""
    investment_rows["notes"] = investment_rows["notes"].fillna("").astype(str)
    return investment_rows


def build_spending_transactions(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return real expense rows plus synthetic investment-fee expenses."""
    if transactions.empty:
        return transactions.copy()

    expense_rows = transactions.loc[transactions["flow_group"].eq("Expense")].copy()
    fee_rows = _investment_fee_rows(transactions)
    if fee_rows.empty:
        return expense_rows.reset_index(drop=True)
    return pd.concat([expense_rows, fee_rows], ignore_index=True)


def _estimate_santander_cash(
    transactions: pd.DataFrame,
    statement_balances: pd.DataFrame,
    *,
    as_of_date: pd.Timestamp,
    currency: str,
) -> float:
    """Estimate Santander cash from statement balance anchors and later flows."""
    santander_balances = statement_balances.loc[
        statement_balances["bank"].eq(SANTANDER_BANK_NAME)
        & statement_balances["currency"].eq(currency)
    ].copy()
    santander_transactions = transactions.loc[
        transactions["bank"].eq(SANTANDER_BANK_NAME)
        & transactions["currency"].eq(currency)
    ]
    if santander_balances.empty:
        return float(
            santander_transactions.loc[
                santander_transactions["date"].le(as_of_date), "amount"
            ].sum()
        )

    previous_balances = santander_balances.loc[
        santander_balances["statement_end_date"].le(as_of_date)
    ].sort_values("statement_end_date")
    if not previous_balances.empty:
        anchor = previous_balances.iloc[-1]
        anchor_date = pd.Timestamp(anchor["statement_end_date"])
        later_flows = santander_transactions.loc[
            santander_transactions["date"].gt(anchor_date)
            & santander_transactions["date"].le(as_of_date),
            "amount",
        ].sum()
        return float(anchor["closing_balance"] + later_flows)

    first_balance = santander_balances.sort_values("statement_start_date").iloc[0]
    anchor_date = pd.Timestamp(first_balance["statement_start_date"])
    later_flows = santander_transactions.loc[
        santander_transactions["date"].ge(anchor_date)
        & santander_transactions["date"].le(as_of_date),
        "amount",
    ].sum()
    return float(first_balance["opening_balance"] + later_flows)


def _is_revolut_savings_balance(row: pd.Series) -> bool:
    """Return whether one Revolut balance row belongs to savings."""
    return (
        str(row.get("subaccount", "")).lower() == "instant access savings"
        or str(row.get("account", "")).lower() == "deposit"
    )


def _estimate_revolut_components(
    transactions: pd.DataFrame,
    revolut_balances: pd.DataFrame,
    *,
    as_of_date: pd.Timestamp,
    currency: str,
) -> tuple[float, float]:
    """Estimate Revolut non-savings cash and savings balances."""
    if revolut_balances.empty:
        return 0.0, 0.0

    balances = revolut_balances.loc[revolut_balances["currency"].eq(currency)].copy()
    if balances.empty:
        return 0.0, 0.0

    statement_dates = balances["source_file"].apply(_parse_revolut_statement_dates)
    balances["statement_start_date"] = statement_dates.str[0]
    balances["statement_end_date"] = statement_dates.str[1]
    revolut_transactions = transactions.loc[
        transactions["bank"].eq(REVOLUT_BANK_NAME)
        & transactions["currency"].eq(currency)
    ]

    non_savings_cash = 0.0
    savings_cash = 0.0
    active_rows = balances.loc[
        balances["statement_start_date"].le(as_of_date)
        & balances["statement_end_date"].ge(as_of_date)
    ].copy()
    if active_rows.empty:
        previous_rows = balances.loc[
            balances["statement_end_date"].le(as_of_date)
        ].copy()
        if previous_rows.empty:
            return 0.0, 0.0
        latest_end_date = previous_rows["statement_end_date"].max()
        scoped_balances = previous_rows.loc[
            previous_rows["statement_end_date"].eq(latest_end_date)
        ].copy()
    else:
        scoped_balances = active_rows

    pocket_rows = scoped_balances.loc[scoped_balances["account"].eq("pockets")]
    if not pocket_rows.empty:
        pocket_transactions = revolut_transactions.loc[
            revolut_transactions["account"].eq("pockets")
            & revolut_transactions["source_file"].isin(pocket_rows["source_file"])
            & revolut_transactions["date"].le(as_of_date)
        ].copy()
        if pocket_transactions["balance"].notna().any():
            pocket_transactions = pocket_transactions.sort_values(
                "date",
                kind="stable",
            )
            non_savings_cash += float(
                pocket_transactions.loc[
                    pocket_transactions["balance"].notna(),
                    "balance",
                ].iloc[-1]
            )
        elif active_rows.empty:
            non_savings_cash += float(pocket_rows["closing_balance"].sum())
        else:
            non_savings_cash += float(pocket_rows["opening_balance"].sum())

    for _, balance_group in scoped_balances.loc[
        ~scoped_balances["account"].eq("pockets")
    ].groupby(["account", "subaccount"], dropna=False):
        selected_row = balance_group.sort_values("statement_start_date").iloc[-1]

        row_dict = selected_row.to_dict()
        start_date = row_dict["statement_start_date"]
        end_date = row_dict["statement_end_date"]
        if pd.isna(start_date) or pd.isna(end_date):
            continue

        if start_date <= as_of_date <= end_date:
            matching_transactions = revolut_transactions.loc[
                revolut_transactions["source_file"].eq(row_dict["source_file"])
                & revolut_transactions["account"].eq(row_dict["account"])
                & revolut_transactions["subaccount"].eq(row_dict["subaccount"])
                & revolut_transactions["date"].ge(start_date)
                & revolut_transactions["date"].le(as_of_date)
            ]
            balance = float(
                row_dict["opening_balance"] + matching_transactions["amount"].sum()
            )
        elif end_date <= as_of_date:
            balance = float(row_dict["closing_balance"])
        else:
            balance = 0.0

        if _is_revolut_savings_balance(pd.Series(row_dict)):
            savings_cash += balance
        else:
            non_savings_cash += balance

    return non_savings_cash, savings_cash


def build_net_worth_snapshots(
    transactions: pd.DataFrame,
    statement_balances: pd.DataFrame,
    revolut_balances: pd.DataFrame,
    *,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    market_prices: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return month-end net-worth snapshots for the overview.

    Total Net Worth is limited to account balances, blocked principal, and
    Payback debt. Tracked Wealth adds ETF market value and Klarna accrued
    interest so assets without monthly statements are visible without inflating
    spending calculations.
    """
    columns = [
        "month",
        "month_label",
        "currency",
        "santander_cash",
        "revolut_cash",
        "available_cash",
        "revolut_savings",
        "investments",
        "investment_cost_basis",
        "investment_market_value",
        "investment_gain_loss",
        "blocked_account",
        "blocked_interest_accrued",
        "payback_debt",
        "total_net_worth",
        "tracked_wealth",
    ]
    if transactions.empty:
        return pd.DataFrame(columns=columns)

    price_data = market_prices if market_prices is not None else pd.DataFrame()
    currencies = sorted(transactions["currency"].dropna().unique().tolist())
    rows: list[dict[str, object]] = []
    for month in _month_starts_between(start_date, end_date):
        as_of_date = min(month + pd.offsets.MonthEnd(0), pd.Timestamp(end_date))
        month_label = month.strftime("%Y-%m")
        for currency in currencies:
            santander_cash = _estimate_santander_cash(
                transactions,
                statement_balances,
                as_of_date=as_of_date,
                currency=currency,
            )
            revolut_cash, revolut_savings = _estimate_revolut_components(
                transactions,
                revolut_balances,
                as_of_date=as_of_date,
                currency=currency,
            )
            holdings = build_etf_holdings(
                transactions,
                as_of_date=as_of_date,
                currency=currency,
            )
            valuation = value_etf_holdings(
                holdings,
                price_data,
                as_of_date=as_of_date,
            )
            investment_cost_basis = (
                float(valuation["cost_basis"].sum()) if not valuation.empty else 0.0
            )
            investment_market_value = (
                float(valuation["market_value"].sum()) if not valuation.empty else 0.0
            )
            investment_gain_loss = (
                float(valuation["gain_loss"].sum()) if not valuation.empty else 0.0
            )
            blocked_account = _cumulative_principal(
                transactions,
                category="Blocked Account",
                as_of_date=as_of_date,
                currency=currency,
            )
            blocked_interest = (
                calculate_klarna_accrued_interest(as_of_date)
                if currency == "EUR" and blocked_account > 0
                else 0.0
            )
            payback_debt_amount = _payback_debt_as_of(
                transactions,
                as_of_date=as_of_date,
                currency=currency,
            )
            available_cash = santander_cash + revolut_cash
            total_net_worth = (
                available_cash
                + revolut_savings
                + blocked_account
                - payback_debt_amount
            )
            tracked_wealth = (
                total_net_worth + investment_market_value + blocked_interest
            )
            rows.append(
                {
                    "month": month,
                    "month_label": month_label,
                    "currency": currency,
                    "santander_cash": santander_cash,
                    "revolut_cash": revolut_cash,
                    "available_cash": available_cash,
                    "revolut_savings": revolut_savings,
                    "investments": investment_cost_basis,
                    "investment_cost_basis": investment_cost_basis,
                    "investment_market_value": investment_market_value,
                    "investment_gain_loss": investment_gain_loss,
                    "blocked_account": blocked_account,
                    "blocked_interest_accrued": blocked_interest,
                    "payback_debt": payback_debt_amount,
                    "total_net_worth": total_net_worth,
                    "tracked_wealth": tracked_wealth,
                }
            )

    return pd.DataFrame(rows, columns=columns).sort_values(["currency", "month"])


def build_category_summary(
    transactions: pd.DataFrame,
    *,
    limit: int = 12,
) -> pd.DataFrame:
    """Return the top expense categories for the current filters."""
    expense_transactions = build_spending_transactions(transactions)
    if expense_transactions.empty:
        return pd.DataFrame(
            columns=["currency", "category", "expenses", "transactions"]
        )

    summary = (
        expense_transactions.groupby(["currency", "category"], dropna=False)
        .agg(
            expenses=("expense_amount", "sum"),
            transactions=("category", "size"),
        )
        .reset_index()
        .sort_values(["currency", "expenses"], ascending=[True, False])
    )
    return (
        summary.groupby("currency", group_keys=False).head(limit).reset_index(drop=True)
    )


def build_monthly_spending_totals(
    expense_transactions: pd.DataFrame,
    income_scope_transactions: pd.DataFrame,
) -> pd.DataFrame:
    """Return monthly spending table totals with actual received income.

    The expense input may be narrowed by the Spending tab's category focus.
    Income is calculated from the broader filtered transaction scope so it can
    be compared with focused expenses without being reduced by that focus.
    """
    columns = [
        "month",
        "month_label",
        "currency",
        "income",
        "expenses",
        "money_left",
        "transactions",
    ]
    if expense_transactions.empty:
        return pd.DataFrame(columns=columns)

    group_columns = ["month", "month_label", "currency"]
    expense_totals = (
        expense_transactions.groupby(group_columns, dropna=False)
        .agg(
            expenses=("expense_amount", "sum"),
            transactions=("category", "size"),
        )
        .reset_index()
    )

    income_rows = income_scope_transactions.loc[
        income_scope_transactions["bank"].isin(SPENDING_INCOME_BANKS)
        & income_scope_transactions["flow_group"].eq("Income")
        & income_scope_transactions["amount"].gt(0)
    ].copy()
    if income_rows.empty:
        expense_totals["income"] = 0.0
    else:
        income_totals = (
            income_rows.groupby(group_columns, dropna=False)
            .agg(income=("income_amount", "sum"))
            .reset_index()
        )
        expense_totals = expense_totals.merge(
            income_totals,
            on=group_columns,
            how="left",
        ).fillna({"income": 0.0})

    expense_totals["money_left"] = (
        expense_totals["income"] - expense_totals["expenses"]
    )
    return expense_totals.loc[:, columns].sort_values(["currency", "month"])


def _is_savings_account_row(transactions: pd.DataFrame) -> pd.Series:
    """Return rows that represent the savings account side of a transfer."""
    subaccount = transactions["subaccount"].fillna("").astype(str)
    account = transactions["account"].fillna("").astype(str)
    return subaccount.str.contains(
        "Instant Access Savings",
        case=False,
        na=False,
    ) | account.eq("deposit")


def build_monthly_report(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return a month/category report with separate savings movement columns.

    Income and expenses are based on the derived flow columns, so transfers do not
    inflate spending. Savings movement is calculated only from the savings-account
    side of principal transfers to avoid counting both sides of the same move.
    """
    columns = [
        "month",
        "month_label",
        "currency",
        "category",
        "category_expenses",
        "category_transactions",
        "income",
        "expenses",
        "money_left",
        "savings_transfer_in",
        "savings_transfer_out",
        "net_savings_movement",
    ]
    if transactions.empty:
        return pd.DataFrame(columns=columns)

    group_columns = ["month", "month_label", "currency"]
    monthly_income = (
        transactions.groupby(group_columns, dropna=False)
        .agg(income=("income_amount", "sum"))
        .reset_index()
    )
    expense_rows = build_spending_transactions(transactions)
    if expense_rows.empty:
        monthly_expenses = monthly_income[group_columns].copy()
        monthly_expenses["expenses"] = 0.0
    else:
        monthly_expenses = (
            expense_rows.groupby(group_columns, dropna=False)
            .agg(expenses=("expense_amount", "sum"))
            .reset_index()
        )
    monthly_totals = monthly_income.merge(
        monthly_expenses,
        on=group_columns,
        how="left",
    ).fillna({"expenses": 0.0})
    monthly_totals["money_left"] = monthly_totals["income"] - monthly_totals["expenses"]

    savings_rows = transactions.loc[
        transactions["category"].eq("Savings") & _is_savings_account_row(transactions)
    ].copy()
    if savings_rows.empty:
        savings_totals = monthly_totals[group_columns].copy()
        savings_totals["savings_transfer_in"] = 0.0
        savings_totals["savings_transfer_out"] = 0.0
    else:
        savings_rows["savings_transfer_in"] = savings_rows["amount"].where(
            savings_rows["amount"].gt(0),
            0.0,
        )
        savings_rows["savings_transfer_out"] = (
            savings_rows["amount"]
            .where(
                savings_rows["amount"].lt(0),
                0.0,
            )
            .abs()
        )
        savings_totals = (
            savings_rows.groupby(group_columns, dropna=False)
            .agg(
                savings_transfer_in=("savings_transfer_in", "sum"),
                savings_transfer_out=("savings_transfer_out", "sum"),
            )
            .reset_index()
        )

    monthly_totals = monthly_totals.merge(
        savings_totals,
        on=group_columns,
        how="left",
    ).fillna({"savings_transfer_in": 0.0, "savings_transfer_out": 0.0})
    monthly_totals["net_savings_movement"] = (
        monthly_totals["savings_transfer_in"] - monthly_totals["savings_transfer_out"]
    )

    if expense_rows.empty:
        category_totals = monthly_totals[group_columns].copy()
        category_totals["category"] = "No Expenses"
        category_totals["category_expenses"] = 0.0
        category_totals["category_transactions"] = 0
    else:
        category_totals = (
            expense_rows.groupby([*group_columns, "category"], dropna=False)
            .agg(
                category_expenses=("expense_amount", "sum"),
                category_transactions=("category", "size"),
            )
            .reset_index()
        )

    report = category_totals.merge(
        monthly_totals,
        on=group_columns,
        how="left",
    )
    return (
        report.loc[:, columns]
        .sort_values(
            ["currency", "month", "category"],
        )
        .reset_index(drop=True)
    )


def _report_group_for_expense(row: pd.Series) -> str:
    """Return the high-level Reports expense group for one expense row."""
    subaccount = str(row.get("subaccount", ""))
    if (
        str(row.get("bank", "")).lower() == REVOLUT_BANK_NAME
        and "holiday" in subaccount.lower()
    ):
        return "Travel & Holidays"
    return REPORT_EXPENSE_GROUPS.get(str(row.get("category", "")), "Other")


def build_grouped_monthly_expense_report(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return monthly expense totals grouped for the Reports tab."""
    columns = [
        "month",
        "month_label",
        "currency",
        "report_group",
        "expenses",
        "transactions",
    ]
    expense_rows = build_spending_transactions(transactions)
    if expense_rows.empty:
        return pd.DataFrame(columns=columns)

    grouped_rows = expense_rows.copy()
    grouped_rows["report_group"] = grouped_rows.apply(
        _report_group_for_expense,
        axis=1,
    )
    return (
        grouped_rows.groupby(
            ["month", "month_label", "currency", "report_group"],
            dropna=False,
        )
        .agg(
            expenses=("expense_amount", "sum"),
            transactions=("description", "size"),
        )
        .reset_index()
        .loc[:, columns]
        .sort_values(["currency", "month", "expenses"], ascending=[True, True, False])
        .reset_index(drop=True)
    )


def build_selected_month_expense_groups(
    grouped_report: pd.DataFrame,
    *,
    month_label: str,
) -> pd.DataFrame:
    """Return pie-ready grouped expenses for one selected month."""
    columns = ["month", "month_label", "currency", "report_group", "expenses"]
    if grouped_report.empty:
        return pd.DataFrame(columns=columns)

    month_rows = grouped_report.loc[grouped_report["month_label"].eq(month_label)].copy()
    if month_rows.empty:
        return pd.DataFrame(columns=columns)
    return month_rows.loc[:, columns].sort_values(
        ["currency", "expenses"],
        ascending=[True, False],
    )


def build_grouped_expense_detail(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return transaction-level expense detail with report groups attached."""
    columns = [
        "date",
        "month_label",
        "bank",
        "account",
        "subaccount",
        "category",
        "report_group",
        "description",
        "amount",
        "expense_amount",
        "currency",
        "notes",
        "source_file",
    ]
    expense_rows = build_spending_transactions(transactions)
    if expense_rows.empty:
        return pd.DataFrame(columns=columns)

    detail = expense_rows.copy()
    detail["report_group"] = detail.apply(_report_group_for_expense, axis=1)
    return detail.loc[:, columns].sort_values(
        ["date", "report_group", "expense_amount"],
        ascending=[False, True, False],
    )


def build_report_group_component_summary(
    expense_detail: pd.DataFrame,
    *,
    report_group: str,
) -> pd.DataFrame:
    """Return monthly category components for one Reports expense group."""
    columns = [
        "month",
        "month_label",
        "currency",
        "report_group",
        "category",
        "expenses",
        "transactions",
    ]
    if expense_detail.empty:
        return pd.DataFrame(columns=columns)

    group_detail = expense_detail.loc[
        expense_detail["report_group"].eq(report_group)
    ].copy()
    if group_detail.empty:
        return pd.DataFrame(columns=columns)

    group_detail["month"] = pd.to_datetime(group_detail["date"]).dt.to_period(
        "M"
    ).dt.to_timestamp()
    return (
        group_detail.groupby(
            ["month", "month_label", "currency", "report_group", "category"],
            dropna=False,
        )
        .agg(
            expenses=("expense_amount", "sum"),
            transactions=("description", "size"),
        )
        .reset_index()
        .loc[:, columns]
        .sort_values(["currency", "month", "expenses"], ascending=[True, True, False])
        .reset_index(drop=True)
    )


def build_report_excluded_movement_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return transfer-style monthly totals shown outside the Reports pie."""
    columns = [
        "month",
        "month_label",
        "currency",
        "category",
        "amount",
        "transactions",
    ]
    if transactions.empty:
        return pd.DataFrame(columns=columns)

    movement_rows = build_extra_transaction_rows(transactions)
    if movement_rows.empty:
        return pd.DataFrame(columns=columns)

    movement_rows = movement_rows.loc[
        movement_rows["category"].isin(REPORT_EXCLUDED_MOVEMENT_CATEGORIES)
    ].copy()
    if movement_rows.empty:
        return pd.DataFrame(columns=columns)

    return (
        movement_rows.groupby(["month", "month_label", "currency", "category"])
        .agg(amount=("extra_amount", "sum"), transactions=("category", "size"))
        .reset_index()
        .loc[:, columns]
        .sort_values(["currency", "month", "category"])
        .reset_index(drop=True)
    )


def build_account_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return aggregated results for each bank/account/subaccount."""
    if transactions.empty:
        return pd.DataFrame(
            columns=[
                "bank",
                "account",
                "subaccount",
                "currency",
                "income",
                "expenses",
                "net",
                "transactions",
            ]
        )

    return (
        transactions.groupby(
            ["bank", "account", "subaccount", "currency"],
            dropna=False,
        )
        .agg(
            income=("income_amount", "sum"),
            expenses=("expense_amount", "sum"),
            net=("amount", "sum"),
            transactions=("description", "size"),
        )
        .reset_index()
        .sort_values(["currency", "net"], ascending=[True, False])
    )


def build_top_expense_table(
    transactions: pd.DataFrame,
    *,
    limit: int = 15,
) -> pd.DataFrame:
    """Return the largest expense transactions in the current selection."""
    if transactions.empty:
        return transactions.copy()

    expense_transactions = build_spending_transactions(transactions)
    if expense_transactions.empty:
        return expense_transactions

    expense_transactions["expense_rank"] = expense_transactions["expense_amount"]
    columns = [
        "date",
        "bank",
        "account",
        "subaccount",
        "category",
        "description",
        "expense_amount",
        "currency",
    ]
    return (
        expense_transactions.sort_values("expense_rank", ascending=False)
        .head(limit)[columns]
        .rename(columns={"expense_amount": "amount"})
    )


def build_forecast_summary(
    transactions: pd.DataFrame,
    *,
    focus_month: pd.Timestamp,
    lookback_months: int,
) -> pd.DataFrame:
    """Estimate expected monthly expenses by category from recent history."""
    if transactions.empty:
        return pd.DataFrame(
            columns=[
                "currency",
                "category",
                "expected",
                "actual",
                "variance",
                "variance_pct",
            ]
        )

    expense_transactions = transactions.loc[transactions["flow_group"].eq("Expense")]
    if expense_transactions.empty:
        return pd.DataFrame(
            columns=[
                "currency",
                "category",
                "expected",
                "actual",
                "variance",
                "variance_pct",
            ]
        )

    monthly = (
        expense_transactions.groupby(["month", "currency", "category"], dropna=False)
        .agg(expenses=("expense_amount", "sum"))
        .reset_index()
    )

    history_months = sorted(
        monthly.loc[monthly["month"] < focus_month, "month"].unique()
    )
    recent_months = history_months[-lookback_months:]
    if not recent_months:
        return pd.DataFrame(
            columns=[
                "currency",
                "category",
                "expected",
                "actual",
                "variance",
                "variance_pct",
            ]
        )

    expected = (
        monthly.loc[monthly["month"].isin(recent_months)]
        .groupby(["currency", "category"], dropna=False)["expenses"]
        .mean()
        .rename("expected")
    )
    actual = (
        monthly.loc[monthly["month"].eq(focus_month)]
        .groupby(["currency", "category"], dropna=False)["expenses"]
        .sum()
        .rename("actual")
    )

    forecast = pd.concat([expected, actual], axis=1).fillna(0.0).reset_index()
    forecast["variance"] = forecast["actual"] - forecast["expected"]
    forecast["variance_pct"] = forecast.apply(
        lambda row: ((row["variance"] / row["expected"]) * 100.0)
        if row["expected"] > 0
        else None,
        axis=1,
    )
    return forecast.sort_values(
        ["currency", "actual", "expected"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def latest_statement_balances(statement_balances: pd.DataFrame) -> pd.DataFrame:
    """Return the latest closing balance observed for each bank."""
    if statement_balances.empty:
        return statement_balances

    return (
        statement_balances.sort_values("statement_end_date")
        .groupby("bank", dropna=False)
        .tail(1)
        .sort_values("bank")
        .reset_index(drop=True)
    )


def filter_statement_balances(
    statement_balances: pd.DataFrame,
    selected_banks: tuple[str, ...],
    *,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
    selected_currencies: tuple[str, ...] = tuple(),
) -> pd.DataFrame:
    """Apply bank filters to the statement balance summary."""
    if statement_balances.empty:
        return statement_balances.copy()

    filtered = statement_balances.copy()
    if selected_banks:
        filtered = filtered.loc[filtered["bank"].isin(selected_banks)]
    if selected_currencies:
        filtered = filtered.loc[filtered["currency"].isin(selected_currencies)]
    if start_date is not None and end_date is not None:
        filtered = filtered.loc[
            filtered["statement_end_date"].between(
                start_date,
                end_date,
                inclusive="both",
            )
        ]
    return filtered.copy()


def filter_revolut_balances(
    revolut_balances: pd.DataFrame,
    selected_subaccounts: tuple[str, ...],
) -> pd.DataFrame:
    """Apply subaccount filters to the Revolut balance summary."""
    if revolut_balances.empty:
        return revolut_balances.copy()
    if not selected_subaccounts:
        return revolut_balances.copy()
    return revolut_balances.loc[
        revolut_balances["subaccount"].isin(selected_subaccounts)
    ].copy()
