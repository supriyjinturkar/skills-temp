from __future__ import annotations

"""
collect_servicenow_snapshot.py

Validates that the agent has already saved the MCP get_customer_data__nexon_csi_
response to run/source_snapshots/servicenow.json.

This script does NOT call the MCP server. The agent must call:
    get_customer_data__nexon_csi_(customer_sys_id=..., period_months=...)
and save the full response to run/source_snapshots/servicenow.json before running this.
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
from sn_pipeline import validate_servicenow_snapshot


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_cli_args(argv)
    run_paths = resolve_run_paths(args["run_dir"])
    context = resolve_servicenow_context(load_fleet_customer_context(args["context_path"]))

    snapshot_path = args["snapshot_path"] or run_paths["servicenow_snapshot_file"]
    if not Path(snapshot_path).exists():
        sys.stderr.write(
            f"ServiceNow snapshot not found at {snapshot_path}.\n"
            "Call get_customer_data__nexon_csi_ via the MCP tool and save the response there first.\n"
        )
        return 1

    snapshot = read_json_file(snapshot_path)
    validation = validate_servicenow_snapshot(snapshot)

    if not validation["valid"]:
        sys.stderr.write(f"Snapshot validation failed: {validation['errors']}\n")
        return 1

    sys.stdout.write(
        f"{json.dumps({'ok': True, 'snapshot_path': snapshot_path, 'dataset': validation['dataset'], 'customer_name': validation['customer_name'], 'customer_sys_id': validation['customer_sys_id']})}\n"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
