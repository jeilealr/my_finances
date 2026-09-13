from __future__ import annotations

from pathlib import Path

import pytest

from my_finances.common import paths


def test_discover_workspace_paths_respects_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    statements_root = tmp_path / "statements"
    output_root = tmp_path / "outputs"

    paths.discover_workspace_paths.cache_clear()
    monkeypatch.setenv(paths.WORKSPACE_ROOT_ENV, str(workspace_root))
    monkeypatch.setenv(paths.STATEMENTS_ROOT_ENV, str(statements_root))
    monkeypatch.setenv(paths.OUTPUT_ROOT_ENV, str(output_root))

    resolved = paths.discover_workspace_paths()

    assert resolved.workspace_root == workspace_root
    assert resolved.statements_root == statements_root
    assert resolved.output_root == output_root
    assert resolved.statement_dir("payback") == (
        statements_root / "payback_bank_statements"
    )

    paths.discover_workspace_paths.cache_clear()


def test_statement_dir_rejects_unknown_bank() -> None:
    paths.discover_workspace_paths.cache_clear()
    resolved = paths.discover_workspace_paths()

    with pytest.raises(ValueError, match="Unsupported bank name"):
        resolved.statement_dir("unknown_bank")
