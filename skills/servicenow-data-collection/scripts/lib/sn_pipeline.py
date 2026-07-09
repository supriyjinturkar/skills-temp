from __future__ import annotations

"""
sn_pipeline.py

All ServiceNow data processing logic:
- resolve_servicenow_scope_from_lookup  : parse MCP lookup response → sys_id + candidates
- validate_servicenow_snapshot          : confirm snapshot exists and is valid
- normalize_servicenow_snapshot         : raw CSI response → structured normalized sections
- build_servicenow_artifacts            : normalized sections → report-ready bundle + individual files
- run_servicenow_pipeline               : end-to-end (normalize + bundle) from saved snapshot
"""

from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coerce_str(value, default: str = "") -> str:
    if value in (None, ""):
        return default
    return str(value).strip() or default


def _coerce_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value, default=0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _pct(value) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_list(value) -> list:
    return value if isinstance(value, list) else []


def _safe_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


# ---------------------------------------------------------------------------
# Scope resolution (reads saved MCP lookup response)
# ---------------------------------------------------------------------------

def resolve_servicenow_scope_from_lookup(lookup_payload: dict) -> dict:
    """
    Parse the saved `lookup_customer__nexon_csi_` MCP response.
    Returns resolved scope with sys_id + top candidates.
    """
    result = _safe_dict(lookup_payload.get("result") or lookup_payload)
    ok = result.get("ok", False)
    candidates = _safe_list(result.get("candidates") or [])

    if not ok or not candidates:
        raise ValueError(
            f"ServiceNow customer lookup returned no candidates. "
            f"Raw result: {result}"
        )

    top = candidates[0]
    sys_id = _coerce_str(top.get("sys_id"))
    name = _coerce_str(top.get("name"))
    score = _coerce_int(top.get("score"), default=0)

    if not sys_id:
        raise ValueError("ServiceNow lookup top candidate has no sys_id.")

    confidence = "high" if score >= 100 else "medium" if score >= 85 else "low"

    return {
        "resolved_scope": {
            "servicenow": {
                "customer_sys_id": sys_id,
                "customer_name": name,
            },
        },
        "match_confidence": confidence,
        "top_candidates": [
            {
                "sys_id": _coerce_str(c.get("sys_id")),
                "name": _coerce_str(c.get("name")),
                "score": _coerce_int(c.get("score"), default=0),
                "table": _coerce_str(c.get("table")),
            }
            for c in candidates[:5]
        ],
    }


# ---------------------------------------------------------------------------
# Snapshot validation
# ---------------------------------------------------------------------------

def validate_servicenow_snapshot(snapshot: dict) -> dict:
    """
    Confirms the snapshot written by the agent from get_customer_data__nexon_csi_
    is structurally valid. Returns a validation summary.
    """
    result = _safe_dict(snapshot.get("result") or snapshot)
    ok = result.get("ok", False)
    customer_name = _coerce_str(result.get("customer_name"))
    customer_sys_id = _coerce_str(result.get("customer_sys_id"))
    errors: list[str] = []

    if not ok:
        errors.append("Snapshot ok=false.")
    if not customer_sys_id:
        errors.append("Missing customer_sys_id in snapshot.")
    if not result.get("core"):
        errors.append("Missing 'core' section in snapshot.")
    if not result.get("dimensions"):
        errors.append("Missing 'dimensions' section in snapshot.")

    return {
        "valid": len(errors) == 0,
        "customer_name": customer_name,
        "customer_sys_id": customer_sys_id,
        "errors": errors,
        "dataset": "servicenow_snapshot_validation",
    }


# ---------------------------------------------------------------------------
# Normalize
# ---------------------------------------------------------------------------

def _normalize_by_class(by_class: list[dict]) -> dict:
    """Index by_class list into a dict keyed by ticket class."""
    result: dict[str, dict] = {}
    for entry in _safe_list(by_class):
        cls = _coerce_str(entry.get("class"))
        if cls:
            result[cls] = {
                "label": _coerce_str(entry.get("label"), default=cls),
                "open": _coerce_int(entry.get("open")),
                "closed": _coerce_int(entry.get("closed")),
                "cancelled": _coerce_int(entry.get("cancelled")),
                "total": _coerce_int(entry.get("total")),
            }
    return result


def _normalize_sla_bucket(bucket: dict) -> dict:
    return {
        "met": _coerce_int(bucket.get("met")),
        "breached": _coerce_int(bucket.get("breached")),
        "in_progress": _coerce_int(bucket.get("in_progress")),
        "met_pct": _pct(bucket.get("met_pct")),
    }


