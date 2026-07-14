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

from br_context import parse_cli_args, resolve_backupradar_context, resolve_backupradar_lookup_context
from br_io import resolve_run_paths
from br_pipeline import resolve_backupradar_scope_by_company, run_backupradar_pipeline


# ---------------------------------------------------------------------------
# Fixtures — BackupRadar API v2 response shapes
# ---------------------------------------------------------------------------

def backupradar_fixtures():
    """Return mock v2 API payloads keyed by endpoint path suffix."""
    return {
        "backups": {
            "Total": 4,
            "Page": 1,
            "PageSize": 1000,
            "TotalPages": 1,
            "Results": [
                {
                    "backupId": "job-1",
                    "companyName": "Customer B",
                    "deviceName": "cust-b-sql-01",
                    "deviceType": {"id": 1, "name": "Server"},
                    "jobName": "Customer B Servers SOBR",
                    "methodName": "Veeam",
                    "status": {"id": 1, "name": "Success"},
                    "lastResult": "2026-07-11T02:00:00Z",
                    "lastSuccess": "2026-07-11T02:00:00Z",
                    "isVerified": True,
                    "ticketCount": 0,
                    "tags": [],
                    "history": [
                        {"date": "2026-07-01T00:00:00", "countSuccess": 1, "countFailure": 0, "countWarning": 0, "countNoResult": 0},
                        {"date": "2026-07-02T00:00:00", "countSuccess": 1, "countFailure": 0, "countWarning": 0, "countNoResult": 0},
                        {"date": "2026-07-04T00:00:00", "countSuccess": 0, "countFailure": 1, "countWarning": 0, "countNoResult": 0},
                        {"date": "2026-07-11T00:00:00", "countSuccess": 1, "countFailure": 0, "countWarning": 0, "countNoResult": 0},
                    ],
                },
                {
                    "backupId": "job-2",
                    "companyName": "Customer B",
                    "deviceName": "cust-b-fs-01",
                    "deviceType": {"id": 1, "name": "Server"},
                    "jobName": "Customer B Servers SOBR",
                    "methodName": "Veeam",
                    "status": {"id": 1, "name": "Success"},
                    "lastResult": "2026-07-05T01:40:00Z",
                    "lastSuccess": "2026-07-05T01:40:00Z",
                    "isVerified": False,
                    "ticketCount": 0,
                    "tags": [],
                    "history": [
                        {"date": "2026-07-05T00:00:00", "countSuccess": 1, "countFailure": 0, "countWarning": 0, "countNoResult": 0},
                        {"date": "2026-07-07T00:00:00", "countSuccess": 0, "countFailure": 0, "countWarning": 1, "countNoResult": 0},
                    ],
                },
                {
                    "backupId": "job-3",
                    "companyName": "Customer B",
                    "deviceName": "cust-b-app-01",
                    "deviceType": {"id": 3, "name": "Azure VM"},
                    "jobName": "production_backups",
                    "methodName": "Veeam",
                    "status": {"id": 1, "name": "Success"},
                    "lastResult": "2026-07-09T03:15:00Z",
                    "lastSuccess": "2026-07-09T03:15:00Z",
                    "isVerified": True,
                    "ticketCount": 0,
                    "tags": [],
                    "history": [
                        {"date": "2026-07-09T00:00:00", "countSuccess": 1, "countFailure": 0, "countWarning": 0, "countNoResult": 0},
                    ],
                },
                {
                    # Different company — must NOT appear in Customer B scoped results
                    "backupId": "job-x",
                    "companyName": "Other Company",
                    "deviceName": "other-server",
                    "deviceType": {"id": 1, "name": "Server"},
                    "jobName": "Other SOBR",
                    "methodName": "Veeam",
                    "status": {"id": 1, "name": "Success"},
                    "lastResult": "2026-07-09T00:00:00Z",
                    "lastSuccess": "2026-07-09T00:00:00Z",
                    "isVerified": False,
                    "ticketCount": 0,
                    "tags": [],
                    "history": [],
                },
            ],
        },
        "backups_inactive": {
            "Total": 0, "Page": 1, "PageSize": 1000, "TotalPages": 1, "Results": [],
        },
        "backups_overview": {
            "backups": 4, "office365": 0, "workstations": 0,
            "activePolicies": 10, "inactivePolicies": 2, "retiredPolicies": 5,
        },
    }


