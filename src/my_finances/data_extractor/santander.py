"""Extractor for Santander Girokonto statements."""

from __future__ import annotations

import datetime as dt
import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

from my_finances.common.utils import (
    assign_year,
    normalize_whitespace,
    parse_amount,
    read_pdfs,
)
from my_finances.data_extractor.base import export_statement_data

logger = logging.getLogger(__name__)

DATE_TOKEN_RE = re.compile(r"^(\d{2})\.(\d{2})\.$")
STATEMENT_PERIOD_RE = re.compile(
    r"DIESER KONTOAUSZUG UMFASST DIE UMSÄTZE VOM\s+"
    r"(\d{2})\.(\d{2})\.(\d{4})\s+BIS\s+(\d{2})\.(\d{2})\.(\d{4})",
    re.IGNORECASE,
)
TRANSACTION_LINE_RE = re.compile(
    r"^(?P<booking>\d{2}\.\d{2}\.)\s+"
    r"(?P<value>\d{2}\.\d{2}\.)\s+"
    r"(?P<amount>(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2})\s*"
    r"(?P<sign>-)?\s+"
    r"(?P<description>.+)$"
)
BALANCE_LINE_RE = re.compile(
    r"^\d{1,3}(?:\.\d{3})*,\d{2}\s+"
    r"(?:ALTER SALDO|NEUER SALDO|ÜBERTRAG|ZWISCHENSALDO|ZWISCHENSTAND)\b",
    re.IGNORECASE,
)
OPENING_BALANCE_RE = re.compile(
    r"(\d{1,3}(?:\.\d{3})*,\d{2})\s+ALTER SALDO GEM\. KONTOAUSZUG VOM",
    re.IGNORECASE,
)
CLOSING_BALANCE_RE = re.compile(
    r"(\d{1,3}(?:\.\d{3})*,\d{2})\s+NEUER SALDO",
    re.IGNORECASE,
)
IGNORED_PREFIXES = (
    "Kontoinhaber",
    "Auszug-Nr.",
    "Buchungstag Wert Umsatz Buchungstext",
    "Ihre IBAN:",
    "Stand:",
    "Jeisson Javier Leal Rojas",
    "DIESER KONTOAUSZUG UMFASST DIE UMSÄTZE VOM",
)
IGNORED_EXACT_LINES = {"guzsuaotnoK"}
FOOTER_SECTION_PREFIXES = (
    "NOCH FREIER VERFÜGUNGSRAHMEN:",
    "BIS SALDO EUR",
    "AB SALDO EUR",
    "*DIE ZINSSÄTZE",
    "LIMITS.",
    "Wichtige Hinweise",
    "Wir bitten Sie",
    "Die Gutschrift von Schecks",
    "Dieser Kontoauszug stellt keine Steuerbescheinigung dar.",
    "Finanzdienstleistungen sind umsatzsteuerbefreit.",
    "Wir, als Finanzdienstleister,",
    "Guthaben sind als Einlagen",
)


def _extract_statement_period(text: str) -> tuple[Optional[dt.date], Optional[dt.date]]:
    """Return the statement date range from the Santander header."""
    match = STATEMENT_PERIOD_RE.search(text or "")
    if not match:
        return None, None

    start_day, start_month, start_year, end_day, end_month, end_year = map(
        int, match.groups()
    )
    return (
        dt.date(start_year, start_month, start_day),
        dt.date(end_year, end_month, end_day),
    )


def _normalize_partial_date(
    token: str,
    period_start: Optional[dt.date],
    period_end: Optional[dt.date],
) -> Optional[str]:
    """Return an ISO date from a ``dd.mm.`` token."""
    match = DATE_TOKEN_RE.match(token)
    if not match:
        return None

    day, month = map(int, match.groups())
    if period_start and period_end:
        return assign_year(day, month, period_start, period_end).isoformat()

    return f"{day:02d}.{month:02d}"


