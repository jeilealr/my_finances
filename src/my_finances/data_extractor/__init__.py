"""Statement extraction routines."""

from .base import BankConfig, BankExportResult
from .payback import extract_payback_data, extract_payback_statement
from .pipeline import export_bank_statements, extract_all_data
from .registry import ACTIVE_BANK_ORDER, BANK_CONFIGS
from .revolut import extract_revolut_data, extract_revolut_statement
from .santander import extract_santander_data, extract_santander_statement

__all__ = [
    "ACTIVE_BANK_ORDER",
    "BANK_CONFIGS",
    "BankConfig",
    "BankExportResult",
    "export_bank_statements",
    "extract_all_data",
    "extract_payback_data",
    "extract_payback_statement",
    "extract_revolut_data",
    "extract_revolut_statement",
    "extract_santander_data",
    "extract_santander_statement",
]