def _normalize_monthly_series(monthly: dict) -> dict:
    months = _safe_list(monthly.get("months") or [])
    series_raw = _safe_dict(monthly.get("series") or {})
    series: dict[str, list] = {}
    for cls, values in series_raw.items():
        series[cls] = [_coerce_int(v) for v in _safe_list(values)]
    return {"months": months, "series": series}


def _normalize_dimension_top(dim: dict) -> dict:
    top = [
        {
            "value": _coerce_str(entry.get("value")),
            "sys_id": _coerce_str(entry.get("sys_id")),
            "count": _coerce_int(entry.get("count")),
        }
        for entry in _safe_list(dim.get("top") or [])
    ]
    untagged = _safe_dict(dim.get("untagged") or {})
    return {
        "top": top,
        "untagged_count": _coerce_int(untagged.get("count")),
        "untagged_pct": _pct(untagged.get("pct")),
        "total_in_window": _coerce_int(dim.get("total_in_window")),
        "tagging_completeness_pct": _pct(dim.get("tagging_completeness_pct")),
    }


def _normalize_aged_row(row: dict) -> dict:
    return {
        "number": _coerce_str(row.get("number")) or None,
        "short_description": _coerce_str(row.get("short_description")) or None,
        "state": _coerce_str(row.get("state")) or None,
        "priority": _coerce_str(row.get("priority")) or None,
        "priority_value": _coerce_str(row.get("priority_value")) or None,
        "class": _coerce_str(row.get("class")) or None,
        "assignment_group": _coerce_str(row.get("assignment_group")) or None,
        "caller": _coerce_str(row.get("caller")) or None,
        "opened_at": _coerce_str(row.get("opened_at")) or None,
        "age_days": row.get("age_days"),
    }


def _normalize_critical_row(row: dict) -> dict:
    # Normalize whatever fields the critical list returns
    normalized: dict = {}
    for key, value in row.items():
        normalized[key] = value if value not in (None, "") else None
    return normalized


