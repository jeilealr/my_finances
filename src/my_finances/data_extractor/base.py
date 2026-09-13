"""Shared models and helpers for statement extraction workflows."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from my_finances.common.utils import write_df

ExtractorFunction = Callable[..., pd.DataFrame]
BalanceSummaryFunction = Callable[..., dict[str, object]]

TRANSACTION_OUTPUT_COLUMNS = [
    "bank",
    "account",
    "subaccount",
    "date",
    "value_date",
    "description",
    "amount",
    "currency",
    "balance",
    "notes",
    "page",
    "source_file",
]
TEXT_TRANSACTION_COLUMNS = (
    "bank",
    "account",
    "subaccount",
    "date",
    "value_date",
    "description",
    "currency",
    "notes",
    "source_file",
)
NUMERIC_TRANSACTION_COLUMNS = ("amount", "balance")
INTEGER_TRANSACTION_COLUMNS = ("page",)


@dataclass(frozen=True)
class BankConfig:
    """Configuration for one supported bank statement source."""

    bank_name: str
    file_pattern: str
    input_description: str
    extractor: ExtractorFunction
    balance_summary_extractor: Optional[BalanceSummaryFunction] = None
    default_line_tolerance: Optional[float] = None


@dataclass(frozen=True)
class BankExportResult:
    """Typed result returned by the batch extraction workflow."""

    bank: str
    files_processed: int
    rows_exported: int
    output_path: Path
    dataframe: pd.DataFrame = field(repr=False)
    statement_balance_frame: pd.DataFrame = field(repr=False)
    statement_balance_output: Path | None = None
    revolut_balance_output: Path | None = None

    def summary_row(self) -> dict[str, object]:
        """Return the serializable summary fields written to disk."""
        return {
            "bank": self.bank,
            "files_processed": self.files_processed,
            "rows_exported": self.rows_exported,
            "output_path": str(self.output_path),
        }


def normalize_transaction_frame(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Apply the shared transaction schema to a parsed statement frame."""
    normalized = dataframe.reindex(columns=TRANSACTION_OUTPUT_COLUMNS).copy()

    for column in TEXT_TRANSACTION_COLUMNS:
        normalized[column] = normalized[column].astype("string")

    for column in NUMERIC_TRANSACTION_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    for column in INTEGER_TRANSACTION_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce").astype(
            "Int64"
        )

    return normalized


def sort_transaction_frame(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Apply a stable transaction sort using the normalized schema.

    ``mergesort`` preserves the original row order for ties, which matters when a
    parser already extracted rows in statement order.
    """

    if dataframe.empty:
        return dataframe.copy()

    sortable = dataframe.copy()
    sortable["_statement_order"] = range(len(sortable))
    sortable["_date_sort"] = pd.to_datetime(
        sortable["date"],
        errors="coerce",
        format="mixed",
    )
    return (
        sortable.sort_values(
            by=["_date_sort", "source_file", "page", "_statement_order"],
            kind="mergesort",
            na_position="last",
        )
        .drop(columns=["_date_sort", "_statement_order"])
        .reset_index(drop=True)
    )


def prepare_transaction_frame(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Normalize and sort a parsed statement frame."""
    return sort_transaction_frame(normalize_transaction_frame(dataframe))


def export_statement_data(
    statement_path: str | Path,
    *,
    extractor: ExtractorFunction,
    output_path: str | Path | None = None,
    logger: logging.Logger | None = None,
    **extractor_kwargs: object,
) -> pd.DataFrame:
    """Extract one statement and persist it to CSV."""
    dataframe = extractor(statement_path, **extractor_kwargs)
    if dataframe.empty:
        if logger is not None:
            logger.info("No rows were extracted from %s.", statement_path)
        return dataframe

    prepared = prepare_transaction_frame(dataframe)
    destination = (
        Path(output_path)
        if output_path is not None
        else Path(statement_path).with_suffix(".csv")
    )
    write_df(prepared, destination, "csv")
    if logger is not None:
        logger.info("Saved %s rows to %s", len(prepared), destination)
    return prepared
