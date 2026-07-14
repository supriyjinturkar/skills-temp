---
name: servicenow-data-collection
description: Use when a LangSmith Fleet agent needs to resolve a customer identity in ServiceNow, collect all available customer-scoped CSI data via the Nexon ServiceNow MCP tools, normalize it, and build a reusable Nexon report bundle for downstream drafting and rendering.
---

# Nexon ServiceNow Data Collection - Fleet

This skill packages the Python collection pipeline that a Fleet agent runs inside its sandbox for Nexon customer reporting using the ServiceNow MCP tools.

The MCP tools (`lookup_customer__nexon_csi_` and `get_customer_data__nexon_csi_`) are called by the agent **before** running the scripts. The scripts consume the saved MCP responses, normalize them, and produce report-ready output files — they do not call the MCP server directly.

## Use this skill for

- resolving a company name into a ServiceNow `sys_id` via the MCP lookup tool
- collecting all available customer-scoped CSI data for the reporting window via the MCP data tool
- saving the raw MCP response as a run-scoped source snapshot
- normalizing the snapshot into structured, report-friendly sections
- building one reusable ServiceNow report bundle for all downstream drafting, rendering, review, and delivery steps

## Scripts

- `scripts/resolve_servicenow_scope.py`
- `scripts/collect_servicenow_snapshot.py`
- `scripts/normalize_servicenow_collection.py`
- `scripts/build_servicenow_report_bundle.py`
- `scripts/run_servicenow_report_pipeline.py`

## Required run inputs

Create a sandbox-local `customer_context.json` for the current run.

Minimum unresolved context when only the company name is known:

```json
{
  "company_name": "Altus Financial",
  "customer_name": "Altus Financial",
  "period": {
    "start": "2026-06-01T00:00:00Z",
    "end": "2026-06-30T23:59:59Z",
    "label": "June 2026"
  },
  "source_scope": {
    "servicenow": {}
  }
}
```

Minimum direct-collection context when `sys_id` is already resolved:

```json
{
  "customer_id": "altus-financial",
  "customer_name": "Altus Financial",
  "report_family": "monthly-service-review",
  "template_key": "operations-v1",
  "period": {
    "start": "2026-06-01T00:00:00Z",
    "end": "2026-06-30T23:59:59Z",
    "label": "June 2026"
  },
  "source_scope": {
    "servicenow": {
      "customer_sys_id": "32e9b1cf93468a102949fc3e1dba100e",
      "period_months": 3
    }
  }
}
```

No credentials are needed in the context. The MCP tools are called by the agent using the already-configured `nexon-servicenow-uat` MCP server. The agent saves the MCP responses to disk; the scripts read those saved files.

## Agent-side MCP call flow (before running scripts)

The agent MUST perform these steps first and save outputs to the run directory:

### Step 1 — resolve customer (if `customer_sys_id` is not already known)

Call:
```
lookup_customer__nexon_csi_(query="<company_name>")
```

Save response to:
```
run/source_snapshots/servicenow_lookup.json
```

Merge top candidate `sys_id` into `source_scope.servicenow.customer_sys_id` in `customer_context.json`.

### Step 2 — collect CSI data

Call:
```
get_customer_data__nexon_csi_(
  customer_sys_id="<resolved_sys_id>",
  period_months="<N>"
)
```

Where `period_months` is derived from the reporting window. Use 1 for a single-month report, 3 for a quarter, up to 24 for maximum history.

Save full response to:
```
run/source_snapshots/servicenow.json
```

Then run the scripts below to normalize and bundle.

## Standard pipeline flow

1. Write `customer_context.json`.
2. If `customer_sys_id` is unknown, call `lookup_customer__nexon_csi_` and save to `run/source_snapshots/servicenow_lookup.json`.
3. Merge resolved `sys_id` into context.
4. Call `get_customer_data__nexon_csi_` and save full response to `run/source_snapshots/servicenow.json`.
5. Run the end-to-end pipeline or the stepwise normalize → bundle flow.
6. Reuse the produced bundle for all drafting, rendering, review, and delivery steps.

## Resolver flow (scope resolution only)

```bash
python3 skills/servicenow-data-collection/scripts/resolve_servicenow_scope.py \
  --context /path/to/customer_context.json \
  --run-dir /path/to/run
```

Expected output file:
- `run/resolved_servicenow_scope.json`

This script reads `run/source_snapshots/servicenow_lookup.json` (written by the agent from the MCP call) and writes the resolved `sys_id` and top candidates to the output file.

## Collection flow (snapshot save only)

```bash
python3 skills/servicenow-data-collection/scripts/collect_servicenow_snapshot.py \
  --context /path/to/customer_context.json \
  --run-dir /path/to/run
```

This script validates that `run/source_snapshots/servicenow.json` exists and was written by the agent (from the `get_customer_data__nexon_csi_` MCP call), then emits a confirmation. It does NOT call the MCP server itself.

## Normalize flow

