#!/usr/bin/env python3
"""
pdf_girokonto_extract.py

Compact extractor for GIROKONTO-style statements:
Lines often look like:
  dd.mm  dd.mm  <multi-line Buchungstext>  <amount>
Dates and amounts may contain stray spaces.
Balance lines (ZWISCHENSALDO/NEUER SALDO/etc.) are ignored.

Usage:
  python pdf_girokonto_extract.py input.pdf --out txns.csv
Requires: pip install pdfplumber pandas
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
import pdfplumber

# Initialize logging
logger = logging.getLogger(__name__)

DATE_FUZZY = re.compile(r"^\s*(\d{1,2})\s*[\.\-]\s*(\d{1,2})\s*[\.\-]?\s*$")
# amount with optional thousands/decimal separators; sign is handled separately
AMT_FUZZY = re.compile(
    r"^\s*(?:(?:\d{1,3}(?:[\s\.\,]\d{3})+|\d+)(?:[\,\.]\d{2})?|\d+[\,\.]\d{2})\s*$"
)
BALANCE_KEYWORDS = {
    "ZWISCHENSALDO",
    "NEUER SALDO",
    "ALTER SALDO",
    "ÜBERTRAG",
    "UEBERTRAG",
    "SALDENMITTEILUNG",
    "ZWISCHENSTAND",
}

TRAILING_MINUS = {"-", "−", "\u2212"}  # hyphen, unicode minus chars


def _norm_date(tok: str) -> str | None:
    m = DATE_FUZZY.match(tok)
    if not m:
        return None
    d, mth = m.group(1), m.group(2)
    return f"{int(d):02d}.{int(mth):02d}"


def _is_amount_core(tok: str) -> bool:
    return bool(AMT_FUZZY.match(tok))


def _to_float(tok: str) -> float:
    s = tok.replace(" ", "").replace("\u2212", "-").replace("−", "-")
    if s.count(",") == 1 and (s.count(".") >= 1 or "," in s):
        s = s.replace(".", "").replace(",", ".")  # German style to dot-decimal
    else:
        s = s.replace(",", "")
    return float(s)


def _group_lines(words, y_tol: float):
    if not words:
        return []
    words_sorted = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
    lines, cur, cur_y = [], [], None
    for w in words_sorted:
        y = w["top"]
        if cur_y is None or abs(y - cur_y) <= y_tol:
            cur.append(w)
            if cur_y is None:
                cur_y = y
        else:
            tokens = [t["text"] for t in sorted(cur, key=lambda x: x["x0"])]
            min_x0 = min(t["x0"] for t in cur)
            lines.append((tokens, min_x0))
            cur, cur_y = [w], y
    if cur:
        tokens = [t["text"] for t in sorted(cur, key=lambda x: x["x0"])]
        min_x0 = min(t["x0"] for t in cur)
        lines.append((tokens, min_x0))
    return lines


def _find_amount(
    tokens: List[str],
) -> Tuple[Optional[int], Optional[str], Optional[bool]]:
    """
    Scan from right; return (amount_index, amount_text_without_trailing_minus, is_negative).

    Negative if:
      - explicit leading minus in the amount token (e.g., '-8,88')
      - amount token ends with a minus (e.g., '8,88-' or '8,88−')
      - a standalone trailing minus token follows the amount: ['8,88', '-']
    """
    n = len(tokens)
    for i in range(n - 1, -1, -1):
        t = tokens[i].strip()

        # Case A: trailing minus as its own token after amount
        if (
            t in TRAILING_MINUS
            and i - 1 >= 0
            and _is_amount_core(tokens[i - 1].strip())
        ):
            return i - 1, tokens[i - 1].strip(), True

        # Case B: amount token possibly with trailing minus attached
        # strip trailing minus for the core check
        t_no_trail = t.rstrip("".join(TRAILING_MINUS))
        if _is_amount_core(t_no_trail):
            # negative if minus at the end or minus at the beginning
            neg_trailing = len(t) > len(t_no_trail)
            neg_leading = t_no_trail.lstrip().startswith(("-", "−", "\u2212"))
            return i, t_no_trail, (neg_trailing or neg_leading)

    return None, None, None


def extract(
    input_pdf: str | Path, pages: str = "all", line_tolerance: float = 2.5
) -> pd.DataFrame:
    input_pdf = Path(input_pdf)
    recs = []
    with pdfplumber.open(str(input_pdf)) as pdf:
        if pages.lower() == "all":
            page_numbers = range(1, len(pdf.pages) + 1)
        else:
            page_numbers = []
            for part in pages.split(","):
                part = part.strip()
                if not part:
                    continue
                if "-" in part:
                    a, b = (int(x) for x in part.split("-", 1))
                    lo, hi = sorted((a, b))
                    page_numbers.extend(
                        [i for i in range(lo, hi + 1) if 1 <= i <= len(pdf.pages)]
                    )
                else:
                    i = int(part)
                    if 1 <= i <= len(pdf.pages):
                        page_numbers.append(i)

        for pnum in page_numbers:
            words = (
                pdf.pages[pnum - 1].extract_words(
                    use_text_flow=True, keep_blank_chars=False
                )
                or []
            )
            lines = _group_lines(words, y_tol=line_tolerance)
            current = None
            for tokens, x0 in lines:
                toks = [t.strip() for t in tokens if t.strip()]
                if not toks:
                    continue

                # New transaction line?
                if len(toks) >= 3 and _norm_date(toks[0]) and _norm_date(toks[1]):
                    b_date, v_date = _norm_date(toks[0]), _norm_date(toks[1])
                    amt_idx, amt_text, is_neg = _find_amount(toks)
                    if amt_idx is None:
                        details = " ".join(toks[2:]).strip()
                        amount_val = None
                    else:
                        details = " ".join(toks[2:amt_idx]).strip()
                        val = _to_float(amt_text)
                        amount_val = -abs(val) if is_neg else abs(val)

                    current = {
                        "page": pnum,
                        "booking_date": b_date,
                        "value_date": v_date,
                        "details": details,
                        "amount_eur": amount_val,
                    }
                    if amount_val is not None:
                        recs.append(current)
                    continue

                # Continuation line
                if current is not None:
                    if " ".join(toks).upper().replace("Ü", "UE") in BALANCE_KEYWORDS:
                        continue

                    cont = " ".join(toks).strip()
                    if cont:
                        if current.get("amount_eur") is None:
                            amt_idx, amt_text, is_neg = _find_amount(toks)
                            if amt_idx is not None:
                                val = _to_float(amt_text)
                                current["amount_eur"] = (
                                    -abs(val) if is_neg else abs(val)
                                )
                                # drop amount part from continuation text
                                cont = " ".join(toks[:amt_idx]).strip()
                                # also drop trailing standalone '-' if present
                                if cont.endswith(" -") or cont.endswith(" −"):
                                    cont = cont[:-2].rstrip()

                        if cont:
                            current["details"] = (
                                current["details"] + " " + cont
                            ).strip()

                        if recs and recs[-1] is current:
                            pass
                        elif current.get("amount_eur") is not None:
                            recs.append(current)
                    continue

    df = pd.DataFrame(recs)
    if not df.empty:
        df = df.dropna(subset=["amount_eur"]).reset_index(drop=True)
    return df


def extract_santander_data(
    input_pdf: Path | str,
    line_tolerance: float = 2.5,
    output_path: Optional[Path | str] = None,
) -> None:
    input_pdf = Path(input_pdf)
    # reuse the compact `extract` implementation to get a DataFrame
    df = extract(input_pdf, pages="all", line_tolerance=line_tolerance)
    if df is None or df.empty:
        logger.info(f"No movements found in file {input_pdf}.")
        return

    out_path = Path(output_path) if output_path else Path(input_pdf).with_suffix(".csv")
    df.to_csv(out_path, index=False)
    logger.info(f"Saved {len(df)} rows to {out_path}")
    logger.info(df)
