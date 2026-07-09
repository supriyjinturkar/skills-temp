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
        # source snapshots — written by agent MCP calls
        "servicenow_lookup_file": str(Path(root) / "source_snapshots" / "servicenow_lookup.json"),
        "servicenow_snapshot_file": str(Path(root) / "source_snapshots" / "servicenow.json"),
        # resolved scope
        "resolved_servicenow_scope_file": str(Path(root) / "resolved_servicenow_scope.json"),
        # normalized outputs — written by scripts
        "sn_ticket_summary_file": str(Path(root) / "normalized" / "sn_ticket_summary.json"),
        "sn_incident_summary_file": str(Path(root) / "normalized" / "sn_incident_summary.json"),
        "sn_request_summary_file": str(Path(root) / "normalized" / "sn_request_summary.json"),
        "sn_change_summary_file": str(Path(root) / "normalized" / "sn_change_summary.json"),
        "sn_problem_summary_file": str(Path(root) / "normalized" / "sn_problem_summary.json"),
        "sn_sla_summary_file": str(Path(root) / "normalized" / "sn_sla_summary.json"),
        "sn_sla_trends_file": str(Path(root) / "normalized" / "sn_sla_trends.json"),
        "sn_aged_backlog_file": str(Path(root) / "normalized" / "sn_aged_backlog.json"),
        "sn_dimensions_file": str(Path(root) / "normalized" / "sn_dimensions.json"),
        "sn_fcr_file": str(Path(root) / "normalized" / "sn_fcr.json"),
        "sn_critical_incidents_file": str(Path(root) / "normalized" / "sn_critical_incidents.json"),
        "servicenow_bundle_file": str(Path(root) / "normalized" / "servicenow_report_bundle.json"),
    }
