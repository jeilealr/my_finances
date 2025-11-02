"""Extract N26 PDF statements into a DataFrame and save it.

This subcommand wraps `my_finances.data_extractor.n26.extract_n26_data` so it can be
used from the unified `my_finances` CLI.
"""

import argparse

from my_finances.data_extractor.n26 import extract_n26_data


def add_args(parser: argparse.ArgumentParser) -> None:
    parser.description = "Extract N26 statement transactions to a table."
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
    parser.add_argument(
        "--sort",
        choices=["page", "page+booking"],
        default="page+booking",
        help="Sort order for output rows",
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


def run(args: argparse.Namespace):
    extract_n26_data(
        input_pdf=args.input_pdf,
        pages=args.pages,
        line_tolerance=args.line_tolerance,
        sort=args.sort,
        output_path=args.output_path,
        output_format=args.output_format,
    )
