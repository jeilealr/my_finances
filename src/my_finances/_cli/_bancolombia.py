"""Extract Bancolombia PDF statements into a DataFrame and save it.

This CLI subcommand (registered as ``extract_data_bancolombia``) parses
Bancolombia "Movimientos: Cuentas" PDF statements and produces a
standardized table with the columns: `page`, `date`, `description`,
`reference`, and `amount_cop`.

Usage (as CLI):
    my_finances extract_data_bancolombia --input-pdf path/to/file.pdf

See `my_finances.data_extractor.bancolombia` for implementation details.
"""

import argparse

from my_finances.data_extractor.bancolombia import extract_bancolombia_data


def add_args(parser: argparse.ArgumentParser) -> None:
    parser.description = "Extract Bancolombia statement transactions to a table."
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


def run(args: argparse.Namespace):
    extract_bancolombia_data(
        input_pdf=args.input_pdf,
        line_tolerance=args.line_tolerance,
        output_path=args.output_path,
    )
