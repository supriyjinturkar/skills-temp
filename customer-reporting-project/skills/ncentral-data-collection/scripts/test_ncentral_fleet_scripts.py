from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
LIB_DIR = CURRENT_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from nc_context import parse_cli_args, resolve_ncentral_context, resolve_ncentral_lookup_context
from nc_io import resolve_run_paths
from nc_pipeline import resolve_ncentral_scope_by_company, run_ncentral_pipeline


def build_lookup_context():
    return {
        "company_name": "Customer A",
        "customer_name": "Customer A",
        "period": {
            "start": "2026-07-01T00:00:00Z",
            "end": "2026-07-31T23:59:59Z",
        },
        "source_scope": {
            "ncentral": {
                "base_url": "https://ncentral.example.com",
                "user_api_token": "user-api-token",
                "service_org_id": 1001,
            }
        },
    }


def build_direct_context():
    return {
        "customer_id": "customer-a",
        "customer_name": "Customer A",
        "report_family": "monthly-service-review",
        "template_key": "operations-v1",
        "period": {
            "start": "2026-07-01T00:00:00Z",
            "end": "2026-07-31T23:59:59Z",
            "label": "July 2026",
        },
        "source_scope": {
            "ncentral": {
                "base_url": "https://ncentral.example.com",
                "user_api_token": "user-api-token",
                "service_org_id": 1001,
                "customer_id": 2001,
                "customer_name": "Customer A",
                "org_unit_id": 2001,
                "org_unit_name": "Customer A",
                "org_unit_type": "customer",
                "site_ids": [3001, 3002],
                "site_names": ["Customer A - HQ", "Customer A - Branch"],
                "max_device_custom_property_devices": 10,
            }
        },
    }


