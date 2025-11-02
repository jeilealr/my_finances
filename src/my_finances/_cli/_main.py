"""Command line interface for my_finances."""

import argparse

from my_finances.common.logger import configure_my_finances_logger

from .. import __version__
from . import (
    _bancolombia,
    _n26,
    _payback,
    _santander,
)


class Formatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    """Custom formatter for argparse with help and raw text."""


def add_command_from_module(subparsers, name, module):
    """Add a subcommand from a given module.

    Parameters
    ----------
    subparsers : subparsers
        Subparser to add the command to.
    name : str
        Name of the command to add.
    module : module
        Module containing the `add_args` and `run` functions defining the command.
    """
    desc = module.__doc__ or ""
    # Use module docstring first line as the `help` shown in the parent parser.
    # If the module has no docstring, fall back to the command name so the
    # subcommand will appear in the top-level help listing.
    kwargs = {"description": desc}
    kwargs["help"] = desc.splitlines()[0] if desc.strip() else name
    parser = subparsers.add_parser(name, formatter_class=Formatter, **kwargs)
    module.add_args(parser)
    parser.set_defaults(func=module.run)


def _get_parser():
    parent_parser = argparse.ArgumentParser(
        prog="my_finances",
        description=__doc__,
        formatter_class=Formatter,
    )

    parent_parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=__version__,
        help="Display version information.",
    )

    sub_help = (
        "All tools are provided as sub-commands. "
        "Please refer to the respective help texts."
    )
    subparsers = parent_parser.add_subparsers(
        title="Available Tools",
        dest="command",
        required=True,
        description=sub_help,
        metavar="",
    )

    # all sub-parsers should be added here
    # documentation taken from docstring of respective cli module (first line summary)
    # module needs two functions: add_args and run
    add_command_from_module(subparsers, "extract_data_bancolombia", _bancolombia)
    add_command_from_module(subparsers, "extract_data_n26", _n26)
    add_command_from_module(subparsers, "extract_data_santander", _santander)
    add_command_from_module(subparsers, "extract_data_payback", _payback)

    # add logging, explicit log levels by name
    parent_parser.add_argument(
        "--log_level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Set the log level explicitly.",
    )
    # option 2 regulation verbosity by -v and -q flags default is INFO
    parent_parser.add_argument(
        "--verbose", "-v", action="count", default=0, help="Increase verbosity"
    )
    parent_parser.add_argument(
        "--quiet",
        "-q",
        action="count",
        default=0,
        help="Reduce verbosity can be repeted e.g. -qq",
    )
    # handle file and terminal output
    parent_parser.add_argument(
        "--log_file", type=str, default=None, help="Generate a log file."
    )
    parent_parser.add_argument(
        "--log_file_level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Set log level for the log file. Defaults to console log level.",
    )
    parent_parser.add_argument(
        "--no_console_output", action="store_true", help="Prohibit console output."
    )

    # return the parser
    return parent_parser


def main(argv=None):
    """Execute main CLI routine.

    Parameters
    ----------
    argv : list of str
        command line arguments, default is None

    Returns
    -------
        result of the called sub-argument routine
    """
    args = _get_parser().parse_args(argv)
    configure_my_finances_logger(
        log_level=args.log_level,
        count_verbose=args.verbose,
        count_quiet=args.quiet,
        log_file=args.log_file,
        log_file_level=args.log_file_level,
        no_colsole_logging=args.no_console_output,
    )
    return args.func(args)
