# DemandScience Weekly LogicMonitor Service Review - Template A

## Report identity

- customer: `DemandScience`
- report family: `weekly-service-review`
- template key: `A`
- cadence: `weekly`
- primary datasource: `LogicMonitor`
- report-definition format: markdown only

## Report intent

Template A is the week-1 operating view.

It should look like a Nexon-style service review page, not a flat text summary.

It should emphasize:

- executive posture
- availability
- alert movement through the week
- resource exceptions
- action summary for SDM review

## Presentation rules

- use the HTML template `weekly-logicmonitor-service-review-template-a.html`
- use `ECharts` via CDN for all chart rendering
- use SVG renderer so the shared HTML remains sharp when opened in browser or reviewed from a hosted link
- include both narrative and visuals
- include detail tables for exceptions and top contributors
- do not produce a text-only draft when the required chart datasets are present

## Agenda

1. Executive View
2. Availability and Site Operations
3. Alert Trends
4. Resource Health
5. Detail Tables
6. SDM Commentary and Risks

## Section requirements

### Executive View

- summarize the week in 3 to 5 sentences
- mention overall service posture
- mention whether alert handling remained stable or not
- mention the most important exception
- mention whether any critical devices remained at period end

### Availability and Site Operations

Required metrics and fields:

- `sections.availability_summary.availability_percent`
- `sections.availability_summary.monitored_devices`
- `sections.availability_summary.notable_exceptions`
- `sections.site_operations.sites`

Required output:

- one short paragraph for `{{availability_summary_text}}`
- one chart showing top sites by cleared alert volume using `{{site_operations_json}}`

### Alert Trends

Required metrics and fields:

- `sections.alert_trends.alert_counts_opened`
- `sections.alert_trends.alert_counts_closed`
- `sections.alert_trends.alert_counts_active`
- `sections.alert_trends.clear_rate_percent`
- `sections.alert_trends.daily_alert_flow`
- `sections.alert_trends.alert_severity_breakdown`

Required output:

- one alert flow chart using `{{alert_daily_flow_json}}`
- one severity mix chart using `{{alert_severity_breakdown_json}}`
- one short narrative for `{{alert_trend_summary}}`

### Resource Health

Required metrics and fields:

- `sections.resource_health.healthy_devices`
- `sections.resource_health.warning_devices`
- `sections.resource_health.critical_devices`
- `sections.resource_health.top_unhealthy_resources`
- `sections.alert_trends.top_devices_by_alerts`

Required output:

- one short paragraph for `{{resource_health_summary}}`
- one radar-style health posture chart using `{{health_breakdown_json}}`
- one horizontal bar chart for `{{top_alerting_resources_json}}`

### Detail Tables

Required output:

- `{{top_resources_rows_html}}` must contain the top alerting resources with a useful comment
- `{{exceptions_rows_html}}` must contain notable exceptions plus a clear action statement

### SDM Commentary and Risks

- include one AI-drafted observation block
- include one SDM-editable commentary block
- include one risks/actions block
- narrative should be operationally useful, not generic

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

- MCP live collection tool: `logicmonitor.refresh_report_bundle`
- MCP cached bundle read: `logicmonitor.get_report_bundle`
- call the live collection tool once for the resolved weekly window and tenant, then reuse the cached bundle for every section in this template unless a verified field gap is documented

## Render placeholders

Required HTML placeholders:

- `{{report_title}}`
- `{{period_label}}`
- `{{review_state}}`
- `{{executive_summary}}`
- `{{availability_percent}}`
- `{{availability_subtext}}`
- `{{opened_alerts}}`
- `{{opened_alerts_subtext}}`
- `{{active_alerts}}`
- `{{active_alerts_subtext}}`
- `{{critical_devices}}`
- `{{critical_devices_subtext}}`
- `{{availability_summary_text}}`
- `{{resource_health_summary}}`
- `{{alert_trend_summary}}`
- `{{sdm_commentary}}`
- `{{risks_and_actions}}`
- `{{alert_daily_flow_json}}`
- `{{alert_severity_breakdown_json}}`
- `{{top_alerting_resources_json}}`
- `{{site_operations_json}}`
- `{{health_breakdown_json}}`
- `{{top_resources_rows_html}}`
- `{{exceptions_rows_html}}`

## Data shaping notes

- `{{alert_daily_flow_json}}` should be an array of `{ date, opened, cleared }`
- `{{alert_severity_breakdown_json}}` should be an array of `{ name, value }`
- `{{top_alerting_resources_json}}` should be an array of `{ name, alerts }`
- `{{site_operations_json}}` should be an array of `{ name, cleared_alerts }`
- `{{health_breakdown_json}}` should be an array of `{ name, value, max }`
- keep chart datasets concise enough to stay readable in a shared HTML page
