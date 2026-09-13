"""Path helpers for local statement and output directories."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

STATEMENT_DIRECTORIES = {
    "bancolombia": "bancolombia_bank_statements",
    "payback": "payback_bank_statements",
    "revolut": "revolut_bank_statements",
    "santander": "santander_bank_statements",
}

WORKSPACE_ROOT_ENV = "MY_FINANCES_WORKSPACE_ROOT"
STATEMENTS_ROOT_ENV = "MY_FINANCES_STATEMENTS_ROOT"
OUTPUT_ROOT_ENV = "MY_FINANCES_OUTPUT_ROOT"


@dataclass(frozen=True)
class WorkspacePaths:
    """Resolved filesystem locations used across the project.

    Environment variables are supported so local development and automation can
    point to different data directories without changing code.
    """

    repository_root: Path
    workspace_root: Path
    statements_root: Path
    output_root: Path

    def statement_dir(self, bank_name: str) -> Path:
        """Return the statement directory for one supported bank."""
        try:
            folder_name = STATEMENT_DIRECTORIES[bank_name]
        except KeyError as error:
            available = ", ".join(sorted(STATEMENT_DIRECTORIES))
            raise ValueError(
                f"Unsupported bank name '{bank_name}'. Expected one of: {available}"
            ) from error
        return self.statements_root / folder_name


def _resolve_path(value: str | Path) -> Path:
    """Expand ``~`` and return a normalized path object."""
    return Path(value).expanduser()


@lru_cache(maxsize=1)
def discover_workspace_paths() -> WorkspacePaths:
    """Discover the repository, workspace, statement, and output roots."""
    repository = Path(__file__).resolve().parents[3]
    workspace = _resolve_path(os.environ.get(WORKSPACE_ROOT_ENV, repository.parent))
    statements_root = _resolve_path(
        os.environ.get(STATEMENTS_ROOT_ENV, workspace / "pdf_statements")
    )
    output_root = _resolve_path(os.environ.get(OUTPUT_ROOT_ENV, workspace / "outputs"))
    return WorkspacePaths(
        repository_root=repository,
        workspace_root=workspace,
        statements_root=statements_root,
        output_root=output_root,
    )


def repository_root() -> Path:
    """Return the package repository root."""
    return discover_workspace_paths().repository_root


def workspace_root() -> Path:
    """Return the shared finances workspace root."""
    return discover_workspace_paths().workspace_root


def default_statements_root() -> Path:
    """Return the default statements directory."""
    return discover_workspace_paths().statements_root


def default_output_root() -> Path:
    """Return the default output directory."""
    return discover_workspace_paths().output_root


def default_statement_dir(bank_name: str) -> Path:
    """Return the default input directory for a specific bank."""
    return discover_workspace_paths().statement_dir(bank_name)
