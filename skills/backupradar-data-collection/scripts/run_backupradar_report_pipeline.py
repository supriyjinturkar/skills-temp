from __future__ import annotations

import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
LIB_DIR = CURRENT_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from br_context import load_fleet_customer_context, parse_cli_args, resolve_backupradar_context
from br_io import resolve_run_paths, write_json_file
from br_pipeline import run_backupradar_pipeline


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_cli_args(argv)
    run_paths = resolve_run_paths(args["run_dir"])
    raw_context = load_fleet_customer_context(args["context_path"])
    context = resolve_backupradar_context(raw_context)
    result = run_backupradar_pipeline(context)
    write_json_file(run_paths["customer_context_file"], raw_context)
    write_json_file(run_paths["backupradar_snapshot_file"], result["snapshot"])
    write_json_file(run_paths["backup_file"], result["backup"])
    write_json_file(run_paths["backup_summary_file"], result["backup_summary"])
    write_json_file(run_paths["backup_trends_file"], result["backup_trends"])
    write_json_file(run_paths["backup_exceptions_file"], result["backup_exceptions"])
    write_json_file(run_paths["backupradar_bundle_file"], result["bundle"])
    sys.stdout.write(
        f"{json.dumps({'ok': True, 'run_dir': run_paths['root'], 'outputs': {'snapshot': run_paths['backupradar_snapshot_file'], 'backup': run_paths['backup_file'], 'bundle': run_paths['backupradar_bundle_file']}})}\n",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # pragma: no cover
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
