"""Shared helpers for CLI subcommands."""

from __future__ import annotations

import argparse

from my_finances.common.paths import default_output_root, default_statement_dir
from my_finances.data_extractor.pipeline import export_bank_statements
from my_finances.data_extractor.registry import BANK_CONFIGS


def add_standard_bank_args(
    parser: argparse.ArgumentParser,
    *,
    bank_name: str,
) -> None:
    """Register the common arguments used by bank extraction commands."""
    config = BANK_CONFIGS[bank_name]
    parser.add_argument(
        "--input-path",
        default=str(default_statement_dir(bank_name)),
        help=f"Input {config.input_description}.",
    )
    parser.add_argument(
        "--output-root",
        default=str(default_output_root()),
        help="Root directory for organized outputs.",
    )
    if config.default_line_tolerance is not None:
        parser.add_argument(
            "--line-tolerance",
            type=float,
            default=config.default_line_tolerance,
            help="Line grouping tolerance used for PDF parsing.",
        )


def run_bank_export(bank_name: str, args: argparse.Namespace) -> None:
    """Execute the shared bank export workflow for a CLI namespace."""
    extractor_kwargs: dict[str, object] = {}
    if hasattr(args, "line_tolerance"):
        extractor_kwargs["line_tolerance"] = args.line_tolerance

    export_bank_statements(
        bank_name,
        input_path=args.input_path,
        output_root=args.output_root,
        **extractor_kwargs,
    )