def create_fetch_mock(enable_resilience: bool):
    state = {
        "devices_401_emitted": False,
        "root_429_emitted": False,
        "issued_tokens": [],
    }

    def paged(items):
        return {
            "data": items,
            "pageNumber": 1,
            "pageSize": 200,
            "totalItems": len(items),
            "totalPages": 1,
        }

    customers = [
        {
            "customerId": 2001,
            "customerName": "Customer A",
            "soId": 1001,
        },
        {
            "customerId": 2002,
            "customerName": "Shared Services",
            "soId": 1001,
        },
    ]
    sites = [
        {
            "siteId": 3001,
            "siteName": "Customer A - HQ",
            "customerId": 2001,
            "soId": 1001,
        },
        {
            "siteId": 3002,
            "siteName": "Customer A - Branch",
            "customerId": 2001,
            "soId": 1001,
        },
    ]
    devices = [
        {
            "deviceId": 4001,
            "longName": "cust-a-hq-dc-01",
            "deviceClass": "Server",
            "supportedOs": "Windows Server",
            "customerId": 2001,
            "orgUnitId": 3001,
            "lastApplianceCheckinTime": "2026-08-01T08:45:00Z",
            "lastLoggedInUser": "svc-admin",
        },
        {
            "deviceId": 4002,
            "longName": "cust-a-branch-fw-01",
            "deviceClass": "Firewall",
            "supportedOs": "Appliance OS",
            "customerId": 2001,
            "orgUnitId": 3002,
            "lastApplianceCheckinTime": "2026-07-27T08:45:00Z",
        },
        {
            "deviceId": 4003,
            "longName": "cust-a-hq-ws-01",
            "deviceClass": "Workstation",
            "supportedOs": "Windows 11",
            "customerId": 2001,
            "orgUnitId": 3001,
            "lastApplianceCheckinTime": "2026-08-01T09:00:00Z",
        },
    ]
    root_issues = [
        {
            "deviceId": 4001,
            "siteId": 3001,
            "serviceId": 5001,
            "serviceName": "Disk Free Space",
            "serviceType": "Monitoring",
            "taskId": 6001,
            "notificationState": "Critical",
            "message": "Disk free space below threshold",
            "uri": "/api/active-issues/1",
        },
        {
            "deviceId": 4002,
            "siteId": 3002,
            "serviceId": 5002,
            "serviceName": "AV Signature Age",
            "serviceType": "Security",
            "taskId": 6002,
            "notificationState": "Warning",
            "message": "AV signature age approaching threshold",
            "uri": "/api/active-issues/2",
        },
    ]
    org_unit_properties = [
        {"propertyName": "Service Tier", "value": "Gold"},
        {"propertyName": "Region", "value": "APAC"},
    ]
    device_properties = {
        4001: [{"propertyName": "Environment", "value": "Production"}],
        4002: [{"propertyName": "Environment", "value": "Production"}],
        4003: [{"propertyName": "Environment", "value": "User"}],
    }

    def fetch_impl(method, url, headers, body):
        from urllib.parse import parse_qsl, urlparse

        parsed = urlparse(url)
        path = parsed.path
        query = dict(parse_qsl(parsed.query))
        auth = headers.get("Authorization", "")

        if path.endswith("/api/auth/authenticate"):
            state["issued_tokens"].append("access-1")
            return 200, {}, json.dumps(
                {
                    "accessToken": "access-1",
                    "refreshToken": "refresh-1",
                    "accessTokenExpiresIn": 900,
                    "refreshTokenExpiresIn": 3600,
                }
            )

        if path.endswith("/api/auth/refresh"):
            state["issued_tokens"].append("access-2")
            return 200, {}, json.dumps(
                {
                    "accessToken": "access-2",
                    "refreshToken": "refresh-2",
                    "accessTokenExpiresIn": 900,
                    "refreshTokenExpiresIn": 3600,
                }
            )

        if path.endswith("/api/service-orgs/1001/customers") or path.endswith("/api/customers"):
            return 200, {}, json.dumps(paged(customers))

        if path.endswith("/api/sites"):
            return 200, {}, json.dumps(paged(sites))

        if path.endswith("/api/customers/2001/sites"):
            return 200, {}, json.dumps(paged(sites))

        if path.endswith("/api/org-units/2001/devices"):
            if enable_resilience and auth == "Bearer access-1" and not state["devices_401_emitted"]:
                state["devices_401_emitted"] = True
                return 401, {}, json.dumps({"message": "token expired"})
            return 200, {}, json.dumps(paged(devices))

        if path.endswith("/api/org-units/2001/active-issues"):
            if enable_resilience and not state["root_429_emitted"]:
                state["root_429_emitted"] = True
                return 429, {"Retry-After": "0"}, json.dumps({"message": "rate limited"})
            return 200, {}, json.dumps(paged(root_issues))

        if path.endswith("/api/org-units/3001/active-issues"):
            return 200, {}, json.dumps(paged([root_issues[0]]))

        if path.endswith("/api/org-units/3002/active-issues"):
            return 200, {}, json.dumps(paged([root_issues[1]]))

        if path.endswith("/api/org-units/2001/custom-properties"):
            return 200, {}, json.dumps({"data": org_unit_properties})

        if path.endswith("/api/devices/4001/custom-properties"):
            return 200, {}, json.dumps({"data": device_properties[4001]})

        if path.endswith("/api/devices/4002/custom-properties"):
            return 200, {}, json.dumps({"data": device_properties[4002]})

        if path.endswith("/api/devices/4003/custom-properties"):
            return 200, {}, json.dumps({"data": device_properties[4003]})

        raise AssertionError(f"Unhandled URL {url} with query {query} and auth {auth}")

    return fetch_impl


