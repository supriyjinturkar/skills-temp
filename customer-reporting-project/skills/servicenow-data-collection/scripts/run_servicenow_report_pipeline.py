from __future__ import annotations

"""
run_servicenow_report_pipeline.py

End-to-end ServiceNow pipeline runner.

Prerequisites (agent must complete these before running this script):
  1. Save lookup_customer__nexon_csi_ response to run/source_snapshots/servicenow_lookup.json
  2. Save get_customer_data__nexon_csi_ response to run/source_snapshots/servicenow.json

This script then:
  - Validates the snapshot
  - Normalizes all CSI data
  - Builds all individual section files
  - Builds the merged servicenow_report_bundle.json
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
from sn_pipeline import (
    build_servicenow_artifacts,
    normalize_servicenow_snapshot,
    run_servicenow_pipeline,
    validate_servicenow_snapshot,
)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_cli_args(argv)
    run_paths = resolve_run_paths(args["run_dir"])
    raw_context = load_fleet_customer_context(args["context_path"])
    context = resolve_servicenow_context(raw_context)

    snapshot_path = args["snapshot_path"] or run_paths["servicenow_snapshot_file"]
    if not Path(snapshot_path).exists():
        sys.stderr.write(
            f"ServiceNow snapshot not found at {snapshot_path}.\n"
            "The agent must call get_customer_data__nexon_csi_ and save the response there first.\n"
        )
        return 1

    snapshot = read_json_file(snapshot_path)

    # Validate
    validation = validate_servicenow_snapshot(snapshot)
    if not validation["valid"]:
        sys.stderr.write(f"Snapshot validation failed: {validation['errors']}\n")
        return 1

    # Run full pipeline
    result = run_servicenow_pipeline(context, snapshot)

    # Write normalized blob
    normalized_path = str(Path(run_paths["normalized_dir"]) / "sn_normalized.json")
    write_json_file(normalized_path, result["normalized"])

    # Write individual section files
    write_json_file(run_paths["sn_ticket_summary_file"], result["ticket_summary"])
    write_json_file(run_paths["sn_incident_summary_file"], result["incident_summary"])
    write_json_file(run_paths["sn_request_summary_file"], result["request_summary"])
    write_json_file(run_paths["sn_change_summary_file"], result["change_summary"])
    write_json_file(run_paths["sn_problem_summary_file"], result["problem_summary"])
    write_json_file(run_paths["sn_sla_summary_file"], result["sla_summary"])
    write_json_file(run_paths["sn_sla_trends_file"], result["sla_trends"])
    write_json_file(run_paths["sn_aged_backlog_file"], result["aged_backlog"])
    write_json_file(run_paths["sn_dimensions_file"], result["dimensions"])
    write_json_file(run_paths["sn_fcr_file"], result["fcr"])
    write_json_file(run_paths["sn_critical_incidents_file"], result["critical_incidents"])

    # Write customer context copy
    write_json_file(run_paths["customer_context_file"], raw_context)

    # Write merged bundle
    bundle_path = args["output_path"] or run_paths["servicenow_bundle_file"]
    write_json_file(bundle_path, result["bundle"])

    sys.stdout.write(
        f"{json.dumps({'ok': True, 'run_dir': run_paths['root'], 'outputs': {'snapshot': snapshot_path, 'normalized': normalized_path, 'bundle': bundle_path}})}\n"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
