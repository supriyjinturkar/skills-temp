from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


def _to_iso_ms(value) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        millis = int(value if value > 10_000_000_000 else value * 1000)
        return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _to_epoch_ms(value) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value if value > 10_000_000_000 else value * 1000)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return int(parsed.timestamp() * 1000)


def _round_value(value, decimals=2):
    return round(float(value or 0), decimals)


def _ratio_to_percent(numerator, denominator):
    if not denominator:
        return 0
    return _round_value((numerator / denominator) * 100, 2)


def _normalize_group_path(value) -> str:
    return "/".join([segment.strip() for segment in str(value or "").split("/") if segment.strip()])


def _label_from_group_path(value) -> str:
    normalized = _normalize_group_path(value)
    return normalized.split("/")[-1] if normalized else ""


def _dedupe_strings(values) -> list[str]:
    deduped = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _pick_primary_group(groups) -> dict:
    normalized = _dedupe_strings([_normalize_group_path(group) for group in groups])
    if not normalized:
        return {
            "primary_group_path": "Ungrouped",
            "primary_group_label": "Ungrouped",
            "all_group_paths": [],
            "group_labels": [],
        }
    normalized.sort(key=lambda value: (len(value.split("/")), len(value), value))
    primary = normalized[0]
    return {
        "primary_group_path": primary,
        "primary_group_label": _label_from_group_path(primary),
        "all_group_paths": normalized,
        "group_labels": _dedupe_strings([_label_from_group_path(value) for value in normalized]),
    }


def _normalize_severity(value) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"critical", "crit", "5"}:
        return "critical"
    if raw in {"error", "major", "4"}:
        return "error"
    if raw in {"warn", "warning", "2", "3"}:
        return "warning"
    if raw in {"info", "information", "1"}:
        return "info"
    if raw in {"normal", "ok", "clear", "cleared", "0"}:
        return "ok"
    return raw or "unknown"


def _normalize_host_status(value) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"up", "active", "normal", "reachable", "1"}:
        return "up"
    if raw in {"down", "unreachable", "0", "inactive"}:
        return "down"
    if raw in {"warning", "warn", "degraded"}:
        return "warning"
    return raw or "unknown"


def _parse_string_array(value) -> list[str]:
    if isinstance(value, list):
        return [str(entry).strip() for entry in value if str(entry).strip()]
    if isinstance(value, str):
        return [entry.strip() for entry in value.split(",") if entry.strip()]
    return []


def _safe_float(value):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _flatten_numeric_values(value) -> list[float]:
    if isinstance(value, list):
        values = []
        for entry in value:
            values.extend(_flatten_numeric_values(entry))
        return values
    if isinstance(value, dict):
        for key in ("values", "items", "data", "series", "points"):
            if key in value:
                nested = _flatten_numeric_values(value[key])
                if nested:
                    return nested
        for key in ("value", "avg", "max", "min"):
            numeric = _safe_float(value.get(key))
            if numeric is not None:
                return [numeric]
        return []
    numeric = _safe_float(value)
    return [] if numeric is None else [numeric]


def _average_value(values: list[float]) -> float | None:
    return _round_value(sum(values) / len(values), 2) if values else None


def _max_value(values: list[float]) -> float | None:
    return _round_value(max(values), 2) if values else None


def _section_items(section) -> list:
    if isinstance(section, dict):
        if isinstance(section.get("items"), list):
            return section["items"]
        if isinstance(section.get("items"), dict):
            return list(section["items"].values())
    return []


def _count_collected(section) -> int:
    if isinstance(section, dict):
        try:
            return int(section.get("count_collected") or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def _normalize_website_status(value) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"up", "active", "available", "normal", "healthy", "1"}:
        return "up"
    if raw in {"warning", "warn", "degraded"}:
        return "warning"
    if raw in {"down", "inactive", "unavailable", "critical", "0"}:
        return "down"
    return raw or "unknown"


def _normalize_metric_key(value) -> str:
    return "".join(character.lower() for character in str(value or "") if character.isalnum())


PERFORMANCE_COLLECTION_SPECS = {
    "cpu": {
        "datasource_exact": {"microsoftwindowscpu"},
        "metric_candidates": ["CPUBusyPercent"],
    },
    "memory": {
        "datasource_exact": {"winos"},
        "metric_candidates": ["MemoryUtilizationPercent"],
    },
    "disk": {
        "datasource_prefix": ("winvolumeusage",),
        "metric_candidates": ["PercentUsed"],
    },
    "ping": {
        "datasource_exact": {"ping"},
        "metric_candidates": ["PacketLossPercent"],
        "extra_metric_candidates": ["PingRTT", "RoundTripTime", "ResponseTime", "Latency"],
    },
    "network": {
        "datasource_prefix": ("winif",),
        "metric_candidates": ["ReceivedBitsPerSec", "InboundBitsPerSec"],
        "extra_metric_candidates": ["OutboundBitsPerSec", "TransmittedBitsPerSec", "SentBitsPerSec"],
    },
}


def _normalize_device(device: dict, site_property_key: str) -> dict:
    properties = device.get("systemProperties") or device.get("customProperties") or []
    matching_property = next(
        (
            entry
            for entry in properties
            if str(entry.get("name") or entry.get("key") or "").strip() == site_property_key
        ),
        None,
    )
    derived_groups = _parse_string_array((matching_property or {}).get("value") or (matching_property or {}).get("values") or "")
    group_selection = _pick_primary_group([
        *(_parse_string_array(device.get("__siteGroup") or "")),
        *derived_groups,
    ])
    return {
        "device_id": str(device.get("id") or ""),
        "name": str(
            device.get("displayName")
            or device.get("systemDisplayName")
            or device.get("name")
            or device.get("hostName")
            or device.get("hostname")
            or "unknown-device"
        ),
        "host_status": _normalize_host_status(device.get("hostStatus") or device.get("status")),
        "current_alert_status": _normalize_severity(device.get("currentAlertStatus") or device.get("alertStatus")),
        **group_selection,
    }


def _normalize_alert(alert: dict) -> dict:
    start_ms = _to_epoch_ms(alert.get("startEpoch") or alert.get("startTime") or alert.get("startDate"))
    cleared_ms = _to_epoch_ms(alert.get("clearedEpoch") or alert.get("clearedOn") or alert.get("endEpoch") or alert.get("endTime"))
    return {
        "alert_id": str(alert.get("id") or ""),
        "device_id": str(alert.get("deviceId") or alert.get("resourceId") or ((alert.get("device") or {}).get("id")) or ""),
        "device_name": str(
            alert.get("deviceDisplayName")
            or alert.get("deviceName")
            or alert.get("resourceName")
            or alert.get("monitorObjectName")
            or alert.get("hostName")
            or "unknown-device"
        ),
        "severity": _normalize_severity(alert.get("severity") or alert.get("priority")),
        "start_at": _to_iso_ms(start_ms),
        "start_ms": start_ms,
        "cleared_at": _to_iso_ms(cleared_ms),
        "cleared_ms": cleared_ms,
        "is_cleared": bool(cleared_ms or alert.get("isCleared") is True or alert.get("cleared") is True),
    }


def _build_device_indexes(devices: list[dict]) -> tuple[dict, dict]:
    by_id = {}
    by_name = {}
    for device in devices:
        if device["device_id"]:
            by_id[device["device_id"]] = device
        if device["name"]:
            by_name[device["name"]] = device
    return by_id, by_name


def _attach_alert_context(alerts: list[dict], by_id: dict, by_name: dict) -> list[dict]:
    with_context = []
    for alert in alerts:
        device = by_id.get(alert["device_id"]) or by_name.get(alert["device_name"]) or {}
        with_context.append({
            **alert,
            "device_name": device.get("name") or alert["device_name"],
            "primary_group_path": device.get("primary_group_path") or "Ungrouped",
            "primary_group_label": device.get("primary_group_label") or "Ungrouped",
        })
    return with_context


def normalize_collection(raw_state: dict, site_property_key: str) -> dict:
    devices = [_normalize_device(device, site_property_key) for device in raw_state.get("devices") or []]
    by_id, by_name = _build_device_indexes(devices)
    alerts = _attach_alert_context([_normalize_alert(alert) for alert in raw_state.get("alerts") or []], by_id, by_name)
    return {
        "groups": raw_state.get("groups") or [],
        "devices": devices,
        "alerts": alerts,
    }


def _build_alert_index(alerts: list[dict]) -> dict[str, list[dict]]:
    by_device = defaultdict(list)
    for alert in alerts:
        for key in {str(alert["device_id"]), str(alert["device_name"])}:
            if key:
                by_device[key].append(alert)
    return by_device


def _device_alerts(alert_index: dict[str, list[dict]], device: dict) -> list[dict]:
    return alert_index.get(device["device_id"]) or alert_index.get(device["name"]) or []


def _derive_device_health(device: dict, alerts_for_device: list[dict]) -> str:
    active_alerts = [alert for alert in alerts_for_device if not alert["is_cleared"]]
    severities = {alert["severity"] for alert in active_alerts}
    if device["host_status"] == "down" or "critical" in severities or "error" in severities:
        return "critical"
    if device["host_status"] == "warning" or "warning" in severities:
        return "warning"
    return "healthy"


def _build_daily_buckets(meta: dict, alerts: list[dict]) -> list[dict]:
    start = datetime.fromisoformat(meta["start_iso"].replace("Z", "+00:00")).date()
    end = datetime.fromisoformat(meta["end_iso"].replace("Z", "+00:00")).date()
    buckets = {}
    cursor = start
    while cursor <= end:
        buckets[str(cursor)] = {"date": str(cursor), "opened": 0, "closed": 0}
        cursor = cursor.fromordinal(cursor.toordinal() + 1)
    for alert in alerts:
        if alert["start_at"]:
            opened_key = alert["start_at"][:10]
            if opened_key in buckets:
                buckets[opened_key]["opened"] += 1
        if alert["cleared_at"]:
            closed_key = alert["cleared_at"][:10]
            if closed_key in buckets:
                buckets[closed_key]["closed"] += 1
    return [buckets[key] for key in sorted(buckets)]


