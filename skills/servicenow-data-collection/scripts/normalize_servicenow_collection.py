from __future__ import annotations

"""
normalize_servicenow_collection.py

Reads the saved ServiceNow snapshot (run/source_snapshots/servicenow.json)
and produces the fully normalized output (run/normalized/sn_*.json files).
"""

import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
LIB_DIR = CURRENT_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from sn_context import load_fleet_customer_context, parse_cli_args, resolve_servicenow_context
from sn_io import read_json_file, resolve_run_paths, write_json_file
from sn_pipeline import normalize_servicenow_snapshot


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_cli_args(argv)
    run_paths = resolve_run_paths(args["run_dir"])
    context = resolve_servicenow_context(load_fleet_customer_context(args["context_path"]))

    snapshot_path = args["snapshot_path"] or run_paths["servicenow_snapshot_file"]
    snapshot = read_json_file(snapshot_path)

    normalized = normalize_servicenow_snapshot(context, snapshot)
    output_path = args["output_path"] or run_paths["sn_ticket_summary_file"].replace(
        "sn_ticket_summary.json", "sn_normalized.json"
    )
    # Write the full normalized blob (used by build step)
    normalized_path = str(Path(run_paths["normalized_dir"]) / "sn_normalized.json")
    write_json_file(normalized_path, normalized)

    sys.stdout.write(
        f"{json.dumps({'ok': True, 'output_path': normalized_path, 'dataset': normalized['dataset']})}\n"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
