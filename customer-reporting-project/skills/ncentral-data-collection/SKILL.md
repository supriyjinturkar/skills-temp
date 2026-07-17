---
name: ncentral-data-collection
description: Use when a LangSmith Fleet agent needs to resolve a customer or site in N-central, collect customer-scoped N-central data, normalize it, and build a reusable Nexon report bundle for downstream drafting and rendering.
---

# Nexon N-central Data Collection - Fleet

This skill packages the Python collection pipeline that a Fleet agent can run inside its sandbox for Nexon customer reporting against the N-able N-central REST API.

This skill folder is the authoritative implementation path for the Fleet N-central collector.

## Use this skill for

- resolving a company name into an N-central customer or site scope
- collecting customer-scoped N-central inventory, issue, and custom-property data
- normalizing raw N-central responses into report-friendly infrastructure outputs
- building one reusable report bundle for downstream drafting, rendering, review, and delivery

## Scripts

- `scripts/resolve_ncentral_scope.py`
- `scripts/collect_ncentral_snapshot.py`
- `scripts/normalize_ncentral_collection.py`
- `scripts/build_ncentral_report_bundle.py`
- `scripts/run_ncentral_report_pipeline.py`

## Required run inputs

Create a sandbox-local `customer_context.json` for the current run.

Minimum unresolved context when only the company name is known:

```json
{
  "company_name": "Customer A",
  "customer_name": "Customer A",
  "period": {
    "start": "2026-07-01T00:00:00Z",
    "end": "2026-07-31T23:59:59Z",
    "label": "July 2026"
  },
  "source_scope": {
    "ncentral": {
      "base_url": "https://ncentral.example.com"
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
    "ncentral": {
      "base_url": "https://ncentral.example.com",
      "customer_id": 2001,
      "customer_name": "Customer A",
      "org_unit_id": 2001,
      "org_unit_name": "Customer A",
      "org_unit_type": "customer",
      "site_ids": [3001, 3002],
      "site_names": ["Customer A - HQ", "Customer A - Branch"]
    }
  }
}
```

## Authentication

The collector reads a bearer JWT from the sandbox-local token file.

Provide configuration in either the context or the environment:

- `source_scope.ncentral.base_url` or `NCENTRAL_BASE_URL`
- `source_scope.ncentral.jwt_token_path` or `NCENTRAL_JWT_TOKEN_PATH`

By default, the collector reads the token from:

- `/opt/ncentral/NCENTRAL_JWT_TOKEN`

Do not place the raw JWT in the run context. The collector reads the token text file directly and reloads it from disk if an API call returns `401` or `403`.

## Standard flow

1. Write `customer_context.json` for the current run.
2. If the context does not already include `source_scope.ncentral.org_unit_id`, run the resolver first.
3. Merge the returned `resolved_scope.ncentral` object into `source_scope.ncentral`.
4. Run the end-to-end pipeline or the stepwise collect -> normalize -> bundle flow.
5. Reuse the produced bundle for drafting, rendering, review, and delivery steps.

## Resolver flow

Run:

```bash
python3 skills/ncentral-data-collection/scripts/resolve_ncentral_scope.py \
  --context /path/to/customer_context.json \
  --run-dir /path/to/run
```

Expected output file:

- `run/resolved_ncentral_scope.json`

Expected resolver payload shape:

```json
{
  "resolved_scope": {
    "ncentral": {
      "base_url": "https://ncentral.example.com",
      "customer_id": 2001,
      "customer_name": "Customer A",
      "org_unit_id": 2001,
      "org_unit_name": "Customer A",
      "org_unit_type": "customer",
      "site_ids": [3001, 3002],
      "site_names": ["Customer A - HQ", "Customer A - Branch"]
    }
  }
}
```

Merge using only `resolved_scope.ncentral`.

## Collection flow

End to end:

```bash
python3 skills/ncentral-data-collection/scripts/run_ncentral_report_pipeline.py \
  --context /path/to/customer_context.json \
  --run-dir /path/to/run
```

Step by step:

```bash
python3 skills/ncentral-data-collection/scripts/collect_ncentral_snapshot.py --context /path/to/customer_context.json --run-dir /path/to/run
python3 skills/ncentral-data-collection/scripts/normalize_ncentral_collection.py --context /path/to/customer_context.json --run-dir /path/to/run
python3 skills/ncentral-data-collection/scripts/build_ncentral_report_bundle.py --context /path/to/customer_context.json --run-dir /path/to/run
```

## Run outputs

- `run/source_snapshots/ncentral.json`
- `run/normalized/ncentral_normalized.json`
- `run/normalized/ncentral_inventory_summary.json`
- `run/normalized/ncentral_issue_summary.json`
- `run/normalized/ncentral_site_rollup.json`
- `run/normalized/ncentral_device_health.json`
- `run/normalized/ncentral_custom_property_summary.json`
- `run/normalized/ncentral_scope_summary.json`
- `run/normalized/ncentral_report_bundle.json`

For downstream drafting, treat `ncentral_report_bundle.json.sections` as the canonical section map for N-central-backed report coverage.

## Data coverage

This skill collects:

- customers and customer-site relationships used for scope resolution
- org-unit-scoped devices
- org-unit active issues
- org-unit custom properties
- bounded per-device custom-property enrichment

The report bundle is optimized for infrastructure posture reporting rather than full tenant export.

## Production guardrails

- Collection is customer-scoped or site-scoped by default. Do not use tenant-wide collection as a normal report path.
- The collector reloads the JWT from disk on `401`/`403` responses and retries transient failures, including `429` rate-limit responses.
- The collector respects the documented N-central endpoint concurrency limits:
  - `GET /api/org-units/{orgUnitId}/active-issues`: max `3`
  - `GET /api/customers`, `GET /api/sites`, `GET /api/org-units/{orgUnitId}/devices`, `GET /api/org-units/{orgUnitId}/custom-properties`, `GET /api/devices/{deviceId}/custom-properties`: max `5`
- Site-level issue fan-out and per-device custom-property fan-out are bounded so large customers do not trigger runaway request volume.
- Device custom-property enrichment is adaptive:
  - smaller scopes collect all device properties
  - larger scopes prioritize impacted devices and then stop at a configured cap
- The collector does **not** call `GET /api/devices/{deviceId}/assets/lifecycle-info` because the official docs cap that endpoint at `1` concurrent request, making it unsuitable for routine monthly high-volume collection.
- Do not re-run collection just because drafting, rendering, review-mail, or delivery steps fail later. Reuse the bundle already produced for that run.
