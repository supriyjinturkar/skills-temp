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
        "unmonitored_devices": {
            "items": [{"id": 301, "displayName": "cust-a-retired-01", "hostStatus": "unmonitored"}],
            "total": 1,
        },
        "smcheckpoints": {
            "items": [{"id": 5010, "name": "cust-a-checkpoint"}],
            "total": 1,
        },
        "collectors": {
            "items": [{"id": 6010, "description": "cust-a-collector"}],
            "total": 1,
        },
        "reports": {
            "items": [{"id": 7010, "name": "cust-a-monthly-report", "type": "dashboard"}],
            "total": 1,
        },
        "report_details": {
            "7010": {"id": 7010, "name": "cust-a-monthly-report", "type": "dashboard", "format": "html"},
        },
        "devicedatasources": {
            "1": {
                "items": [
                    {"id": 1001, "name": "Microsoft_Windows_CPU"},
                    {"id": 1002, "name": "WinOS"},
                    {"id": 1003, "name": "WinVolumeUsage-C"},
                    {"id": 1004, "name": "Ping"},
                    {"id": 1005, "name": "WinIf-Ethernet0"},
                ],
                "total": 5,
            },
            "2": {
                "items": [
                    {"id": 2001, "name": "Microsoft_Windows_CPU"},
                    {"id": 2002, "name": "WinOS"},
                    {"id": 2003, "name": "WinVolumeUsage-D"},
                    {"id": 2004, "name": "Ping"},
                    {"id": 2005, "name": "WinIf-Ethernet0"},
                ],
                "total": 5,
            },
        },
        "instances": {
            "1:1001": {"items": [{"id": 11001, "name": "CPU"}], "total": 1},
            "1:1002": {"items": [{"id": 11002, "name": "Memory"}], "total": 1},
            "1:1003": {"items": [{"id": 11003, "name": "C:"}], "total": 1},
            "1:1004": {"items": [{"id": 11004, "name": "Ping"}], "total": 1},
            "1:1005": {"items": [{"id": 11005, "name": "Ethernet0"}], "total": 1},
            "2:2001": {"items": [{"id": 21001, "name": "CPU"}], "total": 1},
            "2:2002": {"items": [{"id": 21002, "name": "Memory"}], "total": 1},
            "2:2003": {"items": [{"id": 21003, "name": "D:"}], "total": 1},
            "2:2004": {"items": [{"id": 21004, "name": "Ping"}], "total": 1},
            "2:2005": {"items": [{"id": 21005, "name": "Ethernet0"}], "total": 1},
        },
        "instance_data": {
            "1:1001:11001": {"datapoints": {"CPUBusyPercent": [3, 4, 5]}},
            "1:1002:11002": {"datapoints": {"MemoryUtilizationPercent": [22, 24, 26]}},
            "1:1003:11003": {"datapoints": {"PercentUsed": [51, 53, 55]}},
            "1:1004:11004": {"datapoints": {"PacketLossPercent": [0, 0.2, 0.1], "PingRTT": [12, 11, 13]}},
            "1:1005:11005": {"datapoints": {"ReceivedBitsPerSec": [1000000, 1200000], "OutboundBitsPerSec": [300000, 400000]}},
            "2:2001:21001": {"datapoints": {"CPUBusyPercent": [44, 45, 46]}},
            "2:2002:21002": {"datapoints": {"MemoryUtilizationPercent": [70, 72, 71]}},
            "2:2003:21003": {"datapoints": {"PercentUsed": [80, 82, 87]}},
            "2:2004:21004": {"datapoints": {"PacketLossPercent": [100, 100], "PingRTT": []}},
            "2:2005:21005": {"datapoints": {"ReceivedBitsPerSec": [90000, 110000], "OutboundBitsPerSec": [22000, 24000]}},
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
        from urllib.parse import parse_qsl, urlparse  # local import for test isolation
        path_value = urlparse(url).path
        query = dict(parse_qsl(urlparse(url).query))
        filter_val = query.get("filter", "")

        # --- Device groups ---
        if path_value.endswith("/device/groups"):
            # BFS subgroup traversal: parentId filter
            if "parentId:101" in filter_val:
                return 200, {}, json.dumps({"items": [
                    {"id": 103, "name": "Servers", "fullPath": "Nexon/Customer A/Servers", "numOfDirectDevices": 1},
                    {"id": 104, "name": "Network", "fullPath": "Nexon/Customer A/Network", "numOfDirectDevices": 1},
                ], "total": 2})
            if "parentId:103" in filter_val or "parentId:104" in filter_val:
                return 200, {}, json.dumps({"items": [], "total": 0})
            # Targeted resolver filters
            if 'name:"Customer A"' in filter_val or 'fullPath~"Customer A"' in filter_val or 'name~"Customer"' in filter_val:
                return 200, {}, json.dumps({"items": [
                    {"id": 101, "name": "Customer A", "fullPath": "Nexon/Customer A"},
                ], "total": 1})
            # Full tenant scan fallback
            return 200, {}, json.dumps(fixture["groups"])

        # --- Bulk device fetch via hostGroupIds filter (new P3 path) ---
        if path_value.endswith("/device/devices") and "hostGroupIds" in filter_val:
            return 200, {}, json.dumps(fixture["devices"])

        if path_value.endswith("/device/groups/101/devices"):
            return 200, {}, json.dumps(fixture["devices"])
        if path_value.endswith("/device/groups/103/devices"):
            return 200, {}, json.dumps({"items": [], "total": 0})
        if path_value.endswith("/device/groups/104/devices"):
            return 200, {}, json.dumps({"items": [], "total": 0})

        if path_value.endswith("/device/groups/101/alerts"):
            if "cleared:true" in filter_val:
                return 200, {}, json.dumps({"items": [], "total": 0})
            return 200, {}, json.dumps(fixture["open_alerts"])
        if path_value.endswith("/device/groups/103/alerts") or path_value.endswith("/device/groups/104/alerts"):
            return 200, {}, json.dumps({"items": [], "total": 0})

        # --- Website groups ---
        if path_value.endswith("/website/groups"):
            return 200, {}, json.dumps(fixture["website_groups"])
        if path_value.endswith("/website/groups/201/groups"):
            return 200, {}, json.dumps({"items": [], "total": 0})
        if path_value.endswith("/website/groups/201/websites"):
            return 200, {}, json.dumps(fixture["websites"])

        # --- Infrastructure inventory ---
        if path_value.endswith("/device/unmonitoreddevices"):
            return 200, {}, json.dumps(fixture["unmonitored_devices"])
        if path_value.endswith("/setting/smcheckpoints"):
            return 200, {}, json.dumps(fixture["smcheckpoints"])
        if path_value.endswith("/setting/collectors"):
            return 200, {}, json.dumps(fixture["collectors"])
        if path_value.endswith("/report/reports"):
            return 200, {}, json.dumps(fixture["reports"])

        # --- Datasources, instances, and data ---
        if path_value.endswith("/device/devices/1/devicedatasources"):
            return 200, {}, json.dumps(fixture["devicedatasources"]["1"])
        if path_value.endswith("/device/devices/2/devicedatasources"):
            return 200, {}, json.dumps(fixture["devicedatasources"]["2"])
        if path_value.endswith("/device/devices/1/devicedatasources/1001/instances"):
            return 200, {}, json.dumps(fixture["instances"]["1:1001"])
        if path_value.endswith("/device/devices/1/devicedatasources/1002/instances"):
            return 200, {}, json.dumps(fixture["instances"]["1:1002"])
        if path_value.endswith("/device/devices/1/devicedatasources/1003/instances"):
            return 200, {}, json.dumps(fixture["instances"]["1:1003"])
        if path_value.endswith("/device/devices/1/devicedatasources/1004/instances"):
            return 200, {}, json.dumps(fixture["instances"]["1:1004"])
        if path_value.endswith("/device/devices/1/devicedatasources/1005/instances"):
            return 200, {}, json.dumps(fixture["instances"]["1:1005"])
        if path_value.endswith("/device/devices/2/devicedatasources/2001/instances"):
            return 200, {}, json.dumps(fixture["instances"]["2:2001"])
        if path_value.endswith("/device/devices/2/devicedatasources/2002/instances"):
            return 200, {}, json.dumps(fixture["instances"]["2:2002"])
        if path_value.endswith("/device/devices/2/devicedatasources/2003/instances"):
            return 200, {}, json.dumps(fixture["instances"]["2:2003"])
        if path_value.endswith("/device/devices/2/devicedatasources/2004/instances"):
            return 200, {}, json.dumps(fixture["instances"]["2:2004"])
        if path_value.endswith("/device/devices/2/devicedatasources/2005/instances"):
            return 200, {}, json.dumps(fixture["instances"]["2:2005"])
        if path_value.endswith("/device/devices/1/devicedatasources/1001/instances/11001/data"):
            return 200, {}, json.dumps(fixture["instance_data"]["1:1001:11001"])
        if path_value.endswith("/device/devices/1/devicedatasources/1002/instances/11002/data"):
            return 200, {}, json.dumps(fixture["instance_data"]["1:1002:11002"])
        if path_value.endswith("/device/devices/1/devicedatasources/1003/instances/11003/data"):
            return 200, {}, json.dumps(fixture["instance_data"]["1:1003:11003"])
        if path_value.endswith("/device/devices/1/devicedatasources/1004/instances/11004/data"):
            return 200, {}, json.dumps(fixture["instance_data"]["1:1004:11004"])
        if path_value.endswith("/device/devices/1/devicedatasources/1005/instances/11005/data"):
            return 200, {}, json.dumps(fixture["instance_data"]["1:1005:11005"])
        if path_value.endswith("/device/devices/2/devicedatasources/2001/instances/21001/data"):
            return 200, {}, json.dumps(fixture["instance_data"]["2:2001:21001"])
        if path_value.endswith("/device/devices/2/devicedatasources/2002/instances/21002/data"):
            return 200, {}, json.dumps(fixture["instance_data"]["2:2002:21002"])
        if path_value.endswith("/device/devices/2/devicedatasources/2003/instances/21003/data"):
            return 200, {}, json.dumps(fixture["instance_data"]["2:2003:21003"])
        if path_value.endswith("/device/devices/2/devicedatasources/2004/instances/21004/data"):
            return 200, {}, json.dumps(fixture["instance_data"]["2:2004:21004"])
        if path_value.endswith("/device/devices/2/devicedatasources/2005/instances/21005/data"):
            return 200, {}, json.dumps(fixture["instance_data"]["2:2005:21005"])

        # --- Individual resource lookups ---
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
        if path_value.endswith("/report/reports/7010"):
            return 200, {}, json.dumps(fixture["report_details"]["7010"])
        raise AssertionError(f"Unhandled URL {url}")

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
            )

    def test_pipeline_produces_scoped_artifacts(self):
        context = resolve_logicmonitor_context(
            build_raw_context(),
            now=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        )
        result = run_logicmonitor_pipeline(context, fetch_impl=create_fetch_mock())
        self.assertEqual(result["snapshot"]["dataset"], "logicmonitor_snapshot")
        self.assertEqual(result["snapshot"]["inventory"]["devices"]["count_collected"], 2)
        self.assertEqual(result["snapshot"]["inventory"]["collectors"]["count_collected"], 0)
        self.assertEqual(result["snapshot"]["inventory"]["reports"]["count_collected"], 0)
        self.assertEqual(result["observability"]["dataset"], "observability")
        self.assertEqual(result["observability"]["totals"]["devices"], 2)
        self.assertEqual(result["alert_trends"]["alert_counts_opened"], 1)
        self.assertEqual(result["alert_trends"]["alert_counts_closed"], 0)
        self.assertEqual(result["resource_health"]["critical_devices"], 1)
        self.assertEqual(result["monitoring_coverage"]["unmonitored_devices"], 1)
        self.assertNotIn("collectors", result["monitoring_coverage"])
        self.assertNotIn("checkpoints", result["monitoring_coverage"])
        self.assertNotIn("reports_available", result["monitoring_coverage"])
        self.assertEqual(result["website_experience"]["monitored_websites"], 1)
        self.assertEqual(result["platform_assets"]["collectors"]["count"], 0)
        self.assertEqual(result["report_inventory"]["reports_available"], 0)
        self.assertEqual(result["inventory_exceptions"]["unmonitored_device_count"], 1)
        self.assertEqual(result["device_availability"]["devices_monitored"], 2)
        self.assertEqual(result["cpu_memory_utilization"]["cpu_devices"][0]["device"], "cust-a-sql-01")
        self.assertEqual(result["disk_capacity_utilization"]["highest_disk_volume_usage_by_device"][0]["device"], "cust-a-sql-01")
        self.assertEqual(result["network_interface_throughput"]["device_network_summary"][0]["device"], "cust-a-fw-01")
        self.assertEqual(result["bundle"]["dataset"], "logicmonitor_report_bundle")
        self.assertEqual(result["bundle"]["sections"]["source_inventory_summary"]["devices"], 2)
        self.assertNotIn("collectors", result["bundle"]["sections"]["source_inventory_summary"])
        self.assertNotIn("checkpoints", result["bundle"]["sections"]["source_inventory_summary"])
        self.assertNotIn("reports", result["bundle"]["sections"]["source_inventory_summary"])
        self.assertNotIn("platform_assets", result["bundle"]["sections"])
        self.assertNotIn("report_inventory", result["bundle"]["sections"])
        self.assertIn("device_availability", result["bundle"]["sections"])
        self.assertIn("monitoring_coverage", result["bundle"]["sections"])

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
                    },
                },
            },
        )
        resolution = resolve_logicmonitor_scope_by_company(lookup_context, fetch_impl=create_fetch_mock())
        self.assertEqual(resolution["match_confidence"], "high")
        self.assertEqual(resolution["resolved_scope"]["logicmonitor"]["root_device_group_id"], 101)
        self.assertEqual(resolution["resolved_scope"]["logicmonitor"]["root_website_group_id"], 201)
        # Per SKILL.md: resolved_scope.logicmonitor.group_identifiers must contain only the
        # single root full path. Descendant groups are available in
        # device_group_resolution.descendant_groups for reference only and must NOT be
        # merged into group_identifiers.
        self.assertEqual(
            resolution["resolved_scope"]["logicmonitor"]["group_identifiers"],
            ["Nexon/Customer A"],
        )
        self.assertEqual(resolution["resolved_scope"]["logicmonitor"]["site_groups"], ["Customer A"])
        # Descendant groups are present in the resolution output for reference.
        descendant_paths = sorted(
            g["full_path"] for g in resolution["device_group_resolution"]["descendant_groups"]
        )
        self.assertIn("Nexon/Customer A", descendant_paths)

    def test_cli_steps_write_expected_files(self):
        context = resolve_logicmonitor_context(
            build_raw_context(),
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
            normalize = subprocess.run(
                [sys.executable, str(CURRENT_DIR / "normalize_logicmonitor_collection.py"), "--context", str(context_path), "--run-dir", str(run_dir)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(normalize.returncode, 0, normalize.stderr)
            bundle = subprocess.run(
                [sys.executable, str(CURRENT_DIR / "build_logicmonitor_report_bundle.py"), "--context", str(context_path), "--run-dir", str(run_dir)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(bundle.returncode, 0, bundle.stderr)
            observability = json.loads(Path(run_paths["observability_file"]).read_text(encoding="utf-8"))
            report_bundle = json.loads(Path(run_paths["logicmonitor_bundle_file"]).read_text(encoding="utf-8"))
            self.assertEqual(observability["dataset"], "observability")
            self.assertEqual(report_bundle["dataset"], "logicmonitor_report_bundle")
            self.assertEqual(json.loads(Path(run_paths["device_availability_file"]).read_text(encoding="utf-8"))["dataset"], "device_availability")
            self.assertEqual(json.loads(Path(run_paths["monitoring_coverage_file"]).read_text(encoding="utf-8"))["dataset"], "monitoring_coverage")

    def test_run_path_layout(self):
        paths = resolve_run_paths("/tmp/customer-run")
        self.assertTrue(Path(paths["logicmonitor_snapshot_file"]).as_posix().endswith("/tmp/customer-run/source_snapshots/logicmonitor.json"))
        self.assertTrue(Path(paths["logicmonitor_bundle_file"]).as_posix().endswith("/tmp/customer-run/normalized/logicmonitor_report_bundle.json"))
        self.assertTrue(Path(paths["device_availability_file"]).as_posix().endswith("/tmp/customer-run/normalized/device_availability.json"))


if __name__ == "__main__":
    unittest.main()
