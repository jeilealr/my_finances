from __future__ import annotations

from pathlib import Path

import pandas as pd

from my_finances.data_extractor.base import (
    TRANSACTION_OUTPUT_COLUMNS,
    export_statement_data,
    prepare_transaction_frame,
)


def _dummy_extractor(
    statement_path: str | Path,
    **_: object,
) -> pd.DataFrame:
    del statement_path
    return pd.DataFrame(
        [
            {
                "bank": "demo",
                "account": "checking",
                "subaccount": None,
                "date": "2026-03-02",
                "value_date": None,
                "description": "later transaction",
                "amount": -15.0,
                "currency": "EUR",
                "balance": None,
                "notes": None,
                "page": 2,
                "source_file": "statement.pdf",
            },
            {
                "bank": "demo",
                "account": "checking",
                "subaccount": None,
                "date": "2026-03-01",
                "value_date": None,
                "description": "earlier transaction",
                "amount": 25.0,
                "currency": "EUR",
                "balance": None,
                "notes": None,
                "page": 1,
                "source_file": "statement.pdf",
            },
        ]
    )


def test_prepare_transaction_frame_applies_schema_and_sorting() -> None:
    prepared = prepare_transaction_frame(_dummy_extractor("statement.pdf"))

    assert list(prepared.columns) == TRANSACTION_OUTPUT_COLUMNS
    assert prepared["description"].tolist() == [
        "earlier transaction",
        "later transaction",
    ]
    assert str(prepared["page"].dtype) == "Int64"


def test_export_statement_data_writes_the_prepared_frame(tmp_path: Path) -> None:
    output_path = tmp_path / "prepared.csv"

    exported = export_statement_data(
        "statement.pdf",
        extractor=_dummy_extractor,
        output_path=output_path,
    )

    written = pd.read_csv(output_path)
    assert output_path.exists()
    assert len(written) == len(exported)
    assert written["description"].tolist() == [
        "earlier transaction",
        "later transaction",
    ]
