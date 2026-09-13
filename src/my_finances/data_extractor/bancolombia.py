"""Extractor for Bancolombia account statements."""

from __future__ import annotations

import datetime as dt
import logging
import re
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from my_finances.common.utils import (
    assign_year,
    cluster_values,
    normalize_whitespace,
    parse_amount,
    read_pdfs,
    vertical_center,
)
from my_finances.data_extractor.base import export_statement_data

logger = logging.getLogger(__name__)

DATE_DAY_MONTH_RE = re.compile(r"^(\d{1,2})/(\d{1,2})$")
PERIOD_RE = re.compile(
    r"DESDE:\s*(\d{4})/(\d{2})/(\d{2})\s+HASTA:\s*(\d{4})/(\d{2})/(\d{2})",
    re.IGNORECASE,
)
AMOUNT_RE = re.compile(r"^[+\-−\u2212]?(?:\d{1,3}(?:,\d{3})*|\d+)?\.\d{2}$")
OPENING_BALANCE_RE = re.compile(
    r"SALDO ANTERIOR\s+\$\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)
CLOSING_BALANCE_RE = re.compile(
    r"SALDO ACTUAL\s+\$\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)


def _extract_period(text: str) -> tuple[Optional[dt.date], Optional[dt.date]]:
    """Return the statement date range from the first page text."""
    match = PERIOD_RE.search(text or "")
    if not match:
        return None, None

    year_start, month_start, day_start, year_end, month_end, day_end = map(
        int, match.groups()
    )
    try:
        return (
            dt.date(year_start, month_start, day_start),
            dt.date(year_end, month_end, day_end),
        )
    except ValueError:
        return None, None


def _find_table_header_y(words: list[dict[str, Any]]) -> float:
    """Return the y-position of the FECHA table header."""
    for word in words:
        if word.get("text", "").upper() == "FECHA":
            return vertical_center(word)
    return 0.0


def _parse_row(
    row_words: list[dict[str, Any]],
    period_start: Optional[dt.date],
    period_end: Optional[dt.date],
) -> Optional[tuple[str, str, float]]:
    """Parse a Bancolombia transaction row."""
    sorted_words = sorted(row_words, key=lambda item: float(item["x0"]))

    date_word = next(
        (
            word
            for word in sorted_words
            if DATE_DAY_MONTH_RE.match(word.get("text", ""))
        ),
        None,
    )
    if date_word is None:
        return None

    amount_words = [
        word for word in sorted_words if AMOUNT_RE.match(word.get("text", ""))
    ]
    if len(amount_words) < 2:
        return None

    amount_word = sorted(amount_words, key=lambda item: float(item["x0"]))[-2]
    day, month = map(int, DATE_DAY_MONTH_RE.match(date_word["text"]).groups())  # type: ignore[union-attr]

    if period_start and period_end:
        statement_date = assign_year(day, month, period_start, period_end).isoformat()
    else:
        statement_date = date_word["text"]

    date_limit = float(date_word["x1"])
    amount_limit = float(amount_word["x0"])
    description_words = [
        word
        for word in sorted_words
        if float(word["x0"]) > date_limit + 1 and float(word["x1"]) < amount_limit - 1
    ]
    description = normalize_whitespace(
        " ".join(word["text"] for word in description_words)
    )
    if not description:
        return None

    return statement_date, description, parse_amount(amount_word["text"])


def extract_bancolombia_statement(
    statement_path: str | Path,
    line_tolerance: float = 2.6,
) -> pd.DataFrame:
    """Extract one Bancolombia statement into the shared output schema."""
    pdf_path = Path(statement_path)
    rows: list[dict[str, Any]] = []
    sequence = 0

    with read_pdfs(pdf_path) as pdfs:
        pdf = pdfs[0]
        period_start, period_end = _extract_period(pdf.pages[0].extract_text() or "")

        for page_number, page in enumerate(pdf.pages, start=1):
            words = (
                page.extract_words(use_text_flow=False, keep_blank_chars=False) or []
            )
            if not words:
                continue

            header_y = _find_table_header_y(words)
            min_data_y = header_y + (2.0 * line_tolerance)
            date_words = [
                word
                for word in words
                if DATE_DAY_MONTH_RE.match(word.get("text", ""))
                and vertical_center(word) >= min_data_y
            ]
            if not date_words:
                continue

            for row_y in sorted(
                cluster_values(
                    [vertical_center(word) for word in date_words],
                    line_tolerance,
                )
            ):
                row_words = [
                    word
                    for word in words
                    if abs(vertical_center(word) - row_y) <= line_tolerance
                ]
                parsed_row = _parse_row(row_words, period_start, period_end)
                if parsed_row is None:
                    continue

                statement_date, description, amount = parsed_row
                rows.append(
                    {
                        "bank": "bancolombia",
                        "account": "cuenta_ahorros",
                        "subaccount": None,
                        "date": statement_date,
                        "value_date": None,
                        "description": description,
                        "amount": amount,
                        "currency": "COP",
                        "balance": None,
                        "notes": None,
                        "page": page_number,
                        "source_file": pdf_path.name,
                        "_row_y": row_y,
                        "_sequence": sequence,
                    }
                )
                sequence += 1

    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        return dataframe

    dataframe = dataframe.sort_values(
        ["page", "_row_y", "_sequence"],
        kind="mergesort",
    ).reset_index(drop=True)
    return dataframe.drop(columns=["_row_y", "_sequence"])


def extract_bancolombia_statement_balances(
    statement_path: str | Path,
) -> dict[str, object]:
    """Extract opening and closing balances from one Bancolombia statement."""
    pdf_path = Path(statement_path)

    with read_pdfs(pdf_path) as pdfs:
        first_page_text = pdfs[0].pages[0].extract_text() or ""

    period_start, period_end = _extract_period(first_page_text)
    opening_match = OPENING_BALANCE_RE.search(first_page_text)
    closing_match = CLOSING_BALANCE_RE.search(first_page_text)

    return {
        "bank": "bancolombia",
        "source_file": pdf_path.name,
        "statement_start_date": (
            period_start.isoformat() if period_start is not None else None
        ),
        "statement_end_date": period_end.isoformat()
        if period_end is not None
        else None,
        "opening_balance": (
            parse_amount(opening_match.group(1)) if opening_match is not None else None
        ),
        "closing_balance": (
            parse_amount(closing_match.group(1)) if closing_match is not None else None
        ),
        "currency": "COP",
        "summary_method": "pdf_header",
    }


def extract_bancolombia_data(
    input_pdf: str | Path,
    line_tolerance: float = 2.6,
    output_path: Optional[str | Path] = None,
) -> None:
    """Extract one Bancolombia statement and write it to CSV."""
    export_statement_data(
        statement_path=input_pdf,
        extractor=extract_bancolombia_statement,
        output_path=output_path,
        logger=logger,
        line_tolerance=line_tolerance,
    )