def normalize_servicenow_snapshot(context: dict, snapshot: dict) -> dict:
    """
    Transform raw get_customer_data__nexon_csi_ response into structured normalized sections.
    All available data from the MCP response is captured.
    """
    result = _safe_dict(snapshot.get("result") or snapshot)
    core = _safe_dict(result.get("core") or {})
    dimensions = _safe_dict(result.get("dimensions") or {})
    critical_raw = _safe_dict(result.get("critical") or {})
    lists_raw = _safe_dict(result.get("lists") or {})

    customer_name = _coerce_str(result.get("customer_name"))
    customer_sys_id = _coerce_str(result.get("customer_sys_id"))
    period_months = _coerce_float(result.get("period_months"), default=context["period"]["months"])
    generated_at = _coerce_str(result.get("generated_at") or core.get("generated_at") or _now_iso())

    # --- totals ---
    totals_raw = _safe_dict(core.get("totals") or {})
    totals = {
        "tickets": _coerce_int(totals_raw.get("tickets")),
        "open": _coerce_int(totals_raw.get("open")),
        "closed": _coerce_int(totals_raw.get("closed")),
        "cancelled": _coerce_int(totals_raw.get("cancelled")),
    }

    # --- by class ---
    by_class = _normalize_by_class(core.get("by_class") or [])

    # --- monthly opened trend ---
    monthly_trend = _normalize_monthly_series(core.get("monthly_trend") or {})

    # --- monthly closed trend ---
    monthly_closed = _normalize_monthly_series(core.get("monthly_closed") or {})

    # --- SLA ---
    sla_raw = _safe_dict(core.get("sla") or {})
    sla = {
        "response": _normalize_sla_bucket(_safe_dict(sla_raw.get("response") or {})),
        "resolution": _normalize_sla_bucket(_safe_dict(sla_raw.get("resolution") or {})),
        "overall": _normalize_sla_bucket(_safe_dict(sla_raw.get("overall") or {})),
        "unclassified": _normalize_sla_bucket(_safe_dict(sla_raw.get("unclassified") or {})),
    }

    # --- MTTR by priority ---
    mttr_by_priority = _safe_list(core.get("mttr_by_priority") or [])

    # --- FCR ---
    fcr_raw = _safe_dict(core.get("fcr") or {})
    fcr = {
        "eligible": _coerce_int(fcr_raw.get("eligible")),
        "first_contact": _coerce_int(fcr_raw.get("first_contact")),
        "fcr_pct": _pct(fcr_raw.get("fcr_pct")),
        "rule": _coerce_str(fcr_raw.get("rule")),
    }

    # --- dimensions ---
    dim_priority = _normalize_dimension_top(_safe_dict(dimensions.get("priority") or {}))
    dim_assignment_group = _normalize_dimension_top(_safe_dict(dimensions.get("assignment_group") or {}))
    dim_business_service = _normalize_dimension_top(_safe_dict(dimensions.get("business_service") or {}))
    dim_service_offering = _normalize_dimension_top(_safe_dict(dimensions.get("service_offering") or {}))
    dim_contact_type = _normalize_dimension_top(_safe_dict(dimensions.get("contact_type") or {}))

    aged_buckets_raw = _safe_dict(dimensions.get("aged") or {})
    aged_buckets = {
        "0_30": _coerce_int(aged_buckets_raw.get("0-30")),
        "30_60": _coerce_int(aged_buckets_raw.get("30-60")),
        "60_90": _coerce_int(aged_buckets_raw.get("60-90")),
        "90_plus": _coerce_int(aged_buckets_raw.get("90+")),
    }

    # --- critical (P1/P2) list ---
    critical = {
        "ok": critical_raw.get("ok", False),
        "total": _coerce_int(critical_raw.get("total")),
        "returned": _coerce_int(critical_raw.get("returned")),
        "truncated": bool(critical_raw.get("truncated")),
        "rows": [_normalize_critical_row(r) for r in _safe_list(critical_raw.get("rows") or [])],
    }

    # --- aged ticket lists ---
    aged_list_raw = _safe_dict(lists_raw.get("aged") or {})
    aged_incidents_raw = _safe_dict(lists_raw.get("aged_incidents") or {})

    aged_list = {
        "ok": aged_list_raw.get("ok", False),
        "total": _coerce_int(aged_list_raw.get("total")),
        "returned": _coerce_int(aged_list_raw.get("returned")),
        "truncated": bool(aged_list_raw.get("truncated")),
        "rows": [_normalize_aged_row(r) for r in _safe_list(aged_list_raw.get("rows") or [])],
        "data_quality_note": (
            "All row fields null — MCP server data population issue."
            if aged_list_raw.get("returned", 0) > 0
            and all(
                r.get("number") is None
                for r in _safe_list(aged_list_raw.get("rows") or [])
            )
            else None
        ),
    }

    aged_incidents_list = {
        "ok": aged_incidents_raw.get("ok", False),
        "total": _coerce_int(aged_incidents_raw.get("total")),
        "returned": _coerce_int(aged_incidents_raw.get("returned")),
        "truncated": bool(aged_incidents_raw.get("truncated")),
        "rows": [_normalize_aged_row(r) for r in _safe_list(aged_incidents_raw.get("rows") or [])],
        "data_quality_note": (
            "No rows returned despite non-zero total — MCP server data population issue."
            if aged_incidents_raw.get("total", 0) > 0
            and aged_incidents_raw.get("returned", 0) == 0
            else None
        ),
    }

    return {
        "dataset": "servicenow_normalized",
        "customer_name": customer_name,
        "customer_sys_id": customer_sys_id,
        "period_months": period_months,
        "period_label": context["period"]["label"],
        "period_start": context["period"]["start_iso"],
        "period_end": context["period"]["end_iso"],
        "generated_at": generated_at,
        "collected_at": _now_iso(),
        "totals": totals,
        "by_class": by_class,
        "monthly_trend": monthly_trend,
        "monthly_closed": monthly_closed,
        "sla": sla,
        "mttr_by_priority": mttr_by_priority,
        "fcr": fcr,
        "dimensions": {
            "priority": dim_priority,
            "assignment_group": dim_assignment_group,
            "business_service": dim_business_service,
            "service_offering": dim_service_offering,
            "contact_type": dim_contact_type,
            "aged_buckets": aged_buckets,
        },
        "critical_incidents": critical,
        "aged_list": aged_list,
        "aged_incidents_list": aged_incidents_list,
    }


# ---------------------------------------------------------------------------
# Per-section extractors (produce individual normalized files)
# ---------------------------------------------------------------------------

