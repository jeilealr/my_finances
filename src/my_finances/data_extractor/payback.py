#!/usr/bin/env python3
"""
pdf_table_extract_min.py

A compact, reusable extractor for statement-like PDFs where each row has:
  dd.mm  dd.mm  <details ...>  <amount>

- Minimal, "pythonic" structure.
- Returns a pandas DataFrame and optionally writes CSV/Excel/JSON/Parquet.
- CLI: `python pdf_table_extract_min.py input.pdf --out txns.csv`

Requirements: pip install pdfplumber pandas
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Sequence, Tuple

import pandas as pd
import pdfplumber


# ---- Small helpers (kept compact & focused) ----

DATE_RE = re.compile(r"^\d{2}\.\d{2}$")  # dd.mm
# Accept optional +/− and optional trailing currency sign (robust to common cases)
AMOUNT_RE_COMMA = re.compile(r"^[+\-−\u2212]?\d{1,3}(\.\d{3})*,\d{2}(?:€)?$|^[+\-−\u2212]?\d+,\d{2}(?:€)?$")
AMOUNT_RE_DOT   = re.compile(r"^[+\-−\u2212]?\d{1,3}(,\d{3})*\.\d{2}(?:€)?$|^[+\-−\u2212]?\d+\.\d{2}(?:€)?$")


def _pages_list(spec: str, total: int) -> List[int]:
    """Expand 'all' or '1,3-5' into [ints]."""
    if spec.lower() == "all":
        return list(range(1, total + 1))
    out, parts = set(), [p.strip() for p in spec.split(",") if p.strip()]
    for p in parts:
        if "-" in p:
            a, b = (int(x) for x in p.split("-", 1))
            lo, hi = sorted((a, b))
            out.update(i for i in range(lo, hi + 1) if 1 <= i <= total)
        else:
            i = int(p)
            if 1 <= i <= total:
                out.add(i)
    out = sorted(out)
    if not out:
        raise ValueError("No valid pages from pages spec")
    return out


def _group_words_by_line(words: List[Dict[str, Any]], y_tol: float) -> List[List[str]]:
    """Group word dicts into left-to-right token lines by y proximity; return tokens per line."""
    words = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
    lines, cur, cur_y = [], [], None
    for w in words:
        y = w["top"]
        if cur_y is None or abs(y - cur_y) <= y_tol:
            cur.append(w)
            cur_y = y if cur_y is None else cur_y
        else:
            lines.append([t["text"] for t in sorted(cur, key=lambda x: x["x0"])])
            cur, cur_y = [w], y
    if cur:
        lines.append([t["text"] for t in sorted(cur, key=lambda x: x["x0"])])
    return lines


def _amount_regex(style: str) -> re.Pattern:
    return AMOUNT_RE_COMMA if style == "comma" else AMOUNT_RE_DOT


def _amount_to_float(text: str, style: str) -> float:
    # Normalize sign & currency
    text = (
        text.replace("€", "")
            .replace("+", "")
            .replace("\u2212", "-")
            .replace("−", "-")
            .strip()
    )
    if style == "comma":
        return float(text.replace(".", "").replace(",", "."))
    return float(text.replace(",", ""))


def _ddmm_key(s: str) -> Tuple[int, int]:
    try:
        d, m = s.split(".")
        return (int(m), int(d))
    except Exception:
        return (0, 0)


# ---- Public API ----

def extract_table(
    pdf_path: Path | str,
    pages: str = "all",
    y_tol: float = 2.5,
    decimal_style: str = "comma",
    include_foreign_amount: bool = True,
    sort: str = "page+booking",
    force_negative: bool = True,   # NEW: make all amounts negative by default
) -> pd.DataFrame:
    """
    Extract a transaction-like table from a PDF into a DataFrame.
    Returns columns: page, booking_date, value_date, details, amount_eur[, amount_foreign]
    """
    pdf_path = Path(pdf_path)
    rows: List[Dict[str, Any]] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        page_nums = _pages_list(pages, len(pdf.pages))
        amt_re = _amount_regex(decimal_style)

        for pnum in page_nums:
            words = pdf.pages[pnum - 1].extract_words(use_text_flow=True, keep_blank_chars=False) or []
            for tokens in _group_words_by_line(words, y_tol):
                if len(tokens) < 4 or not (DATE_RE.match(tokens[0]) and DATE_RE.match(tokens[1])):
                    continue

                # rightmost amount
                amt_idx = next((i for i in range(len(tokens)-1, -1, -1) if amt_re.match(tokens[i])), None)
                if amt_idx is None:
                    continue

                foreign_tok = None
                if include_foreign_amount and amt_idx - 1 >= 2 and amt_re.match(tokens[amt_idx - 1]):
                    foreign_tok = tokens[amt_idx - 1]
                    details_tokens = tokens[2:amt_idx - 1]
                else:
                    details_tokens = tokens[2:amt_idx]

                details = " ".join(details_tokens).strip()
                if details.upper().startswith("UMSATZ") or "buchungsdatum" in details.lower():
                    continue

                amount_val = _amount_to_float(tokens[amt_idx], decimal_style)
                if force_negative:
                    amount_val = -abs(amount_val)

                row = {
                    "page": pnum,
                    "booking_date": tokens[0],
                    "value_date": tokens[1],
                    "details": details,
                    "amount_eur": amount_val,
                }
                if include_foreign_amount:
                    if isinstance(foreign_tok, str):
                        fval = _amount_to_float(foreign_tok, decimal_style)
                        row["amount_foreign"] = -abs(fval) if force_negative else fval
                    else:
                        row["amount_foreign"] = None
                rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    if sort == "page":
        df = df.sort_values(["page"]).reset_index(drop=True)
    elif sort == "page+booking":
        df = (
            df.assign(_k=df["booking_date"].map(_ddmm_key))
              .sort_values(["page", "_k"])
              .drop(columns="_k")
              .reset_index(drop=True)
        )
    return df


# ---- CLI ----

def _build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Extract a transaction-like table from PDF into a DataFrame.")
    p.add_argument("pdf", help="Path to the input PDF.")
    p.add_argument("--pages", default="all", help="Pages: 'all', '1', '1,3-5' (default: all).")
    p.add_argument("--y-tol", type=float, default=2.5, help="Line grouping y-tolerance (default: 2.5).")
    p.add_argument("--decimal-style", choices=["comma", "dot"], default="comma",
                   help="Number style for amounts (default: comma).")
    p.add_argument("--no-foreign", action="store_true", help="Do not capture a foreign amount column.")
    p.add_argument("--sort", choices=["none", "page", "page+booking"], default="page+booking",
                   help="Sort output rows (default: page+booking).")
    p.add_argument("--out", default=None, help="Output path; defaults to PDF basename with correct extension.")
    p.add_argument("--format", choices=["csv", "xlsx", "json", "parquet"], default="csv",
                   help="Output format (default: csv).")
    p.add_argument("--preview", type=int, default=10, help="Rows to print as preview (default: 10).")
    p.add_argument("--no-force-negative", action="store_true",
                   help="Keep the parsed sign as-is (do NOT force negatives).")
    return p


def _write(df: pd.DataFrame, out_path: Path, fmt: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = fmt.lower()
    if fmt == "csv":
        df.to_csv(out_path, index=False)
    elif fmt in ("xlsx", "excel"):
        df.to_excel(out_path, index=False)
    elif fmt == "json":
        df.to_json(out_path, orient="records", force_ascii=False, indent=2)
    elif fmt == "parquet":
        df.to_parquet(out_path, index=False)
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _build_cli().parse_args(argv)
    df = extract_table(
        pdf_path=args.pdf,
        pages=args.pages,
        y_tol=args.y_tol,
        decimal_style=args.decimal_style,
        include_foreign_amount=not args.no_foreign,
        sort=args.sort,
        force_negative=not args.no_force_negative,  # default: force negatives
    )
    if df.empty:
        print("No rows found."); return

    out_fmt = args.format
    out_path = Path(args.out) if args.out else Path(args.pdf).with_suffix(f".{out_fmt}")
    # _write(df, out_path, out_fmt)

    print(f"Saved {len(df)} rows to: {out_path}")
    with pd.option_context("display.max_columns", None, "display.width", 160):
        print(df.head(args.preview).to_string(index=False))
    print(df)


if __name__ == "__main__":
    main()
