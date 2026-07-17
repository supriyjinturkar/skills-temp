---
name: nexon-html-reporting
description: Create, review, or upgrade HTML-based service reports, monthly reviews, operational dashboards, or strategic reporting pages, especially when turning collected ServiceNow, LogicMonitor, BackupRadar, N-central, or similar managed-service data into branded, evidence-led Nexon-style HTML deliverables. Use when the task involves generating the report itself and the skill should provide flexible guidance on structure, narrative, visuals, caveats, and client readiness for `.html` reports.
---

# HTML Reporting

## Overview

Use this skill to generate polished HTML reports that feel client-ready, auditable, and visually consistent.

Treat this skill as guidance, not a rigid template. Use it to shape good decisions about narrative, structure, presentation, and data honesty while still adapting to the report's purpose, audience, and available evidence.

## What to read

- Read `references/authoring-patterns.md` when building or restructuring an HTML report.
- Read `references/review-checklist.md` when reviewing a draft, scoring quality, or tightening a Fleet-generated report.
- Read `/skills/nexon-brand/assets/html-template.html` before drafting a report shell. Use it as the default starting point for Nexon HTML reports.

## How to use this skill

- Do not start rendering HTML until the Data Signal Report and Report Blueprint exist. Read `nexon-combined-monthly-report/references/data-interrogation-and-blueprint.md` for how to produce them.
- Generate the report based on the user request, source data, and the Report Blueprint.
- Start from the shared Nexon HTML template at `/skills/nexon-brand/assets/html-template.html` unless the user explicitly requires a different shell.
- Keep the template's visual language intact: fixed header, hero, sticky tabs, content rhythm, cards, chart blocks, tables, footer, and appendix treatment.
- Change the report by replacing customer identity, tab labels, section panels, visuals, tables, and commentary - not by inventing a new layout for each run.
- Use this skill as a set of guidelines and patterns, not as a mandatory sequence.
- Borrow the parts that help: report family selection, section rhythm, chart and table choices, source and caveat wording, and QA heuristics.
- Skip or adapt any pattern that does not fit the report.

## Suggested flow

1. Confirm the Data Signal Report (`run/data_signal_report.json`) exists and all sources are assessed.
2. Confirm the Report Blueprint (`run/report_blueprint.json`) exists with all sections, exclusions, and lead messages.
3. Define the report job before writing HTML.
   Clarify the audience, the report type, and the main takeaway the page should leave behind.
4. Choose the report family.
   A monthly service review usually fits period-bound service desk, infrastructure, backup, action, and data-scope reporting. A service intelligence or strategy report usually fits cross-period themes, recurring causes, automation opportunities, and multi-quarter recommendations.
5. Build the shell before filling details.
   Start from `/skills/nexon-brand/assets/html-template.html`, then adapt its tabs and panels to the active blueprint.
   Keep the overall shell stable across reports so typography, spacing, footer treatment, and navigation remain recognisably Nexon.
   If the report uses tabs, make them real in-page section controls that reveal the active panel on click. Do not implement tabs as plain anchor links to sections that are all rendered in one long scroll.
6. For each section in the blueprint, read the named individual section files and render the section using the specified `visual_type` and `lead_message`.
7. Write evidence-led sections.
   Let each section answer a real question and pair charts or metric groups with short interpretation.
8. Be explicit about data scope and caveats.
   Prefer exact reporting windows, named source systems, and direct disclosure of missing or partial coverage.
9. Finish with actions, owners, or next checks.
   When the report supports it, translate risk or opportunity into concrete follow-up.
10. Perform a final HTML QA pass.
    Check narrative, dates, accessibility, responsiveness, consistency, and offline robustness.

Use this flow when it helps, but do not force the report into it if a better shape emerges from the content.

## Core rules

- Prefer self-contained HTML that still reads well if external scripts fail.
- Prefer inline SVG for deterministic charts and diagrams when possible.
- Use external chart libraries only when they materially improve maintainability and the delivery context permits them.
- Keep the visual system intentional, with one brand palette, one type system, and one interaction model.
- If a tabbed layout is used, render only the active tab panel by default and switch panels on click. Do not label simple jump links as tabs.
- Use color semantically, not decoratively.
- Keep tables readable without zooming.
- Keep copy factual and calm, especially in risk sections.
- Never hide uncertainty. If a trend is unavailable, say so. If a reporting window spans multiple months, say so. If a metric covers only a subset of devices or tickets, say so.
- Every section in the HTML must trace back to a blueprint section. Do not add sections that are not in the blueprint without updating the blueprint first.
- Every chart in the report must use the `visual_type` specified in the blueprint for that section, or must have a documented reason for the change.
- When producing a Nexon customer report, preserve the shared template shell unless the request explicitly requires a materially different page type.

These are guardrails, not a narrow spec. The report should still feel authored, context-aware, and purpose-built.

## Nexon-oriented expectations

- Use the shared template at `/skills/nexon-brand/assets/html-template.html` as the default shell for customer-facing HTML reports.
- Treat tabs, section titles, content blocks, and appendix notes as variable; treat typography, spacing, colour tokens, and component rhythm as stable.
- Use bright, presentation-style layouts rather than dark dashboards unless the existing report family requires otherwise.
- Favor `Inter`, `Arial`, or similarly clean sans-serif typography already seen in the reporting set.
- Use Nexon-like semantic accents consistently, with blue for primary emphasis, green for healthy status, amber for caution, and red for breach, outage, or risk.
- Treat source transparency as a feature, not an appendix afterthought.
- In monthly reviews, include action ownership when the source data supports it.

Do not copy reference reports mechanically. Match their level of clarity and quality, but let the report respond to the actual customer, period, data shape, and message.

## Deliverable standard

A strong HTML report should be:

- visually coherent on desktop and mobile
- understandable without narration
- traceable back to data sources and windows
- explicit about missing or partial data
- strong enough to hand to a client without apologizing for it
- consistent with the Report Blueprint - every included section is present, every excluded section is absent
- consistent with the shared Nexon HTML template unless a documented reason requires divergence
