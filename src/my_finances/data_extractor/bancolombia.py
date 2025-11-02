#!/usr/bin/env python3
"""
pdf_bancolombia_extract.py

Extractor for Bancolombia "Movimientos: Cuentas" PDFs like
"MovimientosTusCuentasBancolombia02Nov2025.pdf".

Each movement typically appears as:
  "dd mon yyyy  <Descripción possibly multi-line>  [Referencia?]  <Valor>"
where:
  - Dates use Spanish month abbreviations (ene feb mar abr may jun jul ago sep oct nov dic)
  - Currency is COP with dot thousands and comma decimals (e.g., -$ 151.699,00)
  - Description may spill into the next line(s)
  - A reference number (>= 6 digits) may appear on the same or following line

Output columns: page, date, description, reference, amount_cop

Usage:
  python pdf_bancolombia_extract.py input.pdf --out movimientos.csv

Requires: pip install pdfplumber pandas
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pdfplumber

import logging

# Initialize logging
logger = logging.getLogger(__name__)

# ---- Regexes ----
MONTHS = "ene feb mar abr may jun jul ago sep oct nov dic".split()
DATE_ES = re.compile(
    r"^(\d{1,2})\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\s+(\d{4})$",
    re.IGNORECASE,
)
# amount variations: "-$ 151.699,00", "$760.000,00", "+$ 10,00" (rare), "151.699,00"
AMT_COP = re.compile(r"^[+\-−\u2212]?\$?\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?$")
REF_RE = re.compile(r"\b\d{6,}\b")

HEADERS = {
    "fecha descripción referencia valor",
    "fecha descripcion referencia valor",
}


# ---- Helpers ----
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


def _to_float_cop(text: str) -> float:
    s = (
        text.replace(" ", "")
        .replace("\u2212", "-")
        .replace("−", "-")
        .replace("$", "")
        .replace("+", "")
    )
    # Keep '-' if present; normalize decimals
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")
    return float(s)


def _group_words_by_line(words: List[Dict[str, Any]], y_tol: float):
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
            cur_sorted = sorted(cur, key=lambda t: t["x0"])
            lines.append(cur_sorted)
            cur, cur_y = [w], y
    if cur:
        cur_sorted = sorted(cur, key=lambda t: t["x0"])
        lines.append(cur_sorted)
    return lines


def _tokens(line_words: List[Dict[str, Any]]) -> List[str]:
    return [w["text"].strip() for w in line_words if w["text"].strip()]


def _is_header(tokens: List[str]) -> bool:
    s = " ".join(tokens).lower()
    return (
        any(h in s for h in HEADERS)
        or s.startswith("sucursal virtual")
        or s.startswith("movimientos: cuentas")
        or s.startswith("dirección ip")
        or s.startswith("direccion ip")
    )


def _scan_amount_from_right(tokens: List[str]) -> Tuple[Optional[str], bool]:
    """
    Returns (amount_text, is_negative) scanning from the right, robust to "- $ 151.699,00".
    is_negative is True only if a minus sign appears BEFORE the $/digits.
    """
    # Try windows from rightmost combining up to 4 tokens (to absorb spaces)
    for j in range(len(tokens) - 1, -1, -1):
        candidates = []
        # windows (1..4) tokens
        for n in (1, 2, 3, 4):
            if j - n + 1 >= 0:
                candidates.append("".join(tokens[j - n + 1 : j + 1]))
        ok = next((c for c in candidates if AMT_COP.match(c)), None)
        if ok:
            joined_context = " ".join(tokens[max(0, j - 5) : j + 1])
            # negative if '-' (or unicode minus) appears before the first digit/$
            neg = bool(re.search(r"[−\-\u2212]\s*(?=\$?\s*\d)", joined_context))
            return ok, neg
    return None, False


# ---- Core extractor ----
def extract_bancolombia(
    pdf_path: str | Path, pages: str = "all", y_tol: float = 2.6
) -> pd.DataFrame:
    pdf_path = Path(pdf_path)
    rows: List[Dict[str, Any]] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        pnums = _pages_list(pages, len(pdf.pages))
        current: Optional[Dict[str, Any]] = None
        for pnum in pnums:
            page = pdf.pages[pnum - 1]
            words = page.extract_words(use_text_flow=True, keep_blank_chars=False) or []
            for line in _group_words_by_line(words, y_tol):
                toks = _tokens(line)
                if not toks:
                    continue
                if _is_header(toks):
                    continue

                # Start of a new movement if line begins with a date
                if DATE_ES.match(" ".join(toks[:3]).lower()):
                    # finalize previous record if it had an amount
                    if current and current.get("amount_cop") is not None:
                        rows.append(current)
                    current = {
                        "page": pnum,
                        "date": " ".join(toks[:3]),
                        "description": " ".join(toks[3:]).strip(),
                        "reference": None,
                        "amount_cop": None,
                    }
                    # try to find an amount on same line
                    amt_text, is_neg = _scan_amount_from_right(toks)
                    if amt_text:
                        val = _to_float_cop(amt_text)
                        current["amount_cop"] = -abs(val) if is_neg else abs(val)
                    continue

                # Continuation / details / reference / amount
                if current is not None:
                    joined = " ".join(toks)

                    # possible reference on this line
                    ref_match = REF_RE.search(joined)
                    if ref_match and current.get("reference") is None:
                        current["reference"] = ref_match.group(0)

                    # amount on continuation
                    if current.get("amount_cop") is None:
                        amt_text, is_neg = _scan_amount_from_right(toks)
                        if amt_text:
                            val = _to_float_cop(amt_text)
                            current["amount_cop"] = -abs(val) if is_neg else abs(val)
                            # strip trailing amount from description continuation
                            for n in (4, 3, 2, 1):
                                if len(toks) >= n and AMT_COP.match("".join(toks[-n:])):
                                    toks = toks[:-n]
                                    break

                    # append remaining text as description continuation
                    extra = " ".join(toks).strip()
                    if extra:
                        current["description"] = (current["description"] + " " + extra).strip()

        # flush after all pages
        if current and current.get("amount_cop") is not None:
            rows.append(current)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Clean description whitespace
    df["description"] = df["description"].str.replace(r"\s+", " ", regex=True).str.strip()

    # Sort by page then keep original order within page
    df = df.sort_values(["page"]).reset_index(drop=True)
    return df[["page", "date", "description", "reference", "amount_cop"]]


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


def extract_data_as_df(
        input_pdf: str,
        pages: str = "all",
        line_tolerance: float = 2.6,
        output_path: Optional[str] = None,
        output_format: str = "csv",
    ) -> pd.DataFrame:

    # Extract data
    df = extract_bancolombia(
        input_pdf=input_pdf,
        pages=pages,
        line_tolerance=line_tolerance,
        output_path=output_path,
        output_format=output_format,
    )
    if df.empty:
        logger.info(f"No movements found in file {input_pdf}.")
        return
    
    out_path = Path(output_path) if output_path else Path(input_pdf).with_suffix(f".{output_format}")
    # _write(df, out_path, output_format)
    logger.info(f"Saved {len(df)} rows to {out_path}")
    logger.info(df)
