from __future__ import annotations

import subprocess
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[2]
TARGET_SCRIPT = PROJECT_ROOT / "skills" / "logicmonitor-data-collection" / "scripts" / "resolve_logicmonitor_scope.py"


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    completed = subprocess.run(
        [sys.executable, str(TARGET_SCRIPT), *argv],
        cwd=str(PROJECT_ROOT),
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
