# DemandScience LogicMonitor MCP Path

## Collection approach

Use:

- `MCP + skill`

## Preferred tool

- `logicmonitor.refresh_report_bundle`

## Collector rule

- Treat `logicmonitor.refresh_report_bundle` as the default live collection step for the weekly DemandScience report sections defined by the selected guide.
- After refresh, use `logicmonitor.get_report_bundle` as the default cached bundle read for all covered sections, HTML rendering, SDM review handoff, and delivery validation.
- Do not call `logicmonitor.get_availability_summary` or similar narrower collectors for covered sections unless the bundle was checked first and a specific missing field or quality gap was found.
- Do not re-run `logicmonitor.refresh_report_bundle` because of render failures, artifact lookup mistakes, review-mail failures, or other downstream workflow errors unrelated to the dataset itself.
- Re-run the preferred collector only when the collector itself failed, returned an unusable or empty dataset, or a verified required field is missing from the bundle.
- If a supplemental collector is required, record exactly which field or section was missing from the bundle.

## Optional supporting reads

- `logicmonitor.get_cached_collection`
- `logicmonitor.get_collection_status`
- `logicmonitor.get_report_bundle`
- `logicmonitor.list_tenants`

### Cached-read guardrail

- Use `logicmonitor.get_cached_collection` only with the tool's supported arguments.
- Use `tenant_id` and a supported `dataset` value such as `logicmonitor_report_bundle`.
- Do not pass unsupported fields such as `customer_name` to the cached-read tool.
- A cached-read validation error is a workflow bug, not a reason to trigger another live LogicMonitor collection.

## Why this path is preferred

- the MCP collector already handles pagination
- the MCP collector already handles retries and rate limits
- the MCP collector already returns normalized report-ready section inputs
- the MCP collector already supports cached reruns and persistence behavior needed for weekly operations

## Expected runtime flow

1. The customer agent resolves the period and `template_key`.
2. The customer agent resolves the correct `tenant_id`. If needed, it first calls `logicmonitor.list_tenants`.
3. The customer agent invokes `logicmonitor.refresh_report_bundle` once for that run.
4. The customer agent reads the cached result using `logicmonitor.get_report_bundle` or `logicmonitor.get_cached_collection` with dataset `logicmonitor_report_bundle`.
5. The normalized bundle is reused to draft the report sections defined by the selected report guide.
6. The rendering tool `reporting.render_html_report` is called with the selected template and generated content.
7. The draft artifact is written and verified at the expected path or preview URL.
8. Only after artifact verification, the supervisor sends the SDM review mail using `messaging.send_review_email`.
