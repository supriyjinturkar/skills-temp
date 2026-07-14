---
name: nexon-html-reporting
description: Create, review, or upgrade HTML-based service reports, monthly reviews, operational dashboards, or strategic reporting pages, especially when turning collected ServiceNow, LogicMonitor, BackupRadar, or similar managed-service data into branded, evidence-led Nexon-style HTML deliverables. Use when the task involves generating the report itself and the skill should provide flexible guidance on structure, narrative, visuals, caveats, and client readiness for `.html` reports.
---

# HTML Reporting

## Overview

Use this skill to generate polished HTML reports that feel client-ready, auditable, and visually consistent.

Treat this skill as guidance, not a rigid template. Use it to shape good decisions about narrative, structure, presentation, and data honesty while still adapting to the report's purpose, audience, and available evidence.

## What to read

- Read `references/authoring-patterns.md` when building or restructuring an HTML report.
- Read `references/review-checklist.md` when reviewing a draft, scoring quality, or tightening a Fleet-generated report.

## How to use this skill

- Generate the report based on the user request, source data, and context.
- Use this skill as a set of guidelines and patterns, not as a mandatory sequence.
- Borrow the parts that help: report family selection, section rhythm, chart and table choices, source and caveat wording, and QA heuristics.
- Skip or adapt any pattern that does not fit the report.

## Suggested flow

1. Define the report job before writing.
   Clarify the audience, the report type, and the main takeaway the page should leave behind.
2. Choose the report family.
   A monthly service review usually fits period-bound service desk, infrastructure, backup, action, and data-scope reporting. A service intelligence or strategy report usually fits cross-period themes, recurring causes, automation opportunities, and multi-quarter recommendations.
3. Build the shell before filling details.
   Start with the broad structure, navigation, and component system so the page has a deliberate visual rhythm.
   If the report uses tabs, make them real in-page section controls that reveal the active panel on click. Do not implement tabs as plain anchor links to sections that are all rendered in one long scroll.
4. Write evidence-led sections.
   Build or receive a per-source coverage manifest first so every collected report-ready section is accounted for as main body, appendix, explicit omission, unavailable, or known gap.
   Let each section answer a real question and pair charts or metric groups with short interpretation.
5. Be explicit about data scope and caveats.
   Prefer exact reporting windows, named source systems, and direct disclosure of missing or partial coverage.
6. Finish with actions, owners, or next checks.
   When the report supports it, translate risk or opportunity into concrete follow-up.
7. Perform a final HTML QA pass.
   Check narrative, dates, accessibility, responsiveness, consistency, and offline robustness.

Use this flow when it helps, but do not force the report into it if a better shape emerges from the content.

## Core rules

- Prefer self-contained HTML that still reads well if external scripts fail.
- Before drafting, map each collected report-ready source section to main body, appendix, or an explicit omission note. Do not silently drop collected sections.
- Prefer canonical `bundle.sections` objects when source bundles provide them.
- Prefer inline SVG for deterministic charts and diagrams when possible.
- Use external chart libraries only when they materially improve maintainability and the delivery context permits them.
- Keep the visual system intentional, with one brand palette, one type system, and one interaction model.
- If a tabbed layout is used, render only the active tab panel by default and switch panels on click. Do not label simple jump links as tabs.
- Use color semantically, not decoratively.
- Keep tables readable without zooming.
- Keep copy factual and calm, especially in risk sections.
- Never hide uncertainty. If a trend is unavailable, say so. If a reporting window spans multiple months, say so. If a metric covers only a subset of devices or tickets, say so.

These are guardrails, not a narrow spec. The report should still feel authored, context-aware, and purpose-built.

## Nexon-oriented expectations

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
