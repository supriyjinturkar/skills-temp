---
name: logicmonitor-data-collection
description: Use when a LangSmith Fleet agent needs to resolve customer scope, collect customer-scoped LogicMonitor data, normalize it, or build a reusable Nexon report bundle from the shared LogicMonitor tenant.
---

# Nexon LogicMonitor Data Collection - Fleet

This skill packages the Python collection pipeline that a Fleet agent can run inside its sandbox for Nexon customer reporting.

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
      "account_name": "nexon",
      "auth_mode": "bearer"
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
      "auth_mode": "bearer",
      "group_identifiers": ["Nexon/Customer A"],
      "site_groups": ["Customer A"],
      "root_device_group_id": 101,
      "root_website_group_id": 201
    }
  }
}
```

Provide LogicMonitor credentials through run secrets or environment variables:

- `LOGICMONITOR_BEARER_TOKEN`
- `LOGICMONITOR_API_ACCESS_ID`
- `LOGICMONITOR_API_ACCESS_KEY`
- `LOGICMONITOR_BASIC_USERNAME`
- `LOGICMONITOR_BASIC_PASSWORD`

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
      "group_identifiers": ["Nexon/Customer A", "Nexon/Customer A/Servers"],
      "root_device_group_id": 101,
      "root_website_group_id": 201,
      "site_groups": ["Customer A"]
    }
  }
}
```

Use the returned `logicmonitor` object as the scoped source for collection.

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
- `run/normalized/logicmonitor_report_bundle.json`

## Guardrails

- Nexon uses a shared LogicMonitor tenant, so collection must stay customer-scoped by default.
- The collector fails closed unless `group_identifiers` or `root_device_group_id` is present, unless `allow_full_tenant_collection=true` is set intentionally.
- Prefer the resolved root group plus descendant groups over broad tenant-wide reads.
- Do not re-run collection just because drafting, rendering, review-mail, or artifact-delivery steps fail later. Reuse the bundle already produced for that run.
- Treat one collected bundle as the run-scoped source of truth for all LogicMonitor-backed report sections.
