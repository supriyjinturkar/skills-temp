from __future__ import annotations

"""
build_servicenow_report_bundle.py

Reads the normalized ServiceNow data (run/normalized/sn_normalized.json)
and produces all individual section files plus the final merged bundle.
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
from sn_pipeline import build_servicenow_artifacts


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_cli_args(argv)
    run_paths = resolve_run_paths(args["run_dir"])
    context = resolve_servicenow_context(load_fleet_customer_context(args["context_path"]))

    normalized_path = args["normalized_path"] or str(
        Path(run_paths["normalized_dir"]) / "sn_normalized.json"
    )
    normalized = read_json_file(normalized_path)

    artifacts = build_servicenow_artifacts(context, normalized)

    # Write individual section files
    write_json_file(run_paths["sn_ticket_summary_file"], artifacts["ticket_summary"])
    write_json_file(run_paths["sn_incident_summary_file"], artifacts["incident_summary"])
    write_json_file(run_paths["sn_request_summary_file"], artifacts["request_summary"])
    write_json_file(run_paths["sn_change_summary_file"], artifacts["change_summary"])
    write_json_file(run_paths["sn_problem_summary_file"], artifacts["problem_summary"])
    write_json_file(run_paths["sn_sla_summary_file"], artifacts["sla_summary"])
    write_json_file(run_paths["sn_sla_trends_file"], artifacts["sla_trends"])
    write_json_file(run_paths["sn_aged_backlog_file"], artifacts["aged_backlog"])
    write_json_file(run_paths["sn_dimensions_file"], artifacts["dimensions"])
    write_json_file(run_paths["sn_fcr_file"], artifacts["fcr"])
    write_json_file(run_paths["sn_critical_incidents_file"], artifacts["critical_incidents"])

    # Write merged bundle
    bundle_path = args["output_path"] or run_paths["servicenow_bundle_file"]
    write_json_file(bundle_path, artifacts["bundle"])

    sys.stdout.write(
        f"{json.dumps({'ok': True, 'bundle_path': bundle_path, 'dataset': artifacts['bundle']['dataset']})}\n"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
