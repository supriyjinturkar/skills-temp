# HTML Reporting Authoring Patterns

## Use this reference for

- building a new HTML service report
- upgrading a weak draft into a client-ready report
- choosing between a summary-style page and a richer reporting product

Treat these as patterns to borrow from, not fixed outlines to fill in mechanically.

## Mandatory shell starting point

- Start Nexon customer reports from `/skills/nexon-brand/assets/html-template.html`.
- Keep the shell stable across reports:
  - fixed black header with embedded logo
  - hero block with title, subtitle, and meta chips
  - sticky tab bar for long reports
  - shared page width, card system, chart wrappers, tables, commentary blocks, and footer
- Adapt the report by changing tab labels, tab panels, section blocks, charts, tables, and appendix notes.
- Do not rebuild the page from scratch unless the report type genuinely does not fit the report template.

## Common report structures

### Monthly service review

A monthly service review often works well with some version of this sequence when the report is tied to one reporting period:

1. Hero
2. Executive summary
3. Service desk or ticket performance
4. SLA and backlog detail
5. Infrastructure health
6. Backup or platform-specific operational sections
7. Actions and recommendations
8. Data scope appendix

### Service intelligence report

A service intelligence report often works well with some version of this sequence when the report is cross-period and insight-heavy:

1. Hero
2. Immediate attention summary
3. Trend or theme analysis
4. Root-cause sections
5. Automation or improvement opportunities
6. Prioritized delivery roadmap
7. Supporting detail tables

## Component patterns that work well

- Fixed brand header with compact metadata
- Hero block with period, audience, and purpose
- Sticky tab bar or compact section navigation for longer reports
- When using tabs, treat them as content toggles, not anchors. Clicking a tab should open that section's panel and keep non-active tab panels hidden rather than jumping the reader to another point in a fully expanded page.
- KPI cards for top-line metrics
- Alert or callout boxes for urgent items
- Source banners for per-system sections
- Chart blocks with short interpretation beneath or beside them
- Priority cards or action tables with owner fields
- Data-scope appendix for caveats and method notes

## Patterns that weaken the report

- One long scroll page with no section rhythm
- Tabs that are only hyperlinks to anchors in a page where every section is already expanded
- Charts without commentary
- Commentary without evidence
- Hidden mixed time windows
- Missing ownership in action sections
- Decorative layout changes between sections
- Client-facing reports that depend on CDN-only rendering for core meaning
- Replacing the shared report shell with a new layout when only the content differs

## Chart guidance

- Prefer inline SVG for stable, portable deliverables.
- Use canvas libraries only when the report environment is known to support them.
- Keep charts simple. Bar charts usually work for volume, progress bars for compliance, horizontal bars for top-N comparisons, and compact tables for caller or device detail.
- Avoid too many chart types in one report.
- Add direct labels when possible so the report is readable in screenshots or exports.

## Data honesty patterns

Prefer stating:

- exact reporting window
- whether the window is monthly, trailing, or partial
- source system by section when known
- whether counts are cumulative, in-window, or point-in-time
- whether metrics cover all assets or only the subset returned by the source

Prefer wording like:

- `Reporting window: 1 Jun 2026 - 30 Jun 2026`
- `Service desk window: trailing 3 months as returned by the API`
- `Availability data was present for 17 of 157 monitored devices`
- `Caller-level breakdown was not available for this period`

## Nexon-style lessons from the reference reports

- Strong reports expose sources and windows early.
- Better monthly reports include section-specific source banners.
- Stronger drafts convert risk into named priorities for the next month.
- Strategic reports go beyond symptoms and explain recurring root causes.
- The best reports do not pretend missing data exists.
- Report differences should show up primarily in content, not in wholesale typography or layout changes.

These are quality signals, not mandatory artifacts. If a report can achieve the same clarity another way, prefer the clearer result.

## Delivery robustness

- Prefer embedded logos or local assets over remote brand assets.
- Test the report without network assumptions when possible.
- Avoid making the chart library a single point of failure for understanding the page.
- Keep HTML and CSS readable enough that another agent can revise them quickly.
- If JavaScript fails, the active panel should still be readable and the report should still make sense.