def build_raw_context():
    """v2-compatible customer context with customer_id pre-resolved."""
    return {
        "company_name": "Customer B",
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
                # customer_id is the resolved companyName string in v2
                "customer_id": "Customer B",
                "customer_name": "Customer B",
                "resources": {
                    "backups": {
                        "path": "/backups",
                        "customer_filter_param": "SearchByCompanyName",
                        "start_param": "date",
                        "end_param": "",
                        "page_param": "Page",
                        "page_size_param": "Size",
                        "page_size": 1000,
                        "query": {"HistoryDays": 30},
                    },
                    "backups_inactive": {
                        "path": "/backups/inactive",
                        "customer_filter_param": "SearchByCompanyName",
                        "page_param": "Page",
                        "page_size_param": "Size",
                        "page_size": 1000,
                    },
                    "backups_overview": {
                        "path": "/backups/overview",
                    },
                },
            },
        },
    }


def build_lookup_raw_context():
    """Context for the resolver — no customer_id yet, unscoped discovery enabled."""
    return {
        "company_name": "Customer B",
        "customer_name": "Customer B",
        "period": {
            "start": "2026-07-01T00:00:00Z",
            "end": "2026-07-31T23:59:59Z",
        },
        "source_scope": {
            "backupradar": {
                "base_url": "https://api.backupradar.com",
                "allow_unscoped_collection": True,
                "resources": {
                    "backups": {
                        "path": "/backups",
                        "customer_filter_param": "SearchByCompanyName",
                        "start_param": "date",
                        "end_param": "",
                        "page_param": "Page",
                        "page_size_param": "Size",
                        "page_size": 1000,
                    },
                },
            },
        },
    }


