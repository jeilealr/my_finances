"""Extract Santander/Girokonto-style statements via the shared extractor.

Wraps `my_finances.data_extractor.santander.extract` for use from the
unified `my_finances` CLI.
"""

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd

from my_finances.data_extractor.santander import extract as extract_santander_data


def add_args(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        "Extract Santander/Girokonto statement transactions to a table."
    )
    parser.add_argument("--input-pdf", required=True, help="Input PDF path.")
    parser.add_argument("--pages", default="all", help="Pages like 'all', '1', '2-4'")
    parser.add_argument(
        "--line-tolerance",
        type=float,
        default=2.5,
        help="Line grouping tolerance (default 2.5)",
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
    extract_santander_data(
        input_pdf=args.input_pdf,
        pages=args.pages,
        line_tolerance=args.line_tolerance,
        output_path=args.output_path,
        output_format=args.output_format,
    )
