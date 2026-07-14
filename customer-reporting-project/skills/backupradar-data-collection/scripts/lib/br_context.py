from __future__ import annotations

import argparse
from datetime import datetime, timezone

from br_io import read_json_file


def _to_iso(value: str, field_name: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid date.") from exc
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_string_array(value) -> list[str]:
    if isinstance(value, list):
        return [str(entry).strip() for entry in value if str(entry).strip()]
    if isinstance(value, str):
        return [entry.strip() for entry in value.split(",") if entry.strip()]
    return []


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _parse_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default




def _build_period_label(start_iso: str, end_iso: str, explicit_label: str | None) -> str:
    if isinstance(explicit_label, str) and explicit_label.strip():
        return explicit_label.strip()
    return f"{start_iso[:10]} to {end_iso[:10]}"


def _normalize_path(value: str, default: str) -> str:
    chosen = str(value or default).strip() or default
    if chosen.startswith("http://") or chosen.startswith("https://") or chosen.startswith("/"):
        return chosen
    return f"/{chosen}"


def _resolve_resource(raw_resources: dict, name: str, default_path: str, defaults: dict[str, str | int]) -> dict:
    raw = raw_resources.get(name) or {}
    query = raw.get("query") if isinstance(raw.get("query"), dict) else {}
    return {
        "path": _normalize_path(raw.get("path"), default_path),
        "items_key": str(raw.get("items_key") or defaults["items_key"]).strip(),
        "next_key": str(raw.get("next_key") or defaults["next_key"]).strip(),
        "next_url_key": str(raw.get("next_url_key") or defaults["next_url_key"]).strip(),
        "page_param": str(raw.get("page_param") or defaults["page_param"]).strip(),
        "cursor_param": str(raw.get("cursor_param") or defaults["cursor_param"]).strip(),
        "page_size_param": str(raw.get("page_size_param") or defaults["page_size_param"]).strip(),
        "page_size": _parse_int(raw.get("page_size"), int(defaults["page_size"])),
        "max_pages": _parse_int(raw.get("max_pages"), int(defaults["max_pages"])),
        "customer_filter_param": str(raw.get("customer_filter_param") or defaults["customer_filter_param"]).strip(),
        "start_param": str(raw.get("start_param") or defaults["start_param"]).strip(),
        "end_param": str(raw.get("end_param") or defaults["end_param"]).strip(),
        "id_key": str(raw.get("id_key") or "id").strip() or "id",
        "name_key": str(raw.get("name_key") or "name").strip() or "name",
        "alias_keys": _parse_string_array(raw.get("alias_keys") or "aliases"),
        "query": {str(key): value for key, value in query.items()},
    }


def load_fleet_customer_context(context_path: str):
    return read_json_file(context_path)


def _resolve_backupradar_base_context(raw_context: dict, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    customer_id = str(raw_context.get("customer_id") or raw_context.get("id") or "").strip() or "unknown-customer"
    customer_name = str(
        raw_context.get("customer_name")
        or raw_context.get("display_name")
        or raw_context.get("customer", {}).get("name")
        or customer_id
    ).strip() or customer_id
    report_family = str(
        raw_context.get("report_family")
        or raw_context.get("report", {}).get("family")
        or "monthly-service-review"
    ).strip() or "monthly-service-review"
    template_key = str(
        raw_context.get("template_key")
        or raw_context.get("report", {}).get("template_key")
        or ""
    ).strip()
    raw_period = raw_context.get("period") or raw_context.get("report_period") or {}
    start_iso = _to_iso(raw_period["start"], "period.start")
    end_iso = _to_iso(raw_period["end"], "period.end")
    period_label = _build_period_label(start_iso, end_iso, raw_period.get("label"))
    raw_scope = (raw_context.get("source_scope") or {}).get("backupradar") or raw_context.get("backupradar") or {}
    raw_resources = raw_scope.get("resources") if isinstance(raw_scope.get("resources"), dict) else {}

    # BackupRadar API v2 defaults (API v1 retired 2026-01-09).
    # All endpoints live under /backups.  Customer scoping uses SearchByCompanyName.
    # Auth header is ApiKey (not x-api-key).  Pagination uses Page / Size.
    # The 'date' param is a single as-of reference date (period end), not a range.
    defaults = {
        "items_key": "Results",               # v2 envelope key
        "next_key": "",
        "next_url_key": "",
        "page_param": "Page",                 # v2 pagination (1-based)
        "cursor_param": "",
        "page_size_param": "Size",            # v2 pagination (max 1000)
        "page_size": 1000,
        "max_pages": 10,
        "customer_filter_param": "SearchByCompanyName",  # v2 customer scoping
        "start_param": "date",                # v2 as-of reference date (use period end)
        "end_param": "",                      # v2 has no range end param
    }

    # BackupRadar API v2 — confirmed routes from https://api.backupradar.com/docs/2.0
    # Endpoints that do NOT exist in v2 (all return 404):
    #   /customers, /jobs, /devices, /destinations, /alerts, /issues,
    #   /exceptions, /restores, /sources, /policies, /vaults, /reports
    core_resource_defaults = {
        "backups":          "/backups",
        "backups_inactive": "/backups/inactive",
        "backups_retired":  "/backups/retired",
        "backups_overview": "/backups/overview",
        "backups_filters":  "/backups/filters",
    }
    optional_resource_defaults = {
        # No additional resource routes exist in BackupRadar API v2.
        # Kept empty to prevent 404s from old /customers /jobs /devices paths.
    }

    resources = {
        name: _resolve_resource(raw_resources, name, default_path, defaults)
        for name, default_path in core_resource_defaults.items()
    }
    for name, default_path in optional_resource_defaults.items():
        if name not in raw_resources:
            continue
        resources[name] = _resolve_resource(raw_resources, name, default_path, defaults)
    for name in raw_resources:
        if name in resources:
            continue
        resources[name] = _resolve_resource(raw_resources, name, f"/{name}", defaults)

    required_resources = _parse_string_array(raw_scope.get("required_resources") or "backups")
    scope = {
        "tenant_id": str(raw_scope.get("tenant_id") or "backupradar").strip() or "backupradar",
        "base_url": str(raw_scope.get("base_url") or "https://api.backupradar.com").strip(),
        "customer_id": str(raw_scope.get("customer_id") or raw_scope.get("client_id") or "").strip(),
        "customer_name": str(raw_scope.get("customer_name") or "").strip(),
        "allow_unscoped_collection": _parse_bool(raw_scope.get("allow_unscoped_collection")),
        "request_timeout_seconds": _parse_int(raw_scope.get("request_timeout_seconds"), 60),
        "request_retry_attempts": _parse_int(raw_scope.get("request_retry_attempts"), 3),
        "request_retry_backoff_ms": _parse_int(raw_scope.get("request_retry_backoff_ms"), 1000),
        "resources": resources,
        "required_resources": required_resources or ["backups"],
    }
    return {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "report_family": report_family,
        "template_key": template_key,
        "period": {
            "start_iso": start_iso,
            "end_iso": end_iso,
            "label": period_label,
        },
        "generated_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "backupradar": scope,
        "company_name": str(
            raw_context.get("company_name")
            or raw_context.get("customer_name")
            or raw_context.get("display_name")
            or customer_name
        ).strip() or customer_name,
        "company_aliases": _parse_string_array(
            raw_context.get("company_aliases")
            or raw_context.get("customer_aliases")
            or raw_scope.get("company_aliases")
            or "",
        ),
    }


def _validate_scope(scope: dict) -> None:
    # Authentication is handled by the nexon-backupradar-api sandbox Access Profile proxy.
    if not scope["allow_unscoped_collection"] and not scope["customer_id"]:
        raise ValueError(
            "BackupRadar scope must include customer_id unless allow_unscoped_collection=true.",
        )
    for resource_name in scope["required_resources"]:
        resource = scope["resources"].get(resource_name)
        if resource is None or not resource["path"]:
            raise ValueError(f"BackupRadar resource '{resource_name}' must define a path.")


def resolve_backupradar_context(raw_context: dict, now: datetime | None = None) -> dict:
    context = _resolve_backupradar_base_context(raw_context, now=now)
    _validate_scope(context["backupradar"])
    return context


def resolve_backupradar_lookup_context(raw_context: dict, now: datetime | None = None) -> dict:
    return _resolve_backupradar_base_context(raw_context, now=now)


def parse_cli_args(argv: list[str]) -> dict[str, str]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--context", dest="context_path", required=True)
    parser.add_argument("--run-dir", dest="run_dir", default="run")
    parser.add_argument("--snapshot", dest="snapshot_path", default="")
    parser.add_argument("--normalized", dest="normalized_path", default="")
    parser.add_argument("--output", dest="output_path", default="")
    args, _ = parser.parse_known_args(argv)
    return {
        "context_path": args.context_path,
        "run_dir": args.run_dir,
        "snapshot_path": args.snapshot_path,
        "normalized_path": args.normalized_path,
        "output_path": args.output_path,
    }
