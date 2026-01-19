#!/usr/bin/env python3
"""
my_finances.data_extractor.bancolombia

Extractor for Bancolombia PDFs in the "ESTADO DE CUENTA" layout.

Statements include:
  - Period line: "DESDE: YYYY/MM/DD HASTA: YYYY/MM/DD"
  - Table header: "FECHA DESCRIPCIÓN SUCURSAL DCTO. VALOR SALDO"
  - Rows:
        FECHA: d/m   (no year in row)
        VALOR: second-rightmost numeric
        SALDO: rightmost numeric (ignored)
  - Amount format: "-100,000.00", ".79", "-.02"

Output columns:
  page, date (ISO yyyy-mm-dd), description, amount_cop

Note:
  - This parser is intended for "ESTADO DE CUENTA" statements only.
"""

import datetime
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from my_finances.data_extractor.common.utils import read_pdfs, write_df

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

# --- Patterns ---
DATE_DM = re.compile(r"^(\d{1,2})/(\d{1,2})$")

PERIOD_RE = re.compile(
    r"DESDE:\s*(\d{4})/(\d{2})/(\d{2})\s+HASTA:\s*(\d{4})/(\d{2})/(\d{2})",
    re.IGNORECASE,
)

AMT_US = re.compile(r"^[+\-−\u2212]?(?:\d{1,3}(?:,\d{3})*|\d+)?\.\d{2}$")


def _to_float_us(text: str) -> float:
    """Parse '760,000.00', '-.02', '.79' into float."""
    s = text.replace("\u2212", "-").replace("−", "-").replace(",", "")
    if s.startswith("."):
        s = "0" + s
    if s.startswith("-."):
        s = s.replace("-.", "-0.", 1)
    return float(s)


def _extract_period(
    first_page_text: str,
) -> Tuple[Optional[datetime.date], Optional[datetime.date]]:
    m = PERIOD_RE.search(first_page_text or "")
    if not m:
        return None, None
    y1, mo1, d1, y2, mo2, d2 = map(int, m.groups())
    try:
        return datetime.date(y1, mo1, d1), datetime.date(y2, mo2, d2)
    except Exception:
        return None, None


def _assign_year(
    day: int, month: int, start: datetime.date, end: datetime.date
) -> datetime.date:
    """
    Choose a year for (day, month) so the date falls within [start, end].
    Works for periods that may cross a year boundary.
    """
    for y in {start.year, end.year}:
        try:
            dt = datetime.date(y, month, day)
        except ValueError:
            continue
        if start <= dt <= end:
            return dt

    if start.year != end.year:
        y = end.year if month < start.month else start.year
        return datetime.date(y, month, day)

    return datetime.date(start.year, month, day)


def _y_center(w: Dict[str, Any]) -> float:
    return (float(w["top"]) + float(w["bottom"])) / 2.0


def _cluster(values: List[float], tol: float) -> List[float]:
    """Cluster sorted numeric values into group centers."""
    if not values:
        return []
    vals = sorted(values)
    centers: List[float] = []
    cur: List[float] = [vals[0]]
    for v in vals[1:]:
        center = sum(cur) / len(cur)
        if abs(v - center) <= tol:
            cur.append(v)
        else:
            centers.append(sum(cur) / len(cur))
            cur = [v]
    centers.append(sum(cur) / len(cur))
    return centers


def _find_table_header_y(words: List[Dict[str, Any]]) -> float:
    """Find y of the 'FECHA' header word as an anchor. If not found, return 0."""
    for w in words:
        if w.get("text", "").upper() == "FECHA":
            return _y_center(w)
    return 0.0


