"""Extractor for Revolut account statements."""

from __future__ import annotations

import datetime as dt
import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

from my_finances.common.utils import (
    extract_page_lines,
    normalize_whitespace,
    parse_amount,
    parse_month_name,
    read_pdfs,
)
from my_finances.data_extractor.base import export_statement_data

logger = logging.getLogger(__name__)

MAIN_ACCOUNT_NAME = "Main Account"
DATE_PREFIX_RE = re.compile(r"^\d{1,2}$")
YEAR_RE = re.compile(r"^\d{4}$")
EUR_AMOUNT_RE = re.compile(r"^€[\d,]+\.\d{2}$")
POCKET_NAME_RE = re.compile(r"To pocket EUR (?P<name>.+?) from EUR", re.IGNORECASE)
SAVINGS_NAME_RE = re.compile(r"'(?P<name>[^']+)'")

SECTION_HEADERS = {
    "Account transactions from": "current_account",
    "Personal and Group Pockets transactions from": "pockets",
    "Deposit transactions from": "deposit",
}

IGNORED_LINE_PREFIXES = (
    "EUR Statement",
    "Generated on the",
    "Revolut Bank UAB",
    "JEISSON JAVIER LEAL ROJAS",
    "Petzscher Str.",
    "04129 BIC",
    "Leipzig",
    "Sachsen",
    "Balance summary",
    "Closing",
    "Product Opening balance",
    "balance",
    "Account (Current Account)",
    "Personal and Group Pockets",
    "Deposit €",
    "Total €",
    "The balance on your statement",
    "Please review your transactions",
    "Date Description Money out Money in Balance",
)
FOOTER_SECTION_PREFIX = "Report lost or stolen card"


def _is_transaction_line(tokens: list[str]) -> bool:
    """Return True when a line starts with a Revolut transaction date."""
    return (
        len(tokens) >= 5
        and DATE_PREFIX_RE.match(tokens[0]) is not None
        and YEAR_RE.match(tokens[2]) is not None
    )


def _parse_date(tokens: list[str]) -> str:
    """Parse a Revolut ``day month year`` date."""
    day = int(tokens[0])
    month = parse_month_name(tokens[1])
    year = int(tokens[2])
    return dt.date(year, month, day).isoformat()


def _append_note(current_row: dict[str, object], note: str) -> None:
    """Append continuation text to a transaction note field."""
    normalized_note = normalize_whitespace(note)
    if not normalized_note:
        return

    existing = current_row.get("notes")
    current_row["notes"] = (
        normalized_note if not existing else f"{existing} | {normalized_note}"
    )


def _infer_subaccount(section: str, description: str) -> Optional[str]:
    """Infer a named pocket or savings account from a Revolut description."""
    if section == "current_account":
        return MAIN_ACCOUNT_NAME

    if section == "deposit":
        savings_match = SAVINGS_NAME_RE.search(description)
        return (
            savings_match.group("name") if savings_match else "Instant Access Savings"
        )

    pocket_match = POCKET_NAME_RE.search(description)
    if pocket_match:
        return pocket_match.group("name")

    return MAIN_ACCOUNT_NAME


def _parse_transaction_line(
    line_words: list[dict[str, object]],
    section: str,
    page_number: int,
    source_file: str,
) -> dict[str, object]:
    """Build a transaction row from a Revolut statement line."""
    sorted_words = sorted(line_words, key=lambda item: float(item["x0"]))
    tokens = [
        str(word["text"]).strip() for word in sorted_words if str(word["text"]).strip()
    ]
    date_text = _parse_date(tokens[:3])

    amount_words = [
        word
        for word in sorted_words
        if EUR_AMOUNT_RE.match(str(word["text"]).strip()) is not None
    ]
    if len(amount_words) < 2:
        logger.warning(
            "Skipping Revolut row — fewer than 2 amount tokens: %s",
            normalize_whitespace(" ".join(str(w["text"]) for w in sorted_words)),
        )
        raise ValueError("fewer than 2 amount tokens")
    balance_word = max(amount_words, key=lambda item: float(item["x0"]))
    balance = parse_amount(str(balance_word["text"]))

    transaction_word = sorted(amount_words, key=lambda item: float(item["x0"]))[-2]
    transaction_value = parse_amount(str(transaction_word["text"]))
    amount = (
        -transaction_value if float(transaction_word["x0"]) < 380 else transaction_value
    )

    description_tokens = [
        word
        for word in sorted_words[3:]
        if float(word["x1"]) < float(transaction_word["x0"]) - 1
    ]
    description = normalize_whitespace(
        " ".join(str(word["text"]) for word in description_tokens)
    )

    return {
        "bank": "revolut",
        "account": section,
        "subaccount": _infer_subaccount(section, description),
        "date": date_text,
        "value_date": None,
        "description": description,
        "amount": amount,
        "currency": "EUR",
        "balance": balance,
        "notes": None,
        "page": page_number,
        "source_file": source_file,
    }


