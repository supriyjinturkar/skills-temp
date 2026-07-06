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

from br_context import parse_cli_args, resolve_backupradar_context, resolve_backupradar_lookup_context
from br_io import resolve_run_paths
from br_pipeline import resolve_backupradar_scope_by_company, run_backupradar_pipeline


def backupradar_fixtures():
    return {
        "customers": [
            {"id": "12345", "name": "Customer B", "aliases": ["Customer Bee"]},
            {"id": "99999", "name": "Shared Tenant Customer"},
        ],
        "jobs": [
            {
                "id": "job-1",
                "device_id": "dev-1",
                "device_name": "cust-b-sql-01",
                "destination_id": "vault-1",
                "destination_name": "Azure Vault",
                "status": "Success",
                "completed_at": "2026-07-02T01:00:00Z",
                "bytes_protected": 1000000000,
                "reported_at": "2026-07-02T02:00:00Z",
            },
            {
                "id": "job-2",
                "device_id": "dev-2",
                "device_name": "cust-b-fs-01",
                "destination_id": "vault-1",
                "destination_name": "Azure Vault",
                "status": "Failed",
                "completed_at": "2026-07-04T01:30:00Z",
                "message": "Storage quota exceeded",
            },
            {
                "id": "job-3",
                "device_id": "dev-2",
                "device_name": "cust-b-fs-01",
                "destination_id": "vault-1",
                "destination_name": "Azure Vault",
                "status": "Retried",
                "completed_at": "2026-07-05T01:40:00Z",
                "message": "Recovered after retry",
            },
            {
                "id": "job-4",
                "device_id": "dev-4",
                "device_name": "cust-b-queue-01",
                "destination_id": "vault-2",
                "destination_name": "Local Appliance",
                "status": "Pending",
                "completed_at": "2026-07-07T03:15:00Z",
                "review_status": "Pending backups checked and cleared",
                "checked": True,
                "cleared": True,
            },
            {
                "id": "job-5",
                "device_id": "dev-3",
                "device_name": "cust-b-app-01",
                "destination_id": "vault-2",
                "destination_name": "Local Appliance",
                "status": "Warning",
                "completed_at": "2026-07-09T03:15:00Z",
                "message": "Completed with warnings",
                "verified": True,
                "cleared": True,
            },
            {
                "id": "job-6",
                "device_id": "dev-1",
                "device_name": "cust-b-sql-01",
                "destination_id": "vault-1",
                "destination_name": "Azure Vault",
                "status": "Success",
                "completed_at": "2026-07-11T02:00:00Z",
                "bytes_protected": 2500000000,
            },
        ],
        "devices": [
            {"id": "dev-1", "name": "cust-b-sql-01", "site": "Primary DC", "platform": "Windows"},
            {"id": "dev-2", "name": "cust-b-fs-01", "site": "Primary DC", "platform": "Windows"},
            {"id": "dev-3", "name": "cust-b-app-01", "site": "Regional Site", "platform": "Linux"},
            {"id": "dev-4", "name": "cust-b-queue-01", "site": "Regional Site", "platform": "Windows"},
        ],
        "destinations": [
            {"id": "vault-1", "name": "Azure Vault", "type": "cloud"},
            {"id": "vault-2", "name": "Local Appliance", "type": "appliance"},
        ],
        "alerts": [
            {"id": "alert-1", "name": "Pending review alert", "status": "Pending", "created_at": "2026-07-08T00:00:00Z"},
            {"id": "alert-2", "name": "Warning verified", "status": "Warning", "verified": True, "cleared": True, "resolved_at": "2026-07-08T04:00:00Z"},
        ],
        "restores": [
            {"id": "restore-1", "device_id": "dev-1", "destination_id": "vault-1", "status": "Success", "completed_at": "2026-07-12T02:00:00Z"},
            {"id": "restore-2", "device_id": "dev-2", "destination_id": "vault-1", "status": "Failed", "completed_at": "2026-07-12T03:00:00Z", "message": "Restore validation failed"},
        ],
        "sources": [
            {"id": "source-1", "name": "M365", "status": "Healthy", "enabled": True, "protected_devices": 120},
            {"id": "source-2", "name": "NAS", "status": "Warning", "enabled": False, "protected_devices": 12},
        ],
        "policies": [
            {"id": "policy-1", "name": "Daily Servers", "enabled": True, "protected_devices": 80},
            {"id": "policy-2", "name": "Weekly Archive", "enabled": False, "protected_devices": 20},
        ],
        "vaults": [
            {"id": "vault-1", "name": "Azure Vault", "capacity_bytes": 10000000000, "used_bytes": 6500000000},
            {"id": "vault-2", "name": "Local Appliance", "capacity_bytes": 5000000000, "used_bytes": 2000000000},
        ],
    }


