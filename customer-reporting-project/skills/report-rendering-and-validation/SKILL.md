---
name: report-rendering-and-validation
description: Use when the orchestrator is about to render a draft artifact or run any of the three validation passes. Covers pre-render checks, validation order, hand-off minimums, and review/delivery readiness.
---

# Report Rendering and Validation

Load this skill only when the draft is ready for first render.

## Pre-render checks

Before rendering, confirm:

- `run/data_signal_report.json` exists
- `run/report_blueprint.json` exists
- every included section has a `lead_message`
- every included section names the individual section files it uses
- included sections are drafted
- the draft follows the senior analyst bar: signal-first, interpretive, no unsupported claims, visuals for chartable data
- for HTML output, the shared shell from `skills/nexon-brand/assets/html-template.html` is being preserved rather than replaced

If any check fails, fix it before rendering.

## PPTX and brand safety

- Prefer native `python-pptx` charts for PPTX output.
- Do not convert logo/image binaries through text storage.
- Use binary reads/writes for PNG/JPG/PDF/PPTX assets.
- Follow the active `nexon-brand` skill for exact asset handling.

## Validation order

Run the three validation sub-agents in this exact order and never in parallel:

1. `reporting-data-validation`
2. `reporting-editorial-validation`
3. `reporting-qa`

Use these exact three named subagents for validation, each only for its intended scope. Do not substitute a generic delegated worker for any validation pass.

Each pass may change the artifact. The next pass must review the corrected version.

For HTML reports, run:

```bash
python assets/validate_html_template_shell.py --html /path/to/report.html --output /path/to/run/validation/html_template_shell_validation.json
```

Do this before final QA approval. A failed shell-validation result is a release blocker.

## Hand-off minimums

Pass the minimum context needed for the next step.

- Prefer file references, compact summaries, and targeted excerpts over full raw dumps.
- Do not forward whole source snapshots, bundle bodies, or large debug outputs when a validator only needs a small evidentiary slice.
- Keep correction logs concise and actionable so later turns do not inherit unnecessary prompt weight.

### Pass 1: `reporting-data-validation`

Pass:
- rendered artifact or extracted content
- normalized source bundles
- source snapshots only when needed to verify claims

Require back:
- verdict
- claim-level findings
- corrections made
- severity
- corrected wording or corrected values when provable

If not pass, revise and re-run before moving on.

### Pass 2: `reporting-editorial-validation`

Pass:
- rendered artifact
- `run/report_blueprint.json`
- `run/data_signal_report.json`
- source bundles as needed for depth/coverage review

Require back:
- verdict
- coverage findings
- depth findings
- editorial/visualisation findings
- corrections made
- severity

If not pass, revise and re-run before moving on.

### Pass 3: `reporting-qa`

Pass:
- rendered artifact reference
- preview assets only when needed for visual inspection

Require back:
- verdict
- location-based findings
- corrections made
- severity
- recommended fixes

If not pass, revise and re-run QA on changed sections and then final skim.

## Review and delivery rules

- Do not mark the artifact verified until all three passes are complete.
- Do not send SDM review handoff before all three passes pass.
- Reuse the same source bundles, blueprint, and artifact through revision loops.
- Do not re-collect because rendering or review failed.
- Treat visible layout defects as release blockers even when the numbers are correct.
- Treat shared-template shell drift in customer-facing HTML reports as a release blocker even when the content is otherwise strong.

## Expected run outputs

Every completed run should leave:

- resolved customer context
- source collection outputs for attempted sources
- `run/data_signal_report.json`
- `run/report_blueprint.json`
- rendered draft artifact
- data-validation verdict/log
- editorial-validation verdict/log
- QA verdict/log
- final delivery artifact reference
