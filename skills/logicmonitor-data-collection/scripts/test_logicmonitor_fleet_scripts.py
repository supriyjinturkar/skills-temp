from __future__ import annotations

import json
import os
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

from lm_context import parse_cli_args, resolve_logicmonitor_context, resolve_logicmonitor_lookup_context
from lm_io import resolve_run_paths
from lm_pipeline import resolve_logicmonitor_scope_by_company, run_logicmonitor_pipeline


def tenant_fixtures():
    return {
        "groups": {
            "items": [
                {"id": 101, "name": "Customer A", "fullPath": "Nexon/Customer A"},
                {"id": 103, "name": "Servers", "fullPath": "Nexon/Customer A/Servers"},
                {"id": 104, "name": "Network", "fullPath": "Nexon/Customer A/Network"},
                {"id": 102, "name": "Shared", "fullPath": "Nexon/Shared"},
            ],
            "total": 4,
        },
        "devices": {
            "items": [
                {
                    "id": 1,
                    "displayName": "cust-a-fw-01",
                    "hostStatus": "up",
                    "currentAlertStatus": "warning",
                    "systemProperties": [{"name": "system.groups", "value": "Nexon/Customer A"}],
                },
                {
                    "id": 2,
                    "displayName": "cust-a-sql-01",
                    "hostStatus": "down",
                    "currentAlertStatus": "critical",
                    "systemProperties": [{"name": "system.groups", "value": "Nexon/Customer A"}],
                },
            ],
            "total": 2,
        },
        "open_alerts": {
            "items": [
                {
                    "id": 501,
                    "deviceId": 2,
                    "deviceDisplayName": "cust-a-sql-01",
                    "severity": "critical",
                    "startEpoch": 1719792000,
                },
            ],
            "total": 1,
        },
        "websites": {
            "items": [{"id": 901, "name": "cust-a-portal", "domain": "a.example.com"}],
            "total": 1,
        },
        "website_groups": {
            "items": [
                {"id": 201, "name": "Customer A", "fullPath": "Web/Customer A"},
                {"id": 202, "name": "Shared", "fullPath": "Web/Shared"},
            ],
            "total": 2,
        },
    }


def build_raw_context():
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
            "logicmonitor": {
                "tenant_id": "nexon-logicmonitor",
                "account_name": "nexon",
                "auth_mode": "bearer",
                "group_identifiers": ["Nexon/Customer A"],
                "site_groups": ["Customer A"],
                "root_device_group_id": 101,
                "root_website_group_id": 201,
            },
        },
    }


def create_fetch_mock():
    fixture = tenant_fixtures()

    def fetch_impl(method, url, headers, body):
        parsed = Path(urlparse(url).path)
        path_value = str(parsed)
        query = dict(parse_qsl(urlparse(url).query))
        if path_value.endswith("/device/groups"):
            return 200, {}, json.dumps(fixture["groups"])
        if path_value.endswith("/device/groups/101/devices"):
            return 200, {}, json.dumps(fixture["devices"])
        if path_value.endswith("/device/groups/103/devices"):
            return 200, {}, json.dumps({"items": [], "total": 0})
        if path_value.endswith("/device/groups/104/devices"):
            return 200, {}, json.dumps({"items": [], "total": 0})
        if path_value.endswith("/device/groups/101/alerts"):
            if "cleared:true" in query.get("filter", ""):
                return 200, {}, json.dumps({"items": [], "total": 0})
            return 200, {}, json.dumps(fixture["open_alerts"])
        if path_value.endswith("/device/groups/103/alerts") or path_value.endswith("/device/groups/104/alerts"):
            return 200, {}, json.dumps({"items": [], "total": 0})
        if path_value.endswith("/website/groups"):
            return 200, {}, json.dumps(fixture["website_groups"])
        if path_value.endswith("/website/groups/201/websites"):
            return 200, {}, json.dumps(fixture["websites"])
        if path_value.endswith("/device/groups/101"):
            return 200, {}, json.dumps({"id": 101, "name": "Customer A", "fullPath": "Nexon/Customer A"})
        if path_value.endswith("/device/groups/103"):
            return 200, {}, json.dumps({"id": 103, "name": "Servers", "fullPath": "Nexon/Customer A/Servers"})
        if path_value.endswith("/device/groups/104"):
            return 200, {}, json.dumps({"id": 104, "name": "Network", "fullPath": "Nexon/Customer A/Network"})
        if path_value.endswith("/device/devices/1"):
            return 200, {}, json.dumps({**fixture["devices"]["items"][0], "detail": True})
        if path_value.endswith("/device/devices/2"):
            return 200, {}, json.dumps({**fixture["devices"]["items"][1], "detail": True})
        if path_value.endswith("/website/groups/201"):
            return 200, {}, json.dumps({"id": 201, "name": "Customer A Web", "fullPath": "Web/Customer A"})
        if path_value.endswith("/website/websites/901"):
            return 200, {}, json.dumps({"id": 901, "name": "cust-a-portal", "domain": "a.example.com", "status": "up"})
        raise AssertionError(f"Unhandled URL {url}")

    from urllib.parse import parse_qsl, urlparse  # local import for test isolation

    return fetch_impl


