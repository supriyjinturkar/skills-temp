from __future__ import annotations

import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
LIB_DIR = CURRENT_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from nc_context import load_fleet_customer_context, parse_cli_args, resolve_ncentral_context
from nc_io import read_json_file, resolve_run_paths, write_json_file
from nc_pipeline import build_ncentral_artifacts


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_cli_args(argv)
    run_paths = resolve_run_paths(args["run_dir"])
    context = resolve_ncentral_context(load_fleet_customer_context(args["context_path"]))
    snapshot = read_json_file(args["snapshot_path"] or run_paths["ncentral_snapshot_file"])
    normalized = read_json_file(args["normalized_path"] or run_paths["ncentral_normalized_file"])
    artifacts = build_ncentral_artifacts(context, snapshot, normalized)
    write_json_file(run_paths["ncentral_inventory_summary_file"], artifacts["inventory_summary"])
    write_json_file(run_paths["ncentral_issue_summary_file"], artifacts["issue_summary"])
    write_json_file(run_paths["ncentral_site_rollup_file"], artifacts["site_rollup"])
    write_json_file(run_paths["ncentral_device_health_file"], artifacts["device_health"])
    write_json_file(run_paths["ncentral_custom_property_summary_file"], artifacts["custom_property_summary"])
    write_json_file(run_paths["ncentral_scope_summary_file"], artifacts["scope_summary"])
    bundle_path = args["output_path"] or run_paths["ncentral_bundle_file"]
    write_json_file(bundle_path, artifacts["bundle"])
    sys.stdout.write(f"{json.dumps({'ok': True, 'bundle_path': bundle_path, 'dataset': artifacts['bundle']['dataset']})}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # pragma: no cover
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
