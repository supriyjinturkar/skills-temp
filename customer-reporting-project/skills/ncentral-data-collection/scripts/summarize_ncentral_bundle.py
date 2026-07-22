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
from nc_io import resolve_run_paths


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_summary_args(argv)
    run_paths = resolve_run_paths(args["run_dir"] or "run")
    output_path = args["output_path"] or str(Path(run_paths["evidence_dir"]) / "ncentral_compact_summary.json")
    section_files = {
        "ncentral_inventory_summary": run_paths["ncentral_inventory_summary_file"],
        "ncentral_issue_summary": run_paths["ncentral_issue_summary_file"],
        "ncentral_site_rollup": run_paths["ncentral_site_rollup_file"],
        "ncentral_device_health": run_paths["ncentral_device_health_file"],
        "ncentral_custom_property_summary": run_paths["ncentral_custom_property_summary_file"],
        "ncentral_scope_summary": run_paths["ncentral_scope_summary_file"],
    }
    result = build_source_summary(
        source="ncentral",
        run_root=run_paths["root"],
        bundle_path=run_paths["ncentral_bundle_file"],
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
