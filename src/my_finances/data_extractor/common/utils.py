import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path
from contextlib import ExitStack, contextmanager

import pandas as pd
import pdfplumber


# Initialize logging
logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


def _expand_pdf_paths(path: PathLike) -> list[Path]:
    """
    Expand a single PDF path, a directory, or a glob pattern into concrete PDF files.

    Accepts:
      - "/x/y/file.pdf"
      - "/x/y/dir/"            -> all *.pdf in that dir
      - "/x/y/*.pdf"
      - "/x/y/**/*.pdf"        -> recursive
    """
    p = Path(path)

    # Case 1: It's an existing directory -> read all PDFs in it (non-recursive).
    if p.exists() and p.is_dir():
        logger.info("Existing directory, reading all PDF files.")
        return sorted([f for f in p.glob("*.pdf") if f.is_file()])

    # Case 2: It's an existing file -> must be a PDF.
    if p.exists() and p.is_file():
        if p.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF file: {p}")
        logger.info("Reading single PDF file.")
        return [p]

    # Case 3: It doesn't exist as-is -> treat as glob pattern.
    # Use Path().glob on the pattern. This handles *, ?, and **.
    # If the pattern is absolute, anchor the glob at the filesystem root.
    pattern = str(p)
    if p.is_absolute():
        root = Path(p.anchor)  # e.g. "/" on Unix, "C:\\" on Windows
        rel_pattern = pattern[len(p.anchor) :].lstrip(
            "\\/"
        )  # pattern relative to anchor
        matches = root.glob(rel_pattern)
    else:
        matches = Path().glob(pattern)
    logger.info("Expanding glob pattern to read multiple PDF files, found matches.")

    pdfs = sorted([m for m in matches if m.is_file() and m.suffix.lower() == ".pdf"])
    if not pdfs:
        raise FileNotFoundError(f"No PDF files matched: {path}")
    return pdfs


@contextmanager
def read_pdfs(path: PathLike):
    pdf_paths = _expand_pdf_paths(path)
    with ExitStack() as stack:
        pdfs = [stack.enter_context(pdfplumber.open(str(p))) for p in pdf_paths]
        yield pdfs


def pages_list(spec: str, total: int) -> List[int]:
    """Expand page specs like 'all' or '1,3-5' into a sorted list of ints."""
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
    return out


def group_words_by_line(
    words: List[Dict[str, Any]], y_tol: float
) -> List[Tuple[List[Dict[str, Any]], float]]:
    """Group pdfplumber word dicts into lines by top position.

    Returns a list of tuples: (line_words, min_x0).
    """
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
            cur_sorted = sorted(cur, key=lambda t: t["x0"])  # left→right
            lines.append((cur_sorted, min(t["x0"] for t in cur_sorted)))
            cur = [w]
            cur_y = y
    if cur:
        cur_sorted = sorted(cur, key=lambda t: t["x0"])
        lines.append((cur_sorted, min(t["x0"] for t in cur_sorted)))
    return lines


def join_text(words: List[Dict[str, Any]], *, x_until: Optional[float] = None) -> str:
    toks: List[str] = []
    for w in words:
        if x_until is not None and w["x0"] >= x_until:
            break
        s = w["text"].strip()
        if s:
            toks.append(s)
    return " ".join(toks).strip()


def write_df(df: pd.DataFrame, out_path: Path, fmt: str) -> None:
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
