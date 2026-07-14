from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from math import ceil

from sn_io import read_json_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_iso(value: str, field_name: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 date string.") from exc
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_str(value, default: str = "") -> str:
    if value in (None, ""):
        return default
    return str(value).strip() or default


def _first_non_empty(*values) -> str:
    for v in values:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _derive_period_months(start_iso: str, end_iso: str) -> int:
    """Derive period_months from start/end dates, rounding up to the nearest month."""
    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        delta_days = (end - start).days
        return max(1, ceil(delta_days / 30))
    except Exception:
        return 3


def _build_period_label(start_iso: str, end_iso: str, explicit_label: str | None) -> str:
    if isinstance(explicit_label, str) and explicit_label.strip():
        return explicit_label.strip()
    return f"{start_iso[:10]} to {end_iso[:10]}"


# ---------------------------------------------------------------------------
# CLI args
# ---------------------------------------------------------------------------

def parse_cli_args(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", dest="context_path", required=True)
    parser.add_argument("--run-dir", dest="run_dir", default="run")
    parser.add_argument("--snapshot", dest="snapshot_path", default=None)
    parser.add_argument("--normalized", dest="normalized_path", default=None)
    parser.add_argument("--output", dest="output_path", default=None)
    ns = parser.parse_args(argv)
    return {
        "context_path": ns.context_path,
        "run_dir": ns.run_dir,
        "snapshot_path": ns.snapshot_path,
        "normalized_path": ns.normalized_path,
        "output_path": ns.output_path,
    }


# ---------------------------------------------------------------------------
# Context loaders
# ---------------------------------------------------------------------------

def load_fleet_customer_context(context_path: str) -> dict:
    return read_json_file(context_path)


def resolve_servicenow_lookup_context(raw_context: dict) -> dict:
    """Minimal context for the scope resolver (company name only required)."""
    company_name = _first_non_empty(
        raw_context.get("company_name"),
        raw_context.get("customer_name"),
    )
    if not company_name:
        raise ValueError("customer_context.json must include 'company_name' or 'customer_name'.")
    return {
        "company_name": company_name,
        "customer_name": company_name,
    }


def resolve_servicenow_context(raw_context: dict, env: dict[str, str] | None = None) -> dict:
    """
    Full context for collection and normalization.
    Requires either source_scope.servicenow.customer_sys_id or a pre-resolved sys_id
    in the top-level customer_sys_id field.
    """
    env = env or os.environ

    customer_id = _coerce_str(
        raw_context.get("customer_id") or raw_context.get("id"),
        default="unknown-customer",
    )
    customer_name = _coerce_str(
        raw_context.get("customer_name")
        or raw_context.get("display_name")
        or customer_id,
        default=customer_id,
    )
    report_family = _coerce_str(raw_context.get("report_family"), default="monthly-service-review")
    template_key = _coerce_str(raw_context.get("template_key"), default="operations-v1")

    # Period
    period_raw = raw_context.get("period") or {}
    period_start = _to_iso(str(period_raw.get("start", "")), "period.start") if period_raw.get("start") else ""
    period_end = _to_iso(str(period_raw.get("end", "")), "period.end") if period_raw.get("end") else ""
    period_label = _build_period_label(period_start, period_end, period_raw.get("label"))

    if not period_start or not period_end:
        raise ValueError("customer_context.json must include period.start and period.end.")

    # ServiceNow scope
    sn_scope_raw = (raw_context.get("source_scope") or {}).get("servicenow") or {}

    customer_sys_id = _coerce_str(
        sn_scope_raw.get("customer_sys_id")
        or raw_context.get("customer_sys_id"),
    )
    if not customer_sys_id:
        raise ValueError(
            "ServiceNow customer_sys_id is required. "
            "Run resolve_servicenow_scope.py first or provide source_scope.servicenow.customer_sys_id."
        )

    period_months = int(sn_scope_raw.get("period_months") or _derive_period_months(period_start, period_end))
    period_months = max(1, min(period_months, 24))

    return {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "report_family": report_family,
        "template_key": template_key,
        "period": {
            "start_iso": period_start,
            "end_iso": period_end,
            "label": period_label,
            "months": period_months,
        },
        "servicenow": {
            "customer_sys_id": customer_sys_id,
            "period_months": period_months,
        },
    }