def build_raw_context():
    return {
        "customer_id": "customer-b",
        "customer_name": "Customer B",
        "report_family": "monthly-service-review",
        "template_key": "operations-v1",
        "period": {
            "start": "2026-07-01T00:00:00Z",
            "end": "2026-07-31T23:59:59Z",
            "label": "July 2026",
        },
        "source_scope": {
            "backupradar": {
                "tenant_id": "nexon-backupradar",
                "base_url": "https://api.backupradar.com",
                "auth_mode": "api_key",
                "customer_id": "12345",
                "resources": {
                    "customers": {"path": "/customers"},
                    "jobs": {
                        "path": "/jobs",
                        "customer_filter_param": "customer_id",
                        "start_param": "start_date",
                        "end_param": "end_date",
                    },
                    "devices": {"path": "/devices", "customer_filter_param": "customer_id"},
                    "destinations": {"path": "/destinations", "customer_filter_param": "customer_id"},
                    "alerts": {"path": "/alerts", "customer_filter_param": "customer_id", "start_param": "start_date", "end_param": "end_date"},
                    "restores": {"path": "/restores", "customer_filter_param": "customer_id", "start_param": "start_date", "end_param": "end_date"},
                    "sources": {"path": "/sources", "customer_filter_param": "customer_id"},
                    "policies": {"path": "/policies", "customer_filter_param": "customer_id"},
                    "vaults": {"path": "/vaults", "customer_filter_param": "customer_id"},
                },
            },
        },
    }


def create_fetch_mock():
    fixture = backupradar_fixtures()

    def fetch_impl(method, url, headers, body):
        from urllib.parse import parse_qsl, urlparse

        parsed = urlparse(url)
        path_value = parsed.path
        query = dict(parse_qsl(parsed.query))
        if path_value.endswith("/customers"):
            if query.get("customer_id") == "12345":
                return 200, {}, json.dumps({"items": [fixture["customers"][0]]})
            return 200, {}, json.dumps({"items": fixture["customers"]})
        if path_value.endswith("/jobs"):
            if query.get("customer_id") != "12345":
                raise AssertionError(f"Unexpected customer filter for jobs: {query}")
            return 200, {}, json.dumps({"items": fixture["jobs"]})
        if path_value.endswith("/devices"):
            return 200, {}, json.dumps({"items": fixture["devices"]})
        if path_value.endswith("/destinations"):
            return 200, {}, json.dumps({"items": fixture["destinations"]})
        if path_value.endswith("/alerts"):
            return 200, {}, json.dumps({"items": fixture["alerts"]})
        if path_value.endswith("/restores"):
            return 200, {}, json.dumps({"items": fixture["restores"]})
        if path_value.endswith("/sources"):
            return 200, {}, json.dumps({"items": fixture["sources"]})
        if path_value.endswith("/policies"):
            return 200, {}, json.dumps({"items": fixture["policies"]})
        if path_value.endswith("/vaults"):
            return 200, {}, json.dumps({"items": fixture["vaults"]})
        raise AssertionError(f"Unhandled URL {url}")

    return fetch_impl