```bash
python3 skills/servicenow-data-collection/scripts/normalize_servicenow_collection.py \
  --context /path/to/customer_context.json \
  --run-dir /path/to/run
```

## Bundle flow

```bash
python3 skills/servicenow-data-collection/scripts/build_servicenow_report_bundle.py \
  --context /path/to/customer_context.json \
  --run-dir /path/to/run
```

## End-to-end pipeline (normalize + bundle, after agent MCP calls)

```bash
python3 skills/servicenow-data-collection/scripts/run_servicenow_report_pipeline.py \
  --context /path/to/customer_context.json \
  --run-dir /path/to/run
```

## Run outputs

### Source snapshots (written by agent MCP calls)
- `run/source_snapshots/servicenow_lookup.json` — raw customer lookup response
- `run/source_snapshots/servicenow.json` — raw CSI data response

### Normalized files (written by scripts)
- `run/normalized/sn_ticket_summary.json` — total ticket counts by type, open/closed/cancelled
- `run/normalized/sn_incident_summary.json` — incident counts, priority breakdown, monthly trend
- `run/normalized/sn_request_summary.json` — request item counts and monthly trend
- `run/normalized/sn_change_summary.json` — change counts and monthly trend
- `run/normalized/sn_problem_summary.json` — problem counts and monthly trend
- `run/normalized/sn_sla_summary.json` — response SLA %, resolution SLA %, overall SLA %, breach counts
- `run/normalized/sn_sla_trends.json` — monthly opened vs closed per ticket class
- `run/normalized/sn_aged_backlog.json` — aged bucket breakdown (0-30, 30-60, 60-90, 90+) + aged ticket list
- `run/normalized/sn_dimensions.json` — priority, assignment group, business service, service offering, contact type dimensions
- `run/normalized/sn_fcr.json` — first contact resolution eligible/resolved/pct + rule
- `run/normalized/sn_critical_incidents.json` — P1/P2 incident list
- `run/normalized/servicenow_report_bundle.json` — single merged bundle for all report sections

For downstream drafting, treat `servicenow_report_bundle.json.sections` as the canonical section map.
The bundle also keeps the legacy top-level section keys for backward compatibility.

## Data coverage

The ServiceNow CSI API returns the following data which this skill collects and normalizes:

**Header / identity**
- customer name, customer sys_id, reporting period (months), generated_at timestamp

**Ticket volume totals**
- total, open, closed, cancelled across all ticket classes

**Ticket counts by class**
- Incident, Request Item, Catalog Task, Change, Problem, Project, Project Task, Change Task
- per class: open, closed, cancelled, total

**Monthly opened trend**
- per-month opened counts for each ticket class (up to `period_months` months)

**Monthly closed trend**
- per-month closed counts for each ticket class

**SLA metrics**
- response SLA: met, breached, in_progress, met_pct
- resolution SLA: met, breached, in_progress, met_pct
- overall SLA: met, breached, in_progress, met_pct
- unclassified SLA bucket

**MTTR by priority**
- mean time to resolve per priority (when data is available)

**FCR (First Contact Resolution)**
- eligible count, first_contact count, fcr_pct, rule definition

**Dimensions**
- priority breakdown (top values with counts)
- assignment group breakdown (top values with counts)
- business service breakdown (top values + untagged + completeness %)
- service offering breakdown (top values + untagged + completeness %)
- contact type / channel breakdown (top values + untagged + completeness %)
- aged buckets: 0-30, 30-60, 60-90, 90+ days

**P1/P2 critical incident list**
- row-level detail for critical incidents (when present)

**Aged ticket list**
- row-level list with: number, short_description, state, priority, priority_value, class, assignment_group, caller, opened_at, age_days

**Aged incidents list**
- same schema filtered to incident class only

## Known data gaps (not available from MCP)

These fields are NOT returned by the current MCP API and cannot be collected by this skill:

- category / subcategory breakdown
- caller/requester name as a dimension or top-caller list
- SLA breach detail list (per-ticket breach records)
- monthly SLA breach counts
- per-priority SLA targets and actuals
- open request list (RITM-level rows)
- change detail list (CHG-level rows)
- problem detail list (PRB-level rows)
- CSAT / survey data
- request subtype / classification breakdown (onboarding, offboarding, etc.)
- action register items
- DaaS-specific backlog

When report sections require these fields, note them as "not available from ServiceNow CSI API" in the draft.

## Guardrails

- Always scope collection to the resolved `customer_sys_id`. Do not collect without a resolved sys_id.
- Do not re-run the MCP calls because normalization, bundling, rendering, or delivery steps fail. Reuse the snapshot already saved for that run.
- Do not re-run collection because the report window changed without updating the context and re-calling the MCP tools.
- Treat `run/source_snapshots/servicenow.json` as the run-scoped source of truth for all ServiceNow-backed report sections.
- If `lists.aged_incidents.rows` is empty despite a non-zero total, note the data gap in the bundle but do not fail the pipeline.
- If `mttr_by_priority` is empty, carry it as an empty list in the bundle without error.
