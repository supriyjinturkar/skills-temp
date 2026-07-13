---
name: logicmonitor-data-collection
description: Use when a LangSmith Fleet agent needs to resolve customer scope, collect customer-scoped LogicMonitor data, normalize it, or build a reusable Nexon report bundle from the shared LogicMonitor tenant.
---

# Nexon LogicMonitor Data Collection - Fleet

This skill packages the Python collection pipeline that a Fleet agent can run inside its sandbox for Nexon customer reporting.

This skill folder is the authoritative implementation path for the Fleet LogicMonitor collector.

## Use this skill for

- resolving a company name into LogicMonitor customer scope
- collecting customer-scoped LogicMonitor data from the shared Nexon tenant
- normalizing raw LogicMonitor data into report-friendly observability outputs
- building one reusable report bundle for downstream drafting and rendering

## Scripts

- `scripts/resolve_logicmonitor_scope.py`
- `scripts/collect_logicmonitor_snapshot.py`
- `scripts/normalize_logicmonitor_collection.py`
- `scripts/build_logicmonitor_report_bundle.py`
- `scripts/run_logicmonitor_report_pipeline.py`

## Required run inputs

Create a sandbox-local `customer_context.json` for the current run.

Minimum unresolved context when only the company name is known:

```json
{
  "company_name": "Customer A",
  "customer_name": "Customer A",
  "period": {
    "start": "2026-07-01T00:00:00Z",
    "end": "2026-07-31T23:59:59Z"
  },
  "source_scope": {
    "logicmonitor": {
      "account_name": "nexon"
    }
  }
}
```

Minimum direct-collection context when scope is already known:

```json
{
  "customer_id": "customer-a",
  "customer_name": "Customer A",
  "report_family": "monthly-service-review",
  "template_key": "operations-v1",
  "period": {
    "start": "2026-07-01T00:00:00Z",
    "end": "2026-07-31T23:59:59Z",
    "label": "July 2026"
  },
  "source_scope": {
    "logicmonitor": {
      "account_name": "nexon",
      "group_identifiers": ["Nexon/Customer A"],
      "site_groups": ["Customer A"],
      "root_device_group_id": 101,
      "root_website_group_id": 201
    }
  }
}
```

## Authentication

Authentication is handled automatically by the `nexon-logicmonitor-api` sandbox Access Profile.
The proxy injects the `Authorization` header on every outbound request to `nexon.logicmonitor.com`.
Do not set `auth_mode`, credential fields, or any `LOGICMONITOR_*` environment variables.
No credentials configuration is required in `customer_context.json` or the environment.

## Standard flow

1. Write `customer_context.json` for the current run.
2. If the context does not already include `group_identifiers` or `root_device_group_id`, run the resolver first.
3. Merge the returned `resolved_scope.logicmonitor` object into `source_scope.logicmonitor`.
4. Run the end-to-end pipeline or the stepwise collect -> normalize -> bundle flow.
5. Reuse the produced bundle for drafting, rendering, review, and delivery steps.

## Resolver flow

Run:

```bash
python3 skills/logicmonitor-data-collection/scripts/resolve_logicmonitor_scope.py \
  --context /path/to/customer_context.json \
  --run-dir /path/to/run
```

Expected output file:

- `run/resolved_logicmonitor_scope.json`

Expected resolver payload shape:

```json
{
  "resolved_scope": {
    "logicmonitor": {
      "group_identifiers": ["Customers/Nexon Clients/Customer A"],
      "root_device_group_id": 101,
      "root_website_group_id": 201,
      "site_groups": ["Customer A"]
    }
  }
}
```

`group_identifiers` contains **only the single root full path**. The collector recurses into
sub-groups internally via `_fetch_all_subgroups`. Do NOT expand `descendant_groups` from the
resolver output into `group_identifiers` — that list is for resolver scoring only and must not
be used as the collection scope.

Merge using **only** `resolved_scope.logicmonitor`, never `device_group_resolution.descendant_groups`:

```python
import json

with open("/run/resolved_logicmonitor_scope.json") as f:
    resolved = json.load(f)

with open("/run/customer_context.json") as f:
    ctx = json.load(f)

# Correct: merge only resolved_scope.logicmonitor
ctx["source_scope"]["logicmonitor"].update(resolved["resolved_scope"]["logicmonitor"])

with open("/run/customer_context.json", "w") as f:
    json.dump(ctx, f, indent=2)
```

## Collection flow

End to end:

```bash
python3 skills/logicmonitor-data-collection/scripts/run_logicmonitor_report_pipeline.py \
  --context /path/to/customer_context.json \
  --run-dir /path/to/run
```

Step by step:

```bash
python3 skills/logicmonitor-data-collection/scripts/collect_logicmonitor_snapshot.py --context /path/to/customer_context.json --run-dir /path/to/run
python3 skills/logicmonitor-data-collection/scripts/normalize_logicmonitor_collection.py --context /path/to/customer_context.json --run-dir /path/to/run
python3 skills/logicmonitor-data-collection/scripts/build_logicmonitor_report_bundle.py --context /path/to/customer_context.json --run-dir /path/to/run
```

## Run outputs

- `run/source_snapshots/logicmonitor.json`
- `run/normalized/observability.json`
- `run/normalized/availability_summary.json`
- `run/normalized/alert_trends.json`
- `run/normalized/resource_health.json`
- `run/normalized/monitoring_coverage.json`
- `run/normalized/website_experience.json`
- `run/normalized/platform_assets.json`
- `run/normalized/report_inventory.json`
- `run/normalized/inventory_exceptions.json`
- `run/normalized/root_scope_summary.json`
- `run/normalized/device_availability.json`
- `run/normalized/cpu_memory_utilization.json`
- `run/normalized/disk_capacity_utilization.json`
- `run/normalized/network_interface_throughput.json`
- `run/normalized/logicmonitor_report_bundle.json`

## Device collection behaviour — recursive sub-group traversal

The LogicMonitor API endpoint `GET /device/groups/{id}/devices` returns only the
**direct members** of that group. It does NOT recurse into sub-groups.

Customers typically assign devices to leaf sub-groups several levels deep (e.g.
`Altus Financial / Servers / SY3 / RDS`). The root group's `numOfHosts` metadata
reflects the full recursive count, but a direct API call on the root group returns
0 devices.

**The collector handles this correctly** by:

1. Enumerating all descendant sub-groups under the resolved root group via repeated
   `GET /device/groups?filter=parentId:{id}` calls (breadth-first).
2. Calling `GET /device/groups/{id}/devices` only on groups where
   `numOfDirectDevices > 0`, skipping intermediate container groups.
3. Deduplicating all collected devices by device `id` so that devices appearing in
   multiple dynamic groups (e.g. "Windows Servers" and "Domain Controller") are
   counted only once.
4. Tagging each device with its leaf group `fullPath` as `__siteGroup` for
   downstream site-level grouping.

**Known LogicMonitor group patterns to be aware of:**

- Root groups (e.g. `Customers/Nexon Clients/Altus Financial`) hold 0 direct devices.
- Intermediate groups (e.g. `Servers`, `Public Cloud`) often hold 0 direct devices.
- Leaf groups (e.g. `Servers/SY3/RDS`, `Devices by Type/Windows Servers`) hold direct devices.
- Dynamic/view groups (e.g. `Devices by Type`, `Devices by Location`) cross-reference
  the same physical devices under different classification trees — deduplication
  ensures these are not double-counted.

## Coverage summary

This skill now collects:

- scoped devices, groups, alerts, and root website inventory (recursive sub-group traversal)
- unmonitored devices
- collectors
- checkpoints
- saved reports and report details
- performance aggregates for device availability, CPU, memory, disk, and network throughput

By default, the skill collects all currently supported LogicMonitor report modules for the resolved customer scope in one run-scoped bundle.

The currently supported performance datasource families are:

- `Microsoft_Windows_CPU`
- `WinOS`
- `WinVolumeUsage-*`
- `Ping`
- `WinIf-*`

This is not yet a generic "collect every arbitrary LogicMonitor datasource" mode, and it is not yet a per-customer datasource-selection policy engine.

## Guardrails

- Nexon uses a shared LogicMonitor tenant, so collection must stay customer-scoped by default.
- The collector fails closed unless `group_identifiers` or `root_device_group_id` is present, unless `allow_full_tenant_collection=true` is set intentionally.
- Prefer the resolved root group plus descendant groups over broad tenant-wide reads.
- Do not re-run collection just because drafting, rendering, review-mail, or artifact-delivery steps fail later. Reuse the bundle already produced for that run.
- Treat one collected bundle as the run-scoped source of truth for all LogicMonitor-backed report sections.
- Never call `/device/groups/{id}/devices` on the root group alone and treat 0 results as authoritative — always recurse into sub-groups first.