class BackupRadarFleetScriptsTest(unittest.TestCase):
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
        with self.assertRaisesRegex(ValueError, "customer_id"):
            resolve_backupradar_context(
                {
                    "customer_id": "x",
                    "customer_name": "X",
                    "period": {"start": "2026-07-01T00:00:00Z", "end": "2026-07-02T00:00:00Z"},
                    "source_scope": {"backupradar": {"base_url": "https://api.backupradar.com"}},
                },
                env={"BACKUPRADAR_API_KEY": "token"},
            )

    def test_pipeline_produces_scoped_artifacts(self):
        context = resolve_backupradar_context(
            build_raw_context(),
            env={"BACKUPRADAR_API_KEY": "token"},
            now=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        )
        result = run_backupradar_pipeline(context, fetch_impl=create_fetch_mock())
        self.assertEqual(result["snapshot"]["dataset"], "backupradar_snapshot")
        self.assertEqual(result["snapshot"]["inventory"]["jobs"]["count_collected"], 6)
        self.assertEqual(result["snapshot"]["inventory"]["alerts"]["count_collected"], 2)
        self.assertEqual(result["backup"]["dataset"], "backup")
        self.assertEqual(result["backup"]["totals"]["jobs"], 6)
        self.assertEqual(result["backup"]["totals"]["failed_jobs"], 1)
        self.assertEqual(result["backup"]["totals"]["pending_jobs"], 1)
        self.assertEqual(result["backup"]["totals"]["pending_jobs_cleared"], 1)
        self.assertEqual(result["backup"]["totals"]["warning_jobs_verified"], 1)
        self.assertEqual(result["backup"]["totals"]["warning_jobs_cleared"], 1)
        self.assertEqual(result["backup"]["totals"]["successful_jobs_reported"], 1)
        self.assertEqual(result["backup"]["totals"]["restore_jobs"], 2)
        self.assertEqual(result["backup"]["totals"]["restore_failed_jobs"], 1)
        self.assertEqual(result["backup"]["totals"]["source_count"], 2)
        self.assertEqual(result["backup"]["totals"]["policy_count"], 2)
        self.assertEqual(result["backup"]["totals"]["vault_count"], 2)
        self.assertEqual(result["backup_summary"]["dataset"], "backup_summary")
        self.assertEqual(result["backup_trends"]["dataset"], "backup_trends")
        self.assertEqual(result["backup_exceptions"]["exception_count"], 3)
        self.assertEqual(result["bundle"]["dataset"], "backupradar_report_bundle")
        self.assertEqual(result["bundle"]["sections"]["source_inventory_summary"]["devices"], 4)
        self.assertEqual(result["bundle"]["sections"]["source_inventory_summary"]["alerts"], 2)
        self.assertEqual(result["bundle"]["sections"]["backup_operational_outcomes"]["pending_jobs_cleared"], 1)

    def test_company_name_resolver_builds_customer_scope(self):
        lookup_context = resolve_backupradar_lookup_context(
            {
                "company_name": "Customer B",
                "customer_name": "Customer B",
                "period": {"start": "2026-07-01T00:00:00Z", "end": "2026-07-31T23:59:59Z"},
                "source_scope": {
                    "backupradar": {
                        "base_url": "https://api.backupradar.com",
                        "auth_mode": "api_key",
                        "resources": {"customers": {"path": "/customers"}},
                    },
                },
            },
            env={"BACKUPRADAR_API_KEY": "token"},
        )
        resolution = resolve_backupradar_scope_by_company(lookup_context, fetch_impl=create_fetch_mock())
        self.assertEqual(resolution["match_confidence"], "high")
        self.assertEqual(resolution["resolved_scope"]["backupradar"]["customer_id"], "12345")
        self.assertEqual(resolution["resolved_scope"]["backupradar"]["customer_name"], "Customer B")

    def test_cli_steps_write_expected_files(self):
        context = resolve_backupradar_context(
            build_raw_context(),
            env={"BACKUPRADAR_API_KEY": "token"},
            now=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        )
        pipeline = run_backupradar_pipeline(context, fetch_impl=create_fetch_mock())
        with tempfile.TemporaryDirectory(prefix="fleet-backupradar-scripts-") as root:
            root_path = Path(root)
            context_path = root_path / "customer_context.json"
            run_dir = root_path / "run"
            context_path.write_text(f"{json.dumps(build_raw_context(), indent=2)}\n", encoding="utf-8")
            run_paths = resolve_run_paths(run_dir)
            Path(run_paths["backupradar_snapshot_file"]).parent.mkdir(parents=True, exist_ok=True)
            Path(run_paths["backupradar_snapshot_file"]).write_text(
                f"{json.dumps(pipeline['snapshot'], indent=2)}\n",
                encoding="utf-8",
            )
            env = {**os.environ, "BACKUPRADAR_API_KEY": "token"}
            normalize = subprocess.run(
                [sys.executable, str(CURRENT_DIR / "normalize_backupradar_collection.py"), "--context", str(context_path), "--run-dir", str(run_dir)],
                cwd=root,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(normalize.returncode, 0, normalize.stderr)
            bundle = subprocess.run(
                [sys.executable, str(CURRENT_DIR / "build_backupradar_report_bundle.py"), "--context", str(context_path), "--run-dir", str(run_dir)],
                cwd=root,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(bundle.returncode, 0, bundle.stderr)
            backup = json.loads(Path(run_paths["backup_file"]).read_text(encoding="utf-8"))
            report_bundle = json.loads(Path(run_paths["backupradar_bundle_file"]).read_text(encoding="utf-8"))
            self.assertEqual(backup["dataset"], "backup")
            self.assertEqual(report_bundle["dataset"], "backupradar_report_bundle")

    def test_run_path_layout(self):
        paths = resolve_run_paths("/tmp/customer-run")
        self.assertEqual(paths["backupradar_snapshot_file"], "/tmp/customer-run/source_snapshots/backupradar.json")
        self.assertEqual(paths["backupradar_bundle_file"], "/tmp/customer-run/normalized/backupradar_report_bundle.json")


if __name__ == "__main__":
    unittest.main()
