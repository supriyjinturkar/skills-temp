---
name: report-rendering-and-validation
description: Use when the orchestrator is about to render a draft artifact or run any of the three validation passes (data, editorial, QA). Covers PPTX generation rules, Nexon logo binary safety, validation pipeline hand-off detail, review and delivery rules, and expected outputs per run. Load at step 13 of the working method (before first render).
---

# Report Rendering and Validation

Load this skill at the point the draft artifact is about to be rendered — before the first render call and before any validation sub-agent is invoked.

---

## PPTX generation rules

- Always use `python-pptx` native charts (`ChartData` + `slide.shapes.add_chart()`) for all bar, clustered bar, stacked bar, line, and donut charts in PPTX output.
- Never use matplotlib (or any external image-rendering library) to produce charts embedded as images in PPTX — this produces non-editable pixel blobs and is not permitted by Nexon output standards.
- Use matplotlib only as an explicit last resort for chart types that `python-pptx` cannot produce natively, and only if the active skill or the user explicitly permits it.
- Always follow the implementation approach shown in the active brand skill (e.g. `nexon-brand/assets/pptx-guide.md`) — do not substitute a different library because it is faster to write.

---

## Nexon logo — binary asset safety rule

- Never route PNG, JPG, PDF, or PPTX files through memory/text storage or UTF-8 transformations.
- Use only binary reads/writes for logo and image assets.
- Validate the PNG signature `89504E470D0A1A0A` before use.
- If a copied file fails PNG signature validation, fall back to the original upload — do not attempt to repair from text.

---

## Pre-render self-check

Before calling any render tool or script, confirm all of the following are true:

- `run/data_signal_report.json` exists and is complete
- `run/report_blueprint.json` exists and is complete
- every section in the blueprint has a `lead_message`
- every included section references named individual section files
- no section is listed as included but has not been drafted
- the Senior analyst standard has been applied: signal-first structure, interpretation not description, no unsupported claims, visuals for chartable data

If any of these checks fail, resolve the gap before rendering.

---

## Validation pipeline — hand-off detail

**STRICT ENFORCEMENT RULE: The three validation sub-agents MUST run in the exact sequential order below. They MUST NOT be parallelised. Each pass may modify the artifact — the next sub-agent must always review the corrected output from the previous pass.**

### Pass 1 — `reporting-data-validation`

Run before any review handoff or delivery step.

Pass to the sub-agent:
- the rendered artifact or extracted report content
- the run-scoped normalized source bundles
- any saved source snapshots needed to validate claims

Require the sub-agent to return:
- verdict
- claim-level findings
- corrections made
- severity for each finding
- corrected wording or corrected metrics where possible

Let the sub-agent fix any in-scope data issues it can prove from source evidence, then require it to re-run validation before returning.

If the verdict is not a pass, revise remaining issues and re-run `reporting-data-validation` before proceeding to Pass 2.

### Pass 2 — `reporting-editorial-validation`

Run only after `reporting-data-validation` returns a pass.

Pass to the sub-agent:
- the rendered artifact
- the Report Blueprint at `run/report_blueprint.json`
- the Data Signal Report at `run/data_signal_report.json`
- the source bundles

Require the sub-agent to return:
- verdict
- coverage findings (sections in the blueprint absent or under-represented in the report)
- depth findings (sections where data richness was not matched by report depth)
- editorial findings (commentary quality, story coherence, visualisation appropriateness)
- corrections made
- severity for each finding

Let the sub-agent fix what it can, then require it to re-run before returning.

If the verdict is not a pass, revise remaining issues and re-run `reporting-editorial-validation` before proceeding to Pass 3.

### Pass 3 — `reporting-qa`

Run only after `reporting-editorial-validation` returns a pass. Apply to customer-facing HTML and PPT/slide deck outputs.

Pass to the sub-agent:
- the rendered artifact reference
- any preview assets needed for visual inspection

Require the sub-agent to return:
- verdict
- location-based findings
- corrections made
- severity for each finding
- recommended fixes

Let the sub-agent fix any in-scope visual issues it can safely resolve, then require it to re-run QA before returning.

If the verdict is not a pass, revise remaining artifact issues and re-run `reporting-qa` on the affected sections and then on the final artifact skim.

---

## Review and delivery rules

- Keep review state explicit throughout the run.
- Do not mark draft generation complete until the artifact exists and was verified.
- For HTML and PPT artifacts, `verified` means all of the following are true:
  - the file exists on disk
  - `run/data_signal_report.json` exists and is complete
  - `run/report_blueprint.json` exists and is complete
  - the rendered report passed `reporting-data-validation`
  - the rendered report passed `reporting-editorial-validation`
  - the rendered report passed `reporting-qa`
  - any blocker or major findings from all three passes were resolved
  - the report meets the Senior analyst standard: signal-first, interpretive commentary, no unsupported claims, visuals for chartable data, honest about gaps
- Do not mark review handoff complete until the review message is confirmed sent successfully.
- Carry forward the same run bundle and draft artifact references through the entire review loop.
- Use the output format required by the selected customer/report flow — do not assume a rendering format by default.
- Do not treat a render as verified if visible layout defects remain, even when data content is correct.
- If SDM review is required, send the review handoff only after all three validation passes are complete.
- Support revision requests without re-collecting source data unless a true data gap is confirmed.

---

## Expected outputs per run

Every completed run must produce all of the following:

- resolved customer context
- source collection outputs (all three sources attempted: ServiceNow, LogicMonitor, BackupRadar)
- `run/data_signal_report.json` — structured interrogation result
- `run/report_blueprint.json` — explicit section plan with inclusion/exclusion decisions
- normalized multi-source report bundle
- rendered draft artifact
- `reporting-data-validation` verdict and correction log
- `reporting-editorial-validation` verdict and correction log
- `reporting-qa` verdict and correction log
- review state and handoff evidence
- final delivery artifact reference
