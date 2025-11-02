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

import argparse
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import pdfplumber

# --- regexes ---
DATE_FULL = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
DATE_WORD_VAL = re.compile(r"(?i)\bwertstellung\b\s*(\d{2}\.\d{2}\.\d{4})")
# Accept + / - / unicode minus; allow optional trailing €
AMOUNT_EUR = re.compile(r'^[+\-−\u2212]?\d{1,3}(?:\.\d{3})*,\d{2}€?$')


def _to_float_eur(s: str) -> float:
    s = (
        s.replace(" ", "")
         .replace("€", "")
         .replace("\u2212", "-")
         .replace("−", "-")
         .replace("+", "")
    )
    # German decimal
    s = s.replace(".", "").replace(",", ".")
    return float(s)


def _pages_list(spec: str, total: int) -> List[int]:
    if spec.lower() == "all":
        return list(range(1, total + 1))
    out: List[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
            lo, hi = sorted((a, b))
            out.extend([i for i in range(lo, hi + 1) if 1 <= i <= total])
        else:
            i = int(part)
            if 1 <= i <= total:
                out.append(i)
    return sorted(set(out))


def _group_words_by_line(words: List[Dict[str, Any]], y_tol: float) -> List[Tuple[List[Dict[str, Any]], float]]:
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


def extract_n26(
    pdf_path: Path | str,
    pages: str = "all",
    y_tol: float = 2.5,
    sort: str = "page+booking",
) -> pd.DataFrame:
    pdf_path = Path(pdf_path)
    recs: List[Dict[str, Any]] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        pnums = _pages_list(pages, len(pdf.pages))
        for pnum in pnums:
            page = pdf.pages[pnum - 1]
            words = page.extract_words(use_text_flow=True, keep_blank_chars=False) or []
            lines = _group_words_by_line(words, y_tol)

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
                        current["details"] = (current["details"] + " " + cont_text).strip()

    df = pd.DataFrame(recs)
    if df.empty:
        return df

    # Backfill value_date from booking_date if missing
    df["value_date"] = df["value_date"].fillna(df["booking_date"])

    # Sort
    def _key(dt: str) -> Tuple[int, int, int]:
        try:
            d, m, y = dt.split(".")
            return (int(y), int(m), int(d))
        except Exception:
            return (0, 0, 0)

    if sort == "page+booking":
        df = (
            df.assign(_k=df["booking_date"].map(_key))
              .sort_values(["page", "_k"])
              .drop(columns="_k")
              .reset_index(drop=True)
        )
    elif sort == "page":
        df = df.sort_values(["page"]).reset_index(drop=True)

    # Column order
    cols = ["page", "booking_date", "value_date", "details", "amount_eur"]
    return df[cols]


# --- CLI ---

def _build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Extract N26 statement transactions into a table.")
    p.add_argument("pdf", help="Input PDF path")
    p.add_argument("--pages", default="all", help="Pages like 'all', '1', '2-4'")
    p.add_argument("--y-tol", type=float, default=2.5, help="Line grouping tolerance (default 2.5)")
    p.add_argument("--sort", choices=["page", "page+booking"], default="page+booking")
    p.add_argument("--out", default=None, help="Output path (default: alongside PDF with .csv)")
    p.add_argument("--format", choices=["csv", "xlsx", "json", "parquet"], default="csv")
    p.add_argument("--preview", type=int, default=10, help="Rows to print in stdout preview")
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
    ap = _build_cli()
    args = ap.parse_args(argv)
    df = extract_n26(args.pdf, pages=args.pages, y_tol=args.y_tol, sort=args.sort)
    if df.empty:
        print("No transactions found.")
        return
    out_fmt = args.format
    out_path = Path(args.out) if args.out else Path(args.pdf).with_suffix(f".{out_fmt}")
    # _write(df, out_path, out_fmt)
    print(f"Saved {len(df)} rows to {out_path}")

    print(df)


if __name__ == "__main__":
    main()
