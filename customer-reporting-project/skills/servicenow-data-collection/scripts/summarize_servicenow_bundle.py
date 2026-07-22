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
from sn_io import resolve_run_paths


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_summary_args(argv)
    run_paths = resolve_run_paths(args["run_dir"] or "run")
    output_path = args["output_path"] or str(Path(run_paths["evidence_dir"]) / "servicenow_compact_summary.json")
    section_files = {
        "sn_ticket_summary": run_paths["sn_ticket_summary_file"],
        "sn_incident_summary": run_paths["sn_incident_summary_file"],
        "sn_request_summary": run_paths["sn_request_summary_file"],
        "sn_change_summary": run_paths["sn_change_summary_file"],
        "sn_problem_summary": run_paths["sn_problem_summary_file"],
        "sn_sla_summary": run_paths["sn_sla_summary_file"],
        "sn_sla_trends": run_paths["sn_sla_trends_file"],
        "sn_aged_backlog": run_paths["sn_aged_backlog_file"],
        "sn_dimensions": run_paths["sn_dimensions_file"],
        "sn_fcr": run_paths["sn_fcr_file"],
        "sn_critical_incidents": run_paths["sn_critical_incidents_file"],
    }
    result = build_source_summary(
        source="servicenow",
        run_root=run_paths["root"],
        bundle_path=run_paths["servicenow_bundle_file"],
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