def _append_note(current_row: dict[str, object], note: str) -> None:
    """Append text to the notes field."""
    normalized_note = normalize_whitespace(note)
    if not normalized_note:
        return

    existing = current_row.get("notes")
    current_row["notes"] = (
        normalized_note if not existing else f"{existing} | {normalized_note}"
    )


def _should_ignore_line(line: str) -> bool:
    """Return True for non-transaction header lines."""
    normalized_line = normalize_whitespace(line)
    if not normalized_line:
        return True

    if normalized_line in IGNORED_EXACT_LINES:
        return True

    if normalized_line.startswith(IGNORED_PREFIXES):
        return True

    return bool(
        re.match(r"^\d{3}\s+\d+\s+\d{2}\.\d{2}\.\d{4}\s+\d+,\d{2}$", normalized_line)
    )


def _starts_footer_section(line: str) -> bool:
    """Return True when Santander moves from transactions into boilerplate."""
    return line.startswith(FOOTER_SECTION_PREFIXES)


def extract_santander_statement(
    statement_path: str | Path,
    line_tolerance: float = 2.5,
) -> pd.DataFrame:
    """Extract one Santander statement into the shared output schema."""
    del line_tolerance  # kept for CLI compatibility

    pdf_path = Path(statement_path)
    rows: list[dict[str, object]] = []
    current_row: Optional[dict[str, object]] = None

    with read_pdfs(pdf_path) as pdfs:
        pdf = pdfs[0]
        period_start, period_end = _extract_statement_period(
            pdf.pages[0].extract_text() or ""
        )

        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            for raw_line in page_text.splitlines():
                line = normalize_whitespace(raw_line)
                if _should_ignore_line(line):
                    continue

                if BALANCE_LINE_RE.match(line):
                    continue

                if _starts_footer_section(line):
                    current_row = None
                    continue

                transaction_match = TRANSACTION_LINE_RE.match(line)
                if transaction_match:
                    amount = parse_amount(transaction_match.group("amount"))
                    if transaction_match.group("sign") == "-":
                        amount = -abs(amount)

                    current_row = {
                        "bank": "santander",
                        "account": "girokonto",
                        "subaccount": None,
                        "date": _normalize_partial_date(
                            transaction_match.group("booking"),
                            period_start,
                            period_end,
                        ),
                        "value_date": _normalize_partial_date(
                            transaction_match.group("value"),
                            period_start,
                            period_end,
                        ),
                        "description": normalize_whitespace(
                            transaction_match.group("description")
                        ),
                        "amount": amount,
                        "currency": "EUR",
                        "balance": None,
                        "notes": None,
                        "page": page_number,
                        "source_file": pdf_path.name,
                    }
                    rows.append(current_row)
                    continue

                if current_row is None:
                    continue

                _append_note(current_row, line)

    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        return dataframe

    return dataframe.reset_index(drop=True)


def extract_santander_statement_balances(
    statement_path: str | Path,
) -> dict[str, object]:
    """Extract opening and closing balances from one Santander statement."""
    pdf_path = Path(statement_path)

    with read_pdfs(pdf_path) as pdfs:
        pdf = pdfs[0]
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        first_page_text = pdf.pages[0].extract_text() or ""

    period_start, period_end = _extract_statement_period(first_page_text)
    opening_match = OPENING_BALANCE_RE.search(full_text)
    closing_matches = list(CLOSING_BALANCE_RE.finditer(full_text))
    closing_match = closing_matches[-1] if closing_matches else None

    return {
        "bank": "santander",
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
        "currency": "EUR",
        "summary_method": "pdf_balance_lines",
    }


def extract_santander_data(
    input_pdf: str | Path,
    line_tolerance: float = 2.5,
    output_path: Optional[str | Path] = None,
) -> None:
    """Extract one Santander statement and write it to CSV."""
    export_statement_data(
        statement_path=input_pdf,
        extractor=extract_santander_statement,
        output_path=output_path,
        logger=logger,
        line_tolerance=line_tolerance,
    )
