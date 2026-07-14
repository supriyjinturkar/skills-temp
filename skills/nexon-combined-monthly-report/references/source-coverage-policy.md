# Source Coverage Policy

Use this reference when the report combines multiple collected source bundles and you need to decide what appears in the main body, what moves to appendix, and what may be omitted.

## Coverage contract

Before drafting, enumerate the report-ready sections available from each collected source bundle.

For each section, assign exactly one status:

- `main_body`
- `appendix`
- `omitted_with_reason`
- `unavailable`
- `known_gap`

Do not silently drop a collected section.

## Canonical bundle reading

Prefer `bundle.sections` when it exists.

If a bundle exposes both:

- a canonical `sections` object
- backward-compatible top-level aliases

treat `sections` as the source of truth for coverage accounting.

## Omission rules

`omitted_with_reason` is acceptable only when the reason is explicit and defensible, such as:

- the section duplicates stronger evidence already shown elsewhere
- the section is low-value for this customer and month
- the section is too detailed for the main body and no appendix treatment is needed
- the section is method-limited or too incomplete to present safely

Weak reasons:

- "we already collected it"
- "there was no room"
- "the source was not the strongest"

If a section is not strong enough to show, say why. If it is detailed but still useful, move it to appendix rather than dropping it.

## Minimum source treatment

When a source has more than one usable section, prefer at least:

- one posture or summary view
- one evidence, trend, ranking, or exception view

If you do less than this, explain the reduction in the coverage manifest or in a data-scope note.

## Good coverage behavior

- ServiceNow bundle has ticket, SLA, and backlog sections.
  Classify ticket overview as `main_body`, SLA as `main_body`, backlog detail as `appendix`.
- LogicMonitor bundle has availability, alert trends, resource health, and capacity hotspots.
  Classify availability as `main_body`, alert trends as `main_body`, hotspots as `appendix` if the month is otherwise healthy.
- BackupRadar bundle has summary, trends, exceptions, and operational outcomes.
  Classify summary as `main_body`, exceptions as `main_body` when failures exist or `appendix` when exceptions are minor, trends as `main_body` or `appendix` depending on space.

## Release check

Before handoff, confirm that another reviewer could answer:

- Which collected sections were used?
- Which were moved to appendix?
- Which were omitted and why?
- Which were unavailable because collection failed?
- Which are known source-side gaps?
