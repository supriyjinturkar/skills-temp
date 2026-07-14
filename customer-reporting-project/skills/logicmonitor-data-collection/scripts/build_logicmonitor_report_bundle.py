from __future__ import annotations

import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
LIB_DIR = CURRENT_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from lm_context import load_fleet_customer_context, parse_cli_args, resolve_logicmonitor_context
from lm_io import read_json_file, resolve_run_paths, write_json_file
from lm_pipeline import build_logicmonitor_artifacts


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_cli_args(argv)
    run_paths = resolve_run_paths(args["run_dir"])
    context = resolve_logicmonitor_context(load_fleet_customer_context(args["context_path"]))
    snapshot = read_json_file(args["snapshot_path"] or run_paths["logicmonitor_snapshot_file"])
    observability = read_json_file(args["normalized_path"] or run_paths["observability_file"])
    artifacts = build_logicmonitor_artifacts(context, snapshot, observability)
    write_json_file(run_paths["availability_summary_file"], artifacts["availability_summary"])
    write_json_file(run_paths["alert_trends_file"], artifacts["alert_trends"])
    write_json_file(run_paths["resource_health_file"], artifacts["resource_health"])
    write_json_file(run_paths["monitoring_coverage_file"], artifacts["monitoring_coverage"])
    write_json_file(run_paths["website_experience_file"], artifacts["website_experience"])
    write_json_file(run_paths["platform_assets_file"], artifacts["platform_assets"])
    write_json_file(run_paths["report_inventory_file"], artifacts["report_inventory"])
    write_json_file(run_paths["inventory_exceptions_file"], artifacts["inventory_exceptions"])
    write_json_file(run_paths["root_scope_summary_file"], artifacts["root_scope_summary"])
    write_json_file(run_paths["device_availability_file"], artifacts["device_availability"])
    write_json_file(run_paths["cpu_memory_utilization_file"], artifacts["cpu_memory_utilization"])
    write_json_file(run_paths["disk_capacity_utilization_file"], artifacts["disk_capacity_utilization"])
    write_json_file(run_paths["network_interface_throughput_file"], artifacts["network_interface_throughput"])
    bundle_path = args["output_path"] or run_paths["logicmonitor_bundle_file"]
    write_json_file(bundle_path, artifacts["bundle"])
    sys.stdout.write(f"{json.dumps({'ok': True, 'bundle_path': bundle_path, 'dataset': artifacts['bundle']['dataset']})}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # pragma: no cover
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
