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
        "--line-tolerance",
        type=float,
        default=2.6,
        help="Line grouping tolerance (default 2.6)",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help="Output path (default: alongside PDF with .csv)",
    )


def run(args: argparse.Namespace) -> Optional[pd.DataFrame]:
    extract_payback_data(
        input_pdf=args.input_pdf,
        line_tolerance=args.line_tolerance,
        output_path=args.output_path,
    )
