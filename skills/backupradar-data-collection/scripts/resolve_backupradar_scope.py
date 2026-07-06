from __future__ import annotations

import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
LIB_DIR = CURRENT_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from br_context import load_fleet_customer_context, parse_cli_args, resolve_backupradar_lookup_context
from br_io import resolve_run_paths, write_json_file
from br_pipeline import resolve_backupradar_scope_by_company


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_cli_args(argv)
    run_paths = resolve_run_paths(args["run_dir"])
    context = resolve_backupradar_lookup_context(load_fleet_customer_context(args["context_path"]))
    resolution = resolve_backupradar_scope_by_company(context)
    output_path = args["output_path"] or str(Path(run_paths["root"]) / "resolved_backupradar_scope.json")
    write_json_file(output_path, resolution)
    sys.stdout.write(
        f"{json.dumps({'ok': True, 'output_path': output_path, 'match_confidence': resolution['match_confidence']})}\n",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # pragma: no cover
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
