""""""

import argparse

from my_finances.data_extractor.bancolombia import extract_data_as_df


def add_args(parser: argparse.ArgumentParser) -> None:
    """Add all specific flags and options to the given subparser."""

    parser.description = "Configures and executes mHM."
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
    """
    """

    extract_data_as_df(
        input_pdf=args.input_pdf,
        pages=args.pages,
        line_tolerance=args.line_tolerance,
        output_path=args.output_path,
        output_format=args.output_format,
    )
