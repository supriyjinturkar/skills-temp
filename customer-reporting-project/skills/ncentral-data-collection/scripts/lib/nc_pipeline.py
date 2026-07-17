from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


class ApiResponseError(RuntimeError):
    def __init__(self, status: int, url: str, payload):
        super().__init__(f"N-central API request failed with {status} for {url}: {payload}")
        self.status = status
        self.url = url
        self.payload = payload


def _coerce_text(value, default: str = "") -> str:
    if value in (None, ""):
        return default
    return str(value).strip() or default


def _coerce_int(value, default=0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _coerce_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round_value(value, decimals=2):
    return round(float(value or 0), decimals)


def _ratio_to_percent(numerator, denominator):
    if not denominator:
        return 0
    return _round_value((numerator / denominator) * 100, 2)


def _to_iso(value) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    text = str(value).strip()
    for formatter in (
        lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")),
        lambda v: datetime.strptime(v, "%Y-%m-%d %H:%M:%S"),
    ):
        try:
            parsed = formatter(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            continue
    return None


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


def _build_url(base_url: str, path: str, query: dict[str, object] | None = None) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        root = path
    else:
        root = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    clean_query = {
        key: value
        for key, value in (query or {}).items()
        if value not in (None, "", [])
    }
    return f"{root}?{urlencode(clean_query, doseq=True)}" if clean_query else root


def _load_json(body: str):
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def _lookup_key(payload: dict, dotted_key: str):
    current = payload
    for part in dotted_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _extract_page_items(payload, preferred_keys: tuple[str, ...] = ()) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in preferred_keys:
        if isinstance(payload.get(key), list):
            return payload[key]
    for key in (
        "data",
        "items",
        "results",
        "customers",
        "sites",
        "devices",
        "serviceOrgs",
        "activeIssues",
        "issues",
        "customProperties",
        "properties",
    ):
        if isinstance(payload.get(key), list):
            return payload[key]
    list_values = [value for value in payload.values() if isinstance(value, list)]
    if len(list_values) == 1:
        return list_values[0]
    return []


def _extract_inline_error(payload) -> str:
    if not isinstance(payload, dict):
        return ""
    for key, value in payload.items():
        normalized = "".join(ch.lower() for ch in str(key) if ch.isalnum())
        if normalized in {"errormessage", "error"} and value not in (None, "", [], {}):
            return _coerce_text(value)
    return ""


def _normalize_candidate_text(value: str) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _candidate_names(record: dict, keys: list[str]) -> list[str]:
    names: list[str] = []
    for key in keys:
        value = record.get(key)
        if value in (None, ""):
            continue
        text = str(value).strip()
        if text and text not in names:
            names.append(text)
    return names


def _score_name_candidate(record: dict, queries: list[str], keys: list[str]) -> tuple[int, str]:
    names = _candidate_names(record, keys)
    if not names:
        return 0, "no candidate names"
    normalized_names = [_normalize_candidate_text(name) for name in names]
    best_score = 0
    best_reason = "no match"
    for query in queries:
        query_text = str(query or "").strip()
        if not query_text:
            continue
        normalized_query = _normalize_candidate_text(query_text)
        for raw_name, normalized_name in zip(names, normalized_names):
            if raw_name == query_text:
                return 130, f"exact display-name match on '{raw_name}'"
            if normalized_name == normalized_query:
                return 120, f"normalized exact match on '{raw_name}'"
            if raw_name.lower().startswith(query_text.lower()):
                score = 105
                reason = f"prefix match on '{raw_name}'"
            elif query_text.lower() in raw_name.lower():
                score = 95
                reason = f"substring match on '{raw_name}'"
            elif normalized_query and normalized_query in normalized_name:
                score = 90
                reason = f"normalized substring match on '{raw_name}'"
            else:
                query_tokens = {token for token in query_text.lower().split() if token}
                name_tokens = {token for token in raw_name.lower().replace("-", " ").split() if token}
                overlap = len(query_tokens & name_tokens)
                if overlap:
                    score = 70 + min(overlap * 5, 15)
                    reason = f"token-overlap match on '{raw_name}'"
                else:
                    score = 0
                    reason = "no match"
            if score > best_score:
                best_score = score
                best_reason = reason
    return best_score, best_reason


def _confidence_label(best_score: int, second_score: int) -> str:
    if best_score >= 120 and best_score - second_score >= 10:
        return "high"
    if best_score >= 95:
        return "medium"
    return "low"


def _normalize_issue_state(value: str) -> str:
    raw = _coerce_text(value).lower()
    if any(token in raw for token in ("critical", "failed", "down", "error")):
        return "critical"
    if any(token in raw for token in ("warn", "degraded", "attention")):
        return "warning"
    if any(token in raw for token in ("info", "notice")):
        return "info"
    return raw or "unknown"


def _issue_sort_rank(value: str) -> int:
    return {"critical": 0, "warning": 1, "info": 2, "unknown": 3}.get(value, 4)


def _issue_key(issue: dict) -> str:
    parts = [
        _coerce_text(issue.get("deviceId") or issue.get("device_id")),
        _coerce_text(issue.get("serviceId") or issue.get("service_id")),
        _coerce_text(issue.get("serviceItemId") or issue.get("service_item_id")),
        _coerce_text(issue.get("taskId") or issue.get("task_id")),
        _coerce_text(issue.get("uri")),
        _coerce_text(issue.get("serviceName") or issue.get("service_name")),
    ]
    return "|".join(parts)


def _pick_site_id(issue: dict, default_site_id: str = "") -> str:
    for key in ("siteId", "orgUnitId", "site_id", "org_unit_id"):
        value = issue.get(key)
        if value not in (None, ""):
            return str(value)
    extra = issue.get("_extra") or {}
    for key in ("siteId", "orgUnitId"):
        value = extra.get(key)
        if value not in (None, ""):
            return str(value)
    return default_site_id


def _pick_customer_id(issue: dict, default_customer_id: str = "") -> str:
    for key in ("customerId", "customer_id"):
        value = issue.get(key)
        if value not in (None, ""):
            return str(value)
    extra = issue.get("_extra") or {}
    value = extra.get("customerId")
    return str(value) if value not in (None, "") else default_customer_id


class NCentralApi:
    def __init__(self, config: dict, fetch_impl=None, sleep_impl=None):
        self.config = config
        self.fetch_impl = fetch_impl
        self.sleep_impl = sleep_impl or time.sleep
        self.access_token = ""
        self.refresh_token = ""
        self.access_token_expires_at = 0.0
        self.refresh_token_expires_at = 0.0
        self.diagnostics = {
            "requests_by_endpoint": defaultdict(int),
            "rate_limit_retries": 0,
            "auth_refreshes": 0,
            "warnings": [],
        }

    def get_diagnostics(self) -> dict:
        return {
            **self.diagnostics,
            "requests_by_endpoint": dict(self.diagnostics["requests_by_endpoint"]),
        }

    def _transport(self, method: str, url: str, headers: dict[str, str], body_text: str):
        if self.fetch_impl:
            status, response_headers, response_body = self.fetch_impl(method, url, headers, body_text)
            return int(status), {str(k): str(v) for k, v in (response_headers or {}).items()}, str(response_body or "")
        request = Request(
            url,
            headers=headers,
            method=method,
            data=body_text.encode("utf-8") if body_text else None,
        )
        try:
            with urlopen(request, timeout=int(self.config["request_timeout_seconds"])) as response:
                return int(response.status), dict(response.headers.items()), response.read().decode("utf-8")
        except HTTPError as error:  # pragma: no cover
            return int(error.code), dict(error.headers.items()), error.read().decode("utf-8") if error.fp else _coerce_text(error.reason)
        except URLError as error:  # pragma: no cover
            raise RuntimeError(f"N-central request failed for {url}: {error}") from error

    def _token_expired(self, expires_at: float) -> bool:
        skew = float(self.config["auth_refresh_skew_seconds"])
        return not expires_at or time.time() >= max(expires_at - skew, 0)

    def _store_tokens(self, payload: dict, fallback_seconds: int = 900) -> None:
        access_token = _coerce_text(
            payload.get("accessToken")
            or payload.get("access_token")
            or _lookup_key(payload, "data.accessToken")
            or _lookup_key(payload, "tokens.accessToken")
            or _lookup_key(payload, "tokens.access.token"),
        )
        refresh_token = _coerce_text(
            payload.get("refreshToken")
            or payload.get("refresh_token")
            or _lookup_key(payload, "data.refreshToken")
            or _lookup_key(payload, "tokens.refreshToken")
            or _lookup_key(payload, "tokens.refresh.token"),
        )
        if not access_token:
            raise RuntimeError(f"N-central authentication response did not include an access token: {payload}")
        now = time.time()
        access_expires_in = _coerce_int(
            payload.get("accessTokenExpiresIn")
            or payload.get("expiresIn")
            or _lookup_key(payload, "data.accessTokenExpiresIn")
            or _lookup_key(payload, "tokens.access.expirySeconds")
            or fallback_seconds,
            fallback_seconds,
        )
        refresh_expires_in = _coerce_int(
            payload.get("refreshTokenExpiresIn")
            or _lookup_key(payload, "data.refreshTokenExpiresIn")
            or _lookup_key(payload, "tokens.refresh.expirySeconds")
            or max(access_expires_in * 4, 3600),
            max(access_expires_in * 4, 3600),
        )
        self.access_token = access_token
        self.refresh_token = refresh_token or self.refresh_token
        self.access_token_expires_at = now + max(access_expires_in, 1)
        if self.refresh_token:
            self.refresh_token_expires_at = now + max(refresh_expires_in, 1)

    def _load_jwt_token(self) -> None:
        token_path = _coerce_text(self.config.get("jwt_token_path"))
        if not token_path:
            raise RuntimeError("N-central JWT token path is required in the collector config.")
        try:
            token = Path(token_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"N-central JWT token file could not be read at {token_path}: {exc}") from exc
        if not token:
            raise RuntimeError(f"N-central JWT token file was empty at {token_path}.")
        self.access_token = token
        self.access_token_expires_at = float("inf")
        self.refresh_token = ""
        self.refresh_token_expires_at = 0.0

    def authenticate(self) -> None:
        self._load_jwt_token()

    def refresh(self) -> None:
        self._load_jwt_token()
        self.diagnostics["auth_refreshes"] += 1

    def _ensure_access_token(self) -> None:
        if self.access_token:
            return
        self.authenticate()

    def request_json(
        self,
        method: str,
        path: str,
        query: dict[str, object] | None = None,
        body: dict | list | None = None,
        endpoint_key: str = "default",
        auth_mode: str = "access_token",
        allow_refresh_on_401: bool = True,
    ):
        if auth_mode == "access_token":
            self._ensure_access_token()
        attempts = max(int(self.config["request_retry_attempts"]), 1)
        backoff_seconds = max(float(self.config["request_retry_backoff_ms"]) / 1000.0, 0.1)
        auth_retry_available = allow_refresh_on_401 and auth_mode == "access_token"
        for attempt in range(attempts):
            headers = {
                "Accept": "application/json",
            }
            if body is not None:
                headers["Content-Type"] = "application/json"
            if auth_mode == "access_token":
                headers["Authorization"] = f"Bearer {self.access_token}"
            elif auth_mode == "refresh_token":
                headers["Authorization"] = f"Bearer {self.refresh_token}"
            url = _build_url(self.config["base_url"], path, query)
            body_text = json.dumps(body) if body is not None else ""
            status, response_headers, response_body = self._transport(method, url, headers, body_text)
            payload = _load_json(response_body)
            if status in {401, 403} and auth_retry_available:
                auth_retry_available = False
                self.refresh()
                continue
            if status == 429 and attempt + 1 < attempts:
                self.diagnostics["rate_limit_retries"] += 1
                delay = _parse_retry_after(response_headers) or backoff_seconds * (2 ** attempt)
                self.sleep_impl(delay)
                continue
            if status in {500, 502, 503, 504} and attempt + 1 < attempts:
                self.sleep_impl(backoff_seconds * (2 ** attempt))
                continue
            if status >= 400:
                raise ApiResponseError(status, url, payload)
            inline_error = _extract_inline_error(payload)
            if inline_error:
                raise ApiResponseError(status, url, payload)
            self.diagnostics["requests_by_endpoint"][endpoint_key] += 1
            return payload, response_headers
        raise RuntimeError(f"N-central request retry budget exhausted for {path}")

    def list_paged(
        self,
        path: str,
        query: dict[str, object] | None = None,
        endpoint_key: str = "default",
        preferred_keys: tuple[str, ...] = (),
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> dict:
        page_size = int(page_size or self.config["fetch_page_size"])
        max_pages = int(max_pages if max_pages is not None else self.config["max_pages_per_endpoint"])
        page_number = 1
        items: list[dict] = []
        total_items = 0
        total_pages = 0
        while True:
            current_query = {
                **(query or {}),
                "pageSize": page_size,
                "pageNumber": page_number,
            }
            payload, _headers = self.request_json("GET", path, query=current_query, endpoint_key=endpoint_key)
            page_items = _extract_page_items(payload, preferred_keys=preferred_keys)
            items.extend(page_items)
            total_items = _coerce_int(payload.get("totalItems"), len(items)) or len(items)
            total_pages = _coerce_int(payload.get("totalPages"), total_pages)
            if total_pages and page_number >= total_pages:
                break
            if total_items and len(items) >= total_items:
                break
            if len(page_items) < page_size:
                break
            page_number += 1
            if max_pages and page_number > max_pages:
                raise RuntimeError(
                    f"N-central paging safety limit exceeded for {path}. "
                    f"Collected {len(items)} rows before hitting max_pages_per_endpoint={max_pages}.",
                )
        return {
            "count_collected": len(items),
            "items": items,
            "total": total_items or len(items),
            "pages_collected": page_number,
        }

    def list_customers(self, service_org_id=None) -> dict:
        if service_org_id is not None:
            return self.list_paged(
                f"/api/service-orgs/{int(service_org_id)}/customers",
                endpoint_key="service_org_customers",
                preferred_keys=("customers", "data"),
            )
        return self.list_paged(
            "/api/customers",
            endpoint_key="customers",
            preferred_keys=("customers", "data"),
        )

    def list_sites(self) -> dict:
        return self.list_paged(
            "/api/sites",
            endpoint_key="sites",
            preferred_keys=("sites", "data"),
        )

    def list_customer_sites(self, customer_id: int) -> dict:
        return self.list_paged(
            f"/api/customers/{int(customer_id)}/sites",
            endpoint_key="customer_sites",
            preferred_keys=("sites", "data"),
        )

    def list_org_unit_devices(self, org_unit_id: int) -> dict:
        return self.list_paged(
            f"/api/org-units/{int(org_unit_id)}/devices",
            endpoint_key="org_unit_devices",
            preferred_keys=("devices", "data"),
        )

    def list_active_issues(self, org_unit_id: int) -> dict:
        return self.list_paged(
            f"/api/org-units/{int(org_unit_id)}/active-issues",
            endpoint_key="active_issues",
            preferred_keys=("activeIssues", "issues", "data"),
        )

    def get_org_unit_custom_properties(self, org_unit_id: int) -> list[dict]:
        payload, _headers = self.request_json(
            "GET",
            f"/api/org-units/{int(org_unit_id)}/custom-properties",
            endpoint_key="org_unit_custom_properties",
        )
        items = _extract_page_items(payload, preferred_keys=("customProperties", "properties", "data"))
        if items:
            return items
        if isinstance(payload, dict):
            return [
                {"name": key, "value": value}
                for key, value in payload.items()
                if key not in {"totalItems", "pageNumber", "pageSize", "totalPages"}
            ]
        return []

    def get_device_custom_properties(self, device_id: int) -> list[dict]:
        payload, _headers = self.request_json(
            "GET",
            f"/api/devices/{int(device_id)}/custom-properties",
            endpoint_key="device_custom_properties",
        )
        items = _extract_page_items(payload, preferred_keys=("customProperties", "properties", "data"))
        if items:
            return items
        if isinstance(payload, dict):
            return [
                {"name": key, "value": value}
                for key, value in payload.items()
                if key not in {"totalItems", "pageNumber", "pageSize", "totalPages"}
            ]
        return []


def resolve_ncentral_scope_by_company(context: dict, fetch_impl=None, sleep_impl=None) -> dict:
    api = NCentralApi(context["ncentral"], fetch_impl=fetch_impl, sleep_impl=sleep_impl)
    queries = [
        query
        for query in [
            context.get("company_name"),
            context.get("customer_name"),
            *(context.get("company_aliases") or []),
        ]
        if isinstance(query, str) and query.strip()
    ]
    if not queries:
        raise ValueError("company_name or customer_name is required to resolve N-central scope.")

    customers = api.list_customers(context["ncentral"]["service_org_id"])
    scored_customers = []
    for customer in customers["items"]:
        score, reason = _score_name_candidate(
            customer,
            queries,
            ["customerName", "longName", "name", "displayName", "customerShortName"],
        )
        if score >= 85:
            scored_customers.append(
                {
                    "customer_id": customer.get("customerId") or customer.get("id"),
                    "customer_name": _coerce_text(
                        customer.get("customerName")
                        or customer.get("longName")
                        or customer.get("name")
                        or customer.get("displayName"),
                    ),
                    "service_org_id": customer.get("soId") or customer.get("serviceOrgId"),
                    "score": score,
                    "reason": reason,
                }
            )
    scored_customers.sort(key=lambda entry: (-entry["score"], len(entry["customer_name"]), entry["customer_name"]))

    site_candidates = []
    best_customer_score = scored_customers[0]["score"] if scored_customers else 0
    if best_customer_score < 120:
        sites = api.list_sites()
        for site in sites["items"]:
            score, reason = _score_name_candidate(
                site,
                queries,
                ["siteName", "longName", "name", "displayName"],
            )
            if score >= 85:
                site_candidates.append(
                    {
                        "site_id": site.get("siteId") or site.get("id"),
                        "site_name": _coerce_text(
                            site.get("siteName")
                            or site.get("longName")
                            or site.get("name")
                            or site.get("displayName"),
                        ),
                        "customer_id": site.get("customerId"),
                        "service_org_id": site.get("soId") or site.get("serviceOrgId"),
                        "score": score,
                        "reason": reason,
                    }
                )
        site_candidates.sort(key=lambda entry: (-entry["score"], len(entry["site_name"]), entry["site_name"]))

    if scored_customers:
        top_customer = scored_customers[0]
        customer_sites = api.list_customer_sites(int(top_customer["customer_id"]))
        site_names = []
        site_ids = []
        for site in customer_sites["items"]:
            site_id = site.get("siteId") or site.get("id")
            site_name = _coerce_text(site.get("siteName") or site.get("longName") or site.get("name") or site.get("displayName"))
            if site_id is not None:
                site_ids.append(int(site_id))
            if site_name:
                site_names.append(site_name)
        second_customer_score = scored_customers[1]["score"] if len(scored_customers) > 1 else 0
        return {
            "company_name": queries[0],
            "queries_used": queries,
            "match_confidence": _confidence_label(top_customer["score"], second_customer_score),
            "matched_customer_candidates": scored_customers[:10],
            "matched_site_candidates": site_candidates[:10],
            "resolved_scope": {
                "ncentral": {
                    "base_url": context["ncentral"]["base_url"],
                    "service_org_id": top_customer["service_org_id"] or context["ncentral"]["service_org_id"],
                    "customer_id": int(top_customer["customer_id"]),
                    "customer_name": top_customer["customer_name"],
                    "org_unit_id": int(top_customer["customer_id"]),
                    "org_unit_name": top_customer["customer_name"],
                    "org_unit_type": "customer",
                    "site_ids": site_ids,
                    "site_names": site_names,
                    "request_timeout_seconds": context["ncentral"]["request_timeout_seconds"],
                    "request_retry_attempts": context["ncentral"]["request_retry_attempts"],
                    "request_retry_backoff_ms": context["ncentral"]["request_retry_backoff_ms"],
                    "fetch_page_size": context["ncentral"]["fetch_page_size"],
                    "max_pages_per_endpoint": context["ncentral"]["max_pages_per_endpoint"],
                    "max_parallel_device_property_requests": context["ncentral"]["max_parallel_device_property_requests"],
                    "max_parallel_site_issue_requests": context["ncentral"]["max_parallel_site_issue_requests"],
                    "device_custom_properties_mode": context["ncentral"]["device_custom_properties_mode"],
                    "full_device_custom_properties_threshold": context["ncentral"]["full_device_custom_properties_threshold"],
                    "max_device_custom_property_devices": context["ncentral"]["max_device_custom_property_devices"],
                    "site_issue_query_limit": context["ncentral"]["site_issue_query_limit"],
                    "fetch_site_active_issues": context["ncentral"]["fetch_site_active_issues"],
                    "stale_checkin_hours": context["ncentral"]["stale_checkin_hours"],
                },
            },
            "collection_log": api.get_diagnostics(),
        }

    if not site_candidates:
        raise RuntimeError(f"No N-central customers or sites matched company name '{queries[0]}'.")

    top_site = site_candidates[0]
    second_site_score = site_candidates[1]["score"] if len(site_candidates) > 1 else 0
    return {
        "company_name": queries[0],
        "queries_used": queries,
        "match_confidence": _confidence_label(top_site["score"], second_site_score),
        "matched_customer_candidates": scored_customers[:10],
        "matched_site_candidates": site_candidates[:10],
        "resolved_scope": {
            "ncentral": {
                "base_url": context["ncentral"]["base_url"],
                "service_org_id": top_site["service_org_id"] or context["ncentral"]["service_org_id"],
                "customer_id": _coerce_int(top_site["customer_id"]),
                "org_unit_id": int(top_site["site_id"]),
                "org_unit_name": top_site["site_name"],
                "org_unit_type": "site",
                "site_id": int(top_site["site_id"]),
                "site_name": top_site["site_name"],
                "site_ids": [int(top_site["site_id"])],
                "site_names": [top_site["site_name"]],
                "request_timeout_seconds": context["ncentral"]["request_timeout_seconds"],
                "request_retry_attempts": context["ncentral"]["request_retry_attempts"],
                "request_retry_backoff_ms": context["ncentral"]["request_retry_backoff_ms"],
                "fetch_page_size": context["ncentral"]["fetch_page_size"],
                "max_pages_per_endpoint": context["ncentral"]["max_pages_per_endpoint"],
                "max_parallel_device_property_requests": context["ncentral"]["max_parallel_device_property_requests"],
                "max_parallel_site_issue_requests": context["ncentral"]["max_parallel_site_issue_requests"],
                "device_custom_properties_mode": context["ncentral"]["device_custom_properties_mode"],
                "full_device_custom_properties_threshold": context["ncentral"]["full_device_custom_properties_threshold"],
                "max_device_custom_property_devices": context["ncentral"]["max_device_custom_property_devices"],
                "site_issue_query_limit": context["ncentral"]["site_issue_query_limit"],
                "fetch_site_active_issues": context["ncentral"]["fetch_site_active_issues"],
                "stale_checkin_hours": context["ncentral"]["stale_checkin_hours"],
            },
        },
        "collection_log": api.get_diagnostics(),
    }


def _select_device_ids_for_property_enrichment(context: dict, devices: list[dict], issues: list[dict], warnings: list[str]) -> list[int]:
    config = context["ncentral"]
    mode = config["device_custom_properties_mode"]
    if mode == "none":
        return []
    sorted_device_ids = [
        int(device_id)
        for device_id in sorted(
            {
                _coerce_int(device.get("deviceId") or device.get("id"))
                for device in devices
                if _coerce_int(device.get("deviceId") or device.get("id"))
            }
        )
    ]
    if mode == "all":
        selected = sorted_device_ids
    elif len(sorted_device_ids) <= config["full_device_custom_properties_threshold"]:
        selected = sorted_device_ids
    else:
        impacted_ids = []
        seen = set()
        for issue in issues:
            device_id = _coerce_int(issue.get("deviceId"))
            if device_id and device_id not in seen:
                seen.add(device_id)
                impacted_ids.append(device_id)
        remaining = [device_id for device_id in sorted_device_ids if device_id not in seen]
        selected = impacted_ids + remaining
    limit = config["max_device_custom_property_devices"]
    if limit and len(selected) > limit:
        warnings.append(
            f"N-central device custom-property enrichment capped at {limit} devices "
            f"(candidate device count: {len(selected)}).",
        )
        selected = selected[:limit]
    return selected


def _fetch_device_custom_properties(api: NCentralApi, device_ids: list[int], context: dict, warnings: list[str]) -> list[dict]:
    if not device_ids:
        return []
    results: list[dict] = []
    max_workers = min(
        max(int(context["ncentral"]["max_parallel_device_property_requests"]), 1),
        5,
        len(device_ids),
    )
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(api.get_device_custom_properties, device_id): device_id
            for device_id in device_ids
        }
        for future in as_completed(future_map):
            device_id = future_map[future]
            try:
                properties = future.result()
            except Exception as error:
                warnings.append(f"N-central device custom-property fetch failed for device {device_id}: {error}")
                continue
            results.append(
                {
                    "device_id": device_id,
                    "properties": properties,
                }
            )
    results.sort(key=lambda entry: entry["device_id"])
    return results


def _fetch_site_issue_details(api: NCentralApi, site_records: list[dict], context: dict, warnings: list[str]) -> dict[str, dict]:
    config = context["ncentral"]
    if not config["fetch_site_active_issues"]:
        return {}
    if len(site_records) > config["site_issue_query_limit"]:
        warnings.append(
            f"N-central per-site issue fan-out skipped because site count {len(site_records)} "
            f"exceeds site_issue_query_limit={config['site_issue_query_limit']}.",
        )
        return {}
    max_workers = min(
        max(int(config["max_parallel_site_issue_requests"]), 1),
        3,
        len(site_records) or 1,
    )
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {}
        for site in site_records:
            site_id = _coerce_int(site.get("siteId") or site.get("id"))
            if not site_id:
                continue
            future_map[executor.submit(api.list_active_issues, site_id)] = str(site_id)
        for future in as_completed(future_map):
            site_id = future_map[future]
            try:
                results[site_id] = future.result()
            except Exception as error:
                warnings.append(f"N-central site issue fetch failed for site {site_id}: {error}")
    return results


def collect_ncentral_snapshot(context: dict, fetch_impl=None, sleep_impl=None) -> dict:
    api = NCentralApi(context["ncentral"], fetch_impl=fetch_impl, sleep_impl=sleep_impl)
    scope = context["ncentral"]
    warnings: list[str] = []
    customer_id = _coerce_int(scope["customer_id"])
    org_unit_id = _coerce_int(scope["org_unit_id"])
    site_records_result = (
        api.list_customer_sites(customer_id)
        if customer_id and scope["org_unit_type"] == "customer"
        else {"count_collected": len(scope["site_ids"]), "items": [], "total": len(scope["site_ids"])}
    )
    site_records = site_records_result["items"]
    if scope["org_unit_type"] == "site" and scope["site_id"] is not None and not site_records:
        site_records = [
            {
                "siteId": int(scope["site_id"]),
                "siteName": scope["site_name"] or scope["org_unit_name"] or "",
                "customerId": customer_id or None,
                "soId": scope["service_org_id"] or None,
            }
        ]
        site_records_result = {
            "count_collected": 1,
            "items": site_records,
            "total": 1,
        }

    devices = api.list_org_unit_devices(org_unit_id)
    active_issues = api.list_active_issues(org_unit_id)
    site_issue_details = _fetch_site_issue_details(api, site_records, context, warnings)
    org_unit_custom_properties = api.get_org_unit_custom_properties(org_unit_id)
    device_property_ids = _select_device_ids_for_property_enrichment(
        context,
        devices["items"],
        active_issues["items"],
        warnings,
    )
    device_custom_properties = _fetch_device_custom_properties(api, device_property_ids, context, warnings)

    return {
        "datasource": "ncentral",
        "dataset": "ncentral_snapshot",
        "collection_path": "fleet script",
        "customer_id": context["customer_id"],
        "customer_name": context["customer_name"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period_label": context["period"]["label"],
        "generated_at": context["generated_at"],
        "metadata": {
            "base_url": context["ncentral"]["base_url"],
            "collected_at_utc": context["generated_at"],
            "scope_note": "Customer-scoped N-central snapshot for Fleet reporting.",
            "source_scope": {
                "service_org_id": context["ncentral"]["service_org_id"],
                "customer_id": context["ncentral"]["customer_id"],
                "customer_name": context["ncentral"]["customer_name"],
                "org_unit_id": context["ncentral"]["org_unit_id"],
                "org_unit_name": context["ncentral"]["org_unit_name"],
                "org_unit_type": context["ncentral"]["org_unit_type"],
                "site_ids": context["ncentral"]["site_ids"],
                "site_names": context["ncentral"]["site_names"],
            },
        },
        "inventory": {
            "sites": {
                "count_collected": site_records_result["count_collected"],
                "items": site_records,
                "total": site_records_result["total"],
            },
            "devices": devices,
            "org_unit_custom_properties": {
                "count_collected": len(org_unit_custom_properties),
                "items": org_unit_custom_properties,
                "total": len(org_unit_custom_properties),
            },
            "device_custom_properties": {
                "count_collected": len(device_custom_properties),
                "items": device_custom_properties,
                "total": len(device_custom_properties),
            },
        },
        "active_issues": {
            "count_collected": active_issues["count_collected"],
            "items": active_issues["items"],
            "total": active_issues["total"],
            "by_site": {
                site_id: {
                    "count_collected": details["count_collected"],
                    "items": details["items"],
                    "total": details["total"],
                }
                for site_id, details in site_issue_details.items()
            },
        },
        "warnings": warnings,
        "collection_log": api.get_diagnostics(),
    }


def _normalize_site_record(site: dict) -> dict:
    return {
        "site_id": _coerce_text(site.get("siteId") or site.get("id")),
        "site_name": _coerce_text(site.get("siteName") or site.get("longName") or site.get("name") or site.get("displayName")),
        "customer_id": _coerce_text(site.get("customerId")),
        "service_org_id": _coerce_text(site.get("soId") or site.get("serviceOrgId")),
    }


def _normalize_property_record(record: dict) -> dict:
    return {
        "name": _coerce_text(record.get("propertyName") or record.get("name") or record.get("key")),
        "value": record.get("value"),
    }


def _normalize_device_record(device: dict, site_index: dict[str, dict], property_index: dict[str, list[dict]], stale_cutoff_iso: str) -> dict:
    device_id = _coerce_text(device.get("deviceId") or device.get("id"))
    site_id = _coerce_text(device.get("siteId") or device.get("orgUnitId"))
    last_checkin = _to_iso(device.get("lastApplianceCheckinTime") or device.get("lastCheckinTime") or device.get("lastSeen"))
    is_stale = bool(last_checkin and last_checkin < stale_cutoff_iso)
    properties = [_normalize_property_record(entry) for entry in property_index.get(device_id, [])]
    return {
        "device_id": device_id,
        "uri": _coerce_text(device.get("uri")),
        "device_name": _coerce_text(device.get("longName") or device.get("deviceName") or device.get("name") or device.get("displayName")) or "unknown-device",
        "description": _coerce_text(device.get("description")),
        "device_class": _coerce_text(device.get("deviceClass") or device.get("className") or device.get("type")),
        "supported_os": _coerce_text(device.get("supportedOs") or device.get("operatingSystem") or device.get("os")),
        "customer_id": _coerce_text(device.get("customerId")),
        "service_org_id": _coerce_text(device.get("soId") or device.get("serviceOrgId")),
        "site_id": site_id,
        "site_name": site_index.get(site_id, {}).get("site_name") or _coerce_text(device.get("siteName")) or "Unknown Site",
        "last_logged_in_user": _coerce_text(device.get("lastLoggedInUser")),
        "still_logged_in": bool(device.get("stillLoggedIn")) if device.get("stillLoggedIn") is not None else None,
        "last_checkin_at": last_checkin,
        "is_stale_checkin": is_stale,
        "custom_property_count": len(properties),
        "custom_properties": properties,
        "raw": device,
    }


def _normalize_issue_record(issue: dict, device_index: dict[str, dict], site_index: dict[str, dict], default_site_id: str = "") -> dict:
    device_id = _coerce_text(issue.get("deviceId"))
    device = device_index.get(device_id, {})
    site_id = _pick_site_id(issue, default_site_id=default_site_id or device.get("site_id", ""))
    notification_state = _normalize_issue_state(issue.get("notificationState") or issue.get("status"))
    title = _coerce_text(
        issue.get("message")
        or issue.get("serviceName")
        or issue.get("serviceType")
        or issue.get("uri"),
    )
    return {
        "issue_key": _issue_key(issue),
        "device_id": device_id,
        "device_name": device.get("device_name") or _coerce_text(issue.get("deviceName")) or "unknown-device",
        "customer_id": _pick_customer_id(issue, default_customer_id=device.get("customer_id", "")),
        "site_id": site_id,
        "site_name": site_index.get(site_id, {}).get("site_name") or device.get("site_name") or "Unknown Site",
        "service_id": _coerce_text(issue.get("serviceId")),
        "service_name": _coerce_text(issue.get("serviceName")),
        "service_type": _coerce_text(issue.get("serviceType")),
        "service_item_id": _coerce_text(issue.get("serviceItemId")),
        "task_id": _coerce_text(issue.get("taskId")),
        "notification_state": notification_state,
        "title": title or "Unnamed issue",
        "uri": _coerce_text(issue.get("uri")),
        "raw": issue,
    }


def _dedupe_issues(root_issues: list[dict], site_issues: dict[str, dict], device_index: dict[str, dict], site_index: dict[str, dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for issue in root_issues:
        normalized = _normalize_issue_record(issue, device_index, site_index)
        deduped[normalized["issue_key"]] = normalized
    for site_id, details in site_issues.items():
        for issue in details.get("items") or []:
            normalized = _normalize_issue_record(issue, device_index, site_index, default_site_id=site_id)
            deduped[normalized["issue_key"]] = normalized
    return sorted(
        deduped.values(),
        key=lambda entry: (_issue_sort_rank(entry["notification_state"]), entry["site_name"], entry["device_name"], entry["title"]),
    )


def normalize_ncentral_snapshot(context: dict, snapshot: dict) -> dict:
    raw_sites = snapshot.get("inventory", {}).get("sites", {}).get("items") or []
    raw_devices = snapshot.get("inventory", {}).get("devices", {}).get("items") or []
    raw_org_properties = snapshot.get("inventory", {}).get("org_unit_custom_properties", {}).get("items") or []
    raw_device_property_rows = snapshot.get("inventory", {}).get("device_custom_properties", {}).get("items") or []
    raw_root_issues = snapshot.get("active_issues", {}).get("items") or []
    raw_site_issue_details = snapshot.get("active_issues", {}).get("by_site") or {}

    normalized_sites = [_normalize_site_record(site) for site in raw_sites]
    site_index = {site["site_id"]: site for site in normalized_sites if site["site_id"]}
    property_index = {
        _coerce_text(row.get("device_id")): row.get("properties") or []
        for row in raw_device_property_rows
    }
    stale_cutoff_iso = (
        datetime.fromisoformat(context["generated_at"].replace("Z", "+00:00")) - timedelta(hours=context["ncentral"]["stale_checkin_hours"])
    ).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    normalized_devices = [
        _normalize_device_record(device, site_index, property_index, stale_cutoff_iso)
        for device in raw_devices
    ]
    device_index = {device["device_id"]: device for device in normalized_devices if device["device_id"]}
    normalized_issues = _dedupe_issues(raw_root_issues, raw_site_issue_details, device_index, site_index)

    issue_counts_by_device = Counter(issue["device_id"] for issue in normalized_issues if issue["device_id"])
    issue_counts_by_site = Counter(issue["site_id"] for issue in normalized_issues if issue["site_id"])
    state_counts = Counter(issue["notification_state"] for issue in normalized_issues)
    class_counts = Counter(device["device_class"] or "Unknown" for device in normalized_devices)
    os_counts = Counter(device["supported_os"] or "Unknown" for device in normalized_devices)
    service_counts = Counter(issue["service_name"] or issue["service_type"] or "Unspecified service" for issue in normalized_issues)
    impacted_device_ids = {device_id for device_id, count in issue_counts_by_device.items() if count > 0}
    impacted_site_ids = {site_id for site_id, count in issue_counts_by_site.items() if count > 0}
    org_properties = [_normalize_property_record(record) for record in raw_org_properties]
    devices_with_properties = len([device for device in normalized_devices if device["custom_property_count"] > 0])

    return {
        "datasource": "ncentral",
        "dataset": "ncentral_normalized",
        "collection_path": "fleet script",
        "customer_name": snapshot.get("metadata", {}).get("source_scope", {}).get("customer_name") or context["customer_name"],
        "customer_id": _coerce_text(snapshot.get("metadata", {}).get("source_scope", {}).get("customer_id")),
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "generated_at": context["generated_at"],
        "scope": snapshot.get("metadata", {}).get("source_scope", {}),
        "sites": normalized_sites,
        "devices": normalized_devices,
        "issues": normalized_issues,
        "org_unit_custom_properties": org_properties,
        "state_counts": dict(state_counts),
        "device_class_counts": dict(class_counts),
        "operating_system_counts": dict(os_counts),
        "service_counts": dict(service_counts),
        "totals": {
            "sites": len(normalized_sites),
            "devices": len(normalized_devices),
            "impacted_devices": len(impacted_device_ids),
            "healthy_devices": len(normalized_devices) - len(impacted_device_ids),
            "stale_checkin_devices": len([device for device in normalized_devices if device["is_stale_checkin"]]),
            "active_issues": len(normalized_issues),
            "impacted_sites": len(impacted_site_ids),
            "org_unit_custom_properties": len(org_properties),
            "device_property_devices_collected": len(raw_device_property_rows),
            "devices_with_custom_properties": devices_with_properties,
        },
        "warnings": snapshot.get("warnings", []),
        "collection_log": snapshot.get("collection_log", {}),
    }


def build_ncentral_inventory_summary(context: dict, normalized: dict) -> dict:
    top_sites = []
    devices_by_site = Counter(device["site_name"] for device in normalized["devices"])
    for site_name, count in devices_by_site.most_common(10):
        top_sites.append({"site_name": site_name, "devices": count})
    device_classes = [
        {"device_class": name, "count": count}
        for name, count in sorted(normalized["device_class_counts"].items(), key=lambda entry: (-entry[1], entry[0]))
    ]
    operating_systems = [
        {"supported_os": name, "count": count}
        for name, count in sorted(normalized["operating_system_counts"].items(), key=lambda entry: (-entry[1], entry[0]))
    ]
    totals = normalized["totals"]
    notable_points = []
    if totals["stale_checkin_devices"]:
        notable_points.append(f"{totals['stale_checkin_devices']} devices have stale N-central check-in timestamps.")
    if totals["impacted_devices"]:
        notable_points.append(f"{totals['impacted_devices']} devices currently have active N-central issues.")
    if not notable_points:
        notable_points.append("No stale device check-ins or active device issues were found in scope.")
    return {
        "datasource": "ncentral",
        "dataset": "ncentral_inventory_summary",
        "collection_path": "fleet script",
        "customer_name": normalized["customer_name"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "summary_kpis": {
            "sites": totals["sites"],
            "devices": totals["devices"],
            "healthy_devices": totals["healthy_devices"],
            "impacted_devices": totals["impacted_devices"],
            "active_issues": totals["active_issues"],
            "stale_checkin_devices": totals["stale_checkin_devices"],
        },
        "device_class_breakdown": device_classes,
        "operating_system_breakdown": operating_systems,
        "top_sites_by_device_count": top_sites,
        "notable_points": notable_points,
    }


def build_ncentral_issue_summary(context: dict, normalized: dict) -> dict:
    site_issue_counts = Counter(issue["site_name"] for issue in normalized["issues"])
    service_counts = [
        {"service_name": name, "count": count}
        for name, count in sorted(normalized["service_counts"].items(), key=lambda entry: (-entry[1], entry[0]))
    ]
    state_counts = [
        {"notification_state": name, "count": count}
        for name, count in sorted(normalized["state_counts"].items(), key=lambda entry: (_issue_sort_rank(entry[0]), -entry[1], entry[0]))
    ]
    hotspots = []
    for site_name, count in site_issue_counts.most_common(10):
        site_devices = len({device["device_id"] for device in normalized["devices"] if device["site_name"] == site_name})
        hotspots.append(
            {
                "site_name": site_name,
                "active_issues": count,
                "devices": site_devices,
                "issues_per_100_devices": _round_value((count / max(site_devices, 1)) * 100, 2),
            }
        )
    examples = [
        {
            "site_name": issue["site_name"],
            "device_name": issue["device_name"],
            "notification_state": issue["notification_state"],
            "service_name": issue["service_name"] or issue["service_type"],
            "title": issue["title"],
        }
        for issue in normalized["issues"][:10]
    ]
    notable_points = []
    if normalized["totals"]["active_issues"]:
        critical_count = normalized["state_counts"].get("critical", 0)
        if critical_count:
            notable_points.append(f"{critical_count} active issues are in a critical state.")
        notable_points.append(f"{normalized['totals']['impacted_sites']} sites currently have one or more active issues.")
    else:
        notable_points.append("No active N-central issues were collected for the scoped customer.")
    return {
        "datasource": "ncentral",
        "dataset": "ncentral_issue_summary",
        "collection_path": "fleet script",
        "customer_name": normalized["customer_name"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "summary_kpis": {
            "active_issues": normalized["totals"]["active_issues"],
            "impacted_devices": normalized["totals"]["impacted_devices"],
            "impacted_sites": normalized["totals"]["impacted_sites"],
            "critical_issues": normalized["state_counts"].get("critical", 0),
            "warning_issues": normalized["state_counts"].get("warning", 0),
        },
        "notification_state_breakdown": state_counts,
        "service_breakdown": service_counts[:10],
        "site_hotspots": hotspots,
        "issue_examples": examples,
        "notable_points": notable_points,
    }


def build_ncentral_site_rollup(context: dict, normalized: dict) -> dict:
    issue_counts = Counter(issue["site_id"] for issue in normalized["issues"])
    impacted_device_ids_by_site: dict[str, set[str]] = defaultdict(set)
    for issue in normalized["issues"]:
        if issue["site_id"] and issue["device_id"]:
            impacted_device_ids_by_site[issue["site_id"]].add(issue["device_id"])
    devices_by_site: dict[str, list[dict]] = defaultdict(list)
    for device in normalized["devices"]:
        devices_by_site[device["site_id"]].append(device)
    rows = []
    for site in normalized["sites"]:
        site_id = site["site_id"]
        site_devices = devices_by_site.get(site_id, [])
        stale_count = len([device for device in site_devices if device["is_stale_checkin"]])
        impacted_count = len(impacted_device_ids_by_site.get(site_id, set()))
        rows.append(
            {
                "site_id": site_id,
                "site_name": site["site_name"] or "Unknown Site",
                "devices": len(site_devices),
                "impacted_devices": impacted_count,
                "active_issues": issue_counts.get(site_id, 0),
                "stale_checkin_devices": stale_count,
                "issue_density_per_100_devices": _round_value((issue_counts.get(site_id, 0) / max(len(site_devices), 1)) * 100, 2),
            }
        )
    rows.sort(key=lambda row: (-row["active_issues"], -row["stale_checkin_devices"], row["site_name"]))
    return {
        "datasource": "ncentral",
        "dataset": "ncentral_site_rollup",
        "collection_path": "fleet script",
        "customer_name": normalized["customer_name"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "rows": rows,
    }


def build_ncentral_device_health(context: dict, normalized: dict) -> dict:
    issues_by_device: dict[str, list[dict]] = defaultdict(list)
    for issue in normalized["issues"]:
        issues_by_device[issue["device_id"]].append(issue)
    rows = []
    for device in normalized["devices"]:
        device_issues = sorted(
            issues_by_device.get(device["device_id"], []),
            key=lambda entry: (_issue_sort_rank(entry["notification_state"]), entry["title"]),
        )
        rows.append(
            {
                "device_id": device["device_id"],
                "device_name": device["device_name"],
                "site_name": device["site_name"],
                "device_class": device["device_class"],
                "supported_os": device["supported_os"],
                "last_checkin_at": device["last_checkin_at"],
                "is_stale_checkin": device["is_stale_checkin"],
                "issue_count": len(device_issues),
                "highest_issue_state": device_issues[0]["notification_state"] if device_issues else "healthy",
                "top_issue_titles": [issue["title"] for issue in device_issues[:3]],
                "custom_property_count": device["custom_property_count"],
            }
        )
    rows.sort(
        key=lambda row: (
            row["issue_count"] == 0,
            _issue_sort_rank(row["highest_issue_state"]),
            -row["issue_count"],
            row["device_name"],
        ),
    )
    return {
        "datasource": "ncentral",
        "dataset": "ncentral_device_health",
        "collection_path": "fleet script",
        "customer_name": normalized["customer_name"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "impacted_device_count": normalized["totals"]["impacted_devices"],
        "healthy_device_count": normalized["totals"]["healthy_devices"],
        "rows": rows[:50],
    }


def build_ncentral_custom_property_summary(context: dict, normalized: dict) -> dict:
    property_name_counts = Counter()
    for device in normalized["devices"]:
        for prop in device["custom_properties"]:
            property_name_counts[prop["name"] or "Unnamed Property"] += 1
    coverage_rows = [
        {
            "property_name": name,
            "devices_present": count,
            "coverage_percent": _ratio_to_percent(count, normalized["totals"]["device_property_devices_collected"]),
        }
        for name, count in sorted(property_name_counts.items(), key=lambda entry: (-entry[1], entry[0]))
    ]
    return {
        "datasource": "ncentral",
        "dataset": "ncentral_custom_property_summary",
        "collection_path": "fleet script",
        "customer_name": normalized["customer_name"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "org_unit_properties": normalized["org_unit_custom_properties"],
        "org_unit_property_count": normalized["totals"]["org_unit_custom_properties"],
        "device_property_devices_collected": normalized["totals"]["device_property_devices_collected"],
        "devices_with_custom_properties": normalized["totals"]["devices_with_custom_properties"],
        "device_property_coverage_percent": _ratio_to_percent(
            normalized["totals"]["devices_with_custom_properties"],
            normalized["totals"]["device_property_devices_collected"],
        ),
        "top_device_property_presence": coverage_rows[:25],
    }


def build_ncentral_scope_summary(context: dict, snapshot: dict, normalized: dict) -> dict:
    scope = normalized["scope"]
    return {
        "datasource": "ncentral",
        "dataset": "ncentral_scope_summary",
        "collection_path": "fleet script",
        "customer_name": normalized["customer_name"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "source_scope": scope,
        "sites_in_scope": normalized["totals"]["sites"],
        "devices_in_scope": normalized["totals"]["devices"],
        "collection_warnings": normalized.get("warnings", []),
        "collection_log": snapshot.get("collection_log", {}),
    }


def build_ncentral_artifacts(context: dict, snapshot: dict, normalized: dict) -> dict:
    inventory_summary = build_ncentral_inventory_summary(context, normalized)
    issue_summary = build_ncentral_issue_summary(context, normalized)
    site_rollup = build_ncentral_site_rollup(context, normalized)
    device_health = build_ncentral_device_health(context, normalized)
    custom_property_summary = build_ncentral_custom_property_summary(context, normalized)
    scope_summary = build_ncentral_scope_summary(context, snapshot, normalized)
    bundle = {
        "datasource": "ncentral",
        "dataset": "ncentral_report_bundle",
        "collection_path": "fleet script",
        "customer_name": normalized["customer_name"],
        "customer_id": normalized["customer_id"],
        "report_family": context["report_family"],
        "template_key": context["template_key"],
        "period": context["period"],
        "generated_at": context["generated_at"],
        "sections": {
            "source_inventory_summary": {
                "sites": snapshot["inventory"]["sites"]["count_collected"],
                "devices": snapshot["inventory"]["devices"]["count_collected"],
                "org_unit_custom_properties": snapshot["inventory"]["org_unit_custom_properties"]["count_collected"],
                "device_custom_properties": snapshot["inventory"]["device_custom_properties"]["count_collected"],
                "active_issues": snapshot["active_issues"]["count_collected"],
            },
            "inventory_summary": inventory_summary,
            "issue_summary": issue_summary,
            "site_rollup": site_rollup,
            "device_health": device_health,
            "custom_property_summary": custom_property_summary,
            "scope_summary": scope_summary,
        },
        "warnings": normalized.get("warnings", []),
    }
    return {
        "inventory_summary": inventory_summary,
        "issue_summary": issue_summary,
        "site_rollup": site_rollup,
        "device_health": device_health,
        "custom_property_summary": custom_property_summary,
        "scope_summary": scope_summary,
        "bundle": bundle,
    }


def run_ncentral_pipeline(context: dict, fetch_impl=None, sleep_impl=None) -> dict:
    snapshot = collect_ncentral_snapshot(context, fetch_impl=fetch_impl, sleep_impl=sleep_impl)
    normalized = normalize_ncentral_snapshot(context, snapshot)
    artifacts = build_ncentral_artifacts(context, snapshot, normalized)
    return {
        "snapshot": snapshot,
        "normalized": normalized,
        **artifacts,
    }