def _calculate_mttr_hours(cleared_alerts: list[dict]) -> float:
    if not cleared_alerts:
        return 0
    durations = [
        (alert["cleared_ms"] - alert["start_ms"]) / 3_600_000
        for alert in cleared_alerts
        if alert["cleared_ms"] and alert["start_ms"] and alert["cleared_ms"] >= alert["start_ms"]
    ]
    return _round_value(sum(durations) / len(durations), 2) if durations else 0


def _calculate_oldest_open_alert_hours(meta: dict, alerts: list[dict]) -> float:
    end_ms = meta["end_ms"]
    open_alerts = [alert for alert in alerts if not alert["is_cleared"] and alert["start_ms"]]
    if not open_alerts:
        return 0
    oldest = min(open_alerts, key=lambda alert: alert["start_ms"])
    return _round_value((end_ms - oldest["start_ms"]) / 3_600_000, 2)


def _top_resources(devices: list[dict], alert_index: dict[str, list[dict]], limit: int) -> list[dict]:
    rows = []
    for device in devices:
        alerts = _device_alerts(alert_index, device)
        health = _derive_device_health(device, alerts)
        active = [alert for alert in alerts if not alert["is_cleared"]]
        issue = active[0]["severity"] if active else device["host_status"]
        rows.append({
            "name": device["name"],
            "site": device["primary_group_label"],
            "health": health,
            "issue": issue,
            "active_alerts": len(active),
        })
    rows.sort(key=lambda row: (row["health"] != "critical", -row["active_alerts"], row["name"]))
    return rows[:limit]


def _build_collection_metrics(meta: dict, normalized: dict) -> dict:
    alert_index = _build_alert_index(normalized["alerts"])
    site_summaries = {}
    impacted_devices = []
    healthy_devices = 0
    warning_devices = 0
    critical_devices = 0
    for device in normalized["devices"]:
        alerts = _device_alerts(alert_index, device)
        health = _derive_device_health(device, alerts)
        site = site_summaries.setdefault(device["primary_group_label"], {
            "name": device["primary_group_label"],
            "monitored_devices": 0,
            "healthy_devices": 0,
            "warning_devices": 0,
            "critical_devices": 0,
            "active_alerts": 0,
        })
        site["monitored_devices"] += 1
        site["active_alerts"] += len([alert for alert in alerts if not alert["is_cleared"]])
        if health == "healthy":
            healthy_devices += 1
            site["healthy_devices"] += 1
        elif health == "warning":
            warning_devices += 1
            site["warning_devices"] += 1
            impacted_devices.append(device)
        else:
            critical_devices += 1
            site["critical_devices"] += 1
            impacted_devices.append(device)
    site_rows = sorted(site_summaries.values(), key=lambda row: row["name"])
    cleared_alerts = [alert for alert in normalized["alerts"] if alert["is_cleared"]]
    active_alerts = [alert for alert in normalized["alerts"] if not alert["is_cleared"]]
    for site in site_rows:
        site["availability_percent"] = _ratio_to_percent(site["healthy_devices"], site["monitored_devices"])
        site["active_alerts_per_100_devices"] = _round_value((site["active_alerts"] / max(site["monitored_devices"], 1)) * 100, 2)
    return {
        "alert_index": alert_index,
        "site_summaries": site_rows,
        "cleared_alerts": cleared_alerts,
        "active_alerts": active_alerts,
        "impacted_devices": impacted_devices,
        "device_health_counts": {
            "healthy_devices": healthy_devices,
            "warning_devices": warning_devices,
            "critical_devices": critical_devices,
        },
        "kpis": {
            "monitored_devices": len(normalized["devices"]),
            "sites_in_scope": len(site_rows),
            "alerts_opened": len(normalized["alerts"]),
            "alerts_closed": len(cleared_alerts),
            "alerts_active_end_of_window": len(active_alerts),
            "clear_rate_percent": _ratio_to_percent(len(cleared_alerts), len(normalized["alerts"])),
            "alerts_per_100_devices": _round_value((len(normalized["alerts"]) / max(len(normalized["devices"]), 1)) * 100, 2),
            "active_alerts_per_100_devices": _round_value((len(active_alerts) / max(len(normalized["devices"]), 1)) * 100, 2),
            "impacted_devices": len(impacted_devices),
            "impacted_devices_percent": _ratio_to_percent(len(impacted_devices), len(normalized["devices"])),
            "healthy_devices": healthy_devices,
            "warning_devices": warning_devices,
            "critical_devices": critical_devices,
            "healthy_device_percent": _ratio_to_percent(healthy_devices, len(normalized["devices"])),
            "critical_device_percent": _ratio_to_percent(critical_devices, len(normalized["devices"])),
            "mttr_hours": _calculate_mttr_hours(cleared_alerts),
            "oldest_open_alert_hours": _calculate_oldest_open_alert_hours(meta, normalized["alerts"]),
        },
    }


def build_availability_summary(meta: dict, normalized: dict) -> dict:
    metrics = _build_collection_metrics(meta, normalized)
    totals = {
        "monitored_devices": sum(site["monitored_devices"] for site in metrics["site_summaries"]),
        "healthy_devices": sum(site["healthy_devices"] for site in metrics["site_summaries"]),
        "warning_devices": sum(site["warning_devices"] for site in metrics["site_summaries"]),
        "critical_devices": sum(site["critical_devices"] for site in metrics["site_summaries"]),
    }
    notable = _top_resources(normalized["devices"], metrics["alert_index"], 3)
    return {
        "datasource": "logicmonitor",
        "dataset": "availability_summary",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "uptime_window": {
            "start": meta["start_iso"],
            "end": meta["end_iso"],
        },
        "availability_percent": _ratio_to_percent(totals["healthy_devices"], totals["monitored_devices"]),
        "monitored_devices": totals["monitored_devices"],
        "healthy_devices": totals["healthy_devices"],
        "warning_devices": totals["warning_devices"],
        "critical_devices": totals["critical_devices"],
        "impacted_devices": metrics["kpis"]["impacted_devices"],
        "impacted_devices_percent": metrics["kpis"]["impacted_devices_percent"],
        "sites": metrics["site_summaries"],
        "availability_method": "logicmonitor_device_health_proxy",
        "grouping_method": "single_primary_group_per_device",
        "notable_exceptions": [f"{resource['name']} ({resource['health']}, {resource['issue']})" for resource in notable],
    }


def build_alert_trends(meta: dict, normalized: dict) -> dict:
    metrics = _build_collection_metrics(meta, normalized)
    severity_breakdown = {"critical": 0, "error": 0, "warning": 0, "info": 0, "ok": 0, "unknown": 0}
    top_devices = defaultdict(int)
    top_sites = defaultdict(int)
    for alert in normalized["alerts"]:
        severity_breakdown[alert["severity"]] = int(severity_breakdown.get(alert["severity"], 0)) + 1
        top_devices[alert["device_name"]] += 1
        top_sites[alert["primary_group_label"] or "Ungrouped"] += 1
    return {
        "datasource": "logicmonitor",
        "dataset": "alert_trends",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "alert_counts_opened": len(normalized["alerts"]),
        "alert_counts_closed": len(metrics["cleared_alerts"]),
        "alert_counts_active": len(metrics["active_alerts"]),
        "clear_rate_percent": metrics["kpis"]["clear_rate_percent"],
        "mean_time_to_clear_hours": metrics["kpis"]["mttr_hours"],
        "oldest_open_alert_hours": metrics["kpis"]["oldest_open_alert_hours"],
        "alerts_per_100_devices": metrics["kpis"]["alerts_per_100_devices"],
        "active_alerts_per_100_devices": metrics["kpis"]["active_alerts_per_100_devices"],
        "alert_severity_breakdown": severity_breakdown,
        "daily_alert_flow": _build_daily_buckets(meta, normalized["alerts"]),
        "top_devices_by_alerts": [
            {"name": name, "alerts": count}
            for name, count in sorted(top_devices.items(), key=lambda item: (-item[1], item[0]))[:5]
        ],
        "top_sites_by_alerts": [
            {"name": name, "alerts": count}
            for name, count in sorted(top_sites.items(), key=lambda item: (-item[1], item[0]))[:5]
        ],
    }


def build_resource_health(meta: dict, normalized: dict) -> dict:
    metrics = _build_collection_metrics(meta, normalized)
    return {
        "datasource": "logicmonitor",
        "dataset": "resource_health",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "monitored_devices": len(normalized["devices"]),
        "healthy_devices": metrics["device_health_counts"]["healthy_devices"],
        "warning_devices": metrics["device_health_counts"]["warning_devices"],
        "critical_devices": metrics["device_health_counts"]["critical_devices"],
        "healthy_device_percent": metrics["kpis"]["healthy_device_percent"],
        "critical_device_percent": metrics["kpis"]["critical_device_percent"],
        "impacted_devices": metrics["kpis"]["impacted_devices"],
        "impacted_devices_percent": metrics["kpis"]["impacted_devices_percent"],
        "top_unhealthy_resources": _top_resources(normalized["devices"], metrics["alert_index"], 5),
    }