def _parse_row_from_words(
    row_words: List[Dict[str, Any]],
    start: Optional[datetime.date],
    end: Optional[datetime.date],
) -> Optional[Tuple[str, str, float]]:
    """
    Given all words belonging to one transaction row (same y band),
    return (date_iso, description, amount_float) or None.
    """
    row_sorted = sorted(row_words, key=lambda w: float(w["x0"]))

    # Date token (d/m)
    date_w = next((w for w in row_sorted if DATE_DM.match(w.get("text", ""))), None)
    if not date_w:
        return None

    # Numeric tokens (VALOR & SALDO are the rightmost two AMT_US matches)
    nums = [w for w in row_sorted if AMT_US.match(w.get("text", ""))]
    nums = sorted(nums, key=lambda w: float(w["x0"]))
    if len(nums) < 2:
        return None

    valor_w = nums[-2]  # second-rightmost
    # saldo_w = nums[-1]  # rightmost (not used)

    # Build ISO date using statement period
    m = DATE_DM.match(date_w["text"])
    assert m is not None
    day = int(m.group(1))
    month = int(m.group(2))

    if start and end:
        dt = _assign_year(day, month, start, end)
        date_iso = dt.isoformat()
    else:
        date_iso = date_w["text"]  # fallback

    # Description = words between date token and VALOR token by x-position
    date_x1 = float(date_w["x1"])
    valor_x0 = float(valor_w["x0"])

    desc_words = [
        w
        for w in row_sorted
        if float(w["x0"]) > date_x1 + 1 and float(w["x1"]) < valor_x0 - 1
    ]
    desc_words = sorted(desc_words, key=lambda w: float(w["x0"]))
    description = " ".join(w["text"] for w in desc_words).strip()

    amount = _to_float_us(valor_w["text"])
    return date_iso, description, amount


def extract_bancolombia_data(
    input_pdf: PathLike,
    line_tolerance: float = 2.6,
    output_path: Optional[PathLike] = None,
) -> None:
    pdf_path = Path(input_pdf)

    with read_pdfs(pdf_path) as pdfs_obj:
        # Be tolerant if read_pdfs yields (pdfs,) instead of pdfs
        pdfs = pdfs_obj[0] if isinstance(pdfs_obj, tuple) else pdfs_obj

        rows: List[Dict[str, Any]] = []
        seq = 0  # stable insertion order fallback

        for pdf in pdfs:
            first_text = pdf.pages[0].extract_text() or ""
            start, end = _extract_period(first_text)

            for pnum, page in enumerate(pdf.pages, start=1):
                words = (
                    page.extract_words(use_text_flow=False, keep_blank_chars=False)
                    or []
                )
                if not words:
                    continue

                header_y = _find_table_header_y(words)
                min_data_y = header_y + (2.0 * line_tolerance)

                # Identify date words below the table header
                date_words = [
                    w
                    for w in words
                    if DATE_DM.match(w.get("text", "")) and _y_center(w) >= min_data_y
                ]
                if not date_words:
                    continue

                # Cluster rows by the y position of the date words
                row_ys = _cluster(
                    [_y_center(w) for w in date_words], tol=line_tolerance
                )

                # IMPORTANT: process rows top->bottom
                for y in sorted(row_ys):
                    row_words = [
                        w for w in words if abs(_y_center(w) - y) <= line_tolerance
                    ]
                    parsed = _parse_row_from_words(row_words, start, end)
                    if not parsed:
                        continue

                    date_iso, description, amount = parsed
                    if not description:
                        continue

                    rows.append(
                        {
                            "page": pnum,
                            "date": date_iso,
                            "description": description,
                            "amount_cop": amount,
                            "_row_y": float(y),  # internal: table position
                            "_seq": seq,  # internal: stable tie-breaker
                        }
                    )
                    seq += 1

        df = pd.DataFrame(rows)
        if df.empty:
            logger.info(f"No movements found in file {input_pdf}.")
            return

        df["description"] = (
            df["description"]
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

        # FIX: stable ordering matching PDF table:
        # page, then top-to-bottom within page.
        df = df.sort_values(["page", "_row_y", "_seq"], kind="mergesort").reset_index(
            drop=True
        )

        if output_path:
            out_path = Path(output_path)
        else:
            # Name output using earliest/latest ISO dates when possible
            dates = []
            for d in df["date"].tolist():
                try:
                    dates.append(datetime.date.fromisoformat(d))
                except Exception:
                    pass
            if dates:
                earliest, latest = min(dates), max(dates)
                fname = f"bancolombiaStatements_{earliest:%Y%m%d}_{latest:%Y%m%d}.csv"
            else:
                fname = pdf_path.with_suffix(".csv").name
            out_path = pdf_path.parent / fname

        out_df = df[["page", "date", "description", "amount_cop"]]
        write_df(out_df, out_path, "csv")
        logger.info(f"Saved {len(out_df)} rows to {out_path}")
