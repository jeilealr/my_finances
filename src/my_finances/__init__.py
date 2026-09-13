"""Top-level package for personal finance extraction and analysis tools."""

try:
    from ._version import __version__
except ModuleNotFoundError:
    __version__ = "1.0.0"

from . import common, data_extractor

__all__ = [
    "__version__",
    "data_extractor",
    "common",
]
