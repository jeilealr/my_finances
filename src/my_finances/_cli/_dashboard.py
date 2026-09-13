"""Launch the interactive Streamlit dashboard."""

from __future__ import annotations

import argparse

from dashboard.cli import main as run_dashboard
from my_finances.data_extractor.pipeline import extract_all_data


def add_args(parser: argparse.ArgumentParser) -> None:
    """Register dashboard CLI arguments and forwarded Streamlit flags."""
    parser.add_argument(
        "--update",
        action="store_true",
        help="Run the full extraction pipeline before launching the dashboard.",
    )
    parser.add_argument(
        "streamlit_args",
        nargs=argparse.REMAINDER,
        help=(
            "Optional arguments forwarded to Streamlit. Prefix them with '--' when "
            "calling through the my_finances CLI."
        ),
    )


def run(args: argparse.Namespace) -> int:
    """Execute the interactive dashboard, optionally refreshing outputs first."""
    if args.update:
        extract_all_data()

    forwarded_args = list(args.streamlit_args)
    if forwarded_args and forwarded_args[0] == "--":
        forwarded_args = forwarded_args[1:]
    return run_dashboard(forwarded_args)
