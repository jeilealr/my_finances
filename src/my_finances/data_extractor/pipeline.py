"""Batch extraction workflows for all supported statement sources."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from my_finances.common.paths import default_output_root, default_statement_dir
from my_finances.common.utils import collect_files, write_df

from .base import BankExportResult, prepare_transaction_frame
from .revolut import (
    calculate_revolut_subaccount_balances_from_csv,
)
from .registry import ACTIVE_BANK_ORDER, BANK_CONFIGS

logger = logging.getLogger(__name__)


def _resolve_input_path(bank_name: str, input_path: Optional[str | Path]) -> Path:
    """Return the input directory or statement file for one bank."""
    return Path(input_path) if input_path else default_statement_dir(bank_name)


def export_bank_statements(
    bank_name: str,
    *,
    input_path: Optional[str | Path] = None,
    output_root: Optional[str | Path] = None,
    **extractor_kwargs: object,
) -> BankExportResult:
    """Extract and export every statement for one bank."""
    config = BANK_CONFIGS[bank_name]
    source_path = _resolve_input_path(bank_name, input_path)
    output_root_path = Path(output_root) if output_root else default_output_root()
    bank_output_dir = output_root_path / bank_name
    per_statement_dir = bank_output_dir / "statements"

    extracted_frames: list[pd.DataFrame] = []
    balance_summary_rows: list[dict[str, object]] = []
    statement_files = collect_files(source_path, config.file_pattern)

    for statement_file in statement_files:
        try:
            dataframe = config.extractor(statement_file, **extractor_kwargs)
        except Exception as e:
            logger.warning("Skipping %s: %s", statement_file, e)
            continue
        if dataframe.empty:
            logger.info("No rows were extracted from %s.", statement_file)
            continue

        dataframe = prepare_transaction_frame(dataframe)
        per_statement_output = per_statement_dir / f"{statement_file.stem}.csv"
        write_df(dataframe, per_statement_output, "csv")
        extracted_frames.append(dataframe)
        logger.info("Wrote %s rows to %s", len(dataframe), per_statement_output)

        if config.balance_summary_extractor is not None:
            balance_summary_rows.append(
                config.balance_summary_extractor(statement_file)
            )

    combined_output = bank_output_dir / f"{bank_name}_transactions.csv"
    if extracted_frames:
        combined_frame = prepare_transaction_frame(
            pd.concat(extracted_frames, ignore_index=True)
        )
        write_df(combined_frame, combined_output, "csv")
        row_count = len(combined_frame)
    else:
        combined_frame = pd.DataFrame()
        row_count = 0

    balance_summary_frame = pd.DataFrame(balance_summary_rows)
    if not balance_summary_frame.empty:
        balance_summary_output = bank_output_dir / f"{bank_name}_statement_balances.csv"
        write_df(balance_summary_frame, balance_summary_output, "csv")
    else:
        balance_summary_output = None

    if bank_name == "revolut" and combined_output.exists():
        revolut_balance_frame = calculate_revolut_subaccount_balances_from_csv(
            combined_output
        )
        revolut_balance_output = bank_output_dir / "revolut_subaccount_balances.csv"
        write_df(revolut_balance_frame, revolut_balance_output, "csv")
    else:
        revolut_balance_output = None

    return BankExportResult(
        bank=bank_name,
        files_processed=len(statement_files),
        rows_exported=row_count,
        output_path=combined_output,
        dataframe=combined_frame,
        statement_balance_frame=balance_summary_frame,
        statement_balance_output=balance_summary_output,
        revolut_balance_output=revolut_balance_output,
    )


def extract_all_data(
    *,
    output_root: Optional[str | Path] = None,
    statements_root: Optional[str | Path] = None,
    revolut_line_tolerance: float = 2.5,
    santander_line_tolerance: float = 2.5,
) -> pd.DataFrame:
    """Run the active extraction pipeline and write all outputs."""
    output_root_path = Path(output_root) if output_root else default_output_root()
    statements_root_path = Path(statements_root) if statements_root else None

    run_config = {
        "payback": {},
        "revolut": {"line_tolerance": revolut_line_tolerance},
        "santander": {"line_tolerance": santander_line_tolerance},
    }

    summary_rows: list[dict[str, object]] = []
    all_frames: list[pd.DataFrame] = []
    all_statement_balance_frames: list[pd.DataFrame] = []

    for bank_name in ACTIVE_BANK_ORDER:
        bank_input_path = (
            statements_root_path / default_statement_dir(bank_name).name
            if statements_root_path
            else None
        )
        result = export_bank_statements(
            bank_name,
            input_path=bank_input_path,
            output_root=output_root_path,
            **run_config[bank_name],
        )
        summary_rows.append(result.summary_row())
        if not result.dataframe.empty:
            all_frames.append(result.dataframe)
        if not result.statement_balance_frame.empty:
            all_statement_balance_frames.append(result.statement_balance_frame)

    summary_frame = pd.DataFrame(summary_rows)
    write_df(summary_frame, output_root_path / "extraction_summary.csv", "csv")

    if all_statement_balance_frames:
        statement_balance_frame = pd.concat(
            all_statement_balance_frames,
            ignore_index=True,
        )
        write_df(
            statement_balance_frame,
            output_root_path / "statement_balance_summary.csv",
            "csv",
        )

    if not all_frames:
        combined_frame = pd.DataFrame()
    else:
        combined_frame = prepare_transaction_frame(
            pd.concat(all_frames, ignore_index=True)
        )
        write_df(
            combined_frame,
            output_root_path / "combined" / "all_transactions.csv",
            "csv",
        )

    return combined_frame
