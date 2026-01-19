#!/usr/bin/env python3
"""
pdf_n26_extract.py

Extractor tailored for N26 monthly statements like the provided sample.
It detects transaction rows that visually have three columns:
  [Beschreibung …]   [Buchungsdatum dd.mm.yyyy]   [Betrag ±9,99€]
…and enriches the row with a value date read from a following
"Wertstellung dd.mm.yyyy" sub-line when present. Any additional sub-lines
(e.g., card type/category) are appended to the details field.

Usage:
  python pdf_n26_extract.py input.pdf --out txns.csv

Requires: pip install pdfplumber pandas
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pdfplumber

# Initialize logging
logger = logging.getLogger(__name__)

# --- regexes ---
DATE_FULL = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
DATE_WORD_VAL = re.compile(r"(?i)\bwertstellung\b\s*(\d{2}\.\d{2}\.\d{4})")
# Accept + / - / unicode minus; allow optional trailing €
AMOUNT_EUR = re.compile(r"^[+\-−\u2212]?\d{1,3}(?:\.\d{3})*,\d{2}€?$")


def _to_float_eur(s: str) -> float:
    s = (
        s.replace(" ", "")
        .replace("€", "")
        .replace("\u2212", "-")
        .replace("−", "-")
        .replace("+", "")
        .replace(".", "")
        .replace(",", ".")
    )
    return float(s)


def _group_words_by_line(
    words: List[Dict[str, Any]], y_tol: float
) -> List[Tuple[List[Dict[str, Any]], float]]:
    """Return a list of (line_words, min_x0) keeping original word dicts."""
    if not words:
        return []
    words_sorted = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
    lines: List[Tuple[List[Dict[str, Any]], float]] = []
    cur: List[Dict[str, Any]] = []
    cur_y: Optional[float] = None
    for w in words_sorted:
        y = w["top"]
        if cur_y is None or abs(y - cur_y) <= y_tol:
            cur.append(w)
            if cur_y is None:
                cur_y = y
        else:
            if cur:
                cur_sorted = sorted(cur, key=lambda t: t["x0"])  # left→right
                lines.append((cur_sorted, min(t["x0"] for t in cur_sorted)))
            cur = [w]
            cur_y = y
    if cur:
        cur_sorted = sorted(cur, key=lambda t: t["x0"])
        lines.append((cur_sorted, min(t["x0"] for t in cur_sorted)))
    return lines


def _join_text(words: List[Dict[str, Any]], *, x_until: Optional[float] = None) -> str:
    toks: List[str] = []
    for w in words:
        if x_until is not None and w["x0"] >= x_until:
            break
        s = w["text"].strip()
        if s:
            toks.append(s)
    return " ".join(toks).strip()


def extract_n26_data(
    input_pdf: Path | str,
    line_tolerance: float = 2.5,
    output_path: Optional[Path | str] = None,
) -> None:
    pdf_path = Path(input_pdf)
    recs: List[Dict[str, Any]] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        for pnum, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(use_text_flow=True, keep_blank_chars=False) or []
            lines = _group_words_by_line(words, line_tolerance)

            current: Optional[Dict[str, Any]] = None
            for line_words, _ in lines:
                tokens = [w["text"].strip() for w in line_words if w["text"].strip()]
                if not tokens:
                    continue

                # Find booking date position (rightmost dd.mm.yyyy on the line)
                date_idx = None
                for i, t in enumerate(tokens):
                    if DATE_FULL.match(t):
                        date_idx = i

                # Robust right-side amount detection (handles '+', separated '€', etc.)
                amount_text = None
                for j in range(len(tokens) - 1, -1, -1):
                    candidates = []
                    if j >= 0:
                        candidates.append(tokens[j])
                    if j - 1 >= 0:
                        candidates.append(tokens[j - 1] + tokens[j])
                    if j - 2 >= 0:
                        candidates.append(tokens[j - 2] + tokens[j - 1] + tokens[j])
                    ok = next((c for c in candidates if AMOUNT_EUR.match(c)), None)
                    if ok:
                        amount_text = ok
                        break

                if date_idx is not None and amount_text is not None:
                    # Start a new transaction row
                    date_x = line_words[date_idx]["x0"]
                    details_text = _join_text(line_words, x_until=date_x).strip()
                    current = {
                        "page": pnum,
                        "booking_date": tokens[date_idx],
                        "value_date": None,
                        "details": details_text,
                        "amount_eur": _to_float_eur(amount_text),
                    }
                    recs.append(current)
                    continue

                # Continuation lines: append to details and try to capture Wertstellung
                if current is not None:
                    cont_text = " ".join(tokens)
                    m = DATE_WORD_VAL.search(cont_text)
                    if m and not current.get("value_date"):
                        current["value_date"] = m.group(1)
                        cont_text = DATE_WORD_VAL.sub("", cont_text).strip()
                    if cont_text:
                        current["details"] = (
                            current["details"] + " " + cont_text
                        ).strip()

    df = pd.DataFrame(recs)
    if df.empty:
        logger.info(f"No movements found in file {input_pdf}.")
        return

    # Backfill value_date from booking_date if missing
    df["value_date"] = df["value_date"].fillna(df["booking_date"])

    # Sort
    df = df.sort_values(["page"]).reset_index(drop=True)

    # Column order
    cols = ["page", "booking_date", "value_date", "details", "amount_eur"]
    df[cols]

    out_path = Path(output_path) if output_path else Path(input_pdf).with_suffix(".csv")
    df.to_csv(out_path, index=False)
    logger.info(f"Saved {len(df)} rows to {out_path}")
    logger.info(df)