def extract_revolut_statement(
    statement_path: str | Path,
    line_tolerance: float = 2.5,
) -> pd.DataFrame:
    """Extract one Revolut statement into the shared output schema."""
    pdf_path = Path(statement_path)
    rows: list[dict[str, object]] = []
    current_row: Optional[dict[str, object]] = None
    current_section: Optional[str] = None

    with read_pdfs(pdf_path) as pdfs:
        pdf = pdfs[0]
        for page_number, page in enumerate(pdf.pages, start=1):
            skipping_footer = False
            for line_words, _ in extract_page_lines(
                page,
                line_tolerance,
                use_text_flow=True,
                bottom_margin=95.0,
            ):
                tokens = [
                    str(word["text"]).strip()
                    for word in line_words
                    if str(word["text"]).strip()
                ]
                if not tokens:
                    continue

                line_text = normalize_whitespace(" ".join(tokens))

                if line_text.startswith(FOOTER_SECTION_PREFIX):
                    current_row = None
                    skipping_footer = True
                    continue

                if skipping_footer:
                    continue

                section_match = next(
                    (
                        section_name
                        for prefix, section_name in SECTION_HEADERS.items()
                        if line_text.startswith(prefix)
                    ),
                    None,
                )
                if section_match is not None:
                    current_section = section_match
                    current_row = None
                    continue

                if line_text.startswith(IGNORED_LINE_PREFIXES):
                    continue

                if current_section is None:
                    continue

                if _is_transaction_line(tokens):
                    try:
                        current_row = _parse_transaction_line(
                            line_words=line_words,
                            section=current_section,
                            page_number=page_number,
                            source_file=pdf_path.name,
                        )
                    except ValueError:
                        current_row = None
                        continue
                    rows.append(current_row)
                    continue

                if current_row is None:
                    continue

                if YEAR_RE.match(line_text) and current_row["description"].startswith(
                    "Net Interest Paid"
                ):
                    current_row["description"] = (
                        f"{current_row['description']} {line_text}"
                    )
                    continue

                _append_note(current_row, line_text)

    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        return dataframe

    return dataframe.reset_index(drop=True)


def extract_revolut_data(
    input_pdf: str | Path,
    line_tolerance: float = 2.5,
    output_path: Optional[str | Path] = None,
) -> None:
    """Extract one Revolut statement and write it to CSV."""
    export_statement_data(
        statement_path=input_pdf,
        extractor=extract_revolut_statement,
        output_path=output_path,
        logger=logger,
        line_tolerance=line_tolerance,
    )


def calculate_revolut_subaccount_balances_from_csv(
    csv_path: str | Path,
) -> pd.DataFrame:
    """Build a Revolut balance summary from the exported transactions CSV."""
    transactions = pd.read_csv(csv_path)
    if transactions.empty:
        return pd.DataFrame()

    transactions["subaccount"] = (
        transactions["subaccount"]
        .fillna(MAIN_ACCOUNT_NAME)
        .replace("", MAIN_ACCOUNT_NAME)
    )
    transactions["amount"] = pd.to_numeric(transactions["amount"], errors="coerce")
    transactions["balance"] = pd.to_numeric(transactions["balance"], errors="coerce")

    summary_rows: list[dict[str, object]] = []

    # Revolut pocket rows expose one running aggregate pockets balance even when
    # the transaction text names a specific pocket. Keeping pocket subaccounts as
    # separate balance rows would double-count stale pocket balances across
    # statement formats, so balances are summarized at the account level.
    balance_transactions = transactions.copy()
    balance_transactions["balance_subaccount"] = balance_transactions[
        "subaccount"
    ].where(balance_transactions["account"].ne("pockets"), "All Pockets")
    grouped = balance_transactions.groupby(
        ["source_file", "account", "balance_subaccount", "currency"],
        sort=False,
        dropna=False,
    )
    for (source_file, account, subaccount, currency), group in grouped:
        ordered_group = group.reset_index(drop=True)
        opening_balance: Optional[float]
        closing_balance: Optional[float]
        summary_method: str

        if (
            account in {"current_account", "deposit", "pockets"}
            and ordered_group["balance"].notna().any()
        ):
            first_balance = float(ordered_group.iloc[0]["balance"])
            first_amount = float(ordered_group.iloc[0]["amount"])
            last_balance = float(ordered_group.iloc[-1]["balance"])
            opening_balance = first_balance - first_amount
            closing_balance = last_balance
            summary_method = "running_balance"
        else:
            opening_balance = 0.0
            closing_balance = float(ordered_group["amount"].sum())
            summary_method = "net_transaction_amount"

        summary_rows.append(
            {
                "bank": "revolut",
                "source_file": source_file,
                "account": account,
                "subaccount": subaccount,
                "opening_balance": opening_balance,
                "closing_balance": closing_balance,
                "currency": currency,
                "transactions_count": len(ordered_group),
                "summary_method": summary_method,
            }
        )

    return pd.DataFrame(summary_rows)
