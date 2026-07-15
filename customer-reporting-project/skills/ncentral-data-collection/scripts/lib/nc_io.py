from __future__ import annotations

import json
from pathlib import Path


def ensure_dir(dir_path: str | Path) -> None:
    Path(dir_path).mkdir(parents=True, exist_ok=True)


def read_json_file(file_path: str | Path):
    path = Path(file_path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Expected input file not found: {path}. "
            "Check that the previous pipeline step completed successfully and wrote this file."
        ) from None
    except PermissionError as exc:
        raise PermissionError(f"Cannot read file (permission denied): {path}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise json.JSONDecodeError(
            f"File is not valid JSON: {path} - {exc.msg}",
            exc.doc,
            exc.pos,
        ) from exc


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
        "ncentral_snapshot_file": str(Path(root) / "source_snapshots" / "ncentral.json"),
        "resolved_ncentral_scope_file": str(Path(root) / "resolved_ncentral_scope.json"),
        "ncentral_normalized_file": str(Path(root) / "normalized" / "ncentral_normalized.json"),
        "ncentral_inventory_summary_file": str(Path(root) / "normalized" / "ncentral_inventory_summary.json"),
        "ncentral_issue_summary_file": str(Path(root) / "normalized" / "ncentral_issue_summary.json"),
        "ncentral_site_rollup_file": str(Path(root) / "normalized" / "ncentral_site_rollup.json"),
        "ncentral_device_health_file": str(Path(root) / "normalized" / "ncentral_device_health.json"),
        "ncentral_custom_property_summary_file": str(Path(root) / "normalized" / "ncentral_custom_property_summary.json"),
        "ncentral_scope_summary_file": str(Path(root) / "normalized" / "ncentral_scope_summary.json"),
        "ncentral_bundle_file": str(Path(root) / "normalized" / "ncentral_report_bundle.json"),
    }
