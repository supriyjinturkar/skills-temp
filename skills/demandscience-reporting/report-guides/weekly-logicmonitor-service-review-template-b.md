# DemandScience Weekly LogicMonitor Service Review - Template B

## Report identity

- customer: `DemandScience`
- report family: `weekly-service-review`
- template key: `B`
- cadence: `weekly`
- primary datasource: `LogicMonitor`
- report-definition format: markdown only

## Report intent

Template B is the week-2 operational review.

It should keep the same visual quality bar as template A, but shift the emphasis toward monitoring scope, site view, and SDM commentary.

It should emphasize:

- operational highlights
- monitoring coverage
- site-level observations
- alert movement
- commentary and actions

## Presentation rules

- use the HTML template `weekly-logicmonitor-service-review-template-b.html`
- use `ECharts` via CDN for all charts
- include narrative plus charts plus evidence tables
- avoid text-only output when chart data is available

## Agenda

1. Executive Summary
2. Monitoring Coverage
3. Site Operations
4. Alert Trends
5. SDM Commentary and Actions

## Section requirements

### Executive Summary

- summarize the week in 3 to 5 sentences
- mention the most important service observation
- mention one positive or stabilizing point when supported by the data
- mention one action item or follow-up area

### Monitoring Coverage

Required metrics and fields:

- `sections.monitoring_coverage.monitored_devices`
- `sections.monitoring_coverage.unmonitored_devices`
- `sections.monitoring_coverage.monitoring_coverage_percent`
- `sections.availability_summary.availability_percent`

Required output:

- KPI cards for monitored devices, unmonitored devices, site count, and availability
- one summary narrative for coverage posture

### Site Operations

Required metrics and fields:

- `sections.site_operations.sites`
- `sections.availability_summary.sites`

Required output:

- one chart using `{{site_operations_json}}`
- one table using `{{site_rows_html}}`
- mention only the most relevant site observations

### Alert Trends

Required metrics and fields:

- `sections.alert_trends.alert_counts_opened`
- `sections.alert_trends.alert_counts_closed`
- `sections.alert_trends.alert_counts_active`
- `sections.alert_trends.daily_alert_flow`
- `sections.alert_trends.top_devices_by_alerts`

Required output:

- one trend chart using `{{alert_daily_flow_json}}`
- one table of top alerting resources using `{{top_resources_rows_html}}`

### SDM Commentary and Actions

- include an AI-drafted narrative for SDM review
- allow SDM to add customer-specific context
- include short action statements

## Review workflow

- SDM review is required for this report
- after the draft HTML is generated, verify the draft artifact exists at the expected path
- send a review mail using `messaging.send_review_email` only after that artifact verification succeeds
- load the destination addresses from `references/company-profile.md` field `review delivery emails`
- include the customer name, report period, template key, review state, and draft artifact reference in the mail
- mark the draft state as `Draft Generated` only after artifact verification succeeds
- mark the draft state as `SDM Review Pending` only after the review mail is sent successfully

## Collector binding

Preferred collector path for this rollout:

- MCP tool: `logicmonitor.collect_report_bundle`
- call the preferred collector once for the resolved weekly window and reuse that bundle for every section in this template unless a verified field gap is documented
- this bundle is expected to provide the required availability, site, and alert inputs for Template B
- do not add a separate `logicmonitor.collect_availability_summary` call unless the bundle was checked first and found to be missing a required Template B field

## Render placeholders

Required HTML placeholders:

- `{{report_title}}`
- `{{period_label}}`
- `{{executive_summary}}`
- `{{coverage_percent}}`
- `{{monitored_devices}}`
- `{{unmonitored_devices}}`
- `{{review_state}}`
- `{{opened_alerts}}`
- `{{opened_alerts_subtext}}`
- `{{active_alerts}}`
- `{{active_alerts_subtext}}`
- `{{site_count}}`
- `{{site_count_subtext}}`
- `{{availability_percent}}`
- `{{availability_subtext}}`
- `{{site_operations_summary}}`
- `{{sdm_commentary}}`
- `{{actions_summary}}`
- `{{site_operations_json}}`
- `{{alert_daily_flow_json}}`
- `{{site_rows_html}}`
- `{{top_resources_rows_html}}`

## Data shaping notes

- `{{site_operations_json}}` should be an array of site rows shaped for charting
- `{{alert_daily_flow_json}}` should be an array of `{ date, opened, cleared }`
- `{{site_rows_html}}` should focus on the most important site rows, not every site
- `{{top_resources_rows_html}}` should include short interpretation text, not only raw counts
