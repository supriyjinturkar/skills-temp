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

## Use this skill for

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

## Core guidance

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

### Opening

- Start with report identity and reporting period.
- Use the agenda to orient the reader to the themes actually included for that customer and month.
- Follow reasonably early with an executive summary that shows the overall service posture before drilling into detail.

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

## Edit expectations

This skill should support edits such as:

- turn a thin combined report into a proper summary-plus-drill-down deck
- add missing visuals to sections that already have chartable data
- move overloaded detail tables into appendix slides
- tighten or expand the agenda based on customer module needs
- rewrite commentary so it sounds customer-facing and operationally grounded
- add methodology notes and caveats where the data interpretation would otherwise be misleading
