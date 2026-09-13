"""Shared helpers used across statement extractors."""

from __future__ import annotations

import datetime as dt
import logging
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

import pandas as pd
import pdfplumber

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]
PDFWord = Dict[str, Any]
PDFLine = Tuple[List[PDFWord], float]

MONTH_LOOKUP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def collect_files(path: PathLike, pattern: str) -> list[Path]:
    """Return a sorted list of files from a file or a directory."""
    resolved_path = Path(path)

    if not resolved_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {resolved_path}")

    if resolved_path.is_file():
        return [resolved_path]

    files = sorted(item for item in resolved_path.glob(pattern) if item.is_file())
    if not files:
        raise FileNotFoundError(
            f"No files matching '{pattern}' were found in {resolved_path}"
        )
    return files


@contextmanager
def read_pdfs(path: PathLike) -> Iterator[list[pdfplumber.pdf.PDF]]:
    """Open one PDF file or all PDFs in a directory."""
    pdf_paths = collect_files(path, "*.pdf")
    with ExitStack() as stack:
        pdfs = [
            stack.enter_context(pdfplumber.open(str(pdf_path)))
            for pdf_path in pdf_paths
        ]
        yield pdfs


def pages_list(spec: str, total: int) -> list[int]:
    """Expand page specs such as ``all`` or ``1,3-5``."""
    if spec.lower() == "all":
        return list(range(1, total + 1))

    page_numbers = set()
    for part in (chunk.strip() for chunk in spec.split(",")):
        if not part:
            continue
        if "-" in part:
            start_page, end_page = (int(value) for value in part.split("-", 1))
            lower, upper = sorted((start_page, end_page))
            page_numbers.update(
                page for page in range(lower, upper + 1) if 1 <= page <= total
            )
            continue

        page = int(part)
        if 1 <= page <= total:
            page_numbers.add(page)

    return sorted(page_numbers)


def group_words_by_line(words: list[PDFWord], y_tolerance: float) -> list[PDFLine]:
    """Group pdfplumber words by their vertical position."""
    if not words:
        return []

    lines: list[PDFLine] = []
    current_words: list[PDFWord] = []
    current_y: Optional[float] = None

    for word in sorted(words, key=lambda item: (round(item["top"], 1), item["x0"])):
        top = float(word["top"])
        if current_y is None or abs(top - current_y) <= y_tolerance:
            current_words.append(word)
            if current_y is None:
                current_y = top
            continue

        sorted_words = sorted(current_words, key=lambda item: item["x0"])
        lines.append((sorted_words, min(item["x0"] for item in sorted_words)))
        current_words = [word]
        current_y = top

    if current_words:
        sorted_words = sorted(current_words, key=lambda item: item["x0"])
        lines.append((sorted_words, min(item["x0"] for item in sorted_words)))

    return lines


def group_lines_with_text(
    words: list[PDFWord], y_tolerance: float
) -> list[Tuple[list[str], float]]:
    """Group words by line and return only their text."""
    grouped_words = group_words_by_line(words, y_tolerance)
    return [
        ([word["text"] for word in line_words], min_x0)
        for line_words, min_x0 in grouped_words
    ]


def extract_page_lines(
    page: pdfplumber.page.Page,
    y_tolerance: float,
    *,
    use_text_flow: bool = False,
    bottom_margin: float = 0.0,
) -> list[PDFLine]:
    """Extract grouped lines from a PDF page."""
    words = (
        page.extract_words(
            use_text_flow=use_text_flow,
            keep_blank_chars=False,
        )
        or []
    )

    if bottom_margin > 0:
        words = [
            word
            for word in words
            if float(word["top"]) < float(page.height) - bottom_margin
        ]

    return group_words_by_line(words, y_tolerance)


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace into single spaces."""
    return " ".join(text.split())


def join_text(words: list[PDFWord], *, x_until: Optional[float] = None) -> str:
    """Join word text in left-to-right order."""
    tokens: list[str] = []
    for word in words:
        if x_until is not None and float(word["x0"]) >= x_until:
            break
        token = word["text"].strip()
        if token:
            tokens.append(token)
    return normalize_whitespace(" ".join(tokens))


def vertical_center(word: PDFWord) -> float:
    """Return the vertical center of a pdfplumber word box."""
    return (float(word["top"]) + float(word["bottom"])) / 2.0


def cluster_values(values: list[float], tolerance: float) -> list[float]:
    """Cluster close numeric values and return cluster centers."""
    if not values:
        return []

    centers: list[float] = []
    current_cluster = [min(values)]

    for value in sorted(values)[1:]:
        center = sum(current_cluster) / len(current_cluster)
        if abs(value - center) <= tolerance:
            current_cluster.append(value)
            continue

        centers.append(sum(current_cluster) / len(current_cluster))
        current_cluster = [value]

    centers.append(sum(current_cluster) / len(current_cluster))
    return centers


def parse_amount(text: str) -> float:
    """Parse a signed amount token with either decimal style."""
    cleaned = (
        text.strip()
        .replace("€", "")
        .replace("$", "")
        .replace("\u2212", "-")
        .replace("−", "-")
        .replace("+", "")
        .replace(" ", "")
    )

    if cleaned.startswith("."):
        cleaned = f"0{cleaned}"
    if cleaned.startswith("-."):
        cleaned = cleaned.replace("-.", "-0.", 1)

    has_comma = "," in cleaned
    has_dot = "." in cleaned

    if has_comma and has_dot:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif has_comma:
        decimal_part = cleaned.rsplit(",", maxsplit=1)[-1]
        if len(decimal_part) == 2:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    return float(cleaned)


def parse_month_name(month_name: str) -> int:
    """Translate an English month name into a month number."""
    normalized = month_name.strip().lower().rstrip(".")
    if normalized not in MONTH_LOOKUP:
        raise ValueError(f"Unsupported month name: {month_name}")
    return MONTH_LOOKUP[normalized]


def assign_year(
    day: int,
    month: int,
    start_date: dt.date,
    end_date: dt.date,
) -> dt.date:
    """Choose the year that places a day/month inside a statement range."""
    for year in {start_date.year, end_date.year}:
        try:
            candidate = dt.date(year, month, day)
        except ValueError:
            continue

        if start_date <= candidate <= end_date:
            return candidate

    if start_date.year != end_date.year:
        target_year = end_date.year if month < start_date.month else start_date.year
        return dt.date(target_year, month, day)

    return dt.date(start_date.year, month, day)


def write_df(df: pd.DataFrame, out_path: PathLike, fmt: str = "csv") -> None:
    """Write a DataFrame to disk, creating missing parent directories."""
    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    normalized_format = fmt.lower()
    if normalized_format == "csv":
        df.to_csv(destination, index=False)
        return
    if normalized_format in {"xlsx", "excel"}:
        df.to_excel(destination, index=False)
        return
    if normalized_format == "json":
        df.to_json(destination, orient="records", force_ascii=False, indent=2)
        return
    if normalized_format == "parquet":
        df.to_parquet(destination, index=False)
        return

    raise ValueError(f"Unsupported format: {fmt}")
