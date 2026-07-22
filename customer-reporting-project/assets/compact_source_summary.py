from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IGNORED_SCALAR_KEYS = {
    "dataset",
    "datasource",
    "collection_path",
    "generated_at",
    "generated_at_utc",
    "report_family",
    "template_key",
}

SECTION_NAME_ALIASES = {
    "availability_summary",
    "alert_trends",
    "resource_health",
    "monitoring_coverage",
    "website_experience",
    "platform_assets",
    "report_inventory",
    "inventory_exceptions",
    "root_scope_summary",
    "device_availability",
    "cpu_memory_utilization",
    "disk_capacity_utilization",
    "network_interface_throughput",
    "backup_summary",
    "backup_trends",
    "backup_exceptions",
    "sn_ticket_summary",
    "sn_incident_summary",
    "sn_request_summary",
    "sn_change_summary",
    "sn_problem_summary",
    "sn_sla_summary",
    "sn_sla_trends",
    "sn_aged_backlog",
    "sn_dimensions",
    "sn_fcr",
    "sn_critical_incidents",
    "ncentral_inventory_summary",
    "ncentral_issue_summary",
    "ncentral_site_rollup",
    "ncentral_device_health",
    "ncentral_custom_property_summary",
    "ncentral_scope_summary",
}


def parse_summary_args(argv: list[str] | None = None) -> dict[str, str | None]:
    parser = argparse.ArgumentParser(description="Create a compact source summary artifact.")
    parser.add_argument("--run-dir", default="run", help="Run directory containing normalized outputs.")
    parser.add_argument("--output-path", default=None, help="Optional explicit summary output path.")
    args = parser.parse_args(argv)
    return {"run_dir": args.run_dir, "output_path": args.output_path}


def ensure_dir(dir_path: str | Path) -> None:
    Path(dir_path).mkdir(parents=True, exist_ok=True)


def read_json_file(file_path: str | Path) -> Any:
    return json.loads(Path(file_path).read_text(encoding="utf-8"))


def write_json_file(file_path: str | Path, payload: Any) -> None:
    path = Path(file_path)
    ensure_dir(path.parent)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def truncate_string(value: str, limit: int = 120) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


def is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def payload_for_metrics(data: Any) -> Any:
    if isinstance(data, dict) and "dataset" in data and isinstance(data["dataset"], (dict, list)):
        return data["dataset"]
    return data


def infer_populated(data: Any) -> bool:
    payload = payload_for_metrics(data)
    if isinstance(payload, list):
        return len(payload) > 0
    if isinstance(payload, dict):
        if isinstance(payload.get("populated"), bool):
            return payload["populated"]
        for key, value in payload.items():
            if value is None:
                continue
            if isinstance(value, (list, dict)) and len(value) > 0:
                return True
            if isinstance(value, (int, float, bool)):
                return True
            if isinstance(value, str):
                candidate = value.strip()
                if candidate and candidate not in SECTION_NAME_ALIASES:
                    return True
        return False
    return bool(payload)


def extract_scalar_metrics(data: Any, limit: int = 12) -> dict[str, Any]:
    payload = payload_for_metrics(data)
    scalar_metrics: dict[str, Any] = {}
    if isinstance(data, dict):
        sources = [data]
        if payload is not data and isinstance(payload, dict):
            sources.append(payload)
        for source in sources:
            for key, value in source.items():
                if key in scalar_metrics or key in IGNORED_SCALAR_KEYS:
                    continue
                if not is_scalar(value):
                    continue
                if isinstance(value, str):
                    candidate = value.strip()
                    if not candidate or candidate in SECTION_NAME_ALIASES:
                        continue
                    scalar_metrics[key] = truncate_string(candidate)
                else:
                    scalar_metrics[key] = value
                if len(scalar_metrics) >= limit:
                    return scalar_metrics
    elif isinstance(payload, list):
        scalar_metrics["record_count"] = len(payload)
    return scalar_metrics


def extract_collection_sizes(data: Any, limit: int = 8) -> dict[str, int]:
    payload = payload_for_metrics(data)
    sizes: dict[str, int] = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, (list, dict)):
                sizes[key] = len(value)
                if len(sizes) >= limit:
                    break
    elif isinstance(payload, list):
        sizes["records"] = len(payload)
    return sizes


def relative_path(path: str | Path, root: str | Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(Path(path))


def summarize_section(name: str, file_path: str | Path, run_root: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    summary: dict[str, Any] = {
        "file": relative_path(path, run_root),
        "exists": path.exists(),
        "populated": False,
    }
    if not path.exists():
        return summary

    data = read_json_file(path)
    payload = payload_for_metrics(data)
    summary["populated"] = infer_populated(data)
    if isinstance(data, dict):
        summary["top_level_keys"] = list(data.keys())[:12]
    if isinstance(payload, dict) and payload is not data:
        summary["dataset_keys"] = list(payload.keys())[:12]
    summary["scalar_metrics"] = extract_scalar_metrics(data)
    summary["collection_sizes"] = extract_collection_sizes(data)
    return summary


def summarize_bundle(bundle_path: str | Path, run_root: str | Path) -> dict[str, Any]:
    path = Path(bundle_path)
    bundle_summary: dict[str, Any] = {
        "file": relative_path(path, run_root),
        "exists": path.exists(),
        "meta": {},
        "section_keys": [],
    }
    if not path.exists():
        return bundle_summary

    bundle = read_json_file(path)
    meta = bundle.get("meta", {}) if isinstance(bundle, dict) else {}
    sections = bundle.get("sections", {}) if isinstance(bundle, dict) else {}
    bundle_summary["meta"] = {
        key: truncate_string(value) if isinstance(value, str) else value
        for key, value in meta.items()
        if is_scalar(value) and key not in {"collection_path"}
    }
    if isinstance(sections, dict):
        bundle_summary["section_keys"] = list(sections.keys())
    return bundle_summary


def build_source_summary(
    *,
    source: str,
    run_root: str | Path,
    bundle_path: str | Path,
    output_path: str | Path,
    section_files: dict[str, str],
) -> dict[str, Any]:
    section_summaries = {
        section_name: summarize_section(section_name, file_path, run_root)
        for section_name, file_path in section_files.items()
    }
    populated_sections = sorted(
        section_name
        for section_name, summary in section_summaries.items()
        if summary["exists"] and summary["populated"]
    )
    empty_sections = sorted(
        section_name
        for section_name, summary in section_summaries.items()
        if summary["exists"] and not summary["populated"]
    )
    missing_sections = sorted(
        section_name for section_name, summary in section_summaries.items() if not summary["exists"]
    )

    summary = {
        "source": source,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_root": str(Path(run_root).resolve()),
        "bundle": summarize_bundle(bundle_path, run_root),
        "populated_sections": populated_sections,
        "empty_sections": empty_sections,
        "missing_sections": missing_sections,
        "sections": section_summaries,
    }
    write_json_file(output_path, summary)
    return {
        "ok": True,
        "source": source,
        "summary_path": str(output_path),
        "populated_sections": len(populated_sections),
        "empty_sections": len(empty_sections),
        "missing_sections": len(missing_sections),
    }
