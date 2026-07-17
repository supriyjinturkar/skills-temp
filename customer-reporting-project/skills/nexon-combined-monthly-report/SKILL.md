---
name: nexon-combined-monthly-report
description: Use when designing, drafting, reviewing, or improving a combined Nexon monthly customer report that merges multiple operational sources into one customer-facing report, especially when choosing useful sections, visuals, metrics, and commentary while preserving source-level depth instead of collapsing the report into a thin executive summary.
---

# Nexon Combined Monthly Report

This skill helps an agent make better combined Nexon monthly customer reports.

Use it when one report needs to bring together multiple sources such as:

- ServiceNow
- LogicMonitor
- BackupRadar
- customer-provided or manually curated operational sections

## How to use this skill

- Treat this skill as guidance, not a mandatory slide-by-slide recipe.
- Use it to improve report quality, section choice, visual choice, and commentary quality.
- Adapt the report to the customer, the reporting month, and the data actually available.
- Do not force every suggested module, visual, or metric into every report.
- Use it as a standalone report-making guide when no other Nexon report-writing skill is attached.
- When the chosen output is HTML, pair this skill with the shared report shell at `/skills/nexon-brand/assets/html-template.html` so report differences come from tabs, sections, and evidence rather than a new layout each time.

## Use this skill for

- interrogating source bundles before drafting - identifying signal vs. noise
- producing the Report Blueprint before any section is written
- deciding what a combined monthly report should contain
- choosing which modules belong in the main body versus appendix
- selecting visuals, charts, tables, and KPI cards for each section
- deciding which metrics are most useful before a section is considered report-ready
- writing customer-facing commentary that is factual, useful, and action-oriented
- reviewing whether a combined report feels thin, repetitive, chart-poor, or over-compressed

## What to read

- For section families, common modules, and optional modules:
  - `references/section-catalog.md`
- For chart, metric, and table expectations by section type:
  - `references/visuals-and-metrics.md`
- For commentary rules, quality gates, and standards-style reporting discipline:
  - `references/commentary-quality-gates.md`
- For recurring patterns observed in reviewed Nexon monthly report decks:
  - `references/sample-deck-signals.md`
- For data interrogation and blueprint guidance:
  - `references/data-interrogation-and-blueprint.md`

## Core guidance

- Think before you write. Interrogate the data first. Build the blueprint second. Draft third.
- Build a combined report, not a stitched summary page followed by source dumps.
- Keep the opening concise, usually around:
  - cover
  - agenda
  - executive posture
- Use a summary-first structure for major service areas where it helps clarity:
  - posture
  - evidence
  - commentary
  - detail or appendix
- Preserve depth from the underlying sources when the data supports it.
- Do not reduce a data-rich source to one thin summary block if the source bundle supports trend, breakdown, exception, or ranked-detail views.
- In most strong combined reports, each major source contributes more than one content view:
  - a posture or summary view
  - an evidence or drill-down view
  - appendix support when needed
- Prefer at least one meaningful visual for each major main-body module when chartable data exists.
- Do not flatten trend-ready source data into narrative paragraphs.
- Do not include a section just because a source exists. Include sections because they add customer value for that month.
- Prefer confident, presentation-ready structure over exhaustive data dumping.
- Keep customer variability explicit:
  - operations-first customers need stronger service-desk, SLA, backlog, and observability coverage
  - security-first customers need stronger security posture, vulnerability, and governance coverage
  - governance-heavy customers need stronger actions, projects, commercials, and planning coverage

## Standards-style reporting rules

- Use exact reporting windows and label them consistently.
- Define the metric scope clearly:
  - in-window
  - trailing three months
  - rolling twelve months
  - point-in-time
- Keep units explicit:
  - percent
  - count
  - hours
  - days
  - devices
  - jobs
- Keep caveats visible when data is incomplete, provisional, excluded, or method-limited.
- Do not claim formal IEEE compliance. Use disciplined, traceable, standards-style reporting behavior instead.

## Combined report behavior

### Before drafting - Data Interrogation

Before writing a single section, perform a full interrogation of every source bundle.

For each source, read every individual section file - not only the merged bundle:

**ServiceNow section files to read:**
- `sn_ticket_summary` - total tickets, class split, opened vs closed
- `sn_incident_summary` - incident volume, priority breakdown
- `sn_request_summary` - request volume, category breakdown
- `sn_change_summary` - change count, risk, outcomes
- `sn_problem_summary` - open problems, recurring patterns
- `sn_sla_summary` - response and resolution SLA percentages, breach counts
- `sn_sla_trends` - month-by-month SLA trend data
- `sn_aged_backlog` - aged open tickets by priority and age bucket
- `sn_dimensions` - top callers, categories, assignment groups
- `sn_fcr` - first-contact resolution rate
- `sn_critical_incidents` - P1/P2 incident details

**LogicMonitor section files to read:**
- `availability_summary` - overall availability posture
- `alert_trends` - alert volume by severity and period
- `resource_health` - unhealthy and critical resources
- `monitoring_coverage` - coverage summary and gaps
- `website_experience` - website/service availability where configured
- `device_availability` - per-device availability breakdown
- `cpu_memory_utilization` - top CPU and memory consumers
- `disk_capacity_utilization` - disk capacity hotspots
- `network_interface_throughput` - top network consumers
- `inventory_exceptions` - devices with monitoring exceptions

**BackupRadar section files to read:**
- `backup_summary` - success rate, protected jobs, protected devices
- `backup_trends` - job outcome trend by period
- `backup_exceptions` - failed, warning, and pending job details

