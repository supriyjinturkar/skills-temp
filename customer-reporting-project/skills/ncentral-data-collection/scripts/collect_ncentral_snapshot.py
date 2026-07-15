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
from nc_pipeline import collect_ncentral_snapshot


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_cli_args(argv)
    run_paths = resolve_run_paths(args["run_dir"])
    context = resolve_ncentral_context(load_fleet_customer_context(args["context_path"]))
    snapshot = collect_ncentral_snapshot(context)
    output_path = args["output_path"] or run_paths["ncentral_snapshot_file"]
    write_json_file(output_path, snapshot)
    sys.stdout.write(f"{json.dumps({'ok': True, 'output_path': output_path, 'dataset': snapshot['dataset']})}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # pragma: no cover
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