class NCentralFleetScriptsTest(unittest.TestCase):
    def test_context_parser_preserves_flags(self):
        self.assertEqual(
            parse_cli_args(["--context", "ctx.json", "--run-dir", "run-a", "--snapshot", "snap.json", "--normalized", "norm.json", "--output", "out.json"]),
            {
                "context_path": "ctx.json",
                "run_dir": "run-a",
                "snapshot_path": "snap.json",
                "normalized_path": "norm.json",
                "output_path": "out.json",
            },
        )

    def test_context_requires_scope(self):
        with self.assertRaisesRegex(ValueError, "org_unit_id, customer_id, or site_id"):
            resolve_ncentral_context(
                {
                    "customer_id": "x",
                    "customer_name": "X",
                    "period": {"start": "2026-07-01T00:00:00Z", "end": "2026-07-02T00:00:00Z"},
                    "source_scope": {
                        "ncentral": {
                            "base_url": "https://ncentral.example.com",
                            "user_api_token": "token",
                        }
                    },
                },
            )

    def test_scope_resolver_builds_customer_scope(self):
        lookup_context = resolve_ncentral_lookup_context(build_lookup_context())
        resolution = resolve_ncentral_scope_by_company(lookup_context, fetch_impl=create_fetch_mock(enable_resilience=False), sleep_impl=lambda _delay: None)
        self.assertEqual(resolution["match_confidence"], "high")
        self.assertEqual(resolution["resolved_scope"]["ncentral"]["customer_id"], 2001)
        self.assertEqual(resolution["resolved_scope"]["ncentral"]["org_unit_id"], 2001)
        self.assertEqual(resolution["resolved_scope"]["ncentral"]["site_ids"], [3001, 3002])

    def test_pipeline_handles_refresh_and_rate_limit(self):
        context = resolve_ncentral_context(
            build_direct_context(),
            now=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        )
        result = run_ncentral_pipeline(
            context,
            fetch_impl=create_fetch_mock(enable_resilience=True),
            sleep_impl=lambda _delay: None,
        )
        self.assertEqual(result["snapshot"]["dataset"], "ncentral_snapshot")
        self.assertEqual(result["snapshot"]["inventory"]["devices"]["count_collected"], 3)
        self.assertEqual(result["snapshot"]["active_issues"]["count_collected"], 2)
        self.assertEqual(result["normalized"]["dataset"], "ncentral_normalized")
        self.assertEqual(result["normalized"]["totals"]["devices"], 3)
        self.assertEqual(result["normalized"]["totals"]["impacted_devices"], 2)
        self.assertEqual(result["inventory_summary"]["summary_kpis"]["stale_checkin_devices"], 1)
        self.assertEqual(result["issue_summary"]["summary_kpis"]["critical_issues"], 1)
        self.assertEqual(result["device_health"]["impacted_device_count"], 2)
        self.assertEqual(result["bundle"]["dataset"], "ncentral_report_bundle")
        self.assertEqual(result["bundle"]["sections"]["source_inventory_summary"]["devices"], 3)
        self.assertEqual(result["snapshot"]["collection_log"]["rate_limit_retries"], 1)
        self.assertEqual(result["snapshot"]["collection_log"]["auth_refreshes"], 1)

    def test_cli_steps_write_expected_files(self):
        context = resolve_ncentral_context(
            build_direct_context(),
            now=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        )
        pipeline = run_ncentral_pipeline(
            context,
            fetch_impl=create_fetch_mock(enable_resilience=False),
            sleep_impl=lambda _delay: None,
        )
        with tempfile.TemporaryDirectory(prefix="fleet-ncentral-scripts-") as root:
            root_path = Path(root)
            context_path = root_path / "customer_context.json"
            run_dir = root_path / "run"
            context_path.write_text(f"{json.dumps(build_direct_context(), indent=2)}\n", encoding="utf-8")
            run_paths = resolve_run_paths(run_dir)
            Path(run_paths["ncentral_snapshot_file"]).parent.mkdir(parents=True, exist_ok=True)
            Path(run_paths["ncentral_snapshot_file"]).write_text(
                f"{json.dumps(pipeline['snapshot'], indent=2)}\n",
                encoding="utf-8",
            )
            normalize = subprocess.run(
                [sys.executable, str(CURRENT_DIR / "normalize_ncentral_collection.py"), "--context", str(context_path), "--run-dir", str(run_dir)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(normalize.returncode, 0, normalize.stderr)
            bundle = subprocess.run(
                [sys.executable, str(CURRENT_DIR / "build_ncentral_report_bundle.py"), "--context", str(context_path), "--run-dir", str(run_dir)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bundle.returncode, 0, bundle.stderr)
            normalized = json.loads(Path(run_paths["ncentral_normalized_file"]).read_text(encoding="utf-8"))
            report_bundle = json.loads(Path(run_paths["ncentral_bundle_file"]).read_text(encoding="utf-8"))
            self.assertEqual(normalized["dataset"], "ncentral_normalized")
            self.assertEqual(report_bundle["dataset"], "ncentral_report_bundle")
            self.assertEqual(json.loads(Path(run_paths["ncentral_issue_summary_file"]).read_text(encoding="utf-8"))["dataset"], "ncentral_issue_summary")
            self.assertEqual(json.loads(Path(run_paths["ncentral_site_rollup_file"]).read_text(encoding="utf-8"))["dataset"], "ncentral_site_rollup")

    def test_run_path_layout(self):
        paths = resolve_run_paths("/tmp/customer-run")
        self.assertTrue(Path(paths["ncentral_snapshot_file"]).as_posix().endswith("/tmp/customer-run/source_snapshots/ncentral.json"))
        self.assertTrue(Path(paths["ncentral_bundle_file"]).as_posix().endswith("/tmp/customer-run/normalized/ncentral_report_bundle.json"))
        self.assertTrue(Path(paths["ncentral_device_health_file"]).as_posix().endswith("/tmp/customer-run/normalized/ncentral_device_health.json"))


if __name__ == "__main__":
    unittest.main()