def create_fetch_mock():
    """Return a fetch_impl that serves v2 fixture data based on URL path."""
    fixture = backupradar_fixtures()

    def fetch_impl(method, url, headers, body):
        from urllib.parse import parse_qsl, urlparse

        parsed = urlparse(url)
        path_value = parsed.path
        query = dict(parse_qsl(parsed.query))

        # GET /backups/retired
        if path_value.endswith("/backups/retired"):
            return 200, {}, json.dumps({"Total": 0, "Page": 1, "PageSize": 1000, "TotalPages": 1, "Results": []})

        # GET /backups/filters
        if path_value.endswith("/backups/filters"):
            return 200, {}, json.dumps({})

        # GET /backups/overview  (must check before /backups to avoid prefix match)
        if path_value.endswith("/backups/overview"):
            return 200, {}, json.dumps(fixture["backups_overview"])

        # GET /backups/inactive
        if path_value.endswith("/backups/inactive"):
            return 200, {}, json.dumps(fixture["backups_inactive"])

        # GET /backups  (scoped or unscoped)
        if path_value.endswith("/backups"):
            company_filter = query.get("SearchByCompanyName", "")
            all_results = fixture["backups"]["Results"]
            scoped = [r for r in all_results if r.get("companyName") == company_filter] if company_filter else all_results
            payload = {**fixture["backups"], "Results": scoped, "Total": len(scoped)}
            return 200, {}, json.dumps(payload)

        raise AssertionError(f"Unhandled URL in v2 mock: {url}")

    return fetch_impl


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class BackupRadarFleetScriptsTest(unittest.TestCase):

    def test_context_parser_preserves_flags(self):
        self.assertEqual(
            parse_cli_args([
                "--context", "ctx.json",
                "--run-dir", "run-a",
                "--snapshot", "snap.json",
                "--normalized", "norm.json",
                "--output", "out.json",
            ]),
            {
                "context_path": "ctx.json",
                "run_dir": "run-a",
                "snapshot_path": "snap.json",
                "normalized_path": "norm.json",
                "output_path": "out.json",
            },
        )

    def test_context_requires_customer_scope(self):
        """resolve_backupradar_context must raise if customer_id is missing and unscoped not allowed."""
        with self.assertRaisesRegex(ValueError, "customer_id"):
            resolve_backupradar_context(
                {
                    "customer_id": "x",
                    "customer_name": "X",
                    "period": {"start": "2026-07-01T00:00:00Z", "end": "2026-07-02T00:00:00Z"},
                    "source_scope": {
                        "backupradar": {
                            "base_url": "https://api.backupradar.com",
                        }
                    },
                },
            )

    def test_context_defaults_use_v2_settings(self):
        """Default auth_header must be ApiKey and required_resources must include backups."""
        ctx = resolve_backupradar_context(
            build_raw_context(),
            now=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        )
        br = ctx["backupradar"]
        self.assertIn("backups", br["required_resources"])
        self.assertNotIn("jobs", br["required_resources"])
        self.assertIn("backups", br["resources"])
        self.assertNotIn("customers", br["resources"])
        self.assertNotIn("jobs", br["resources"])

    def test_pipeline_produces_scoped_artifacts(self):
        """Full pipeline run with v2 mock — verify counts, datasets, and bundle sections."""
        context = resolve_backupradar_context(
            build_raw_context(),
            now=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        )
        result = run_backupradar_pipeline(context, fetch_impl=create_fetch_mock())

        # Snapshot
        self.assertEqual(result["snapshot"]["dataset"], "backupradar_snapshot")
        self.assertGreater(result["snapshot"]["inventory"]["backups"]["count_collected"], 0)

        # History expansion:
        # job-1: 4 history days (1S, 1S, 1F, 1S) = 4 records
        # job-2: 2 history days (1S, 1W) = 2 records
        # job-3: 1 history day  (1S) = 1 record
        # Total for Customer B = 7
        backup = result["backup"]
        self.assertEqual(backup["dataset"], "backup")
        self.assertEqual(backup["totals"]["jobs"], 7)
        self.assertEqual(backup["totals"]["success_jobs"], 5)
        self.assertEqual(backup["totals"]["failed_jobs"], 1)
        self.assertEqual(backup["totals"]["warning_jobs"], 1)

        self.assertEqual(result["backup_summary"]["dataset"], "backup_summary")
        self.assertEqual(result["backup_trends"]["dataset"], "backup_trends")
        self.assertIn("daily_status_counts", result["backup_trends"])

        # failed + warning = 2 non-success records → 2 exception rows
        self.assertEqual(result["backup_exceptions"]["exception_count"], 2)

        bundle = result["bundle"]
        self.assertEqual(bundle["dataset"], "backupradar_report_bundle")
        self.assertIn("backup_summary", bundle["sections"])
        self.assertIn("backup_trends", bundle["sections"])
        self.assertIn("backup_operational_outcomes", bundle["sections"])

    def test_company_name_resolver_discovers_from_backups(self):
        """Resolver must discover Customer B from /backups companyName (no /customers endpoint)."""
        lookup_context = resolve_backupradar_lookup_context(
            build_lookup_raw_context(),
        )
        resolution = resolve_backupradar_scope_by_company(lookup_context, fetch_impl=create_fetch_mock())
        self.assertEqual(resolution["match_confidence"], "high")
        # In v2, customer_id is the matched companyName string
        self.assertEqual(resolution["resolved_scope"]["backupradar"]["customer_id"], "Customer B")
        self.assertEqual(resolution["resolved_scope"]["backupradar"]["customer_name"], "Customer B")

    def test_scoped_collection_filters_by_company(self):
        """Jobs from 'Other Company' must not appear in a Customer B scoped run."""
        context = resolve_backupradar_context(
            build_raw_context(),
            now=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        )
        result = run_backupradar_pipeline(context, fetch_impl=create_fetch_mock())
        customer_names = {j["customer_name"] for j in result["backup"]["jobs"]}
        self.assertNotIn("Other Company", customer_names)
        self.assertIn("Customer B", customer_names)

    def test_cli_steps_write_expected_files(self):
        """normalize and bundle CLI scripts must produce valid output files."""
        context = resolve_backupradar_context(
            build_raw_context(),
            now=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        )
        pipeline = run_backupradar_pipeline(context, fetch_impl=create_fetch_mock())
        with tempfile.TemporaryDirectory(prefix="fleet-backupradar-scripts-") as root:
            root_path = Path(root)
            context_path = root_path / "customer_context.json"
            run_dir = root_path / "run"
            context_path.write_text(
                f"{json.dumps(build_raw_context(), indent=2)}\n", encoding="utf-8"
            )
            run_paths = resolve_run_paths(run_dir)
            Path(run_paths["backupradar_snapshot_file"]).parent.mkdir(parents=True, exist_ok=True)
            Path(run_paths["backupradar_snapshot_file"]).write_text(
                f"{json.dumps(pipeline['snapshot'], indent=2)}\n", encoding="utf-8"
            )

            normalize = subprocess.run(
                [sys.executable, str(CURRENT_DIR / "normalize_backupradar_collection.py"),
                 "--context", str(context_path), "--run-dir", str(run_dir)],
                cwd=root, capture_output=True, text=True, check=False,
            )
            self.assertEqual(normalize.returncode, 0, normalize.stderr)

            bundle_proc = subprocess.run(
                [sys.executable, str(CURRENT_DIR / "build_backupradar_report_bundle.py"),
                 "--context", str(context_path), "--run-dir", str(run_dir)],
                cwd=root, capture_output=True, text=True, check=False,
            )
            self.assertEqual(bundle_proc.returncode, 0, bundle_proc.stderr)

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
