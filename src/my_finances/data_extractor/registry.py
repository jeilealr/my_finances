"""Registry of supported bank extractors."""

from __future__ import annotations

import logging

from .base import BankConfig
from .payback import extract_payback_statement
from .revolut import extract_revolut_statement
from .santander import extract_santander_statement, extract_santander_statement_balances

_logger = logging.getLogger(__name__)

BANK_CONFIGS: dict[str, BankConfig] = {}

try:
    from .bancolombia import (
        extract_bancolombia_statement,
        extract_bancolombia_statement_balances,
    )

    BANK_CONFIGS["bancolombia"] = BankConfig(
        bank_name="bancolombia",
        file_pattern="*.pdf",
        input_description="PDF file or directory",
        extractor=extract_bancolombia_statement,
        balance_summary_extractor=extract_bancolombia_statement_balances,
        default_line_tolerance=2.6,
    )
except ImportError:
    _logger.warning("Bancolombia extractor could not be imported; skipping registration.")

BANK_CONFIGS["payback"] = BankConfig(
    bank_name="payback",
    file_pattern="*.csv",
    input_description="CSV file or directory",
    extractor=extract_payback_statement,
)
BANK_CONFIGS["revolut"] = BankConfig(
    bank_name="revolut",
    file_pattern="*.pdf",
    input_description="PDF file or directory",
    extractor=extract_revolut_statement,
    default_line_tolerance=2.5,
)
BANK_CONFIGS["santander"] = BankConfig(
    bank_name="santander",
    file_pattern="*.pdf",
    input_description="PDF file or directory",
    extractor=extract_santander_statement,
    balance_summary_extractor=extract_santander_statement_balances,
    default_line_tolerance=2.5,
)

ACTIVE_BANK_ORDER = ("payback", "revolut", "santander")
