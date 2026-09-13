"""Extract Bancolombia statements into organized CSV outputs."""

from __future__ import annotations

import argparse

from ._shared import add_standard_bank_args, run_bank_export

BANK_NAME = "bancolombia"


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register CLI arguments for Bancolombia extraction."""
    add_standard_bank_args(parser, bank_name=BANK_NAME)


def run(args: argparse.Namespace) -> None:
    """Execute the Bancolombia extraction workflow."""
    run_bank_export(BANK_NAME, args)
