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
from lm_pipeline import normalize_logicmonitor_snapshot


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_cli_args(argv)
    run_paths = resolve_run_paths(args["run_dir"])
    context = resolve_logicmonitor_context(load_fleet_customer_context(args["context_path"]))
    snapshot = read_json_file(args["snapshot_path"] or run_paths["logicmonitor_snapshot_file"])
    observability = normalize_logicmonitor_snapshot(context, snapshot)
    output_path = args["output_path"] or run_paths["observability_file"]
    write_json_file(output_path, observability)
    sys.stdout.write(f"{json.dumps({'ok': True, 'output_path': output_path, 'dataset': observability['dataset']})}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # pragma: no cover
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