class LogicMonitorFleetScriptsTest(unittest.TestCase):
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

    def test_context_requires_customer_scope(self):
        with self.assertRaisesRegex(ValueError, "group_identifiers or root_device_group_id"):
            resolve_logicmonitor_context(
                {
                    "customer_id": "x",
                    "customer_name": "X",
                    "period": {"start": "2026-07-01T00:00:00Z", "end": "2026-07-02T00:00:00Z"},
                    "source_scope": {"logicmonitor": {"account_name": "nexon"}},
                },
                env={"LOGICMONITOR_BEARER_TOKEN": "token"},
            )

    def test_pipeline_produces_scoped_artifacts(self):
        context = resolve_logicmonitor_context(
            build_raw_context(),
            env={"LOGICMONITOR_BEARER_TOKEN": "token"},
            now=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        )
        result = run_logicmonitor_pipeline(context, fetch_impl=create_fetch_mock())
        self.assertEqual(result["snapshot"]["dataset"], "logicmonitor_snapshot")
        self.assertEqual(result["snapshot"]["inventory"]["devices"]["count_collected"], 2)
        self.assertEqual(result["observability"]["dataset"], "observability")
        self.assertEqual(result["observability"]["totals"]["devices"], 2)
        self.assertEqual(result["alert_trends"]["alert_counts_opened"], 1)
        self.assertEqual(result["alert_trends"]["alert_counts_closed"], 0)
        self.assertEqual(result["resource_health"]["critical_devices"], 1)
        self.assertEqual(result["bundle"]["dataset"], "logicmonitor_report_bundle")
        self.assertEqual(result["bundle"]["sections"]["source_inventory_summary"]["devices"], 2)

    def test_company_name_resolver_builds_descendant_group_scope(self):
        lookup_context = resolve_logicmonitor_lookup_context(
            {
                "company_name": "Customer A",
                "customer_name": "Customer A",
                "period": {"start": "2026-07-01T00:00:00Z", "end": "2026-07-31T23:59:59Z"},
                "source_scope": {
                    "logicmonitor": {
                        "tenant_id": "nexon-logicmonitor",
                        "account_name": "nexon",
                        "auth_mode": "bearer",
                    },
                },
            },
            env={"LOGICMONITOR_BEARER_TOKEN": "token"},
        )
        resolution = resolve_logicmonitor_scope_by_company(lookup_context, fetch_impl=create_fetch_mock())
        self.assertEqual(resolution["match_confidence"], "high")
        self.assertEqual(resolution["resolved_scope"]["logicmonitor"]["root_device_group_id"], 101)
        self.assertEqual(resolution["resolved_scope"]["logicmonitor"]["root_website_group_id"], 201)
        self.assertEqual(
            resolution["resolved_scope"]["logicmonitor"]["group_identifiers"],
            ["Nexon/Customer A", "Nexon/Customer A/Network", "Nexon/Customer A/Servers"],
        )
        self.assertEqual(resolution["resolved_scope"]["logicmonitor"]["site_groups"], ["Customer A"])

    def test_cli_steps_write_expected_files(self):
        context = resolve_logicmonitor_context(
            build_raw_context(),
            env={"LOGICMONITOR_BEARER_TOKEN": "token"},
            now=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        )
        pipeline = run_logicmonitor_pipeline(context, fetch_impl=create_fetch_mock())
        with tempfile.TemporaryDirectory(prefix="fleet-lm-scripts-") as root:
            root_path = Path(root)
            context_path = root_path / "customer_context.json"
            run_dir = root_path / "run"
            context_path.write_text(f"{json.dumps(build_raw_context(), indent=2)}\n", encoding="utf-8")
            run_paths = resolve_run_paths(run_dir)
            Path(run_paths["logicmonitor_snapshot_file"]).parent.mkdir(parents=True, exist_ok=True)
            Path(run_paths["logicmonitor_snapshot_file"]).write_text(
                f"{json.dumps(pipeline['snapshot'], indent=2)}\n",
                encoding="utf-8",
            )
            env = {**os.environ, "LOGICMONITOR_BEARER_TOKEN": "token"}
            normalize = subprocess.run(
                [sys.executable, str(CURRENT_DIR / "normalize_logicmonitor_collection.py"), "--context", str(context_path), "--run-dir", str(run_dir)],
                cwd=root,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(normalize.returncode, 0, normalize.stderr)
            bundle = subprocess.run(
                [sys.executable, str(CURRENT_DIR / "build_logicmonitor_report_bundle.py"), "--context", str(context_path), "--run-dir", str(run_dir)],
                cwd=root,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(bundle.returncode, 0, bundle.stderr)
            observability = json.loads(Path(run_paths["observability_file"]).read_text(encoding="utf-8"))
            report_bundle = json.loads(Path(run_paths["logicmonitor_bundle_file"]).read_text(encoding="utf-8"))
            self.assertEqual(observability["dataset"], "observability")
            self.assertEqual(report_bundle["dataset"], "logicmonitor_report_bundle")

    def test_run_path_layout(self):
        paths = resolve_run_paths("/tmp/customer-run")
        self.assertEqual(paths["logicmonitor_snapshot_file"], "/tmp/customer-run/source_snapshots/logicmonitor.json")
        self.assertEqual(paths["logicmonitor_bundle_file"], "/tmp/customer-run/normalized/logicmonitor_report_bundle.json")


if __name__ == "__main__":
    unittest.main()