def _extract_ticket_summary(normalized: dict) -> dict:
    return {
        "dataset": "sn_ticket_summary",
        "customer_name": normalized["customer_name"],
        "customer_sys_id": normalized["customer_sys_id"],
        "period_label": normalized["period_label"],
        "period_start": normalized["period_start"],
        "period_end": normalized["period_end"],
        "totals": normalized["totals"],
        "by_class": normalized["by_class"],
    }


def _extract_incident_summary(normalized: dict) -> dict:
    by_class = normalized["by_class"]
    inc = by_class.get("incident", {})
    return {
        "dataset": "sn_incident_summary",
        "customer_name": normalized["customer_name"],
        "period_label": normalized["period_label"],
        "open": inc.get("open", 0),
        "closed": inc.get("closed", 0),
        "cancelled": inc.get("cancelled", 0),
        "total": inc.get("total", 0),
        "priority_breakdown": normalized["dimensions"]["priority"],
        "monthly_opened": {
            "months": normalized["monthly_trend"]["months"],
            "values": normalized["monthly_trend"]["series"].get("incident", []),
        },
        "monthly_closed": {
            "months": normalized["monthly_closed"]["months"],
            "values": normalized["monthly_closed"]["series"].get("incident", []),
        },
    }


def _extract_request_summary(normalized: dict) -> dict:
    by_class = normalized["by_class"]
    req = by_class.get("sc_req_item", {})
    return {
        "dataset": "sn_request_summary",
        "customer_name": normalized["customer_name"],
        "period_label": normalized["period_label"],
        "open": req.get("open", 0),
        "closed": req.get("closed", 0),
        "cancelled": req.get("cancelled", 0),
        "total": req.get("total", 0),
        "monthly_opened": {
            "months": normalized["monthly_trend"]["months"],
            "values": normalized["monthly_trend"]["series"].get("sc_req_item", []),
        },
        "monthly_closed": {
            "months": normalized["monthly_closed"]["months"],
            "values": normalized["monthly_closed"]["series"].get("sc_req_item", []),
        },
    }


def _extract_change_summary(normalized: dict) -> dict:
    by_class = normalized["by_class"]
    chg = by_class.get("change_request", {})
    return {
        "dataset": "sn_change_summary",
        "customer_name": normalized["customer_name"],
        "period_label": normalized["period_label"],
        "open": chg.get("open", 0),
        "closed": chg.get("closed", 0),
        "cancelled": chg.get("cancelled", 0),
        "total": chg.get("total", 0),
        "monthly_opened": {
            "months": normalized["monthly_trend"]["months"],
            "values": normalized["monthly_trend"]["series"].get("change_request", []),
        },
        "monthly_closed": {
            "months": normalized["monthly_closed"]["months"],
            "values": normalized["monthly_closed"]["series"].get("change_request", []),
        },
    }


def _extract_problem_summary(normalized: dict) -> dict:
    by_class = normalized["by_class"]
    prb = by_class.get("problem", {})
    return {
        "dataset": "sn_problem_summary",
        "customer_name": normalized["customer_name"],
        "period_label": normalized["period_label"],
        "open": prb.get("open", 0),
        "closed": prb.get("closed", 0),
        "cancelled": prb.get("cancelled", 0),
        "total": prb.get("total", 0),
        "monthly_opened": {
            "months": normalized["monthly_trend"]["months"],
            "values": normalized["monthly_trend"]["series"].get("problem", []),
        },
        "monthly_closed": {
            "months": normalized["monthly_closed"]["months"],
            "values": normalized["monthly_closed"]["series"].get("problem", []),
        },
    }


def _extract_sla_summary(normalized: dict) -> dict:
    return {
        "dataset": "sn_sla_summary",
        "customer_name": normalized["customer_name"],
        "period_label": normalized["period_label"],
        "response": normalized["sla"]["response"],
        "resolution": normalized["sla"]["resolution"],
        "overall": normalized["sla"]["overall"],
        "unclassified": normalized["sla"]["unclassified"],
        "mttr_by_priority": normalized["mttr_by_priority"],
    }


def _extract_sla_trends(normalized: dict) -> dict:
    return {
        "dataset": "sn_sla_trends",
        "customer_name": normalized["customer_name"],
        "period_label": normalized["period_label"],
        "months": normalized["monthly_trend"]["months"],
        "monthly_opened_by_class": normalized["monthly_trend"]["series"],
        "monthly_closed_by_class": normalized["monthly_closed"]["series"],
    }


