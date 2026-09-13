"""Command line interface for my_finances."""

from __future__ import annotations

import argparse

from my_finances.common.logger import configure_my_finances_logger

from .. import __version__
from . import _dashboard, _extract_all, _payback, _revolut, _santander

COMMAND_MODULES = (
    ("extract_all_data", _extract_all),
    ("extract_data_santander", _santander),
    ("extract_data_payback", _payback),
    ("extract_data_revolut", _revolut),
    ("dashboard", _dashboard),
)


class Formatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawDescriptionHelpFormatter,
):
    """Custom formatter for argparse help output."""


def add_command_from_module(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    module: object,
) -> None:
    """Add one CLI subcommand from a module."""
    description = module.__doc__ or ""
    parser = subparsers.add_parser(
        name,
        formatter_class=Formatter,
        description=description,
        help=description.splitlines()[0] if description.strip() else name,
    )
    module.add_args(parser)
    parser.set_defaults(func=module.run)


def _get_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="my_finances",
        description=__doc__,
        formatter_class=Formatter,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=__version__,
        help="Display version information.",
    )

    subparsers = parser.add_subparsers(
        title="Available Tools",
        dest="command",
        required=True,
        description="All tools are provided as subcommands.",
        metavar="",
    )

    for command_name, module in COMMAND_MODULES:
        add_command_from_module(subparsers, command_name, module)

    parser.add_argument(
        "--log_level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Set the log level explicitly.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity.",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="count",
        default=0,
        help="Reduce verbosity. Repeat to quiet further.",
    )
    parser.add_argument(
        "--log_file",
        type=str,
        default=None,
        help="Write log messages to a file.",
    )
    parser.add_argument(
        "--log_file_level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Set the log level for the log file.",
    )
    parser.add_argument(
        "--no_console_output",
        action="store_true",
        help="Disable console logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> object:
    """Run the CLI."""
    args = _get_parser().parse_args(argv)
    configure_my_finances_logger(
        log_level=args.log_level,
        count_verbose=args.verbose,
        count_quiet=args.quiet,
        log_file=args.log_file,
        log_file_level=args.log_file_level,
        no_console_logging=args.no_console_output,
    )
    return args.func(args)
