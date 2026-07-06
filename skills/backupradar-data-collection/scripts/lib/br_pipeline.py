from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


class ApiResponseError(RuntimeError):
    def __init__(self, status: int, url: str, payload):
        super().__init__(f"BackupRadar API request failed with {status} for {url}: {payload}")
        self.status = status
        self.url = url
        self.payload = payload


def _to_iso(value) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds = seconds / 1000
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _to_number(value, default=0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return int(number) if number.is_integer() else number


def _round_value(value, decimals=2):
    return round(float(value or 0), decimals)


def _ratio_to_percent(numerator, denominator):
    if not denominator:
        return 0
    return _round_value((numerator / denominator) * 100, 2)


def _coerce_text(value) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()


def _first_present(record: dict, keys: list[str], default=None):
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return default


def _normalize_name(value: str) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _guess_items(payload, items_key: str = "") -> list[dict]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    if items_key and isinstance(payload.get(items_key), list):
        return payload[items_key]
    # BackupRadar API v2 uses "Results" as the envelope key for paginated responses.
    # Generic fallbacks follow; stale v1 keys (customers, jobs, devices, destinations) removed.
    for key in ("Results", "items", "data", "results", "records"):
        if isinstance(payload.get(key), list):
            return payload[key]
    return [payload] if payload else []


def _lookup_key(payload: dict, dotted_key: str):
    current = payload
    for part in dotted_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _parse_retry_after(headers: dict[str, str]) -> float:
    header_value = headers.get("Retry-After") or headers.get("retry-after") or ""
    if not header_value:
        return 0
    try:
        return float(header_value)
    except ValueError:
        try:
            target = parsedate_to_datetime(header_value)
        except (TypeError, ValueError):
            return 0
        return max((target - datetime.now(timezone.utc)).total_seconds(), 0)


def _build_url(base_url: str, path: str, query: dict[str, object]) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        root = path
    else:
        root = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    clean_query = {key: value for key, value in query.items() if value not in (None, "", [])}
    return f"{root}?{urlencode(clean_query, doseq=True)}" if clean_query else root


def _load_json(body: str):
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def _request_json(config: dict, url: str, fetch_impl=None):
    headers = {
        "Accept": "application/json",
        config["auth_header"]: config["api_key"],
    }
    attempts = max(int(config["request_retry_attempts"]), 1)
    timeout = int(config["request_timeout_seconds"])
    backoff_ms = int(config["request_retry_backoff_ms"])
    last_error = None
    for attempt in range(attempts):
        try:
            if fetch_impl:
                status, response_headers, body = fetch_impl("GET", url, headers, None)
                payload = _load_json(body)
                normalized_headers = {str(key): str(value) for key, value in (response_headers or {}).items()}
                if status >= 400:
                    raise ApiResponseError(status, url, payload)
                return payload, normalized_headers
            request = Request(url, headers=headers, method="GET")
            with urlopen(request, timeout=timeout) as response:
                payload = _load_json(response.read().decode("utf-8"))
                response_headers = dict(response.headers.items())
                if response.status >= 400:
                    raise ApiResponseError(int(response.status), url, payload)
                return payload, response_headers
        except ApiResponseError as error:
            last_error = error
            if error.status == 429 and attempt + 1 < attempts:
                delay = _parse_retry_after({}) or max(backoff_ms / 1000, 0.1)
                time.sleep(delay)
                continue
            raise
        except HTTPError as error:  # pragma: no cover
            payload = _load_json(error.read().decode("utf-8")) if error.fp else error.reason
            wrapped = ApiResponseError(int(error.code), url, payload)
            last_error = wrapped
            if int(error.code) == 429 and attempt + 1 < attempts:
                delay = _parse_retry_after(dict(error.headers.items())) or max(backoff_ms / 1000, 0.1)
                time.sleep(delay)
                continue
            raise wrapped from error
        except URLError as error:  # pragma: no cover
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(max(backoff_ms / 1000, 0.1))
                continue
            raise RuntimeError(f"BackupRadar request failed for {url}: {error}") from error
    raise last_error if last_error else RuntimeError(f"BackupRadar request failed for {url}")


def _fetch_collection(config: dict, resource: dict, query: dict[str, object] | None = None, fetch_impl=None) -> list[dict]:
    query = query or {}
    merged_query = {**resource.get("query", {}), **query}
    all_items: list[dict] = []
    next_url = ""
    cursor_value = ""
    page_number = 1
    max_pages = max(int(resource["max_pages"]), 1)
    for _ in range(max_pages):
        current_query = dict(merged_query)
        if resource["cursor_param"] and cursor_value:
            current_query[resource["cursor_param"]] = cursor_value
        if resource["page_param"]:
            current_query[resource["page_param"]] = page_number
        if resource["page_size_param"]:
            current_query[resource["page_size_param"]] = resource["page_size"]
        url = next_url or _build_url(config["base_url"], resource["path"], current_query)
        payload, _headers = _request_json(config, url, fetch_impl=fetch_impl)
        page_items = _guess_items(payload, resource["items_key"])
        all_items.extend(page_items)
        if isinstance(payload, dict) and resource["next_url_key"]:
            next_url = _lookup_key(payload, resource["next_url_key"]) or ""
            if next_url:
                continue
        if isinstance(payload, dict) and resource["next_key"] and resource["cursor_param"]:
            cursor_value = _lookup_key(payload, resource["next_key"]) or ""
            if cursor_value:
                continue
        if resource["page_param"]:
            if len(page_items) < int(resource["page_size"]):
                break
            page_number += 1
            continue
        break
    return all_items


def _resolve_optional_collection(config: dict, resource: dict, query: dict[str, object], required: bool, warnings: list[str], fetch_impl=None) -> list[dict]:
    try:
        return _fetch_collection(config, resource, query=query, fetch_impl=fetch_impl)
    except ApiResponseError as error:
        if required:
            raise
        warnings.append(f"Optional BackupRadar resource {resource['path']} returned {error.status}.")
        return []


def _build_resource_query(resource: dict, customer_id: str, period: dict) -> dict[str, object]:
    """Build query params for a resource fetch.

    BackupRadar API v2 notes:
    - Customer scoping uses SearchByCompanyName (set as customer_filter_param in v2 resources).
      customer_id here carries the resolved company name string for v2.
    - /backups accepts a single 'date' reference param (the end/as-of date of the window),
      not a start+end range. end_param is intentionally empty in v2 resource config.
    - start_param is 'date' pointing at period end_iso (the as-of reference date).
    """
    query: dict[str, object] = {}
    if resource["customer_filter_param"] and customer_id:
        query[resource["customer_filter_param"]] = customer_id
    # For v2: start_param="date", end_param="" — use end_iso as the reference date.
    # For legacy configs that still set start_param to a range start, use start_iso.
    if resource["start_param"]:
        date_value = period["end_iso"][:10] if resource["start_param"] == "date" else period["start_iso"]
        query[resource["start_param"]] = date_value
    if resource["end_param"]:
        query[resource["end_param"]] = period["end_iso"]
    return query


def _normalize_device(record: dict) -> dict:
    return {
        "device_id": _coerce_text(_first_present(record, ["id", "device_id", "asset_id", "endpoint_id"])),
        "device_name": _coerce_text(_first_present(record, ["name", "device_name", "asset_name", "endpoint_name", "hostname"])) or "unknown-device",
        "site": _coerce_text(_first_present(record, ["site", "location", "group_name"])),
        "platform": _coerce_text(_first_present(record, ["platform", "device_type", "type"])),
        "raw": record,
    }


def _normalize_destination(record: dict) -> dict:
    return {
        "destination_id": _coerce_text(_first_present(record, ["id", "destination_id", "vault_id"])),
        "destination_name": _coerce_text(_first_present(record, ["name", "destination_name", "vault_name"])) or "unknown-destination",
        "type": _coerce_text(_first_present(record, ["type", "destination_type"])),
        "raw": record,
    }


def _index_by(items: list[dict], id_key: str, name_key: str) -> tuple[dict[str, dict], dict[str, dict]]:
    by_id: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for item in items:
        item_id = _coerce_text(item.get(id_key))
        item_name = _coerce_text(item.get(name_key))
        if item_id:
            by_id[item_id] = item
        if item_name:
            by_name[item_name] = item
    return by_id, by_name


def _normalize_status(value) -> str:
    raw = _coerce_text(value).lower()
    if raw in {"success", "successful", "completed", "passed", "ok", "healthy"}:
        return "success"
    if raw in {"retry", "retried", "recovered", "warning_retried"}:
        return "retried"
    if raw in {"warning", "partial", "degraded"}:
        return "warning"
    if raw in {"failed", "failure", "error", "errored", "missed"}:
        return "failed"
    if raw in {"queued", "pending", "awaiting_review"}:
        return "pending"
    if raw in {"running", "in_progress"}:
        return "running"
    if raw in {"skipped", "ignored"}:
        return "skipped"
    return raw or "unknown"


def _coerce_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = _coerce_text(value).lower()
    if text in {"true", "1", "yes", "y", "verified", "cleared", "reported", "checked", "reviewed", "closed", "resolved"}:
        return True
    if text in {"false", "0", "no", "n", "open", "pending", "uncleared", "unverified"}:
        return False
    return None


def _field_bool(record: dict, keys: list[str]) -> bool | None:
    for key in keys:
        if key not in record:
            continue
        coerced = _coerce_bool(record.get(key))
        if coerced is not None:
            return coerced
    return None


def _joined_text(values: list[object]) -> str:
    return " ".join([_coerce_text(value) for value in values if _coerce_text(value)]).lower()


def _derive_review_flags(record: dict) -> dict:
    review_text = _joined_text([
        _first_present(record, ["review_status", "verification_status", "resolution_status", "lifecycle_status", "status_detail", "detail_status"]),
        _first_present(record, ["message", "detail", "error_message", "notes", "resolution_notes", "review_notes"]),
    ])
    is_verified = _field_bool(record, ["verified", "is_verified", "review_verified", "verification_complete"])
    if is_verified is None:
        is_verified = any(marker in review_text for marker in ("verified", "reviewed", "checked"))
    is_cleared = _field_bool(record, ["cleared", "is_cleared", "resolved", "is_resolved", "closed", "is_closed"])
    if is_cleared is None:
        is_cleared = any(marker in review_text for marker in ("cleared", "resolved", "closed"))
    is_reported = _field_bool(record, ["reported", "is_reported", "included_in_report"])
    if is_reported is None:
        is_reported = bool(_first_present(record, ["reported_at", "report_id", "report_reference"])) or "reported" in review_text
    is_checked = _field_bool(record, ["checked", "is_checked", "reviewed", "is_reviewed"])
    if is_checked is None:
        is_checked = any(marker in review_text for marker in ("checked", "reviewed"))
    return {
        "review_status": _coerce_text(
            _first_present(record, ["review_status", "verification_status", "resolution_status", "lifecycle_status", "status_detail", "detail_status"]),
        ),
        "is_verified": bool(is_verified),
        "is_cleared": bool(is_cleared),
        "is_reported": bool(is_reported),
        "is_checked": bool(is_checked),
        "review_text": review_text,
    }


def _build_daily_status_counts(period: dict, jobs: list[dict]) -> list[dict]:
    start = datetime.fromisoformat(period["start_iso"].replace("Z", "+00:00")).date()
    end = datetime.fromisoformat(period["end_iso"].replace("Z", "+00:00")).date()
    buckets = {}
    cursor = start
    while cursor <= end:
        buckets[str(cursor)] = {
            "date": str(cursor),
            "success": 0,
            "retried": 0,
            "warning": 0,
            "failed": 0,
            "pending": 0,
            "running": 0,
            "skipped": 0,
            "unknown": 0,
        }
        cursor += timedelta(days=1)
    for job in jobs:
        if not job["job_at"]:
            continue
        day_key = job["job_at"][:10]
        bucket = buckets.get(day_key)
        if not bucket:
            continue
        bucket[job["status"] if job["status"] in bucket else "unknown"] += 1
    return [buckets[key] for key in sorted(buckets)]


def _build_device_rollup(jobs: list[dict]) -> list[dict]:
    by_device: dict[str, dict] = {}
    for job in jobs:
        key = job["device_id"] or job["device_name"]
        row = by_device.setdefault(key, {
            "device_id": job["device_id"],
            "device_name": job["device_name"],
            "site": job["site"],
            "platform": job["platform"],
            "success": 0,
            "retried": 0,
            "warning": 0,
            "failed": 0,
            "pending": 0,
            "running": 0,
            "skipped": 0,
            "unknown": 0,
            "latest_job_at": None,
        })
        row[job["status"] if job["status"] in row else "unknown"] += 1
        if job["job_at"] and (row["latest_job_at"] is None or job["job_at"] > row["latest_job_at"]):
            row["latest_job_at"] = job["job_at"]
    rows = list(by_device.values())
    rows.sort(key=lambda entry: (-entry["failed"], -entry["warning"], entry["device_name"]))
    return rows


def _build_destination_rollup(jobs: list[dict]) -> list[dict]:
    by_destination: dict[str, dict] = {}
    for job in jobs:
        key = job["destination_id"] or job["destination_name"]
        row = by_destination.setdefault(key, {
            "destination_id": job["destination_id"],
            "destination_name": job["destination_name"],
            "success": 0,
            "retried": 0,
            "warning": 0,
            "failed": 0,
            "pending": 0,
            "running": 0,
            "skipped": 0,
            "unknown": 0,
        })
        row[job["status"] if job["status"] in row else "unknown"] += 1
    rows = list(by_destination.values())
    rows.sort(key=lambda entry: (-entry["failed"], -entry["warning"], entry["destination_name"]))
    return rows


def _build_exception_rows(jobs: list[dict], limit: int = 25) -> list[dict]:
    rows = [
        {
            "job_id": job["job_id"],
            "device_name": job["device_name"],
            "destination_name": job["destination_name"],
            "status": job["status"],
            "job_at": job["job_at"],
            "detail": job["detail"],
            "site": job["site"],
        }
        for job in jobs
        if job["status"] in {"failed", "warning", "pending", "running", "unknown"}
    ]
    rows.sort(key=lambda row: (row["status"] != "failed", row["status"] != "warning", row["job_at"] or "", row["device_name"]), reverse=True)
    return rows[:limit]


# ---------------------------------------------------------------------------
# BackupRadar API v2 — scope resolver
# ---------------------------------------------------------------------------

def resolve_backupradar_scope_by_company(context: dict, fetch_impl=None) -> dict:
    """Resolve a company name to a BackupRadar customer scope.

    BackupRadar API v2 has no /customers endpoint.  The resolver instead calls
    /backups with no company filter to get all backup jobs, then extracts the
    distinct companyName values and scores them against the requested company name.

    The resolved customer_id is the matched companyName string — it is used as
    the SearchByCompanyName value for all subsequent collection calls.
    """
    config = context["backupradar"]
    # Use the 'backups' resource if configured, otherwise fall back to a minimal inline definition.
    backups_resource = config["resources"].get("backups") or {
        "path": "/backups",
        "items_key": "Results",
        "next_key": "",
        "next_url_key": "",
        "page_param": "Page",
        "cursor_param": "",
        "page_size_param": "Size",
        "page_size": 1000,
        "max_pages": 10,
        "customer_filter_param": "",
        "start_param": "",
        "end_param": "",
        "id_key": "backupId",
        "name_key": "companyName",
        "alias_keys": [],
        "query": {},
    }
    # Fetch without company filter to discover all distinct company names.
    discovery_resource = {**backups_resource, "customer_filter_param": "", "start_param": "", "end_param": ""}
    all_jobs = _fetch_collection(config, discovery_resource, fetch_impl=fetch_impl)

    # Collect distinct company names from results.
    seen: dict[str, str] = {}   # normalised_name -> original companyName
    for job in all_jobs:
        company_raw = _coerce_text(job.get("companyName") or job.get("company_name") or "")
        if company_raw:
            seen[_normalize_name(company_raw)] = company_raw

    if not seen:
        raise ValueError(f"No BackupRadar companies found — cannot resolve '{context['company_name']}'.")

    # Score each distinct company against the requested name + aliases.
    needles = [_normalize_name(context["company_name"]), *[_normalize_name(a) for a in context.get("company_aliases", [])]]
    needles = [n for n in needles if n]

    best_score = 0
    best_name = ""
    candidates = []
    for norm, original in seen.items():
        score = 0
        for needle in needles:
            if norm == needle:
                score = max(score, 100)
            elif needle and needle in norm:
                score = max(score, 85)
            elif norm and norm in needle:
                score = max(score, 70)
        if score > 0:
            candidates.append({"customer_id": original, "customer_name": original, "score": score})
        if score > best_score:
            best_score = score
            best_name = original

    if not candidates:
        raise ValueError(f"No BackupRadar customer match found for '{context['company_name']}'.")

    candidates.sort(key=lambda e: (-e["score"], e["customer_name"]))
    top = candidates[0]
    confidence = "high" if top["score"] >= 100 else "medium" if top["score"] >= 85 else "low"
    return {
        "resolved_scope": {
            "backupradar": {
                "customer_id": top["customer_name"],   # v2: customer_id IS the companyName string
                "customer_name": top["customer_name"],
            },
        },
        "match_confidence": confidence,
        "top_candidates": candidates[:3],
    }


# ---------------------------------------------------------------------------
# BackupRadar API v2 — snapshot collector
# ---------------------------------------------------------------------------

def collect_backupradar_snapshot(context: dict, fetch_impl=None) -> dict:
    """Collect all configured BackupRadar resources for the customer.

    BackupRadar API v2 notes:
    - config["customer_id"] carries the resolved companyName string (set by the resolver).
    - _build_resource_query uses it as the SearchByCompanyName value.
    - Core resource is 'backups'; optional resources are 'backups_inactive',
      'backups_retired', 'backups_overview', 'backups_filters'.
    - Resources named 'customers', 'jobs', 'devices', 'destinations' do not exist
      in v2 and will return 404 — they are treated as optional and silently skipped.
    """
    config = context["backupradar"]
    warnings: list[str] = []
    resources = config["resources"]
    collected_resources: dict[str, list[dict]] = {}
    inventory: dict[str, dict] = {}
    for resource_name, resource in resources.items():
        query = _build_resource_query(resource, config["customer_id"], context["period"])
        rows = _resolve_optional_collection(
            config,
            resource,
            query,
            required=resource_name in config["required_resources"],
            warnings=warnings,
            fetch_impl=fetch_impl,
        )
        collected_resources[resource_name] = rows
        inventory[resource_name] = {"count_collected": len(rows)}
    return {
        "datasource": "backupradar",
        "dataset": "backupradar_snapshot",
        "collection_path": "fleet script",
        "customer_name": config["customer_name"] or context["customer_name"],
        "customer_id": config["customer_id"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "collected_at": context["generated_at"],
        "scope": {
            "tenant_id": config["tenant_id"],
            "base_url": config["base_url"],
            "customer_id": config["customer_id"],
            "customer_name": config["customer_name"] or context["customer_name"],
        },
        "resource_paths": {
            name: resource["path"]
            for name, resource in resources.items()
        },
        "resources": collected_resources,
        "inventory": inventory,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# BackupRadar API v2 — v2 record normalizers
# ---------------------------------------------------------------------------

def _normalize_backup_v2(record: dict, customer_name: str) -> dict:
    """Normalise a single BackupRadar API v2 /backups record into the standard job shape.

    v2 field mapping:
      backupId          -> job_id
      companyName       -> customer_name
      deviceName        -> device_name
      deviceType.name   -> platform
      jobName           -> destination_name  (job name used as logical destination label)
      methodName        -> detail (backup method)
      status.name       -> status  (Success / Failed / Warning / No Result)
      lastResult        -> job_at
      lastSuccess       -> last_success_at
      isVerified        -> is_verified
    """
    raw_status = record.get("status") or {}
    status_name = raw_status.get("name") if isinstance(raw_status, dict) else _coerce_text(raw_status)
    status = _normalize_status(status_name or "")

    raw_dtype = record.get("deviceType") or {}
    platform = _coerce_text(raw_dtype.get("name") if isinstance(raw_dtype, dict) else raw_dtype)

    is_verified = _coerce_bool(record.get("isVerified"))
    return {
        "job_id": _coerce_text(record.get("backupId")) or "unknown-job",
        "customer_name": _coerce_text(record.get("companyName")) or customer_name,
        "device_id": _coerce_text(record.get("backupId")),
        "device_name": _coerce_text(record.get("deviceName")) or "unknown-device",
        "destination_id": "",
        "destination_name": _coerce_text(record.get("jobName")) or "unknown-job",
        "status": status,
        "job_at": _to_iso(record.get("lastResult")),
        "last_success_at": _to_iso(record.get("lastSuccess")),
        "duration_seconds": 0,
        "bytes_protected": 0,
        "detail": _coerce_text(record.get("methodName")),
        "site": "",
        "platform": platform,
        "review_status": "",
        "is_verified": bool(is_verified),
        "is_cleared": bool(is_verified),
        "is_reported": False,
        "is_checked": bool(is_verified),
        "was_pending_and_cleared": False,
        "raw": record,
    }


def _expand_history_to_jobs(backup_records: list[dict], customer_name: str, period: dict) -> list[dict]:
    """Expand per-job daily history arrays into individual day-level job records.

    BackupRadar v2 /backups?HistoryDays=N embeds a history[] array on each job.
    Each history entry carries countSuccess / countFailure / countWarning / countNoResult
    for that day.  We expand these into synthetic job records so the rest of the
    normalization pipeline (daily trend, device rollup, exception rows) works correctly.
    """
    period_start = period["start_iso"][:10]
    period_end = period["end_iso"][:10]
    expanded: list[dict] = []
    for record in backup_records:
        history = record.get("history") or []
        device_name = _coerce_text(record.get("deviceName")) or "unknown-device"
        job_name = _coerce_text(record.get("jobName")) or "unknown-job"
        backup_id = _coerce_text(record.get("backupId")) or "unknown-job"
        raw_dtype = record.get("deviceType") or {}
        platform = _coerce_text(raw_dtype.get("name") if isinstance(raw_dtype, dict) else raw_dtype)
        method = _coerce_text(record.get("methodName"))
        customer = _coerce_text(record.get("companyName")) or customer_name
        is_verified = bool(_coerce_bool(record.get("isVerified")))

        if not history:
            expanded.append(_normalize_backup_v2(record, customer_name))
            continue

        for day in history:
            date_str = _coerce_text(day.get("date") or "")[:10]
            if not date_str or date_str < period_start or date_str > period_end:
                continue
            counts = {
                "success":   int(_to_number(day.get("countSuccess"), 0)),
                "failed":    int(_to_number(day.get("countFailure"), 0)),
                "warning":   int(_to_number(day.get("countWarning"), 0)),
                "no_result": int(_to_number(day.get("countNoResult"), 0)),
            }
            for status_key, count in counts.items():
                if count <= 0:
                    continue
                mapped_status = (
                    "failed"  if status_key == "failed"    else
                    "warning" if status_key == "warning"   else
                    "unknown" if status_key == "no_result" else
                    "success"
                )
                for _ in range(count):
                    expanded.append({
                        "job_id": backup_id,
                        "customer_name": customer,
                        "device_id": backup_id,
                        "device_name": device_name,
                        "destination_id": "",
                        "destination_name": job_name,
                        "status": mapped_status,
                        "job_at": f"{date_str}T00:00:00Z",
                        "last_success_at": _to_iso(record.get("lastSuccess")),
                        "duration_seconds": 0,
                        "bytes_protected": 0,
                        "detail": method,
                        "site": "",
                        "platform": platform,
                        "review_status": "",
                        "is_verified": is_verified,
                        "is_cleared": False,
                        "is_reported": False,
                        "is_checked": False,
                        "was_pending_and_cleared": False,
                        "raw": record,
                    })
    return expanded


# ---------------------------------------------------------------------------
# BackupRadar API v2 — snapshot normalizer
# ---------------------------------------------------------------------------

def normalize_backupradar_snapshot(context: dict, snapshot: dict) -> dict:
    """Normalise a collected BackupRadar snapshot into the standard backup data model.

    BackupRadar API v2 provides all data through /backups (and sub-routes).
    There are no separate /devices, /destinations, /alerts, /restores, /sources,
    /policies, or /vaults endpoints.  This function reads from:

      resources['backups']           — active monitored backup jobs (with history if requested)
      resources['backups_inactive']  — inactive/stale jobs (optional)
      resources['backups_retired']   — retired jobs (optional)

    All other resource keys (jobs, devices, destinations, alerts, etc.) are silently
    ignored — they will be empty from the collector since v2 returns 404 for them.
    """
    resources = snapshot.get("resources", {})
    customer_name = snapshot.get("customer_name") or context["customer_name"]

    # All data in v2 comes from /backups and sub-routes.
    raw_backups = resources.get("backups", [])

    # Devices and destinations derived from backup records (no separate endpoints in v2).
    devices = [
        _normalize_device({
            "id": r.get("backupId"),
            "name": r.get("deviceName"),
            "platform": (r.get("deviceType") or {}).get("name") if isinstance(r.get("deviceType"), dict) else r.get("deviceType"),
        })
        for r in raw_backups
    ]
    destinations = [
        _normalize_destination({
            "id": r.get("backupId"),
            "name": r.get("jobName"),
            "type": r.get("methodName"),
        })
        for r in raw_backups
    ]
    device_by_id, device_by_name = _index_by(devices, "device_id", "device_name")
    destination_by_id, destination_by_name = _index_by(destinations, "destination_id", "destination_name")

    # Expand history into per-day job records for trend/rollup calculations.
    jobs = _expand_history_to_jobs(raw_backups, customer_name, context["period"])
    if not jobs:
        jobs = [_normalize_backup_v2(r, customer_name) for r in raw_backups]

    # v2 has no dedicated alert/restore/source/policy/vault endpoints.
    alerts: list[dict] = []
    restores: list[dict] = []
    sources: list[dict] = []
    policies: list[dict] = []
    vaults: list[dict] = []

    totals = defaultdict(int)
    total_bytes_protected = 0
    for job in jobs:
        totals[job["status"]] += 1
        total_bytes_protected += int(_to_number(job["bytes_protected"], default=0))

    device_rollup = _build_device_rollup(jobs)
    destination_rollup = _build_destination_rollup(jobs)
    exception_rows = _build_exception_rows(jobs)
    successful_jobs = totals["success"] + totals["retried"]
    failed_devices = len([row for row in device_rollup if row["failed"] > 0 or row["warning"] > 0])
    pending_jobs_cleared = len([job for job in jobs if job["was_pending_and_cleared"]])
    warning_jobs_verified = len([job for job in jobs if job["status"] == "warning" and job["is_verified"]])
    warning_jobs_cleared = len([job for job in jobs if job["status"] == "warning" and job["is_cleared"]])
    successful_jobs_reported = len([job for job in jobs if job["status"] in {"success", "retried"} and job["is_reported"]])
    open_alerts = len([alert for alert in alerts if not alert.get("is_cleared")])
    cleared_alerts = len([alert for alert in alerts if alert.get("is_cleared")])
    verified_alerts = len([alert for alert in alerts if alert.get("is_verified")])
    restore_failures = len([restore for restore in restores if restore.get("status") in {"failed", "warning", "unknown"}])
    disabled_sources = len([source for source in sources if not source.get("is_enabled")])
    unhealthy_sources = len([source for source in sources if source.get("status") in {"failed", "warning", "pending", "running", "unknown"}])
    disabled_policies = len([policy for policy in policies if not policy.get("is_enabled")])
    total_vault_capacity = sum(vault.get("capacity_bytes", 0) for vault in vaults)
    total_vault_used = sum(vault.get("used_bytes", 0) for vault in vaults)
    resource_counts = {name: len(entries) for name, entries in resources.items()}

    return {
        "datasource": "backupradar",
        "dataset": "backup",
        "collection_path": "fleet script",
        "customer_name": customer_name,
        "customer_id": snapshot.get("customer_id") or context["backupradar"]["customer_id"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "generated_at": context["generated_at"],
        "totals": {
            "jobs": len(jobs),
            "successful_jobs": successful_jobs,
            "success_jobs": totals["success"],
            "retried_jobs": totals["retried"],
            "warning_jobs": totals["warning"],
            "failed_jobs": totals["failed"],
            "pending_jobs": totals["pending"],
            "running_jobs": totals["running"],
            "skipped_jobs": totals["skipped"],
            "unknown_jobs": totals["unknown"],
            "pending_jobs_cleared": pending_jobs_cleared,
            "warning_jobs_verified": warning_jobs_verified,
            "warning_jobs_cleared": warning_jobs_cleared,
            "successful_jobs_reported": successful_jobs_reported,
            "protected_devices": len({job["device_id"] or job["device_name"] for job in jobs if job["device_name"]}),
            "devices_with_failures": failed_devices,
            "destinations_in_scope": len(destination_rollup),
            "success_rate_percent": _ratio_to_percent(successful_jobs, len(jobs)),
            "failure_rate_percent": _ratio_to_percent(totals["failed"], len(jobs)),
            "warning_rate_percent": _ratio_to_percent(totals["warning"], len(jobs)),
            "bytes_protected_total": total_bytes_protected,
            "bytes_protected_gb": _round_value(total_bytes_protected / 1_000_000_000, 2),
            "alert_count": len(alerts),
            "open_alerts": open_alerts,
            "cleared_alerts": cleared_alerts,
            "verified_alerts": verified_alerts,
            "restore_jobs": len(restores),
            "restore_failed_jobs": restore_failures,
            "source_count": len(sources),
            "disabled_sources": disabled_sources,
            "unhealthy_sources": unhealthy_sources,
            "policy_count": len(policies),
            "disabled_policies": disabled_policies,
            "vault_count": len(vaults),
            "vault_capacity_gb": _round_value(total_vault_capacity / 1_000_000_000, 2),
            "vault_used_gb": _round_value(total_vault_used / 1_000_000_000, 2),
            "vault_usage_percent": _ratio_to_percent(total_vault_used, total_vault_capacity),
        },
        "jobs": jobs,
        "devices": devices,
        "destinations": destinations,
        "alerts": alerts,
        "restores": restores,
        "sources": sources,
        "policies": policies,
        "vaults": vaults,
        "resource_counts": resource_counts,
        "daily_status_counts": _build_daily_status_counts(context["period"], jobs),
        "device_status_rollup": device_rollup,
        "destination_status_rollup": destination_rollup,
        "exception_rows": exception_rows,
        "warnings": snapshot.get("warnings", []),
    }


def build_backup_summary(context: dict, normalized: dict) -> dict:
    totals = normalized["totals"]
    top_failed_devices = [
        {
            "device_name": row["device_name"],
            "failed": row["failed"],
            "warning": row["warning"],
            "latest_job_at": row["latest_job_at"],
        }
        for row in normalized["device_status_rollup"][:5]
        if row["failed"] > 0 or row["warning"] > 0
    ]
    top_failed_destinations = [
        {
            "destination_name": row["destination_name"],
            "failed": row["failed"],
            "warning": row["warning"],
        }
        for row in normalized["destination_status_rollup"][:5]
        if row["failed"] > 0 or row["warning"] > 0
    ]
    notable_points = []
    if totals["failed_jobs"]:
        notable_points.append(f"{totals['failed_jobs']} backup jobs failed during the reporting window.")
    if totals["retried_jobs"]:
        notable_points.append(f"{totals['retried_jobs']} backup jobs succeeded only after retry.")
    if totals["pending_jobs_cleared"]:
        notable_points.append(f"{totals['pending_jobs_cleared']} pending backups were checked and cleared.")
    if totals["warning_jobs_cleared"]:
        notable_points.append(f"{totals['warning_jobs_cleared']} warning backups were verified and cleared.")
    if totals["successful_jobs_reported"]:
        notable_points.append(f"{totals['successful_jobs_reported']} successful backups were explicitly marked as reported.")
    if totals["devices_with_failures"]:
        notable_points.append(f"{totals['devices_with_failures']} protected devices recorded failed or warning states.")
    if not notable_points:
        notable_points.append("No failed or warning backup jobs were recorded for the reporting window.")
    return {
        "datasource": "backupradar",
        "dataset": "backup_summary",
        "collection_path": "fleet script",
        "customer_name": normalized["customer_name"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "summary_kpis": totals,
        "resource_counts": normalized["resource_counts"],
        "top_failed_devices": top_failed_devices,
        "top_failed_destinations": top_failed_destinations,
        "notable_points": notable_points,
    }


def _build_weekly_totals(daily_status_counts: list[dict]) -> list[dict]:
    weekly: dict[str, dict] = {}
    for index, day in enumerate(daily_status_counts):
        week_label = f"W{(index // 7) + 1}"
        row = weekly.setdefault(week_label, {
            "label": week_label,
            "success": 0,
            "retried": 0,
            "warning": 0,
            "failed": 0,
            "pending": 0,
            "running": 0,
            "skipped": 0,
            "unknown": 0,
        })
        for key in ("success", "retried", "warning", "failed", "pending", "running", "skipped", "unknown"):
            row[key] += day[key]
    return list(weekly.values())


def build_backup_trends(context: dict, normalized: dict) -> dict:
    return {
        "datasource": "backupradar",
        "dataset": "backup_trends",
        "collection_path": "fleet script",
        "customer_name": normalized["customer_name"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "daily_status_counts": normalized["daily_status_counts"],
        "weekly_status_totals": _build_weekly_totals(normalized["daily_status_counts"]),
    }


def build_backup_exceptions(context: dict, normalized: dict) -> dict:
    return {
        "datasource": "backupradar",
        "dataset": "backup_exceptions",
        "collection_path": "fleet script",
        "customer_name": normalized["customer_name"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "exception_count": len(normalized["exception_rows"]),
        "rows": normalized["exception_rows"],
    }


def build_backupradar_artifacts(context: dict, snapshot: dict, normalized: dict) -> dict:
    backup_summary = build_backup_summary(context, normalized)
    backup_trends = build_backup_trends(context, normalized)
    backup_exceptions = build_backup_exceptions(context, normalized)
    bundle = {
        "datasource": "backupradar",
        "dataset": "backupradar_report_bundle",
        "collection_path": "fleet script",
        "customer_name": normalized["customer_name"],
        "customer_id": normalized["customer_id"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "generated_at": context["generated_at"],
        "sections": {
            "source_inventory_summary": {
                **{
                    name: meta["count_collected"]
                    for name, meta in snapshot["inventory"].items()
                },
            },
            "backup_summary": backup_summary,
            "backup_trends": backup_trends,
            "backup_exceptions": {
                "exception_count": backup_exceptions["exception_count"],
                "rows": backup_exceptions["rows"],
            },
            "backup_operational_outcomes": {
                "pending_jobs": normalized["totals"]["pending_jobs"],
                "pending_jobs_cleared": normalized["totals"]["pending_jobs_cleared"],
                "warning_jobs_verified": normalized["totals"]["warning_jobs_verified"],
                "warning_jobs_cleared": normalized["totals"]["warning_jobs_cleared"],
                "successful_jobs_reported": normalized["totals"]["successful_jobs_reported"],
                "restore_jobs": normalized["totals"]["restore_jobs"],
                "restore_failed_jobs": normalized["totals"]["restore_failed_jobs"],
                "open_alerts": normalized["totals"]["open_alerts"],
                "cleared_alerts": normalized["totals"]["cleared_alerts"],
            },
        },
        "evidence_candidates": [
            {
                "device_name": row["device_name"],
                "destination_name": row["destination_name"],
                "status": row["status"],
                "job_at": row["job_at"],
            }
            for row in backup_exceptions["rows"][:5]
        ],
        "warnings": normalized.get("warnings", []),
    }
    return {
        "backup_summary": backup_summary,
        "backup_trends": backup_trends,
        "backup_exceptions": backup_exceptions,
        "bundle": bundle,
    }


def run_backupradar_pipeline(context: dict, fetch_impl=None) -> dict:
    snapshot = collect_backupradar_snapshot(context, fetch_impl=fetch_impl)
    backup = normalize_backupradar_snapshot(context, snapshot)
    artifacts = build_backupradar_artifacts(context, snapshot, backup)
    return {
        "snapshot": snapshot,
        "backup": backup,
        **artifacts,
    }