def _build_derived_metrics(meta: dict, normalized: dict) -> dict:
    metrics = _build_collection_metrics(meta, normalized)
    availability_percent = _ratio_to_percent(
        metrics["device_health_counts"]["healthy_devices"],
        len(normalized["devices"]),
    )
    return {
        "datasource": "logicmonitor",
        "dataset": "derived_metrics",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "kpi_cards": [
            {"key": "monitored_devices", "label": "Monitored devices", "value": metrics["kpis"]["monitored_devices"]},
            {"key": "availability_percent", "label": "Availability proxy %", "value": availability_percent, "unit": "%"},
            {"key": "alerts_opened", "label": "Alerts opened", "value": metrics["kpis"]["alerts_opened"]},
            {"key": "alerts_active_end_of_window", "label": "Active alerts at period end", "value": metrics["kpis"]["alerts_active_end_of_window"]},
            {"key": "clear_rate_percent", "label": "Alert clear rate %", "value": metrics["kpis"]["clear_rate_percent"], "unit": "%"},
            {"key": "mttr_hours", "label": "Mean time to clear", "value": metrics["kpis"]["mttr_hours"], "unit": "hours"},
        ],
        "device_health_kpis": {
            "monitored_devices": metrics["kpis"]["monitored_devices"],
            "healthy_devices": metrics["kpis"]["healthy_devices"],
            "warning_devices": metrics["kpis"]["warning_devices"],
            "critical_devices": metrics["kpis"]["critical_devices"],
            "healthy_device_percent": metrics["kpis"]["healthy_device_percent"],
            "critical_device_percent": metrics["kpis"]["critical_device_percent"],
            "impacted_devices": metrics["kpis"]["impacted_devices"],
            "impacted_devices_percent": metrics["kpis"]["impacted_devices_percent"],
        },
        "alert_handling_kpis": {
            "alerts_opened": metrics["kpis"]["alerts_opened"],
            "alerts_closed": metrics["kpis"]["alerts_closed"],
            "alerts_active_end_of_window": metrics["kpis"]["alerts_active_end_of_window"],
            "clear_rate_percent": metrics["kpis"]["clear_rate_percent"],
            "alerts_per_100_devices": metrics["kpis"]["alerts_per_100_devices"],
            "active_alerts_per_100_devices": metrics["kpis"]["active_alerts_per_100_devices"],
            "mean_time_to_clear_hours": metrics["kpis"]["mttr_hours"],
            "oldest_open_alert_hours": metrics["kpis"]["oldest_open_alert_hours"],
        },
    }


def _build_site_operations(meta: dict, normalized: dict) -> dict:
    metrics = _build_collection_metrics(meta, normalized)
    return {
        "datasource": "logicmonitor",
        "dataset": "site_operations",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "sites": metrics["site_summaries"],
    }


def build_report_bundle(meta: dict, normalized: dict, snapshot: dict) -> dict:
    availability = build_availability_summary(meta, normalized)
    alerts = build_alert_trends(meta, normalized)
    health = build_resource_health(meta, normalized)
    derived_metrics = _build_derived_metrics(meta, normalized)
    site_operations = _build_site_operations(meta, normalized)
    monitoring_coverage = build_monitoring_coverage(meta, snapshot)
    website_experience = build_website_experience(meta, snapshot)
    platform_assets = build_platform_assets(meta, snapshot)
    report_inventory = build_report_inventory(meta, snapshot)
    inventory_exceptions = build_inventory_exceptions(meta, snapshot)
    root_scope_summary = build_root_scope_summary(meta, snapshot)
    device_availability = build_device_availability(meta, snapshot)
    cpu_memory_utilization = build_cpu_memory_utilization(meta, snapshot)
    disk_capacity_utilization = build_disk_capacity_utilization(meta, snapshot)
    network_interface_throughput = build_network_interface_throughput(meta, snapshot)
    return {
        "datasource": "logicmonitor",
        "dataset": "logicmonitor_report_bundle",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "generated_at": meta["generated_at"],
        "sections": {
            "executive_summary": " ".join([
                f"{availability['monitored_devices']} monitored devices were evaluated for the reporting window.",
                f"{monitoring_coverage['unmonitored_devices']} additional devices are currently marked as unmonitored.",
                f"{website_experience['monitored_websites']} monitored websites were included in the LogicMonitor collection.",
                f"{alerts['alert_counts_closed']} alerts were cleared compared with {alerts['alert_counts_opened']} alerts opened.",
                f"{health['critical_devices']} devices remained in critical state at the end of the collection window.",
                f"{derived_metrics['alert_handling_kpis']['clear_rate_percent']}% of alerts were cleared inside the reporting window.",
            ]),
            "derived_metrics": derived_metrics,
            "availability_summary": availability,
            "alert_trends": alerts,
            "resource_health": health,
            "site_operations": site_operations,
            "monitoring_coverage": monitoring_coverage,
            "website_experience": website_experience,
            "platform_assets": platform_assets,
            "report_inventory": report_inventory,
            "inventory_exceptions": inventory_exceptions,
            "root_scope_summary": root_scope_summary,
            "device_availability": device_availability,
            "cpu_memory_utilization": cpu_memory_utilization,
            "disk_capacity_utilization": disk_capacity_utilization,
            "network_interface_throughput": network_interface_throughput,
            "collection_notes": {
                "availability_method": availability["availability_method"],
                "grouping_method": availability["grouping_method"],
                "site_groups": [site["name"] for site in availability["sites"]],
            },
        },
    }


def _extract_items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("items"), list):
            return payload["items"]
        data = payload.get("data")
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data, list):
            return data
    return []


def _extract_total(payload):
    if not isinstance(payload, dict):
        return None
    candidates = [payload.get("total"), payload.get("totalCount"), (payload.get("data") or {}).get("total"), (payload.get("data") or {}).get("totalCount")]
    for candidate in candidates:
        try:
            numeric = int(candidate)
        except (TypeError, ValueError):
            continue
        if numeric >= 0:
            return numeric
    return None


