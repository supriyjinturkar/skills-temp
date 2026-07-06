from __future__ import annotations

import base64
import hashlib
import hmac
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
                f"{alerts['alert_counts_closed']} alerts were cleared compared with {alerts['alert_counts_opened']} alerts opened.",
                f"{health['critical_devices']} devices remained in critical state at the end of the collection window.",
                f"{derived_metrics['alert_handling_kpis']['clear_rate_percent']}% of alerts were cleared inside the reporting window.",
            ]),
            "derived_metrics": derived_metrics,
            "availability_summary": availability,
            "alert_trends": alerts,
            "resource_health": health,
            "site_operations": site_operations,
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

    def _authorization_header(self, method: str, resource_path_with_query: str, body_text: str) -> str:
        auth_mode = str(self.config.get("auth_mode") or "bearer").strip().lower()
        if auth_mode == "bearer":
            token = self.config.get("bearer_token") or ""
            if not token:
                raise ValueError("LogicMonitor bearer token is required.")
            return f"Bearer {token}"
        if auth_mode == "basic":
            username = self.config.get("basic_username") or ""
            password = self.config.get("basic_password") or ""
            if not username or not password:
                raise ValueError("LogicMonitor basic credentials are required.")
            encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
            return f"Basic {encoded}"
        if auth_mode == "lmv1":
            access_id = self.config.get("api_access_id") or ""
            access_key = self.config.get("api_access_key") or ""
            if not access_id or not access_key:
                raise ValueError("LogicMonitor LMv1 credentials are required.")
            epoch = str(int(time.time() * 1000))
            signature_base = f"{method.upper()}{epoch}{body_text}{resource_path_with_query}".encode("utf-8")
            signature = base64.b64encode(hmac.new(access_key.encode("utf-8"), signature_base, hashlib.sha256).digest()).decode("ascii")
            return f"LMv1 {access_id}:{signature}:{epoch}"
        raise ValueError(f"Unsupported LogicMonitor auth mode: {auth_mode}")

    def _build_request(self, method: str, resource_path: str, query: dict | None = None, body=None):
        query_string = f"?{urlencode(query or {}, doseq=True)}" if query else ""
        resource_path_with_query = f"{resource_path}{query_string}"
        body_text = "" if body is None else json.dumps(body)
        headers = {
            "Accept": "application/json",
            "X-Version": str(self.config.get("api_version") or 3),
            "Authorization": self._authorization_header(method, resource_path_with_query, body_text),
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
            result["website_group_websites"] = self.list_paged(f"/website/groups/{root_website_group_id}/websites")
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
                "auth_mode": context["logicmonitor"]["auth_mode"],
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
            "unmonitored_devices": _empty_paged_result(),
            "website_groups": website_scope["website_groups"],
            "website_group_details": website_scope["website_group_details"],
            "websites": website_scope["websites"],
            "website_details": website_scope["website_details"],
            "smcheckpoints": _empty_paged_result(),
            "collectors": _empty_paged_result(),
            "reports": _empty_paged_result(),
            "report_details": _empty_entity_details(),
        },
        "alerts": {
            "count_collected": open_alerts["count_collected"] + cleared_alerts["count_collected"],
            "open": open_alerts,
            "cleared": cleared_alerts,
        },
        "aaic_root_scope": root_scope,
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
        "bundle": bundle,
    }


def run_logicmonitor_pipeline(context: dict, fetch_impl=None, sleep_impl=None) -> dict:
    snapshot = collect_logicmonitor_snapshot(context, fetch_impl=fetch_impl, sleep_impl=sleep_impl)
    observability = normalize_logicmonitor_snapshot(context, snapshot)
    return {
        "snapshot": snapshot,
        **build_logicmonitor_artifacts(context, snapshot, observability),
    }
