from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from nc_io import read_json_file


DEFAULT_NCENTRAL_JWT_TOKEN_PATH = "/opt/ncentral/NCENTRAL_JWT_TOKEN"


def _to_iso(value: str, field_name: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid date.") from exc
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_string_array(value) -> list[str]:
    if isinstance(value, list):
        return [str(entry).strip() for entry in value if str(entry).strip()]
    if isinstance(value, str):
        return [entry.strip() for entry in value.split(",") if entry.strip()]
    return []


def _parse_number_array(value) -> list[int]:
    if value in (None, ""):
        return []
    raw_values = value if isinstance(value, list) else _parse_string_array(value)
    parsed: list[int] = []
    for raw_value in raw_values:
        numeric = _parse_optional_number(raw_value, "site_ids[]")
        if numeric is not None:
            parsed.append(int(numeric))
    return parsed


def _parse_optional_number(value, field_name: str = ""):
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        import sys
        label = f" for field '{field_name}'" if field_name else ""
        sys.stderr.write(
            f"WARNING: _parse_optional_number received non-numeric value {value!r}{label}; treating as None.\n"
        )
        return None
    return int(numeric) if numeric.is_integer() else numeric


def _parse_positive_int(value, default: int, field_name: str) -> int:
    parsed = _parse_optional_number(value, field_name)
    if parsed is None:
        return default
    if int(parsed) < 0:
        raise ValueError(f"{field_name} must be >= 0.")
    return int(parsed)


def _build_period_label(start_iso: str, end_iso: str, explicit_label: str | None) -> str:
    if isinstance(explicit_label, str) and explicit_label.strip():
        return explicit_label.strip()
    return f"{start_iso[:10]} to {end_iso[:10]}"


def _validate_scope(scope: dict) -> None:
    if scope["org_unit_id"] is not None:
        return
    if scope["customer_id"] is not None:
        return
    if scope["site_id"] is not None:
        return
    raise ValueError(
        "N-central scope must include org_unit_id, customer_id, or site_id before collection. "
        "Run the resolver first if only company_name is known.",
    )


def load_fleet_customer_context(context_path: str):
    return read_json_file(context_path)


def _read_jwt_token_file(token_path: str) -> str:
    normalized_path = str(token_path or "").strip()
    if not normalized_path:
        raise ValueError(
            "N-central JWT token path is required. Set source_scope.ncentral.jwt_token_path, "
            "NCENTRAL_JWT_TOKEN_PATH, or mount /opt/ncentral/NCENTRAL_JWT_TOKEN.",
        )
    try:
        token = Path(normalized_path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError(f"N-central JWT token file could not be read at {normalized_path}: {exc}") from exc
    if not token:
        raise ValueError(f"N-central JWT token file was empty at {normalized_path}.")
    return token


def _resolve_ncentral_base_context(raw_context: dict, now: datetime | None = None) -> dict:
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
    start_iso = _to_iso(raw_period.get("start") or "", "period.start")
    end_iso = _to_iso(raw_period.get("end") or "", "period.end")
    period_label = _build_period_label(start_iso, end_iso, raw_period.get("label"))
    raw_scope = (raw_context.get("source_scope") or {}).get("ncentral") or raw_context.get("ncentral") or {}

    base_url = str(raw_scope.get("base_url") or os.getenv("NCENTRAL_BASE_URL") or "").strip()
    jwt_token_path = str(
        raw_scope.get("jwt_token_path")
        or os.getenv("NCENTRAL_JWT_TOKEN_PATH")
        or DEFAULT_NCENTRAL_JWT_TOKEN_PATH
        or ""
    ).strip()
    _read_jwt_token_file(jwt_token_path)
    customer_scope_id = _parse_optional_number(raw_scope.get("customer_id"), "customer_id")
    site_scope_id = _parse_optional_number(raw_scope.get("site_id"), "site_id")
    org_unit_id = _parse_optional_number(raw_scope.get("org_unit_id"), "org_unit_id")
    org_unit_type = str(raw_scope.get("org_unit_type") or "").strip().lower()
    if org_unit_id is None and site_scope_id is not None:
        org_unit_id = site_scope_id
    if org_unit_id is None and customer_scope_id is not None:
        org_unit_id = customer_scope_id
    if not org_unit_type:
        if site_scope_id is not None:
            org_unit_type = "site"
        elif customer_scope_id is not None:
            org_unit_type = "customer"
    site_ids = _parse_number_array(raw_scope.get("site_ids"))
    if not site_ids and site_scope_id is not None:
        site_ids = [int(site_scope_id)]

    scope = {
        "base_url": base_url.rstrip("/"),
        "jwt_token_path": jwt_token_path,
        "service_org_id": _parse_optional_number(raw_scope.get("service_org_id"), "service_org_id"),
        "customer_id": customer_scope_id,
        "customer_name": str(raw_scope.get("customer_name") or customer_name).strip() or customer_name,
        "site_id": site_scope_id,
        "site_name": str(raw_scope.get("site_name") or "").strip(),
        "site_ids": site_ids,
        "site_names": _parse_string_array(raw_scope.get("site_names")),
        "org_unit_id": org_unit_id,
        "org_unit_name": str(raw_scope.get("org_unit_name") or raw_scope.get("customer_name") or "").strip(),
        "org_unit_type": org_unit_type or "customer",
        "request_timeout_seconds": _parse_positive_int(raw_scope.get("request_timeout_seconds"), 60, "request_timeout_seconds"),
        "request_retry_attempts": _parse_positive_int(raw_scope.get("request_retry_attempts"), 4, "request_retry_attempts"),
        "request_retry_backoff_ms": _parse_positive_int(raw_scope.get("request_retry_backoff_ms"), 1000, "request_retry_backoff_ms"),
        "auth_refresh_skew_seconds": _parse_positive_int(raw_scope.get("auth_refresh_skew_seconds"), 60, "auth_refresh_skew_seconds"),
        "fetch_page_size": _parse_positive_int(raw_scope.get("fetch_page_size"), 200, "fetch_page_size"),
        "max_pages_per_endpoint": _parse_positive_int(raw_scope.get("max_pages_per_endpoint"), 0, "max_pages_per_endpoint"),
        "max_parallel_device_property_requests": _parse_positive_int(
            raw_scope.get("max_parallel_device_property_requests"),
            5,
            "max_parallel_device_property_requests",
        ),
        "max_parallel_site_issue_requests": _parse_positive_int(
            raw_scope.get("max_parallel_site_issue_requests"),
            3,
            "max_parallel_site_issue_requests",
        ),
        "device_custom_properties_mode": str(raw_scope.get("device_custom_properties_mode") or "adaptive").strip().lower() or "adaptive",
        "full_device_custom_properties_threshold": _parse_positive_int(
            raw_scope.get("full_device_custom_properties_threshold"),
            75,
            "full_device_custom_properties_threshold",
        ),
        "max_device_custom_property_devices": _parse_positive_int(
            raw_scope.get("max_device_custom_property_devices"),
            100,
            "max_device_custom_property_devices",
        ),
        "site_issue_query_limit": _parse_positive_int(raw_scope.get("site_issue_query_limit"), 20, "site_issue_query_limit"),
        "fetch_site_active_issues": raw_scope.get("fetch_site_active_issues") is not False,
        "stale_checkin_hours": _parse_positive_int(raw_scope.get("stale_checkin_hours"), 72, "stale_checkin_hours"),
    }

    if not scope["base_url"]:
        raise ValueError("source_scope.ncentral.base_url or NCENTRAL_BASE_URL is required.")

    start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))

    return {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "report_family": report_family,
        "template_key": template_key,
        "period": {
            "start_iso": start_iso,
            "end_iso": end_iso,
            "start_ms": int(start_dt.timestamp() * 1000),
            "end_ms": int(end_dt.timestamp() * 1000),
            "label": period_label,
        },
        "generated_at": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ncentral": scope,
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


def resolve_ncentral_context(raw_context: dict, now: datetime | None = None) -> dict:
    context = _resolve_ncentral_base_context(raw_context, now=now)
    _validate_scope(context["ncentral"])
    return context


def resolve_ncentral_lookup_context(raw_context: dict, now: datetime | None = None) -> dict:
    return _resolve_ncentral_base_context(raw_context, now=now)


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
