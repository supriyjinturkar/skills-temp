from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

from lm_io import read_json_file


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


def _parse_optional_number(value):
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return int(numeric) if numeric.is_integer() else numeric


def _first_non_empty(*values) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _build_period_label(start_iso: str, end_iso: str, explicit_label: str | None) -> str:
    if isinstance(explicit_label, str) and explicit_label.strip():
        return explicit_label.strip()
    return f"{start_iso[:10]} to {end_iso[:10]}"


def _resolve_credentials(raw_scope: dict, raw_credentials: dict, env: dict[str, str]) -> dict[str, str]:
    auth_mode = str(raw_scope.get("auth_mode") or raw_credentials.get("auth_mode") or "bearer").strip().lower() or "bearer"
    return {
        "auth_mode": auth_mode,
        "bearer_token": _first_non_empty(
            raw_credentials.get("bearer_token"),
            raw_scope.get("bearer_token"),
            env.get("LOGICMONITOR_BEARER_TOKEN"),
        ),
        "api_access_id": _first_non_empty(
            raw_credentials.get("api_access_id"),
            raw_scope.get("api_access_id"),
            env.get("LOGICMONITOR_API_ACCESS_ID"),
        ),
        "api_access_key": _first_non_empty(
            raw_credentials.get("api_access_key"),
            raw_scope.get("api_access_key"),
            env.get("LOGICMONITOR_API_ACCESS_KEY"),
        ),
        "basic_username": _first_non_empty(
            raw_credentials.get("basic_username"),
            raw_scope.get("basic_username"),
            env.get("LOGICMONITOR_BASIC_USERNAME"),
        ),
        "basic_password": _first_non_empty(
            raw_credentials.get("basic_password"),
            raw_scope.get("basic_password"),
            env.get("LOGICMONITOR_BASIC_PASSWORD"),
        ),
    }


def _validate_scope(scope: dict) -> None:
    if scope["allow_full_tenant_collection"]:
        return
    if scope["group_identifiers"]:
        return
    if scope["root_device_group_id"] is not None:
        return
    raise ValueError(
        "LogicMonitor scope must include group_identifiers or root_device_group_id unless allow_full_tenant_collection=true.",
    )


def load_fleet_customer_context(context_path: str):
    return read_json_file(context_path)


def _resolve_logicmonitor_base_context(raw_context: dict, env: dict[str, str] | None = None, now: datetime | None = None) -> dict:
    env = env or os.environ
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
    raw_scope = (raw_context.get("source_scope") or {}).get("logicmonitor") or raw_context.get("logicmonitor") or {}
    raw_credentials = (raw_context.get("credentials") or {}).get("logicmonitor") or {}
    credentials = _resolve_credentials(raw_scope, raw_credentials, env)
    root_device_group_id = _parse_optional_number(raw_scope.get("root_device_group_id"))
    group_identifiers = _parse_string_array(raw_scope.get("group_identifiers"))
    if not group_identifiers and root_device_group_id is not None:
        group_identifiers.append(str(root_device_group_id))

    scope = {
        "tenant_id": str(raw_scope.get("tenant_id") or f"logicmonitor:{raw_scope.get('account_name', 'unknown')}").strip(),
        "account_name": str(raw_scope.get("account_name") or "").strip(),
        "api_version": str(raw_scope.get("api_version") or "3").strip() or "3",
        "site_property_key": str(raw_scope.get("site_property_key") or "system.groups").strip() or "system.groups",
        "group_identifiers": group_identifiers,
        "site_groups": _parse_string_array(raw_scope.get("site_groups")),
        "root_device_group_id": root_device_group_id,
        "root_website_group_id": _parse_optional_number(raw_scope.get("root_website_group_id")),
        "allow_full_tenant_collection": raw_scope.get("allow_full_tenant_collection") is True,
        "request_timeout_seconds": int(raw_scope.get("request_timeout_seconds") or 60),
        "request_retry_attempts": int(raw_scope.get("request_retry_attempts") or 2),
        "request_retry_backoff_ms": int(raw_scope.get("request_retry_backoff_ms") or 1000),
        "fetch_page_size": int(raw_scope.get("fetch_page_size") or 200),
        "max_pages_per_endpoint": int(raw_scope.get("max_pages_per_endpoint") or 0),
        "alert_chunk_hours": int(raw_scope.get("alert_chunk_hours") or 24),
        "detail_fetch_concurrency": int(raw_scope.get("detail_fetch_concurrency") or 5),
        **credentials,
    }

    if not scope["account_name"]:
        raise ValueError("source_scope.logicmonitor.account_name is required.")

    start_ms = int(datetime.fromisoformat(start_iso.replace("Z", "+00:00")).timestamp() * 1000)
    end_ms = int(datetime.fromisoformat(end_iso.replace("Z", "+00:00")).timestamp() * 1000)

    return {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "report_family": report_family,
        "template_key": template_key,
        "period": {
            "start_iso": start_iso,
            "end_iso": end_iso,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "label": period_label,
        },
        "generated_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "logicmonitor": scope,
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


def resolve_logicmonitor_context(raw_context: dict, env: dict[str, str] | None = None, now: datetime | None = None) -> dict:
    context = _resolve_logicmonitor_base_context(raw_context, env=env, now=now)
    _validate_scope(context["logicmonitor"])
    return context


def resolve_logicmonitor_lookup_context(raw_context: dict, env: dict[str, str] | None = None, now: datetime | None = None) -> dict:
    return _resolve_logicmonitor_base_context(raw_context, env=env, now=now)


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