For each section file, note:
- is it populated or empty?
- what are the key metrics and standout values?
- does it have enough data for a chart, or only a KPI card, or is it too sparse?
- is any metric anomalous against prior period data if available?

Identify the 3-5 strongest operational signals for this customer this month. A signal must be either:
- materially better or worse than expected or prior period
- a risk that deserves customer attention
- a result that should drive a customer action or watch item

Write a structured Data Signal Report to `run/data_signal_report.json` before moving to the blueprint.

### Before drafting - Report Blueprint

After interrogation, write a Report Blueprint to `run/report_blueprint.json`.

The blueprint is the explicit decision record for the report. Every section in the final report must trace back to the blueprint. Every non-empty source section must appear in `sections`, `excluded_sections`, or `appendix_sections` - no silent omissions.

For each included section, write the `lead_message` before drafting starts. The lead message forces you to know what the section is saying before you write it.

For each excluded section, write a specific reason.

Only after the blueprint is complete should drafting begin.

### Opening

- Start with report identity and reporting period.
- Use the agenda to orient the reader to the themes actually included for that customer and month.
- Follow reasonably early with an executive summary that shows the overall service posture before drilling into detail.
- The executive summary lead should reflect the top signal from the Data Signal Report.

### Main body

- Build the core report from reusable modules selected from the section catalog.
- A strong module often benefits from:
  - a summary view
  - one supporting visual or evidence view
  - detail only when needed
- When multiple sources are present, use the combined report to organize them well, not to dilute them.
- If one source is shallow because data collection is incomplete, keep that limitation explicit and avoid letting it reduce the depth of stronger available sections.
- Prefer module sequencing that reads from broad operational posture into exceptions, risks, and actions.

### Slide-density rules

- One slide should carry one main message.
- Prefer one chart or table plus one short commentary panel, not multiple competing visual stories on the same slide.
- Do not force four long bullets into one commentary card.
- Prefer at most 3 commentary bullets in one panel.
- Prefer roughly 14 to 16 words or fewer per commentary bullet unless a longer line is unavoidable.
- If commentary exceeds the available space, split it across another slide or move detail into the appendix.
- Do not rely on tiny text, aggressive wrapping, or vertical crowding to keep a slide to one page.
- If a table needs more than a clean presentation-scale row count, continue it on another slide instead of shrinking it.

### Chart-label rules

- Shorten labels aggressively when that improves readability without losing meaning.
- Prefer short month labels such as:
  - `May`
  - `Jun`
  - `Jul (part.)`
- Avoid pie charts when the labels are long, the slices are small, or the labels must compete with percentages inside the chart.
- Prefer bar, stacked bar, clustered bar, or donut views when composition needs to stay readable.
- Do not let legends or data labels overpower the chart itself.
- If the chart needs a paragraph of explanation to be interpretable, choose a clearer visual.

### Appendix

- Use the appendix aggressively for long lists, detailed breach tables, raw inventories, and repeated operational evidence.
- Keep the main body decision-oriented and presentation-scale.
- The appendix should support auditability, not replace the main story.

## Quality checks

- Was a Data Signal Report produced before drafting started?
- Was a Report Blueprint produced before drafting started?
- Does every blueprint section appear in the report?
- Does every non-empty source section appear in the blueprint?
- Can the customer understand the month in the first three to five content slides?
- Does each major module show a visual, not just text and tables?
- Are charts chosen to show movement, comparison, or composition clearly?
- Are metrics labeled with scope, units, and timeframe?
- Are commentary blocks anchored in numbers and operational implications?
- Are commentary blocks short enough to fit cleanly without clipping, crowding, or unreadable wrap?
- Are chart labels, legends, and data labels still readable at presentation scale without collisions?
- Is detailed evidence available without overcrowding the main story?
- Are incomplete sections called out honestly instead of hidden behind generic prose?
- Has the rendered output been visually checked for alignment, overlap, clipping, and spacing issues before review handoff?

## Visualisation selection guide

Use this table to decide the right chart type when data is available:

| Data shape | Preferred visual |
|------------|-----------------|
| Monthly trend (3+ points) | Line chart or column trend |
| Opened vs closed comparison | Clustered bar chart |
| Category breakdown | Stacked bar or horizontal bar |
| Top-N ranking | Horizontal bar chart |
| Posture summary | KPI cards |
| Simple composition (<=5 categories) | Donut chart |
| Mixed operational status | RAG summary table |
| Long exception detail | Detail table in appendix |

Avoid by default:
- Pie charts with more than 5 slices or long labels
- Trend lines with fewer than 3 data points
- Bar charts with a single bar (use a KPI card instead)
- 3D charts
- Dense multi-axis visuals without a clear need

## Edit expectations

This skill should support edits such as:

- turn a thin combined report into a proper summary-plus-drill-down deck
- add missing visuals to sections that already have chartable data
- move overloaded detail tables into appendix slides
- tighten or expand the agenda based on customer module needs
- rewrite commentary so it sounds customer-facing and operationally grounded
- add methodology notes and caveats where the data interpretation would otherwise be misleading
- produce a Data Signal Report and Report Blueprint when starting from scratch

## HTML-specific note

When the report is delivered as HTML:

- use the shared shell at `/skills/nexon-brand/assets/html-template.html`
- preserve the shell's typography, spacing, tab pattern, and footer treatment
- vary the report by changing tabs, panels, visuals, commentary, and appendix notes to match the blueprint
- do not redesign the page just because this month's sections differ from the last report
