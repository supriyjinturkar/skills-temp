---
name: backupradar-data-collection
description: Use when a LangSmith Fleet agent needs to resolve customer scope, collect customer-scoped BackupRadar data, normalize it, or build a reusable Nexon report bundle from the shared BackupRadar tenant.
---

# Nexon BackupRadar Data Collection - Fleet

This skill packages the Python collection pipeline that a Fleet agent can run inside its sandbox for Nexon customer reporting.

## Use this skill for

- resolving a company name into BackupRadar customer scope
- collecting customer-scoped backup job data from the shared Nexon tenant
- normalizing raw BackupRadar data into report-friendly backup outputs
- building one reusable report bundle for downstream drafting and rendering
- collecting every explicitly configured BackupRadar resource definition for the run, not only the base job list

## Scripts

- `scripts/resolve_backupradar_scope.py`
- `scripts/collect_backupradar_snapshot.py`
- `scripts/normalize_backupradar_collection.py`
- `scripts/build_backupradar_report_bundle.py`
- `scripts/run_backupradar_report_pipeline.py`

## Required run inputs

Create a sandbox-local `customer_context.json` for the current run.

Minimum unresolved context when only the company name is known:

```json
{
  "company_name": "Customer B",
  "customer_name": "Customer B",
  "period": {
    "start": "2026-07-01T00:00:00Z",
    "end": "2026-07-31T23:59:59Z"
  },
  "source_scope": {
    "backupradar": {
      "base_url": "https://api.backupradar.com",
      "resources": {
        "customers": {
          "path": "/customers"
        }
      }
    }
  }
}
```

Minimum direct-collection context when the customer scope is already known:

```json
{
  "customer_id": "customer-b",
  "customer_name": "Customer B",
  "report_family": "monthly-service-review",
  "template_key": "operations-v1",
  "period": {
    "start": "2026-07-01T00:00:00Z",
    "end": "2026-07-31T23:59:59Z",
    "label": "July 2026"
  },
  "source_scope": {
    "backupradar": {
      "base_url": "https://api.backupradar.com",
      "customer_id": "12345",
      "resources": {
        "customers": {
          "path": "/customers"
        },
        "jobs": {
          "path": "/jobs",
          "customer_filter_param": "customer_id",
          "start_param": "start_date",
          "end_param": "end_date"
        },
        "devices": {
          "path": "/devices",
          "customer_filter_param": "customer_id"
        },
        "destinations": {
          "path": "/destinations",
          "customer_filter_param": "customer_id"
        },
        "alerts": {
          "path": "/alerts",
          "customer_filter_param": "customer_id",
          "start_param": "start_date",
          "end_param": "end_date"
        },
        "restores": {
          "path": "/restores",
          "customer_filter_param": "customer_id",
          "start_param": "start_date",
          "end_param": "end_date"
        },
        "sources": {
          "path": "/sources",
          "customer_filter_param": "customer_id"
        },
        "policies": {
          "path": "/policies",
          "customer_filter_param": "customer_id"
        },
        "vaults": {
          "path": "/vaults",
          "customer_filter_param": "customer_id"
        }
      }
    }
  }
}
```

## Authentication

Authentication is handled automatically by the `nexon-backupradar-api` sandbox Access Profile.
The proxy injects the `ApiKey` header on every outbound request to `api.backupradar.com`.
Do not set `auth_mode`, `api_key`, or `BACKUPRADAR_API_KEY` in the context or environment.
The `base_url` defaults to `https://api.backupradar.com` and only needs to be set if using a non-standard endpoint.

## Standard flow

1. Write `customer_context.json` for the current run.
2. If the context does not already include `source_scope.backupradar.customer_id`, run the resolver first.
3. Merge the returned `resolved_scope.backupradar` object into `source_scope.backupradar`.
4. Run the end-to-end pipeline or the stepwise resolve -> collect -> normalize -> bundle flow.
5. Reuse the produced bundle for drafting, rendering, review, and delivery steps.

## Resolver flow

Run:

```bash
python3 skills/backupradar-data-collection/scripts/resolve_backupradar_scope.py \
  --context /path/to/customer_context.json \
  --run-dir /path/to/run
```

Expected output file:

- `run/resolved_backupradar_scope.json`

Expected resolver payload shape:

```json
{
  "resolved_scope": {
    "backupradar": {
      "customer_id": "12345",
      "customer_name": "Customer B"
    }
  },
  "match_confidence": "high"
}
```

Use the returned `backupradar` object as the scoped source for collection.

## Collection flow

End to end:

```bash
python3 skills/backupradar-data-collection/scripts/run_backupradar_report_pipeline.py \
  --context /path/to/customer_context.json \
  --run-dir /path/to/run
```

Step by step:

```bash
python3 skills/backupradar-data-collection/scripts/collect_backupradar_snapshot.py --context /path/to/customer_context.json --run-dir /path/to/run
python3 skills/backupradar-data-collection/scripts/normalize_backupradar_collection.py --context /path/to/customer_context.json --run-dir /path/to/run
python3 skills/backupradar-data-collection/scripts/build_backupradar_report_bundle.py --context /path/to/customer_context.json --run-dir /path/to/run
```

## Run outputs

- `run/source_snapshots/backupradar.json`
- `run/normalized/backup.json`
- `run/normalized/backup_summary.json`
- `run/normalized/backup_trends.json`
- `run/normalized/backup_exceptions.json`
- `run/normalized/backupradar_report_bundle.json`

## Resource-path note

The public BackupRadar docs were not machine-readable enough in this environment to safely hardcode vendor endpoint names beyond the API host and auth model.

The collector always fetches the core configured resources:

- `customers`
- `jobs`
- `devices`
- `destinations`

It also fetches any additional configured BackupRadar resources under `source_scope.backupradar.resources`, for example:

- `alerts`
- `issues`
- `exceptions`
- `restores`
- `sources`
- `policies`
- `vaults`
- other tenant-specific resource names

Configure concrete resource paths under `source_scope.backupradar.resources` when the tenant uses different route names, pagination fields, or filter-parameter names.

## Guardrails

- Nexon uses a shared BackupRadar tenant, so collection must stay customer-scoped by default.
- The collector fails closed unless `customer_id` is present, unless `allow_unscoped_collection=true` is set intentionally.
- Prefer one report-level bundle per run rather than many narrow backup queries.
- Do not re-run collection just because drafting, rendering, review-mail, or artifact-delivery steps fail later. Reuse the bundle already produced for that run.
- Treat one collected bundle as the run-scoped source of truth for all BackupRadar-backed report sections.
- Keep request concurrency low and respect `429` and `Retry-After` if the tenant returns them.
- When the source payload exposes operational review fields, the normalizer now surfaces:
  - pending backups
  - pending backups checked and cleared
  - warnings verified and cleared
  - successfully reported backups
