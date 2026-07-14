from __future__ import annotations

import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
LIB_DIR = CURRENT_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from br_context import load_fleet_customer_context, parse_cli_args, resolve_backupradar_context
from br_io import read_json_file, resolve_run_paths, write_json_file
from br_pipeline import build_backupradar_artifacts


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_cli_args(argv)
    run_paths = resolve_run_paths(args["run_dir"])
    context = resolve_backupradar_context(load_fleet_customer_context(args["context_path"]))
    snapshot = read_json_file(args["snapshot_path"] or run_paths["backupradar_snapshot_file"])
    backup = read_json_file(args["normalized_path"] or run_paths["backup_file"])
    artifacts = build_backupradar_artifacts(context, snapshot, backup)
    write_json_file(run_paths["backup_summary_file"], artifacts["backup_summary"])
    write_json_file(run_paths["backup_trends_file"], artifacts["backup_trends"])
    write_json_file(run_paths["backup_exceptions_file"], artifacts["backup_exceptions"])
    bundle_path = args["output_path"] or run_paths["backupradar_bundle_file"]
    write_json_file(bundle_path, artifacts["bundle"])
    sys.stdout.write(f"{json.dumps({'ok': True, 'bundle_path': bundle_path, 'dataset': artifacts['bundle']['dataset']})}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # pragma: no cover
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
