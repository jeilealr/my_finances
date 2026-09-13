"""Run every configured extractor and write organized outputs."""

from __future__ import annotations

import argparse

from my_finances.common.paths import default_output_root, default_statements_root
from my_finances.data_extractor.pipeline import extract_all_data
from my_finances.data_extractor.registry import BANK_CONFIGS


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register CLI arguments for the batch extraction workflow."""
    parser.add_argument(
        "--statements-root",
        default=str(default_statements_root()),
        help="Root directory containing all statement-source folders.",
    )
    parser.add_argument(
        "--output-root",
        default=str(default_output_root()),
        help="Root directory for organized outputs.",
    )
    parser.add_argument(
        "--santander-line-tolerance",
        type=float,
        default=BANK_CONFIGS["santander"].default_line_tolerance,
        help="Line grouping tolerance for Santander PDFs.",
    )
    parser.add_argument(
        "--revolut-line-tolerance",
        type=float,
        default=BANK_CONFIGS["revolut"].default_line_tolerance,
        help="Line grouping tolerance for Revolut PDFs.",
    )


def run(args: argparse.Namespace) -> None:
    """Execute the full extraction workflow."""
    extract_all_data(
        output_root=args.output_root,
        statements_root=args.statements_root,
        santander_line_tolerance=args.santander_line_tolerance,
        revolut_line_tolerance=args.revolut_line_tolerance,
    )
