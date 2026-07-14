# Visuals And Metrics

Use this file to choose useful visuals, chart types, metrics, and table depth for each combined-report module.

## Core principles

- Every main-body module should have at least one visual if chartable data exists.
- Prefer these patterns when they improve clarity, not because the report must mechanically include them.
- When a source section has enough usable data, prefer at least:
  - one posture view
  - one evidence view such as a chart, ranked table, or exception summary
  - one short interpretation block
- Use charts to show one of four things:
  - posture
  - trend
  - composition
  - ranking
- Prefer simple business graphics over decorative graphics.
- Avoid charts that look impressive but communicate little.
- Reuse the depth already present in source bundles when available instead of collapsing the source into cards plus prose.

## Preferred chart types

Best default chart choices:

- KPI cards for posture
- line charts for month-over-month or rolling trends
- clustered or stacked columns for opened versus closed or category comparisons
- horizontal bar charts for top categories, top devices, top risks, or top callers
- heatmaps only when there is a true matrix pattern to show
- RAG summary tables for mixed operational status
- detail tables for appendix evidence

Use sparingly:

- donut or pie charts only for small, simple composition views
- gauges only when the customer already expects them

Avoid by default:

- 3D charts
- decorative radar charts
- dense multi-axis visuals without a clear need

## Executive summary

Often useful visuals:

- 4 to 8 KPI cards
- one compact posture summary table or one cross-source scorecard row

Often useful metrics:

- total tickets or workload count
- response SLA percent
- resolution SLA percent
- open backlog count
- monitored availability percent
- active critical devices or alerts
- backup success percent
- protected device count

Typical commentary expectation:

- 3 to 6 bullets or short callouts that explain the month, not just repeat the cards

## Service desk overview

Often useful visuals:

- clustered column chart for ticket class breakdown
- line or column trend for opened-by-month and closed-by-month
- optional horizontal bar chart for top categories or top callers
- optional breakdown table for class, priority, or assignment composition

Often useful metrics:

- total tickets
- incidents
- requests
- changes
- problems
- opened versus closed counts
- priority mix
- top assignment group or service dimension

Good detail table candidates:

- class totals by month
- top caller or top category rows

Depth hint:

- if ServiceNow data is the strongest source for the month, do not stop at one overview panel
- usually expand into SLA and backlog sections as separate evidence views

## SLA performance

Often useful visuals:

- three KPI cards for response, resolution, and overall SLA
- stacked column or segmented bar for met, breached, and in-progress counts
- optional monthly trend if enough time points exist

Often useful metrics:

- response SLA met percent
- resolution SLA met percent
- overall SLA met percent
- breached counts
- in-progress counts
- MTTR if reliable

Good appendix tables:

- breach details
- top breached services
- high-impact breach lists

## Incident and backlog health

Often useful visuals:

- backlog age-bucket column chart
- open-ticket composition by class or priority
- optional horizontal bar chart for top risk queues or owners

Often useful metrics:

- total open tickets
- age bucket counts
- highest-risk age bucket
- critical or high-priority count
- oldest open item age

Good appendix tables:

- aged incident details
- aged request details

## Infrastructure and monitoring

Often useful visuals:

- KPI cards for monitored estate, availability, open alerts, and critical resources
- line trend for alert flow over time
- RAG table for top unhealthy resources
- optional bar chart for top devices or sites by alert count
- optional ranked view for capacity or performance hotspots

Often useful metrics:

- monitored devices
- availability percent
- alerts opened
- alerts cleared
- active alerts at period end
- clear rate percent
- critical devices
- degraded devices
- monitoring coverage gaps

Good appendix tables:

- top unhealthy resources
- device availability detail
- CPU or memory hotspots
- disk-capacity hotspots
- network throughput hotspots

Depth hint:

- if observability data exists beyond simple scope confirmation, prefer at least one posture view and one resource-level evidence view
- if observability data is missing or incomplete, state that clearly rather than pretending the section is fully report-ready

## Backup and data protection

Often useful visuals:

- KPI cards for success rate, protected devices, failed jobs, and warning jobs
- line or stacked column trend for daily or weekly backup outcomes
- summary table for job outcomes by status
- optional exception table when failures, warnings, or restore activity exist

Often useful metrics:

- total jobs
- successful jobs
- failed jobs
- warning jobs
- retried jobs
- skipped or pending jobs
- success rate percent
- protected devices
- destinations

Good appendix tables:

- failed job details
- warning or pending exceptions
- restore exceptions

Depth hint:

- if backup posture is healthy, keep the main body concise but still show real evidence
- if exceptions exist, expand the section rather than hiding the issue behind a success-rate card

## Security posture

Often useful visuals:

- KPI cards for high-level posture
- trend line for event volume or response behavior
- horizontal bar chart for top risks or alert families
- compact risk table with status and owner

Often useful metrics:

- notable events
- time to acknowledge or respond
- top risk families
- unresolved security issues
- critical advisories or mitigations

## Vulnerability management

Often useful visuals:

- column chart for discovered versus remediated
- ranking bar chart for top immediate risks
- trend line for outstanding vulnerability posture

Often useful metrics:

- unique findings
- total findings
- remediated count
- in-progress remediation count
- top 10 immediate risks

## User, lifecycle, calls, and survey modules

Recommended visuals:

- KPI cards
- compact monthly trend
- simple comparison table

Recommended metrics:

- onboarding count
- offboarding count
- service-desk answered versus abandoned
- average wait time
- survey or CSAT count and outcome

## Visual completeness checks

Use these checks before considering a section complete:

- one summary visual minimum for each major main-body module
- no visually important metric left only in narrative text
- no chart without units, timeframe, or data meaning
- no overloaded slide mixing multiple unrelated visuals
- no visual included if the underlying data is missing or untrustworthy
- no text box should overlap decorative bars, status chips, chart frames, or neighboring cards
- labels, sublabels, and status chips should have visible breathing room rather than touching or crossing
- KPI cards should be checked after rendering, not only at authoring time
- a data-rich source should not appear visually weaker in the combined report than it does in its own source-level summary unless there is a deliberate reason

## Missing-data rules

If a visual cannot be generated safely:

- do not fake or infer the series
- replace the chart with:
  - a compact summary table
  - an explicit data note
  - short commentary about the limitation
- keep the section in draft or provisional state when the missing data materially weakens the report
