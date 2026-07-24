---
name: customer-scope-resolver
description: Use when a Nexon reporting agent needs to create the final run-scoped customer_context.json for a customer report with minimal prompt usage. This skill writes a seed customer context, runs the LogicMonitor, BackupRadar, and N-central resolver scripts, merges their resolved_scope outputs, and leaves a final customer_context.json ready for collection pipelines. Use it when only the company identity and ServiceNow sys_id are known and you want a deterministic final context file without reading multiple source skill docs.
---

# Customer Scope Resolver

Use this skill to build the final `/run/customer_context.json` with minimal model involvement.

This skill is for the **context-building stage only**. It does not collect source data and it does not render the report.

## Use this skill for

- creating the final run-scoped `customer_context.json`
- reducing prompt bloat from reading multiple source skill docs
- resolving LogicMonitor, BackupRadar, and N-central scope from a small seed context
- merging all resolved source scope into one final context file before collection starts

## Scripts

- `scripts/build_final_customer_context.py`
- `scripts/resolve_logicmonitor_scope.py`
- `scripts/resolve_backupradar_scope.py`
- `scripts/resolve_ncentral_scope.py`

The three `resolve_*` scripts are thin wrappers around the existing source resolver scripts. Use them from this skill instead of reading the source skills directly during normal runs.

## Required inputs

The agent should already know:

- company name
- customer name
- report period start/end
- report period label
- ServiceNow `customer_sys_id`

The agent should obtain the ServiceNow `customer_sys_id` first via the ServiceNow lookup tool, then call `build_final_customer_context.py`.

## Standard flow

1. Resolve the ServiceNow customer identity with the lookup tool.
2. Do not read the other source skills just to infer context shape.
3. Run:

```bash
python3 skills/customer-scope-resolver/scripts/build_final_customer_context.py \
  --company-name "Altus Financial" \
  --customer-name "Altus Financial" \
  --period-start "2026-06-01T00:00:00Z" \
  --period-end "2026-06-30T23:59:59Z" \
  --period-label "June 2026" \
  --servicenow-sys-id "32e9b1cf93468a102949fc3e1dba100e" \
  --run-dir /path/to/run
```

4. Reuse the produced `/run/customer_context.json` for all downstream collection scripts and the shared source executor.

## What the builder script does

- writes the seed `customer_context.json`
- runs:
  - `resolve_logicmonitor_scope.py`
  - `resolve_backupradar_scope.py`
  - `resolve_ncentral_scope.py`
- reads each `resolved_*_scope.json`
- merges `resolved_scope.logicmonitor`, `resolved_scope.backupradar`, and `resolved_scope.ncentral` into `source_scope`
- rewrites the final `customer_context.json`

## Outputs

- `run/customer_context.json` - final merged context file
- `run/resolved_logicmonitor_scope.json`
- `run/resolved_backupradar_scope.json`
- `run/resolved_ncentral_scope.json`

The builder script prints only a compact JSON result with:

- final context path
- resolved scope file paths
- per-source match confidence

Do not echo the full resolved scope files into chat. Carry forward only the final context path and compact status.
