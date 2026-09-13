"""Data loading helpers for the interactive dashboard."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from my_finances.common.paths import default_output_root
from my_finances.data_extractor.base import TRANSACTION_OUTPUT_COLUMNS


@dataclass(frozen=True)
class DashboardDataPaths:
    """Resolved file locations used by the dashboard."""

    output_root: Path
    transactions_path: Path
    statement_balances_path: Path
    revolut_balances_path: Path


STATEMENT_BALANCE_COLUMNS = [
    "bank",
    "source_file",
    "statement_start_date",
    "statement_end_date",
    "opening_balance",
    "closing_balance",
    "currency",
    "summary_method",
]
EXCLUDED_DASHBOARD_BANKS = {"bancolombia"}


def build_dashboard_paths(
    output_root: Optional[str | Path] = None,
) -> DashboardDataPaths:
    """Return the standard dashboard input file paths."""
    resolved_root = Path(output_root) if output_root else default_output_root()
    return DashboardDataPaths(
        output_root=resolved_root,
        transactions_path=resolved_root / "combined" / "all_transactions.csv",
        statement_balances_path=resolved_root / "statement_balance_summary.csv",
        revolut_balances_path=resolved_root
        / "revolut"
        / "revolut_subaccount_balances.csv",
    )


def _load_optional_csv(path: Path) -> pd.DataFrame:
    """Return an empty frame when an optional dashboard input is missing."""
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _empty_statement_balance_frame() -> pd.DataFrame:
    """Return an empty frame with the standard balance-history schema."""
    return pd.DataFrame(columns=STATEMENT_BALANCE_COLUMNS)


def _exclude_dashboard_banks(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Remove banks that should stay out of dashboard calculations."""
    if dataframe.empty or "bank" not in dataframe.columns:
        return dataframe.copy()

    bank_names = dataframe["bank"].fillna("").astype(str).str.lower()
    return dataframe.loc[~bank_names.isin(EXCLUDED_DASHBOARD_BANKS)].copy()


def _empty_transaction_frame() -> pd.DataFrame:
    """Return an empty DataFrame with the full transaction schema and correct dtypes."""
    dataframe = pd.DataFrame(columns=TRANSACTION_OUTPUT_COLUMNS)
    for col in ("date", "value_date"):
        dataframe[col] = dataframe[col].astype("datetime64[ns]")
    for col in ("amount", "balance"):
        dataframe[col] = dataframe[col].astype("float64")
    return dataframe


def load_transactions(path: str | Path) -> pd.DataFrame:
    """Load the normalized transaction export used by the dashboard."""
    if not Path(path).exists():
        return _empty_transaction_frame()
    dataframe = pd.read_csv(path)
    if dataframe.empty:
        return dataframe

    dataframe["date"] = pd.to_datetime(dataframe["date"], errors="coerce")
    dataframe["value_date"] = pd.to_datetime(dataframe["value_date"], errors="coerce")
    dataframe["amount"] = pd.to_numeric(dataframe["amount"], errors="coerce")
    dataframe["balance"] = pd.to_numeric(dataframe["balance"], errors="coerce")
    dataframe["page"] = pd.to_numeric(dataframe["page"], errors="coerce").astype(
        "Int64"
    )

    for column in [
        "bank",
        "account",
        "subaccount",
        "description",
        "currency",
        "notes",
        "source_file",
    ]:
        dataframe[column] = dataframe[column].fillna("").astype(str)

    return dataframe


def load_statement_balances(path: str | Path) -> pd.DataFrame:
    """Load statement opening and closing balance data."""
    dataframe = _load_optional_csv(Path(path))
    if dataframe.empty:
        return _empty_statement_balance_frame()

    dataframe["statement_start_date"] = pd.to_datetime(
        dataframe["statement_start_date"],
        errors="coerce",
    )
    dataframe["statement_end_date"] = pd.to_datetime(
        dataframe["statement_end_date"],
        errors="coerce",
    )
    dataframe["opening_balance"] = pd.to_numeric(
        dataframe["opening_balance"],
        errors="coerce",
    )
    dataframe["closing_balance"] = pd.to_numeric(
        dataframe["closing_balance"],
        errors="coerce",
    )
    return dataframe


def load_revolut_balances(path: str | Path) -> pd.DataFrame:
    """Load the derived Revolut balance summary."""
    dataframe = _load_optional_csv(Path(path))
    if dataframe.empty:
        return dataframe

    dataframe["opening_balance"] = pd.to_numeric(
        dataframe["opening_balance"],
        errors="coerce",
    )
    dataframe["closing_balance"] = pd.to_numeric(
        dataframe["closing_balance"],
        errors="coerce",
    )
    dataframe["transactions_count"] = pd.to_numeric(
        dataframe["transactions_count"],
        errors="coerce",
    ).astype("Int64")
    return dataframe


