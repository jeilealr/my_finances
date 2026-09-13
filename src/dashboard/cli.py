"""CLI launcher for the interactive financial dashboard."""

from __future__ import annotations

import subprocess
import sys
from os import environ, pathsep
from pathlib import Path
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the Streamlit dashboard with any forwarded Streamlit flags."""
    app_path = Path(__file__).with_name("app.py")
    src_root = app_path.parents[1]
    forwarded_args = list(argv) if argv is not None else sys.argv[1:]
    python_path_parts = [str(src_root)]
    if environ.get("PYTHONPATH"):
        python_path_parts.append(environ["PYTHONPATH"])

    environment = dict(environ)
    environment["PYTHONPATH"] = pathsep.join(python_path_parts)
    command = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    command.extend(forwarded_args)
    return subprocess.call(command, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
