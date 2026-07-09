from __future__ import annotations

"""
resolve_servicenow_scope.py

Reads the saved MCP lookup response (run/source_snapshots/servicenow_lookup.json)
and writes the resolved sys_id + top candidates to run/resolved_servicenow_scope.json.

The agent must have already called lookup_customer__nexon_csi_ and saved the
response to run/source_snapshots/servicenow_lookup.json before running this script.
"""

import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
LIB_DIR = CURRENT_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from sn_context import load_fleet_customer_context, parse_cli_args
from sn_io import read_json_file, resolve_run_paths, write_json_file
from sn_pipeline import resolve_servicenow_scope_from_lookup


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_cli_args(argv)
    run_paths = resolve_run_paths(args["run_dir"])

    # Verify the lookup snapshot was written by the agent
    lookup_path = run_paths["servicenow_lookup_file"]
    if not Path(lookup_path).exists():
        sys.stderr.write(
            f"Lookup snapshot not found at {lookup_path}.\n"
            "Call lookup_customer__nexon_csi_ via the MCP tool and save the response there first.\n"
        )
        return 1

    lookup_payload = read_json_file(lookup_path)
    resolution = resolve_servicenow_scope_from_lookup(lookup_payload)
    output_path = args["output_path"] or run_paths["resolved_servicenow_scope_file"]
    write_json_file(output_path, resolution)

    sys.stdout.write(
        f"{json.dumps({'ok': True, 'output_path': output_path, 'match_confidence': resolution['match_confidence'], 'sys_id': resolution['resolved_scope']['servicenow']['customer_sys_id']})}\n"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
