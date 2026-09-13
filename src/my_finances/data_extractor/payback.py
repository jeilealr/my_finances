"""Extractor for Payback CSV exports."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from my_finances.common.utils import normalize_whitespace, parse_amount
from my_finances.data_extractor.base import export_statement_data

logger = logging.getLogger(__name__)

PAYBACK_COLUMNS = {
    "Datum": "date",
    "Beschreibung": "description",
    "Betrag": "raw_amount",
}


def _normalize_payback_amount(value: object) -> float:
    """Invert Payback signs so debt is negative and repayments are positive."""
    return -parse_amount(str(value))


def extract_payback_statement(statement_path: str | Path) -> pd.DataFrame:
    """Extract one Payback CSV export into the shared output schema."""
    csv_path = Path(statement_path)
    raw_frame = pd.read_csv(csv_path, encoding="utf-8-sig")

    missing_columns = set(PAYBACK_COLUMNS) - set(raw_frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Payback CSV is missing required columns: {missing}")

    dataframe = raw_frame.rename(columns=PAYBACK_COLUMNS).copy()
    dataframe["date"] = pd.to_datetime(
        dataframe["date"], format="%d/%m/%Y"
    ).dt.strftime("%Y-%m-%d")
    dataframe["description"] = dataframe["description"].map(
        lambda value: normalize_whitespace(str(value))
    )
    dataframe["amount"] = dataframe["raw_amount"].map(_normalize_payback_amount)

    return pd.DataFrame(
        {
            "bank": "payback",
            "account": "payback_card",
            "subaccount": None,
            "date": dataframe["date"],
            "value_date": None,
            "description": dataframe["description"],
            "amount": dataframe["amount"],
            "currency": "EUR",
            "balance": None,
            "notes": None,
            "page": None,
            "source_file": csv_path.name,
        }
    )


def extract_payback_data(
    input_csv: str | Path,
    output_path: Optional[str | Path] = None,
) -> None:
    """Extract one Payback CSV export and write it to CSV."""
    export_statement_data(
        statement_path=input_csv,
        extractor=extract_payback_statement,
        output_path=output_path,
        logger=logger,
    )
