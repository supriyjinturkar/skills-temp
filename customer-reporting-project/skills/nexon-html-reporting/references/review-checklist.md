# HTML Reporting Review Checklist

## Use this reference for

- reviewing a generated HTML report
- comparing a draft against stronger Nexon references
- deciding whether a report is draft-quality or client-ready

## Scoring lenses

Use these lenses to judge the draft. Score each area as `strong`, `acceptable`, or `weak` when a formal review helps, or use the questions informally while revising.

### Narrative

- Does the report have a clear purpose?
- Does each section advance the story?
- Does the report end with implications or actions?

### Visual quality

- Is there a consistent component system?
- Do sections feel intentional rather than generic?
- Are charts readable and visually aligned with the rest of the page?

### Data credibility

- Are reporting windows explicit?
- Are sources named?
- Are missing or partial datasets disclosed?
- Can every collected report-ready source section be accounted for as main body, appendix, explicit omission, unavailable, or known gap?
- Are any claims unsupported by the visible evidence?

### Operational usefulness

- Does the report identify the main risks?
- Does it distinguish healthy areas from problem areas?
- Does it translate findings into next actions or owner-aligned follow-up?

### Delivery robustness

- Does the report still make sense if remote scripts fail?
- Is the page responsive?
- Is the content export-friendly and screenshot-friendly?

## Frequent red flags

- Mixed dates that are not explained
- Commentary that references months outside the headline period without framing
- Placeholder-style caveats that promise future updates instead of closing the gap cleanly
- A collected source section disappears without being shown, deferred to appendix, or explicitly omitted with a reason
- Missing source attribution
- Generic action items with no owner or operational consequence
- Canvas-only charts with no fallback text
- Long pages with no navigation on dense reports
- Tabs that only jump to anchors while all tab content remains visible in one continuous page

## Strong-report signals

- Explicit source banners or data-scope appendix
- A source-coverage note or appendix that explains what was included, condensed, deferred, or omitted
- Exact date windows
- Honest caveats
- Prioritized recommendations
- Section-by-section evidence plus interpretation
- Consistent severity language such as `Healthy`, `Watch`, `Critical`

## Review heuristics drawn from the Nexon references

### When a Fleet-style report is weaker

- It summarizes well but lacks drill-down detail.
- It shows metrics but not method notes.
- It uses one layout pattern for the whole page.
- It lacks ownership in action sections.
- It contains missing-data notices without compensating structure elsewhere.

These are tendencies to watch for, not assumptions that every Fleet-generated report will have the same issues.

### When a Nexon-style report is stronger

- It shows what the metric means, not just the metric.
- It separates sources by system.
- It explains anomalies and partial coverage.
- It translates issues into concrete next-month priorities.
- It uses richer navigation and a clearer information hierarchy on long pages.

Use these as comparison signals rather than a requirement to mimic a specific reference page.

## Final release questions

- Would a service manager trust this report without a verbal explanation?
- Would a client understand the risks and healthy areas in under five minutes?
- Could another agent trace every important claim back to a section, source, or caveat?
- Is there anything in the report that sounds guessed, padded, or visually unfinished?
