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

from compact_source_summary import build_source_summary, parse_summary_args
from lm_io import resolve_run_paths


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_summary_args(argv)
    run_paths = resolve_run_paths(args["run_dir"] or "run")
    output_path = args["output_path"] or str(Path(run_paths["evidence_dir"]) / "logicmonitor_compact_summary.json")
    section_files = {
        "availability_summary": run_paths["availability_summary_file"],
        "alert_trends": run_paths["alert_trends_file"],
        "resource_health": run_paths["resource_health_file"],
        "monitoring_coverage": run_paths["monitoring_coverage_file"],
        "website_experience": run_paths["website_experience_file"],
        "platform_assets": run_paths["platform_assets_file"],
        "report_inventory": run_paths["report_inventory_file"],
        "inventory_exceptions": run_paths["inventory_exceptions_file"],
        "root_scope_summary": run_paths["root_scope_summary_file"],
        "device_availability": run_paths["device_availability_file"],
        "cpu_memory_utilization": run_paths["cpu_memory_utilization_file"],
        "disk_capacity_utilization": run_paths["disk_capacity_utilization_file"],
        "network_interface_throughput": run_paths["network_interface_throughput_file"],
    }
    result = build_source_summary(
        source="logicmonitor",
        run_root=run_paths["root"],
        bundle_path=run_paths["logicmonitor_bundle_file"],
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