class LogicMonitorApi:
    def __init__(self, config: dict, fetch_impl=None, sleep_impl=None):
        self.config = config
        self.fetch_impl = fetch_impl or self._default_fetch
        self.sleep_impl = sleep_impl or time.sleep
        self.timeout_seconds = max(1, int(config.get("request_timeout_seconds", 60)))
        self.retry_attempts = max(0, int(config.get("request_retry_attempts", 2)))
        self.retry_backoff_ms = max(100, int(config.get("request_retry_backoff_ms", 1000)))
        self.fetch_page_size = max(1, int(config.get("fetch_page_size", 200)))
        self.max_pages_per_endpoint = max(0, int(config.get("max_pages_per_endpoint", 0)))
        self.alert_chunk_hours = max(1, int(config.get("alert_chunk_hours", 24)))
        self.diagnostics = {
            "requests_made": [],
            "errors": [],
        }

    def _base_url(self) -> str:
        return f"https://{self.config['account_name']}.logicmonitor.com/santaba/rest"

    def _build_request(self, method: str, resource_path: str, query: dict | None = None, body=None):
        query_string = f"?{urlencode(query or {}, doseq=True)}" if query else ""
        resource_path_with_query = f"{resource_path}{query_string}"
        body_text = "" if body is None else json.dumps(body)
        headers = {
            "Accept": "application/json",
            "X-Version": str(self.config.get("api_version") or 3),
            # Authorization is injected by the nexon-logicmonitor-api sandbox
            # Access Profile proxy — do not set it here.
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        return f"{self._base_url()}{resource_path_with_query}", headers, body_text.encode("utf-8") if body is not None else None

    def _default_fetch(self, method: str, url: str, headers: dict, body):
        request = Request(url=url, method=method, headers=headers, data=body)
        with urlopen(request, timeout=self.timeout_seconds) as response:
            status = getattr(response, "status", 200)
            raw_headers = dict(response.headers.items())
            text = response.read().decode("utf-8")
        return status, raw_headers, text

    def request(self, method: str, resource_path: str, query: dict | None = None, body=None):
        last_error = None
        for attempt in range(self.retry_attempts + 1):
            url, headers, body_bytes = self._build_request(method, resource_path, query=query, body=body)
            try:
                status, response_headers, text = self.fetch_impl(method, url, headers, body_bytes)
                payload = json.loads(text) if text else {}
                self.diagnostics["requests_made"].append({
                    "method": method,
                    "resource_path": resource_path,
                    "status": status,
                    "attempt": attempt + 1,
                    "url": url,
                })
                if status >= 400:
                    raise HTTPError(url, status, text, None, None)
                return payload
            except HTTPError as error:
                last_error = error
                retriable = error.code == 429 or error.code >= 500
                if retriable and attempt < self.retry_attempts:
                    self.sleep_impl((self.retry_backoff_ms * (attempt + 1)) / 1000)
                    continue
                message = f"LogicMonitor API {method} {resource_path} failed with {error.code}: {error.reason or ''}".strip()
                self.diagnostics["errors"].append({"method": method, "resource_path": resource_path, "status": error.code, "message": message})
                raise RuntimeError(message) from error
            except (URLError, ValueError, json.JSONDecodeError) as error:
                last_error = error
                if attempt < self.retry_attempts:
                    self.sleep_impl((self.retry_backoff_ms * (attempt + 1)) / 1000)
                    continue
                message = f"LogicMonitor API {method} {resource_path} failed: {error}"
                self.diagnostics["errors"].append({"method": method, "resource_path": resource_path, "status": "request_error", "message": message})
                raise RuntimeError(message) from error
        raise RuntimeError(str(last_error))

    def list_paged(self, resource_path: str, query: dict | None = None) -> dict:
        items = []
        pages = 0
        total = None
        while True:
            if self.max_pages_per_endpoint > 0 and pages >= self.max_pages_per_endpoint:
                raise RuntimeError(f"LogicMonitor pagination safety limit reached for {resource_path}.")
            payload = self.request("GET", resource_path, query={**(query or {}), "size": self.fetch_page_size, "offset": pages * self.fetch_page_size})
            page_items = _extract_items(payload)
            if total is None:
                total = _extract_total(payload)
            items.extend(page_items)
            pages += 1
            if len(page_items) < self.fetch_page_size:
                break
        return {
            "count_collected": len(items),
            "items": items,
            "total": total if total is not None else len(items),
            "pages": pages,
        }

    def fetch_device_groups(self, group_identifiers: list[str]) -> dict:
        groups = self.list_paged("/device/groups")
        if not group_identifiers:
            return groups
        wanted = {value.strip().lower() for value in group_identifiers if value.strip()}
        filtered = []
        for group in groups["items"]:
            candidates = {
                str(group.get("id") or "").strip().lower(),
                str(group.get("name") or "").strip().lower(),
                str(group.get("fullPath") or group.get("name") or "").strip().lower(),
            }
            if candidates & wanted:
                filtered.append(group)
        return {
            **groups,
            "count_collected": len(filtered),
            "items": filtered,
        }

    def fetch_devices_for_groups(self, groups: list[dict]) -> dict:
        devices = []
        seen = set()
        for group in groups:
            group_devices = self.list_paged(f"/device/groups/{group['id']}/devices")
            for device in group_devices["items"]:
                key = str(device.get("id") or f"{group['id']}:{device.get('name', '')}")
                merged = {
                    **device,
                    "__siteGroup": group.get("fullPath") or group.get("name") or str(group.get("id") or "unknown-group"),
                }
                if key not in seen:
                    seen.add(key)
                    devices.append(merged)
        return {
            "count_collected": len(devices),
            "items": devices,
            "total": len(devices),
        }

    def fetch_devices(self, group_identifiers: list[str]) -> dict:
        groups = self.fetch_device_groups(group_identifiers)
        if groups["items"]:
            return {
                "groups": groups,
                "devices": self.fetch_devices_for_groups(groups["items"]),
            }
        return {
            "groups": {"count_collected": 0, "items": [], "total": 0, "pages": 0},
            "devices": self.list_paged("/device/devices"),
        }

    def fetch_entity_details(self, resource_path_base: str, items: list[dict]) -> dict:
        rows = {}
        for item in items:
            identifier = item.get("id", item)
            payload = self.request("GET", f"{resource_path_base}/{identifier}")
            rows[str(payload.get("id", identifier))] = payload
        return {
            "count_collected": len(rows),
            "items": rows,
        }

    def _is_optional_endpoint_unavailable(self, error: RuntimeError) -> bool:
        message = str(error)
        return "404" in message or "403" in message or "406" in message

    def fetch_optional_paged(self, resource_path: str) -> dict:
        try:
            return self.list_paged(resource_path)
        except RuntimeError as error:
            if not self._is_optional_endpoint_unavailable(error):
                raise
            return _empty_paged_result()

    def fetch_unmonitored_devices(self) -> dict:
        try:
            return self.list_paged("/device/unmonitoreddevices")
        except RuntimeError:
            return self.list_paged("/device/devices", query={"filter": 'hostStatus:"unmonitored"'})

    def fetch_website_groups(self) -> dict:
        return self.fetch_optional_paged("/website/groups")

    def fetch_websites(self) -> dict:
        return self.fetch_optional_paged("/website/websites")

    def fetch_smcheckpoints(self) -> dict:
        return self.fetch_optional_paged("/setting/smcheckpoints")

    def fetch_collectors(self) -> dict:
        return self.fetch_optional_paged("/setting/collectors")

    def fetch_reports(self) -> dict:
        return self.fetch_optional_paged("/report/reports")

    def fetch_device_datasources(self, device_id) -> dict:
        return self.list_paged(f"/device/devices/{device_id}/devicedatasources")

    def fetch_datasource_instances(self, device_id, datasource_id) -> dict:
        return self.list_paged(f"/device/devices/{device_id}/devicedatasources/{datasource_id}/instances")

    def fetch_datasource_instance_data(
        self,
        device_id,
        datasource_id,
        instance_id,
        metric_candidates: list[str],
        start_ms: int,
        end_ms: int,
    ):
        query = {
            "datapoints": ",".join(metric_candidates),
            "start": start_ms,
            "end": end_ms,
        }
        return self.request(
            "GET",
            f"/device/devices/{device_id}/devicedatasources/{datasource_id}/instances/{instance_id}/data",
            query=query,
        )

    def fetch_alerts(self, start_ms: int, end_ms: int, options: dict | None = None) -> dict:
        options = options or {}
        all_alerts = []
        chunk_ms = self.alert_chunk_hours * 3_600_000
        cursor = start_ms
        while cursor < end_ms:
            next_cursor = min(end_ms, cursor + chunk_ms)
            filters = [
                f"startEpoch>:{math.floor(cursor / 1000)}",
                f"startEpoch<:{math.ceil(next_cursor / 1000)}",
            ]
            if options.get("cleared") is True:
                filters.append("cleared:true")
            if options.get("cleared") is False:
                filters.append("cleared:false")
            resource_path = f"/device/groups/{options['group_id']}/alerts" if options.get("group_id") is not None else "/alert/alerts"
            alerts = self.list_paged(resource_path, query={"filter": ",".join(filters), "sort": "+startEpoch"})
            all_alerts.extend(alerts["items"])
            cursor = next_cursor
        deduped = []
        seen = set()
        for alert in all_alerts:
            key = str(alert.get("id") or "")
            if key and key not in seen:
                seen.add(key)
                deduped.append(alert)
        return {
            "count_collected": len(deduped),
            "items": deduped,
        }

    def fetch_root_scope(self, root_device_group_id, root_website_group_id, start_ms: int, end_ms: int) -> dict:
        result = {
            "device_group_id": root_device_group_id,
            "device_group_devices": {"count_collected": 0, "items": [], "total": 0},
            "device_group_alerts": {"count_collected": 0, "items": []},
            "website_group_id": root_website_group_id,
            "website_group_websites": {"count_collected": 0, "items": [], "total": 0},
        }
        if root_device_group_id is not None:
            result["device_group_devices"] = self.list_paged(f"/device/groups/{root_device_group_id}/devices")
            result["device_group_alerts"] = self.fetch_alerts(start_ms, end_ms, {"group_id": root_device_group_id, "cleared": False})
        if root_website_group_id is not None:
            result["website_group_websites"] = self.fetch_optional_paged(f"/website/groups/{root_website_group_id}/websites")
        return result

    def get_diagnostics(self) -> dict:
        return {
            "requests_made": list(self.diagnostics["requests_made"]),
            "errors": list(self.diagnostics["errors"]),
        }


def _empty_paged_result() -> dict:
    return {"count_collected": 0, "items": [], "total": 0, "pages": 0}


def _empty_entity_details() -> dict:
    return {"count_collected": 0, "items": {}}


def _normalize_match_text(value) -> str:
    return " ".join("".join(character.lower() if character.isalnum() else " " for character in str(value or "")).split())


def _tokenize_match_text(value) -> set[str]:
    normalized = _normalize_match_text(value)
    return {token for token in normalized.split(" ") if token}


def _group_depth(group: dict) -> int:
    full_path = str(group.get("fullPath") or group.get("name") or "")
    return len([segment for segment in full_path.split("/") if segment.strip()])


def _group_label(group: dict) -> str:
    return str(group.get("fullPath") or group.get("name") or "").split("/")[-1].strip()


def _score_group_candidate(group: dict, queries: list[str]) -> tuple[int, str]:
    full_path = str(group.get("fullPath") or group.get("name") or "").strip()
    name = str(group.get("name") or "").strip()
    label = _group_label(group)
    normalized_path = _normalize_match_text(full_path)
    normalized_name = _normalize_match_text(name)
    normalized_label = _normalize_match_text(label)
    path_tokens = _tokenize_match_text(full_path)
    name_tokens = _tokenize_match_text(name)
    best_score = 0
    best_reason = "no_match"
    for query in queries:
        normalized_query = _normalize_match_text(query)
        query_tokens = _tokenize_match_text(query)
        if not normalized_query:
            continue
        if normalized_query == normalized_path:
            if 100 > best_score:
                best_score = 100
                best_reason = "exact_full_path"
            continue
        if normalized_query == normalized_name:
            if 95 > best_score:
                best_score = 95
                best_reason = "exact_name"
            continue
        if normalized_query == normalized_label:
            if 92 > best_score:
                best_score = 92
                best_reason = "exact_leaf_label"
            continue
        if normalized_query and normalized_query in normalized_path:
            if 82 > best_score:
                best_score = 82
                best_reason = "path_contains_query"
        if normalized_query and normalized_query in normalized_name:
            if 78 > best_score:
                best_score = 78
                best_reason = "name_contains_query"
        if query_tokens:
            overlap = len(query_tokens & path_tokens)
            if overlap:
                path_score = min(76, 50 + overlap * 8)
                if path_score > best_score:
                    best_score = path_score
                    best_reason = "path_token_overlap"
            name_overlap = len(query_tokens & name_tokens)
            if name_overlap:
                name_score = min(72, 46 + name_overlap * 8)
                if name_score > best_score:
                    best_score = name_score
                    best_reason = "name_token_overlap"
    return best_score, best_reason


def _collect_descendant_groups(root_group: dict, groups: list[dict]) -> list[dict]:
    root_path = str(root_group.get("fullPath") or root_group.get("name") or "").strip()
    if not root_path:
        return [root_group]
    prefix = f"{root_path}/"
    descendants = []
    for group in groups:
        candidate = str(group.get("fullPath") or group.get("name") or "").strip()
        if candidate == root_path or candidate.startswith(prefix):
            descendants.append(group)
    descendants.sort(key=lambda group: (_group_depth(group), str(group.get("fullPath") or group.get("name") or "")))
    return descendants


def _confidence_label(best_score: int, second_score: int) -> str:
    if best_score >= 90 and best_score - second_score >= 10:
        return "high"
    if best_score >= 75:
        return "medium"
    if best_score >= 55:
        return "low"
    return "none"


def _safe_list_paged(api: LogicMonitorApi, resource_path: str) -> dict:
    try:
        return api.list_paged(resource_path)
    except RuntimeError as error:
        message = str(error)
        if "404" not in message and "403" not in message and "406" not in message:
            raise
        return _empty_paged_result()


def _safe_fetch_entity_details(api: LogicMonitorApi, resource_path_base: str, items: list[dict]) -> dict:
    if not items:
        return _empty_entity_details()
    try:
        return api.fetch_entity_details(resource_path_base, items)
    except RuntimeError as error:
        message = str(error)
        if "404" not in message and "403" not in message and "406" not in message:
            raise
        return _empty_entity_details()


def _fetch_scoped_alerts(api: LogicMonitorApi, group_ids: list, start_ms: int, end_ms: int, cleared: bool) -> dict:
    if not group_ids:
        return _empty_paged_result()
    merged = []
    seen = set()
    for group_id in group_ids:
        result = api.fetch_alerts(start_ms, end_ms, {"group_id": group_id, "cleared": cleared})
        for item in result["items"]:
            key = str(item.get("id") or "")
            if key and key not in seen:
                seen.add(key)
                merged.append(item)
    return {"count_collected": len(merged), "items": merged}


def _fetch_website_scope(api: LogicMonitorApi, context: dict) -> dict:
    if context["logicmonitor"]["root_website_group_id"] is None:
        return {
            "website_groups": _empty_paged_result(),
            "website_group_details": _empty_entity_details(),
            "websites": _empty_paged_result(),
            "website_details": _empty_entity_details(),
        }
    root_scope = api.fetch_root_scope(
        None,
        context["logicmonitor"]["root_website_group_id"],
        context["period"]["start_ms"],
        context["period"]["end_ms"],
    )
    website_groups = {
        "count_collected": 1,
        "items": [{"id": context["logicmonitor"]["root_website_group_id"]}],
        "total": 1,
        "pages": 1,
    }
    return {
        "website_groups": website_groups,
        "website_group_details": _safe_fetch_entity_details(api, "/website/groups", website_groups["items"]),
        "websites": root_scope.get("website_group_websites") or _empty_paged_result(),
        "website_details": _safe_fetch_entity_details(api, "/website/websites", (root_scope.get("website_group_websites") or {}).get("items") or []),
    }


def _normalized_input_from_snapshot(snapshot: dict) -> dict:
    return {
        "groups": (snapshot.get("inventory") or {}).get("device_groups", {}).get("items") or [],
        "devices": (snapshot.get("inventory") or {}).get("devices", {}).get("items") or [],
        "alerts": [
            *((snapshot.get("alerts") or {}).get("open", {}).get("items") or []),
            *((snapshot.get("alerts") or {}).get("cleared", {}).get("items") or []),
        ],
    }


def _filter_normalized_collection(normalized: dict, site_groups: list[str]) -> dict:
    wanted = [entry.strip().lower() for entry in site_groups if entry.strip()]
    if not wanted:
        return normalized
    devices = []
    for device in normalized["devices"]:
        candidates = [
            device.get("primary_group_path"),
            device.get("primary_group_label"),
            *(device.get("all_group_paths") or []),
            *(device.get("group_labels") or []),
        ]
        lowered = [str(entry or "").strip().lower() for entry in candidates if str(entry or "").strip()]
        if any(candidate in wanted for candidate in lowered):
            devices.append(device)
    device_keys = {str(device["device_id"]) for device in devices} | {str(device["name"]) for device in devices}
    alerts = [
        alert
        for alert in normalized["alerts"]
        if str(alert["device_id"]) in device_keys
        or str(alert["device_name"]) in device_keys
        or str(alert.get("primary_group_label") or "").strip().lower() in wanted
    ]
    return {
        **normalized,
        "devices": devices,
        "alerts": alerts,
    }


def _build_observability_artifact(context: dict, normalized: dict) -> dict:
    return {
        "datasource": "logicmonitor",
        "dataset": "observability",
        "customer_id": context["customer_id"],
        "customer_name": context["customer_name"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period_label": context["period"]["label"],
        "generated_at": context["generated_at"],
        "source_scope": {
            "group_identifiers": context["logicmonitor"]["group_identifiers"],
            "site_groups": context["logicmonitor"]["site_groups"],
            "root_device_group_id": context["logicmonitor"]["root_device_group_id"],
            "root_website_group_id": context["logicmonitor"]["root_website_group_id"],
        },
        "totals": {
            "groups": len(normalized["groups"]),
            "devices": len(normalized["devices"]),
            "alerts": len(normalized["alerts"]),
        },
        "normalized": normalized,
    }


def _summarize_source_inventory(snapshot: dict) -> dict:
    inventory = snapshot.get("inventory") or {}
    alerts = snapshot.get("alerts") or {}
    return {
        "device_groups": (inventory.get("device_groups") or {}).get("count_collected", 0),
        "devices": (inventory.get("devices") or {}).get("count_collected", 0),
        "unmonitored_devices": (inventory.get("unmonitored_devices") or {}).get("count_collected", 0),
        "website_groups": (inventory.get("website_groups") or {}).get("count_collected", 0),
        "websites": (inventory.get("websites") or {}).get("count_collected", 0),
        "collectors": (inventory.get("collectors") or {}).get("count_collected", 0),
        "checkpoints": (inventory.get("smcheckpoints") or {}).get("count_collected", 0),
        "reports": (inventory.get("reports") or {}).get("count_collected", 0),
        "open_alerts": (alerts.get("open") or {}).get("count_collected", 0),
        "cleared_alerts": (alerts.get("cleared") or {}).get("count_collected", 0),
    }


def _device_name(device: dict) -> str:
    return str(
        device.get("displayName")
        or device.get("systemDisplayName")
        or device.get("name")
        or device.get("hostName")
        or device.get("hostname")
        or f"device-{device.get('id', 'unknown')}"
    )


def _datasource_name_variants(datasource: dict) -> list[str]:
    return [
        _normalize_metric_key(datasource.get("name")),
        _normalize_metric_key(datasource.get("displayName")),
        _normalize_metric_key(datasource.get("dataSourceName")),
    ]


def _match_performance_collection_key(datasource: dict) -> str | None:
    variants = [value for value in _datasource_name_variants(datasource) if value]
    if not variants:
        return None
    for collection_key, spec in PERFORMANCE_COLLECTION_SPECS.items():
        if any(value in spec.get("datasource_exact", set()) for value in variants):
            return collection_key
        if any(any(value.startswith(prefix) for prefix in spec.get("datasource_prefix", ())) for value in variants):
            return collection_key
    return None


def _instance_label(instance: dict) -> str:
    return str(
        instance.get("name")
        or instance.get("displayName")
        or instance.get("instanceDescription")
        or instance.get("description")
        or instance.get("wildvalue")
        or instance.get("id")
        or "unknown-instance"
    )


def _collect_series_from_payload(payload, series: dict[str, list[float]]) -> None:
    if isinstance(payload, dict):
        datapoints = payload.get("datapoints")
        if isinstance(datapoints, dict):
            for name, values in datapoints.items():
                flattened = _flatten_numeric_values(values)
                if flattened:
                    series[_normalize_metric_key(name)] = flattened
        if "name" in payload:
            flattened = _flatten_numeric_values(payload.get("values") or payload.get("data") or payload.get("items"))
            if flattened:
                series[_normalize_metric_key(payload.get("name"))] = flattened
        for value in payload.values():
            if isinstance(value, (dict, list)):
                _collect_series_from_payload(value, series)
        return
    if isinstance(payload, list):
        for item in payload:
            _collect_series_from_payload(item, series)


def _extract_named_series(payload) -> dict[str, list[float]]:
    series: dict[str, list[float]] = {}
    _collect_series_from_payload(payload, series)
    if not series:
        flattened = _flatten_numeric_values(payload)
        if flattened:
            series["default"] = flattened
    return series


def _choose_series_values(series: dict[str, list[float]], candidates: list[str]) -> list[float]:
    for candidate in candidates:
        values = series.get(_normalize_metric_key(candidate))
        if values:
            return values
    return series.get("default") or []


def _collect_performance_metrics(api: LogicMonitorApi, context: dict, devices: list[dict]) -> dict:
    summary = {
        "devices_considered": len(devices),
        "matched_datasources": {key: 0 for key in PERFORMANCE_COLLECTION_SPECS},
        "matched_instances": {key: 0 for key in PERFORMANCE_COLLECTION_SPECS},
    }
    devices_with_metrics = {key: set() for key in PERFORMANCE_COLLECTION_SPECS}
    availability_rows = []
    cpu_rows = []
    memory_rows = []
    disk_rows = []
    network_rows = []
    for device in devices:
        device_id = device.get("id")
        if device_id in (None, ""):
            continue
        device_id_text = str(device_id)
        device_name = _device_name(device)
        try:
            datasource_result = api.fetch_device_datasources(device_id_text)
        except RuntimeError:
            continue
        for datasource in datasource_result.get("items") or []:
            collection_key = _match_performance_collection_key(datasource)
            if not collection_key:
                continue
            spec = PERFORMANCE_COLLECTION_SPECS[collection_key]
            summary["matched_datasources"][collection_key] += 1
            devices_with_metrics[collection_key].add(device_id_text)
            datasource_id = datasource.get("id")
            if datasource_id in (None, ""):
                continue
            try:
                instance_result = api.fetch_datasource_instances(device_id_text, datasource_id)
            except RuntimeError:
                continue
            for instance in instance_result.get("items") or []:
                summary["matched_instances"][collection_key] += 1
                instance_id = instance.get("id")
                if instance_id in (None, ""):
                    continue
                query_metrics = [
                    *spec.get("metric_candidates", []),
                    *spec.get("extra_metric_candidates", []),
                ]
                try:
                    payload = api.fetch_datasource_instance_data(
                        device_id_text,
                        datasource_id,
                        str(instance_id),
                        query_metrics,
                        context["period"]["start_ms"],
                        context["period"]["end_ms"],
                    )
                except RuntimeError:
                    continue
                series = _extract_named_series(payload)
                instance_name = _instance_label(instance)
                if collection_key == "cpu":
                    values = _choose_series_values(series, spec["metric_candidates"])
                    average = _average_value(values)
                    if average is not None:
                        cpu_rows.append({
                            "device_id": device_id_text,
                            "device_name": device_name,
                            "instance_name": instance_name,
                            "avg_percent": average,
                        })
                elif collection_key == "memory":
                    values = _choose_series_values(series, spec["metric_candidates"])
                    average = _average_value(values)
                    if average is not None:
                        memory_rows.append({
                            "device_id": device_id_text,
                            "device_name": device_name,
                            "instance_name": instance_name,
                            "avg_percent": average,
                        })
                elif collection_key == "disk":
                    values = _choose_series_values(series, spec["metric_candidates"])
                    average = _average_value(values)
                    maximum = _max_value(values)
                    if average is not None or maximum is not None:
                        disk_rows.append({
                            "device_id": device_id_text,
                            "device_name": device_name,
                            "volume_name": instance_name,
                            "avg_percent": average,
                            "max_percent": maximum,
                        })
                elif collection_key == "ping":
                    packet_loss = _choose_series_values(series, spec["metric_candidates"])
                    rtt = _choose_series_values(series, spec.get("extra_metric_candidates", []))
                    packet_loss_avg = _average_value(packet_loss)
                    availability = None if packet_loss_avg is None else _round_value(max(0, 100 - packet_loss_avg), 2)
                    availability_rows.append({
                        "device_id": device_id_text,
                        "device_name": device_name,
                        "instance_name": instance_name,
                        "packet_loss_avg_percent": packet_loss_avg,
                        "ping_rtt_avg_ms": _average_value(rtt),
                        "availability_percent": availability,
                    })
                elif collection_key == "network":
                    rx_values = _choose_series_values(series, spec["metric_candidates"])
                    tx_values = _choose_series_values(series, spec.get("extra_metric_candidates", []))
                    rx_avg = _average_value(rx_values)
                    tx_avg = _average_value(tx_values)
                    if rx_avg is not None or tx_avg is not None:
                        network_rows.append({
                            "device_id": device_id_text,
                            "device_name": device_name,
                            "interface_name": instance_name,
                            "rx_mbps_avg": None if rx_avg is None else _round_value(rx_avg / 1_000_000, 3),
                            "tx_mbps_avg": None if tx_avg is None else _round_value(tx_avg / 1_000_000, 3),
                        })
    summary["devices_with_metrics"] = {
        key: len(value)
        for key, value in devices_with_metrics.items()
    }
    return {
        "datasource": "logicmonitor",
        "dataset": "performance_metrics",
        "collection_path": "fleet script",
        "customer_name": context["customer_name"],
        "report_family": context["report_family"],
        "period_label": context["period"]["label"],
        "generated_at": context["generated_at"],
        "summary": summary,
        "availability_rows": availability_rows,
        "cpu_rows": cpu_rows,
        "memory_rows": memory_rows,
        "disk_rows": disk_rows,
        "network_rows": network_rows,
    }


def build_monitoring_coverage(meta: dict, snapshot: dict) -> dict:
    monitored_devices = _count_collected((snapshot.get("inventory") or {}).get("devices"))
    unmonitored_devices = _count_collected((snapshot.get("inventory") or {}).get("unmonitored_devices"))
    total_known_devices = monitored_devices + unmonitored_devices
    return {
        "datasource": "logicmonitor",
        "dataset": "monitoring_coverage",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "monitored_devices": monitored_devices,
        "unmonitored_devices": unmonitored_devices,
        "total_known_devices": total_known_devices,
        "monitoring_coverage_percent": _ratio_to_percent(monitored_devices, total_known_devices),
        "website_groups": _count_collected((snapshot.get("inventory") or {}).get("website_groups")),
        "monitored_websites": _count_collected((snapshot.get("inventory") or {}).get("websites")),
        "collectors": _count_collected((snapshot.get("inventory") or {}).get("collectors")),
        "checkpoints": _count_collected((snapshot.get("inventory") or {}).get("smcheckpoints")),
        "reports_available": _count_collected((snapshot.get("inventory") or {}).get("reports")),
    }


def build_website_experience(meta: dict, snapshot: dict) -> dict:
    websites = _section_items((snapshot.get("inventory") or {}).get("websites"))
    website_details = _section_items((snapshot.get("inventory") or {}).get("website_details"))
    website_groups = _section_items((snapshot.get("inventory") or {}).get("website_groups"))
    website_group_by_id = {
        str(group.get("id") or ""): group
        for group in website_groups
        if str(group.get("id") or "")
    }
    website_summary_by_id = {
        str(website.get("id") or ""): website
        for website in websites
        if str(website.get("id") or "")
    }
    source_rows = website_details or websites
    rows = []
    for detail in source_rows:
        website_id = str(detail.get("id") or "")
        base = website_summary_by_id.get(website_id, {})
        group = website_group_by_id.get(str(base.get("groupId") or detail.get("groupId") or ""), {})
        rows.append({
            "website_id": website_id,
            "name": str(detail.get("name") or base.get("name") or "unknown-website"),
            "domain": str(detail.get("domain") or base.get("domain") or ""),
            "status": _normalize_website_status(detail.get("status") or base.get("status")),
            "group_name": str(group.get("name") or base.get("groupName") or detail.get("groupName") or "Ungrouped"),
        })
    status_breakdown = {"up": 0, "warning": 0, "down": 0, "unknown": 0}
    for row in rows:
        status_breakdown[row["status"]] = int(status_breakdown.get(row["status"], 0)) + 1
    grouped = {}
    for row in rows:
        current = grouped.setdefault(row["group_name"], {
            "name": row["group_name"],
            "website_count": 0,
            "down_websites": 0,
            "warning_websites": 0,
        })
        current["website_count"] += 1
        if row["status"] == "down":
            current["down_websites"] += 1
        if row["status"] == "warning":
            current["warning_websites"] += 1
    websites_by_group = sorted(
        grouped.values(),
        key=lambda row: (-row["down_websites"], -row["warning_websites"], row["name"]),
    )
    return {
        "datasource": "logicmonitor",
        "dataset": "website_experience",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "monitored_websites": len(rows),
        "website_groups": _count_collected((snapshot.get("inventory") or {}).get("website_groups")),
        "status_breakdown": status_breakdown,
        "degraded_websites": [row for row in rows if row["status"] != "up"][:10],
        "websites_by_group": websites_by_group,
    }


def build_platform_assets(meta: dict, snapshot: dict) -> dict:
    collectors = [
        {
            "id": str(collector.get("id") or ""),
            "name": str(collector.get("description") or collector.get("name") or f"collector-{collector.get('id', 'unknown')}"),
        }
        for collector in _section_items((snapshot.get("inventory") or {}).get("collectors"))
    ]
    checkpoints = [
        {
            "id": str(checkpoint.get("id") or ""),
            "name": str(checkpoint.get("name") or checkpoint.get("description") or f"checkpoint-{checkpoint.get('id', 'unknown')}"),
        }
        for checkpoint in _section_items((snapshot.get("inventory") or {}).get("smcheckpoints"))
    ]
    return {
        "datasource": "logicmonitor",
        "dataset": "platform_assets",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "collectors": {"count": len(collectors), "items": collectors[:20]},
        "checkpoints": {"count": len(checkpoints), "items": checkpoints[:20]},
    }


def build_report_inventory(meta: dict, snapshot: dict) -> dict:
    reports = _section_items((snapshot.get("inventory") or {}).get("reports"))
    report_details = _section_items((snapshot.get("inventory") or {}).get("report_details"))
    details_by_id = {
        str(detail.get("id") or ""): detail
        for detail in report_details
        if str(detail.get("id") or "")
    }
    breakdown = {}
    rows = []
    for report in reports:
        report_id = str(report.get("id") or "")
        detail = details_by_id.get(report_id, {})
        report_type = str(report.get("type") or detail.get("type") or "unknown")
        breakdown[report_type] = int(breakdown.get(report_type, 0)) + 1
        rows.append({
            "id": report_id,
            "name": str(report.get("name") or detail.get("name") or "unknown-report"),
            "type": report_type,
            "format": str(detail.get("format") or "unknown"),
        })
    return {
        "datasource": "logicmonitor",
        "dataset": "report_inventory",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "reports_available": len(rows),
        "report_type_breakdown": breakdown,
        "reports": rows[:20],
    }


def build_inventory_exceptions(meta: dict, snapshot: dict) -> dict:
    unmonitored = _section_items((snapshot.get("inventory") or {}).get("unmonitored_devices"))
    rows = [
        {
            "id": str(device.get("id") or ""),
            "name": str(device.get("displayName") or device.get("systemDisplayName") or device.get("name") or f"device-{device.get('id', 'unknown')}"),
            "host_status": _normalize_host_status(device.get("hostStatus") or device.get("status") or "unmonitored"),
        }
        for device in unmonitored
    ]
    return {
        "datasource": "logicmonitor",
        "dataset": "inventory_exceptions",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "unmonitored_device_count": len(rows),
        "unmonitored_devices": rows[:20],
    }


def build_root_scope_summary(meta: dict, snapshot: dict) -> dict:
    root_scope = snapshot.get("aaic_root_scope") or {}
    return {
        "datasource": "logicmonitor",
        "dataset": "root_scope_summary",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "device_group_id": root_scope.get("device_group_id"),
        "website_group_id": root_scope.get("website_group_id"),
        "scoped_devices": _count_collected(root_scope.get("device_group_devices")),
        "scoped_alerts": _count_collected(root_scope.get("device_group_alerts")),
        "scoped_websites": _count_collected(root_scope.get("website_group_websites")),
    }


def build_snapshot_optional_metrics(meta: dict, snapshot: dict) -> dict:
    monitoring_coverage = build_monitoring_coverage(meta, snapshot)
    website_experience = build_website_experience(meta, snapshot)
    root_scope_summary = build_root_scope_summary(meta, snapshot)
    return {
        "metrics_summary": {
            "monitored_devices": monitoring_coverage["monitored_devices"],
            "unmonitored_devices": monitoring_coverage["unmonitored_devices"],
            "monitoring_coverage_percent": monitoring_coverage["monitoring_coverage_percent"],
            "monitored_websites": website_experience["monitored_websites"],
            "website_status_breakdown": website_experience["status_breakdown"],
            "scoped_alerts": root_scope_summary["scoped_alerts"],
            "reports_available": _count_collected((snapshot.get("inventory") or {}).get("reports")),
        },
        "metrics_usage": {
            "report_ready_sections": [
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
            ],
            "collection_window": {
                "start": meta["start_iso"],
                "end": meta["end_iso"],
            },
            "source_scope": {
                "tenant_id": meta["tenant_id"],
                "report_family": meta["report_family"],
                "site_groups": meta["site_groups"],
            },
        },
        "usage_contract_info": None,
    }


def _group_metric_rows_by_device(rows: list[dict], device_field: str = "device_name") -> list[dict]:
    grouped = {}
    for row in rows:
        key = str(row.get("device_id") or row.get(device_field) or "")
        current = grouped.setdefault(key, {"device_id": str(row.get("device_id") or ""), "device_name": str(row.get(device_field) or "")})
        current.setdefault("__rows", []).append(row)
    return list(grouped.values())


def _availability_status(availability_percent, packet_loss_percent) -> str:
    if availability_percent is None:
        return "unknown"
    if availability_percent <= 95 or (packet_loss_percent is not None and packet_loss_percent >= 5):
        return "Critical"
    if availability_percent < 100 or (packet_loss_percent is not None and packet_loss_percent > 0):
        return "Degraded"
    return "Healthy"


def build_device_availability(meta: dict, snapshot: dict) -> dict:
    raw_rows = ((snapshot.get("performance_metrics") or {}).get("availability_rows")) or []
    grouped_rows = _group_metric_rows_by_device(raw_rows)
    rows = []
    for entry in grouped_rows:
        packet_loss_values = [row.get("packet_loss_avg_percent") for row in entry["__rows"] if row.get("packet_loss_avg_percent") is not None]
        rtt_values = [row.get("ping_rtt_avg_ms") for row in entry["__rows"] if row.get("ping_rtt_avg_ms") is not None]
        availability_values = [row.get("availability_percent") for row in entry["__rows"] if row.get("availability_percent") is not None]
        packet_loss_avg = _average_value(packet_loss_values)
        availability = _average_value(availability_values)
        rows.append({
            "device_id": entry["device_id"],
            "device": entry["device_name"],
            "availability_percent": availability,
            "ping_rtt_ms": _average_value(rtt_values),
            "packet_loss_avg_percent": packet_loss_avg,
            "status": _availability_status(availability, packet_loss_avg),
        })
    rows = sorted(rows, key=lambda row: (row["availability_percent"] is None, row["availability_percent"] if row["availability_percent"] is not None else 999, row["device"]))
    availability_values = [row["availability_percent"] for row in rows if row["availability_percent"] is not None]
    return {
        "datasource": "logicmonitor",
        "dataset": "device_availability",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "average_availability_percent": _average_value(availability_values),
        "minimum_availability_percent": _round_value(min(availability_values), 2) if availability_values else None,
        "devices_monitored": len(rows),
        "devices": rows,
    }


def _aggregate_average_by_device(rows: list[dict], value_key: str) -> list[dict]:
    grouped = _group_metric_rows_by_device(rows)
    result = []
    for entry in grouped:
        values = [row.get(value_key) for row in entry["__rows"] if row.get(value_key) is not None]
        average = _average_value(values)
        if average is not None:
            result.append({
                "device_id": entry["device_id"],
                "device": entry["device_name"],
                "avg_percent": average,
            })
    return sorted(result, key=lambda row: (-row["avg_percent"], row["device"]))


def build_cpu_memory_utilization(meta: dict, snapshot: dict) -> dict:
    performance = snapshot.get("performance_metrics") or {}
    cpu_rows = _aggregate_average_by_device(performance.get("cpu_rows") or [], "avg_percent")
    memory_rows = _aggregate_average_by_device(performance.get("memory_rows") or [], "avg_percent")
    return {
        "datasource": "logicmonitor",
        "dataset": "cpu_memory_utilization",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "cpu_devices": cpu_rows,
        "memory_devices": memory_rows,
    }


def build_disk_capacity_utilization(meta: dict, snapshot: dict) -> dict:
    raw_rows = ((snapshot.get("performance_metrics") or {}).get("disk_rows")) or []
    highest_per_device = {}
    for row in raw_rows:
        key = str(row.get("device_id") or row.get("device_name") or "")
        current = highest_per_device.get(key)
        candidate = row.get("max_percent")
        if current is None or ((candidate or -1) > (current.get("max_percent") or -1)):
            highest_per_device[key] = {
                "device_id": str(row.get("device_id") or ""),
                "device": str(row.get("device_name") or ""),
                "max_percent": candidate,
            }
    highest_rows = sorted(highest_per_device.values(), key=lambda row: (-(row["max_percent"] or -1), row["device"]))
    volume_detail = sorted(
        [
            {
                "device_id": str(row.get("device_id") or ""),
                "device": str(row.get("device_name") or ""),
                "volume": str(row.get("volume_name") or ""),
                "avg_percent": row.get("avg_percent"),
                "max_percent": row.get("max_percent"),
            }
            for row in raw_rows
        ],
        key=lambda row: (-(row["max_percent"] or -1), row["device"], row["volume"]),
    )
    return {
        "datasource": "logicmonitor",
        "dataset": "disk_capacity_utilization",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "highest_disk_volume_usage_by_device": highest_rows,
        "volume_detail": volume_detail,
    }


def build_network_interface_throughput(meta: dict, snapshot: dict) -> dict:
    raw_rows = ((snapshot.get("performance_metrics") or {}).get("network_rows")) or []
    grouped = _group_metric_rows_by_device(raw_rows)
    device_summary = []
    for entry in grouped:
        rx_values = [row.get("rx_mbps_avg") or 0 for row in entry["__rows"]]
        tx_values = [row.get("tx_mbps_avg") or 0 for row in entry["__rows"]]
        device_summary.append({
            "device_id": entry["device_id"],
            "device": entry["device_name"],
            "rx_mbps_avg": _round_value(sum(rx_values), 3),
            "tx_mbps_avg": _round_value(sum(tx_values), 3),
        })
    device_summary.sort(key=lambda row: (-(row["rx_mbps_avg"] + row["tx_mbps_avg"]), row["device"]))
    interface_detail = sorted(
        [
            {
                "device_id": str(row.get("device_id") or ""),
                "device": str(row.get("device_name") or ""),
                "interface": str(row.get("interface_name") or ""),
                "rx_mbps_avg": row.get("rx_mbps_avg"),
                "tx_mbps_avg": row.get("tx_mbps_avg"),
            }
            for row in raw_rows
        ],
        key=lambda row: (-((row["rx_mbps_avg"] or 0) + (row["tx_mbps_avg"] or 0)), row["device"], row["interface"]),
    )
    return {
        "datasource": "logicmonitor",
        "dataset": "network_interface_throughput",
        "collection_path": "fleet script",
        "customer_name": meta["customer_name"],
        "report_family": meta["report_family"],
        "period_label": meta["period_label"],
        "device_network_summary": device_summary,
        "interface_detail": interface_detail,
    }


def resolve_logicmonitor_scope_by_company(context: dict, fetch_impl=None, sleep_impl=None) -> dict:
    api = LogicMonitorApi(context["logicmonitor"], fetch_impl=fetch_impl, sleep_impl=sleep_impl)
    queries = [
        context.get("company_name") or context.get("customer_name") or "",
        context.get("customer_name") or "",
        *context.get("company_aliases", []),
    ]
    queries = [query.strip() for query in queries if isinstance(query, str) and query.strip()]
    if not queries:
        raise ValueError("company_name or customer_name is required to resolve LogicMonitor scope.")

    device_groups_result = api.list_paged("/device/groups")
    website_groups_result = _safe_list_paged(api, "/website/groups")

    scored_device_groups = []
    for group in device_groups_result["items"]:
        score, reason = _score_group_candidate(group, queries)
        if score >= 40:
            scored_device_groups.append({
                "id": group.get("id"),
                "name": group.get("name"),
                "full_path": group.get("fullPath") or group.get("name") or "",
                "score": score,
                "reason": reason,
                "depth": _group_depth(group),
            })
    scored_device_groups.sort(key=lambda entry: (-entry["score"], entry["depth"], len(entry["full_path"]), entry["full_path"]))
    if not scored_device_groups:
        raise RuntimeError(f"No LogicMonitor device groups matched company name '{queries[0]}'.")

    root_device_group = next(
        group
        for group in device_groups_result["items"]
        if group.get("id") == scored_device_groups[0]["id"]
    )
    descendant_device_groups = _collect_descendant_groups(root_device_group, device_groups_result["items"])
    device_group_identifiers = [
        str(group.get("fullPath") or group.get("name") or group.get("id"))
        for group in descendant_device_groups
        if str(group.get("fullPath") or group.get("name") or group.get("id")).strip()
    ]

    scored_website_groups = []
    for group in website_groups_result["items"]:
        score, reason = _score_group_candidate(group, queries)
        if score >= 40:
            scored_website_groups.append({
                "id": group.get("id"),
                "name": group.get("name"),
                "full_path": group.get("fullPath") or group.get("name") or "",
                "score": score,
                "reason": reason,
                "depth": _group_depth(group),
            })
    scored_website_groups.sort(key=lambda entry: (-entry["score"], entry["depth"], len(entry["full_path"]), entry["full_path"]))

    root_website_group = None
    if scored_website_groups:
        root_website_group = next(
            group
            for group in website_groups_result["items"]
            if group.get("id") == scored_website_groups[0]["id"]
        )

    best_device_score = scored_device_groups[0]["score"]
    second_device_score = scored_device_groups[1]["score"] if len(scored_device_groups) > 1 else 0
    confidence = _confidence_label(best_device_score, second_device_score)
    root_label = _group_label(root_device_group)

    return {
        "company_name": queries[0],
        "queries_used": queries,
        "match_confidence": confidence,
        "device_group_resolution": {
            "root_group": {
                "id": root_device_group.get("id"),
                "name": root_device_group.get("name"),
                "full_path": root_device_group.get("fullPath") or root_device_group.get("name") or "",
            },
            "matched_candidates": scored_device_groups[:10],
            "descendant_groups": [
                {
                    "id": group.get("id"),
                    "name": group.get("name"),
                    "full_path": group.get("fullPath") or group.get("name") or "",
                }
                for group in descendant_device_groups
            ],
        },
        "website_group_resolution": {
            "root_group": None if root_website_group is None else {
                "id": root_website_group.get("id"),
                "name": root_website_group.get("name"),
                "full_path": root_website_group.get("fullPath") or root_website_group.get("name") or "",
            },
            "matched_candidates": scored_website_groups[:10],
        },
        "resolved_scope": {
            "logicmonitor": {
                "tenant_id": context["logicmonitor"]["tenant_id"],
                "account_name": context["logicmonitor"]["account_name"],
                "api_version": context["logicmonitor"]["api_version"],
                "group_identifiers": device_group_identifiers,
                "site_groups": [root_label] if root_label else [],
                "root_device_group_id": root_device_group.get("id"),
                "root_website_group_id": None if root_website_group is None else root_website_group.get("id"),
                "site_property_key": context["logicmonitor"]["site_property_key"],
                "request_timeout_seconds": context["logicmonitor"]["request_timeout_seconds"],
                "request_retry_attempts": context["logicmonitor"]["request_retry_attempts"],
                "request_retry_backoff_ms": context["logicmonitor"]["request_retry_backoff_ms"],
                "fetch_page_size": context["logicmonitor"]["fetch_page_size"],
                "max_pages_per_endpoint": context["logicmonitor"]["max_pages_per_endpoint"],
                "alert_chunk_hours": context["logicmonitor"]["alert_chunk_hours"],
                "detail_fetch_concurrency": context["logicmonitor"]["detail_fetch_concurrency"],
            },
        },
        "collection_log": api.get_diagnostics(),
    }


def collect_logicmonitor_snapshot(context: dict, fetch_impl=None, sleep_impl=None) -> dict:
    api = LogicMonitorApi(context["logicmonitor"], fetch_impl=fetch_impl, sleep_impl=sleep_impl)
    device_scope = api.fetch_devices(context["logicmonitor"]["group_identifiers"])
    if not context["logicmonitor"]["allow_full_tenant_collection"] and not device_scope["groups"]["items"]:
        raise RuntimeError("No LogicMonitor device groups matched the requested customer scope.")
    scoped_group_ids = [group["id"] for group in device_scope["groups"]["items"] if group.get("id") is not None]
    open_alerts = _fetch_scoped_alerts(api, scoped_group_ids, context["period"]["start_ms"], context["period"]["end_ms"], False)
    cleared_alerts = _fetch_scoped_alerts(api, scoped_group_ids, context["period"]["start_ms"], context["period"]["end_ms"], True)
    device_group_details = _safe_fetch_entity_details(api, "/device/groups", device_scope["groups"]["items"])
    device_details = _safe_fetch_entity_details(api, "/device/devices", device_scope["devices"]["items"])
    website_scope = _fetch_website_scope(api, context)
    unmonitored_devices = api.fetch_unmonitored_devices()
    smcheckpoints = api.fetch_smcheckpoints()
    collectors = api.fetch_collectors()
    reports = api.fetch_reports()
    report_details = _safe_fetch_entity_details(api, "/report/reports", reports.get("items") or [])
    performance_metrics = _collect_performance_metrics(api, context, device_scope["devices"]["items"])
    root_scope = {
        "device_group_id": context["logicmonitor"]["root_device_group_id"],
        "device_group_devices": {
            "count_collected": device_scope["devices"]["count_collected"],
            "items": device_scope["devices"]["items"],
            "total": device_scope["devices"]["total"],
        },
        "device_group_alerts": open_alerts,
        "website_group_id": context["logicmonitor"]["root_website_group_id"],
        "website_group_websites": website_scope["websites"],
    }
    return {
        "datasource": "logicmonitor",
        "dataset": "logicmonitor_snapshot",
        "collection_path": "fleet script",
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "customer_name": context["customer_name"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period_label": context["period"]["label"],
        "generated_at": context["generated_at"],
        "metadata": {
            "base_url": f"https://{context['logicmonitor']['account_name']}.logicmonitor.com/santaba/rest",
            "collected_at_utc": context["generated_at"],
            "scope_note": "Customer-scoped LogicMonitor snapshot for Fleet reporting.",
            "source_scope": {
                "group_identifiers": context["logicmonitor"]["group_identifiers"],
                "site_groups": context["logicmonitor"]["site_groups"],
                "root_device_group_id": context["logicmonitor"]["root_device_group_id"],
                "root_website_group_id": context["logicmonitor"]["root_website_group_id"],
            },
        },
        "inventory": {
            "device_groups": device_scope["groups"],
            "device_group_details": device_group_details,
            "devices": device_scope["devices"],
            "device_details": device_details,
            "unmonitored_devices": unmonitored_devices,
            "website_groups": website_scope["website_groups"],
            "website_group_details": website_scope["website_group_details"],
            "websites": website_scope["websites"],
            "website_details": website_scope["website_details"],
            "smcheckpoints": smcheckpoints,
            "collectors": collectors,
            "reports": reports,
            "report_details": report_details,
        },
        "alerts": {
            "count_collected": open_alerts["count_collected"] + cleared_alerts["count_collected"],
            "open": open_alerts,
            "cleared": cleared_alerts,
        },
        "aaic_root_scope": root_scope,
        "optional_metrics": build_snapshot_optional_metrics({
            "tenant_id": context["logicmonitor"]["tenant_id"],
            "customer_name": context["customer_name"],
            "report_family": context["report_family"],
            "period_label": context["period"]["label"],
            "start_iso": context["period"]["start_iso"],
            "end_iso": context["period"]["end_iso"],
            "site_groups": context["logicmonitor"]["site_groups"],
        }, {
            "inventory": {
                "devices": device_scope["devices"],
                "unmonitored_devices": unmonitored_devices,
                "website_groups": website_scope["website_groups"],
                "websites": website_scope["websites"],
                "collectors": collectors,
                "smcheckpoints": smcheckpoints,
                "reports": reports,
                "website_details": website_scope["website_details"],
                "report_details": report_details,
            },
            "aaic_root_scope": root_scope,
        }),
        "performance_metrics": performance_metrics,
        "collection_log": api.get_diagnostics(),
    }


def normalize_logicmonitor_snapshot(context: dict, snapshot: dict) -> dict:
    normalized = normalize_collection(_normalized_input_from_snapshot(snapshot), context["logicmonitor"]["site_property_key"])
    scoped = _filter_normalized_collection(normalized, context["logicmonitor"]["site_groups"])
    return _build_observability_artifact(context, scoped)


def build_logicmonitor_artifacts(context: dict, snapshot: dict, observability: dict) -> dict:
    meta = {
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "customer_name": context["customer_name"],
        "report_family": context["report_family"],
        "period_label": context["period"]["label"],
        "start_iso": context["period"]["start_iso"],
        "end_iso": context["period"]["end_iso"],
        "start_ms": context["period"]["start_ms"],
        "end_ms": context["period"]["end_ms"],
        "site_groups": context["logicmonitor"]["site_groups"],
        "root_device_group_id": context["logicmonitor"]["root_device_group_id"],
        "root_website_group_id": context["logicmonitor"]["root_website_group_id"],
        "generated_at": context["generated_at"],
    }
    normalized = observability["normalized"]
    availability_summary = {
        **build_availability_summary(meta, normalized),
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
    }
    alert_trends = {
        **build_alert_trends(meta, normalized),
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
    }
    resource_health = {
        **build_resource_health(meta, normalized),
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
    }
    monitoring_coverage = {
        **build_monitoring_coverage(meta, snapshot),
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
    }
    website_experience = {
        **build_website_experience(meta, snapshot),
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
    }
    platform_assets = {
        **build_platform_assets(meta, snapshot),
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
    }
    report_inventory = {
        **build_report_inventory(meta, snapshot),
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
    }
    inventory_exceptions = {
        **build_inventory_exceptions(meta, snapshot),
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
    }
    root_scope_summary = {
        **build_root_scope_summary(meta, snapshot),
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
    }
    device_availability = {
        **build_device_availability(meta, snapshot),
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
    }
    cpu_memory_utilization = {
        **build_cpu_memory_utilization(meta, snapshot),
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
    }
    disk_capacity_utilization = {
        **build_disk_capacity_utilization(meta, snapshot),
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
    }
    network_interface_throughput = {
        **build_network_interface_throughput(meta, snapshot),
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
    }
    report_bundle = build_report_bundle(meta, normalized, snapshot)
    bundle = {
        **report_bundle,
        "customer_id": context["customer_id"],
        "tenant_id": context["logicmonitor"]["tenant_id"],
        "template_key": context["template_key"],
        "source_scope": {
            "group_identifiers": context["logicmonitor"]["group_identifiers"],
            "site_groups": context["logicmonitor"]["site_groups"],
            "root_device_group_id": context["logicmonitor"]["root_device_group_id"],
            "root_website_group_id": context["logicmonitor"]["root_website_group_id"],
        },
        "sections": {
            **report_bundle["sections"],
            "source_inventory_summary": _summarize_source_inventory(snapshot),
        },
    }
    return {
        "observability": observability,
        "availability_summary": availability_summary,
        "alert_trends": alert_trends,
        "resource_health": resource_health,
        "monitoring_coverage": monitoring_coverage,
        "website_experience": website_experience,
        "platform_assets": platform_assets,
        "report_inventory": report_inventory,
        "inventory_exceptions": inventory_exceptions,
        "root_scope_summary": root_scope_summary,
        "device_availability": device_availability,
        "cpu_memory_utilization": cpu_memory_utilization,
        "disk_capacity_utilization": disk_capacity_utilization,
        "network_interface_throughput": network_interface_throughput,
        "bundle": bundle,
    }


def run_logicmonitor_pipeline(context: dict, fetch_impl=None, sleep_impl=None) -> dict:
    snapshot = collect_logicmonitor_snapshot(context, fetch_impl=fetch_impl, sleep_impl=sleep_impl)
    observability = normalize_logicmonitor_snapshot(context, snapshot)
    return {
        "snapshot": snapshot,
        **build_logicmonitor_artifacts(context, snapshot, observability),
    }