def _extract_aged_backlog(normalized: dict) -> dict:
    return {
        "dataset": "sn_aged_backlog",
        "customer_name": normalized["customer_name"],
        "period_label": normalized["period_label"],
        "total_open_incidents": normalized["by_class"].get("incident", {}).get("open", 0),
        "aged_buckets": normalized["dimensions"]["aged_buckets"],
        "assignment_group_breakdown": normalized["dimensions"]["assignment_group"],
        "aged_list": normalized["aged_list"],
        "aged_incidents_list": normalized["aged_incidents_list"],
    }


def _extract_dimensions(normalized: dict) -> dict:
    return {
        "dataset": "sn_dimensions",
        "customer_name": normalized["customer_name"],
        "period_label": normalized["period_label"],
        "priority": normalized["dimensions"]["priority"],
        "assignment_group": normalized["dimensions"]["assignment_group"],
        "business_service": normalized["dimensions"]["business_service"],
        "service_offering": normalized["dimensions"]["service_offering"],
        "contact_type": normalized["dimensions"]["contact_type"],
    }


def _extract_fcr(normalized: dict) -> dict:
    return {
        "dataset": "sn_fcr",
        "customer_name": normalized["customer_name"],
        "period_label": normalized["period_label"],
        **normalized["fcr"],
    }


def _extract_critical_incidents(normalized: dict) -> dict:
    return {
        "dataset": "sn_critical_incidents",
        "customer_name": normalized["customer_name"],
        "period_label": normalized["period_label"],
        **normalized["critical_incidents"],
    }


# ---------------------------------------------------------------------------
# Build artifacts
# ---------------------------------------------------------------------------

def build_servicenow_artifacts(context: dict, normalized: dict) -> dict:
    ticket_summary = _extract_ticket_summary(normalized)
    incident_summary = _extract_incident_summary(normalized)
    request_summary = _extract_request_summary(normalized)
    change_summary = _extract_change_summary(normalized)
    problem_summary = _extract_problem_summary(normalized)
    sla_summary = _extract_sla_summary(normalized)
    sla_trends = _extract_sla_trends(normalized)
    aged_backlog = _extract_aged_backlog(normalized)
    dimensions = _extract_dimensions(normalized)
    fcr = _extract_fcr(normalized)
    critical_incidents = _extract_critical_incidents(normalized)

    bundle = {
        "dataset": "servicenow_report_bundle",
        "customer_name": normalized["customer_name"],
        "customer_sys_id": normalized["customer_sys_id"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period_label": normalized["period_label"],
        "period_start": normalized["period_start"],
        "period_end": normalized["period_end"],
        "generated_at": normalized["generated_at"],
        "bundle_built_at": _now_iso(),
        # All sections
        "ticket_summary": ticket_summary,
        "incident_summary": incident_summary,
        "request_summary": request_summary,
        "change_summary": change_summary,
        "problem_summary": problem_summary,
        "sla_summary": sla_summary,
        "sla_trends": sla_trends,
        "aged_backlog": aged_backlog,
        "dimensions": dimensions,
        "fcr": fcr,
        "critical_incidents": critical_incidents,
        # Known gaps (for report drafting awareness)
        "known_gaps": [
            "category_subcategory_breakdown",
            "caller_dimension_top_callers",
            "sla_breach_detail_list",
            "monthly_sla_breach_counts",
            "per_priority_sla_targets",
            "open_request_list_ritm",
            "change_detail_list_chg",
            "problem_detail_list_prb",
            "csat_survey_data",
            "request_subtype_classification",
            "action_register_items",
            "daas_specific_backlog",
        ],
    }

    return {
        "ticket_summary": ticket_summary,
        "incident_summary": incident_summary,
        "request_summary": request_summary,
        "change_summary": change_summary,
        "problem_summary": problem_summary,
        "sla_summary": sla_summary,
        "sla_trends": sla_trends,
        "aged_backlog": aged_backlog,
        "dimensions": dimensions,
        "fcr": fcr,
        "critical_incidents": critical_incidents,
        "bundle": bundle,
    }


# ---------------------------------------------------------------------------
# Full pipeline entry point
# ---------------------------------------------------------------------------

def run_servicenow_pipeline(context: dict, snapshot: dict) -> dict:
    """
    End-to-end: normalize snapshot + build all artifacts.
    snapshot must be the raw saved response from get_customer_data__nexon_csi_.
    """
    normalized = normalize_servicenow_snapshot(context, snapshot)
    artifacts = build_servicenow_artifacts(context, normalized)
    return {
        "normalized": normalized,
        **artifacts,
    }
