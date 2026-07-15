from __future__ import annotations

import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
LIB_DIR = CURRENT_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from nc_context import load_fleet_customer_context, parse_cli_args, resolve_ncentral_context
from nc_io import resolve_run_paths, write_json_file
from nc_pipeline import run_ncentral_pipeline


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_cli_args(argv)
    run_paths = resolve_run_paths(args["run_dir"])
    raw_context = load_fleet_customer_context(args["context_path"])
    context = resolve_ncentral_context(raw_context)
    result = run_ncentral_pipeline(context)
    write_json_file(run_paths["customer_context_file"], raw_context)
    write_json_file(run_paths["ncentral_snapshot_file"], result["snapshot"])
    write_json_file(run_paths["ncentral_normalized_file"], result["normalized"])
    write_json_file(run_paths["ncentral_inventory_summary_file"], result["inventory_summary"])
    write_json_file(run_paths["ncentral_issue_summary_file"], result["issue_summary"])
    write_json_file(run_paths["ncentral_site_rollup_file"], result["site_rollup"])
    write_json_file(run_paths["ncentral_device_health_file"], result["device_health"])
    write_json_file(run_paths["ncentral_custom_property_summary_file"], result["custom_property_summary"])
    write_json_file(run_paths["ncentral_scope_summary_file"], result["scope_summary"])
    write_json_file(run_paths["ncentral_bundle_file"], result["bundle"])
    sys.stdout.write(
        f"{json.dumps({'ok': True, 'run_dir': run_paths['root'], 'outputs': {'snapshot': run_paths['ncentral_snapshot_file'], 'normalized': run_paths['ncentral_normalized_file'], 'bundle': run_paths['ncentral_bundle_file']}})}\n",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # pragma: no cover
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
