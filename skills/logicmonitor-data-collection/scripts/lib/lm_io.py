from __future__ import annotations

import json
from pathlib import Path


def ensure_dir(dir_path: str | Path) -> None:
    Path(dir_path).mkdir(parents=True, exist_ok=True)


def read_json_file(file_path: str | Path):
    return json.loads(Path(file_path).read_text(encoding="utf-8"))


def write_json_file(file_path: str | Path, payload) -> None:
    path = Path(file_path)
    ensure_dir(path.parent)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def resolve_run_paths(run_dir: str | Path = "run") -> dict[str, str]:
    root = str(Path(run_dir).resolve())
    return {
        "root": root,
        "source_snapshots_dir": str(Path(root) / "source_snapshots"),
        "normalized_dir": str(Path(root) / "normalized"),
        "render_dir": str(Path(root) / "render"),
        "evidence_dir": str(Path(root) / "evidence"),
        "customer_context_file": str(Path(root) / "customer_context.json"),
        "logicmonitor_snapshot_file": str(Path(root) / "source_snapshots" / "logicmonitor.json"),
        "observability_file": str(Path(root) / "normalized" / "observability.json"),
        "availability_summary_file": str(Path(root) / "normalized" / "availability_summary.json"),
        "alert_trends_file": str(Path(root) / "normalized" / "alert_trends.json"),
        "resource_health_file": str(Path(root) / "normalized" / "resource_health.json"),
        "logicmonitor_bundle_file": str(Path(root) / "normalized" / "logicmonitor_report_bundle.json"),
    }