def _parse_revolut_statement_dates(
    source_file: str,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Extract the statement start and end dates from a Revolut source filename."""
    match = re.search(
        r"account-statement_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})", source_file
    )
    if not match:
        return pd.NaT, pd.NaT
    return pd.Timestamp(match.group(1)), pd.Timestamp(match.group(2))


def build_revolut_statement_history(revolut_balances: pd.DataFrame) -> pd.DataFrame:
    """Aggregate Revolut subaccount balances into statement-level bank balances."""
    if revolut_balances.empty:
        return _empty_statement_balance_frame()

    grouped = (
        revolut_balances.groupby(["source_file", "currency"], dropna=False)
        .agg(
            opening_balance=("opening_balance", "sum"),
            closing_balance=("closing_balance", "sum"),
        )
        .reset_index()
    )
    statement_dates = grouped["source_file"].apply(_parse_revolut_statement_dates)
    grouped["statement_start_date"] = statement_dates.str[0]
    grouped["statement_end_date"] = statement_dates.str[1]
    grouped["bank"] = "revolut"
    grouped["summary_method"] = "aggregated_subaccount_balances"
    return grouped.loc[:, STATEMENT_BALANCE_COLUMNS]


def build_inferred_monthly_balance_history(
    transactions: pd.DataFrame,
    *,
    bank_name: str,
) -> pd.DataFrame:
    """Infer month-end balances from cumulative transaction flow when needed."""
    bank_transactions = transactions.loc[transactions["bank"].eq(bank_name)].copy()
    if bank_transactions.empty:
        return _empty_statement_balance_frame()

    bank_transactions["month"] = (
        bank_transactions["date"].dt.to_period("M").dt.to_timestamp()
    )
    monthly = (
        bank_transactions.groupby(["month", "currency"], dropna=False)
        .agg(net_amount=("amount", "sum"))
        .reset_index()
        .sort_values(["currency", "month"])
    )
    if monthly.empty:
        return _empty_statement_balance_frame()

    monthly["closing_balance"] = monthly.groupby("currency")["net_amount"].cumsum()
    monthly["opening_balance"] = (
        monthly.groupby("currency")["closing_balance"].shift(1).fillna(0.0)
    )
    monthly["bank"] = bank_name
    monthly["statement_start_date"] = monthly["month"]
    monthly["statement_end_date"] = monthly["month"] + pd.offsets.MonthEnd(0)
    monthly["source_file"] = monthly["month"].dt.strftime(f"inferred_{bank_name}_%Y-%m")
    monthly["summary_method"] = "inferred_visible_transactions"
    return monthly.loc[:, STATEMENT_BALANCE_COLUMNS]


def build_balance_history(
    transactions: pd.DataFrame,
    statement_balances: pd.DataFrame,
    revolut_balances: pd.DataFrame,
) -> pd.DataFrame:
    """Return the full balance history used by the dashboard."""
    frames = [statement_balances]

    revolut_history = build_revolut_statement_history(revolut_balances)
    if not revolut_history.empty:
        frames.append(revolut_history)

    if (
        "payback"
        not in statement_balances.get("bank", pd.Series(dtype=str)).astype(str).tolist()
    ):
        payback_history = build_inferred_monthly_balance_history(
            transactions,
            bank_name="payback",
        )
        if not payback_history.empty:
            frames.append(payback_history)

    balance_history = pd.concat(frames, ignore_index=True)
    if balance_history.empty:
        return _empty_statement_balance_frame()

    return (
        balance_history.drop_duplicates(
            subset=["bank", "source_file", "statement_end_date", "currency"],
            keep="last",
        )
        .sort_values(["currency", "bank", "statement_end_date"])
        .reset_index(drop=True)
    )


def load_dashboard_datasets(
    output_root: Optional[str | Path] = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all datasets required by the dashboard."""
    paths = build_dashboard_paths(output_root)
    transactions = _exclude_dashboard_banks(load_transactions(paths.transactions_path))
    statement_balances = _exclude_dashboard_banks(
        load_statement_balances(paths.statement_balances_path)
    )
    revolut_balances = load_revolut_balances(paths.revolut_balances_path)
    return (
        transactions,
        build_balance_history(transactions, statement_balances, revolut_balances),
        revolut_balances,
    )
