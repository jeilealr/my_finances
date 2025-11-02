"""Extract Payback-style transaction tables via the shared extractor.

This wrapper calls `my_finances.data_extractor.payback.extract_table`.
"""

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd

from my_finances.data_extractor.payback import extract_payback_data


def add_args(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        "Extract a compact transaction-like table from PDF (payback-style)."
    )
    parser.add_argument(
        "--input-pdf",
        required=True,
        help="Input PDF path.",
    )
    parser.add_argument(
        "--pages",
        default="all",
        help="Pages like 'all', '1', '2-4'",
    )
    parser.add_argument(
        "--line-tolerance",
        type=float,
        default=2.6,
        help="Line grouping tolerance (default 2.6)",
    )
    parser.add_argument("--decimal-style", choices=["comma", "dot"], default="comma")
    parser.add_argument(
        "--no-foreign",
        action="store_true",
        help="Do not capture a foreign amount column",
    )
    parser.add_argument(
        "--sort",
        choices=["page", "page+booking"],
        default="page+booking",
        help="Sort order for output rows",
    )
    parser.add_argument(
        "--no-force-negative",
        action="store_true",
        help="Do NOT force negative sign on amounts",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help="Output path (default: alongside PDF with .csv)",
    )
    parser.add_argument(
        "--output-format",
        choices=["csv", "xlsx", "json", "parquet"],
        default="csv",
    )


def run(args: argparse.Namespace) -> Optional[pd.DataFrame]:
    extract_payback_data(
        input_pdf=args.input_pdf,
        pages=args.pages,
        line_tolerance=args.line_tolerance,
        decimal_style=args.decimal_style,
        include_foreign_amount=not args.no_foreign,
        sort=args.sort,
        force_negative=not args.no_force_negative,  # default: force negatives
        output_path=args.output_path,
        output_format=args.output_format,
    )
