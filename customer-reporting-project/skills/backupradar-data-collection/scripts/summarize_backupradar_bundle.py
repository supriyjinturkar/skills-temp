from __future__ import annotations

import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
COMMON_LIB_DIR = CURRENT_DIR.parents[2] / "assets"
SOURCE_LIB_DIR = CURRENT_DIR / "lib"
for lib_dir in (str(COMMON_LIB_DIR), str(SOURCE_LIB_DIR)):
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)

from br_io import resolve_run_paths
from compact_source_summary import build_source_summary, parse_summary_args


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_summary_args(argv)
    run_paths = resolve_run_paths(args["run_dir"] or "run")
    output_path = args["output_path"] or str(Path(run_paths["evidence_dir"]) / "backupradar_compact_summary.json")
    section_files = {
        "backup_summary": run_paths["backup_summary_file"],
        "backup_trends": run_paths["backup_trends_file"],
        "backup_exceptions": run_paths["backup_exceptions_file"],
    }
    result = build_source_summary(
        source="backupradar",
        run_root=run_paths["root"],
        bundle_path=run_paths["backupradar_bundle_file"],
        output_path=output_path,
        section_files=section_files,
    )
    sys.stdout.write(f"{json.dumps(result)}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # pragma: no cover
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
