"""HydroLand entry‐point and namespace package.

.. toctree::
   :hidden:

   self

Subpackages
===========

Built-in processing and tool functions.

.. autosummary::
   :toctree: api
   :caption: Subpackages

   model
   indicators
   common
   dask
"""

try:
    from ._version import __version__
except ModuleNotFoundError:
    __version__ = "1.2.0"

from . import common, dask, indicators, data_extractor

__all__ = ["__version__", "data_extractor", "indicators", "common", "dask"]
