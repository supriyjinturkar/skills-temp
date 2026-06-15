---
name: demandscience-reporting
description: Use when generating or configuring DemandScience weekly LogicMonitor reports for Nexon on LangSmith Fleet, especially when choosing between weekly template A and template B, invoking the shared LogicMonitor MCP path, and supporting the SDM review and update flow.
---

# DemandScience Reporting - Fleet

This skill is the Fleet-compatible customer reporting pack for DemandScience weekly LogicMonitor service reviews.

## Use this skill for

- DemandScience weekly report generation
- week-1 template A flow
- week-2 template B flow
- SDM draft review and prompt-based updates
- DemandScience-specific wording and section guidance

## What to read

- For customer background:
  - `references/company-profile.md`
- For DemandScience-specific terminology:
  - `references/glossary.md`
- For how this pack should be wired into the supervisor and customer agent:
  - `references/agent-wiring.md`
- For the expected MCP-backed collection path:
  - `references/logicmonitor-mcp-path.md`
- For the actual weekly report definitions:
  - `report-guides/weekly-logicmonitor-service-review-template-a.md`
  - `report-guides/weekly-logicmonitor-service-review-template-b.md`
- For the HTML layouts:
  - `html-templates/weekly-logicmonitor-service-review-template-a.html`
  - `html-templates/weekly-logicmonitor-service-review-template-b.html`

## Important rules

- The report-definition format is markdown only.
- Use `template_key` to choose between template `A` and template `B`.
- Do not put customer credentials in this skill.
- Assume customer-specific datasource credentials are resolved by the MCP service using `customer_id` / tenant configuration.
- Use the shared LogicMonitor MCP path for this Fleet demo flow.
- For weekly LogicMonitor reports, treat `logicmonitor.collect_report_bundle` as the primary collector for all sections it already covers.
- Call the preferred weekly LogicMonitor report-bundle collector once per report run for the resolved customer and reporting window, then reuse that same collected bundle for drafting, rendering, review handoff, and delivery validation.
- Do not call `logicmonitor.collect_availability_summary` or other narrower LogicMonitor collectors unless the bundle is first shown to be missing a required field or unusable for a required section.
- Do not re-collect LogicMonitor data just because HTML rendering failed, the artifact path was wrong, the review-mail step failed, or a cached-read step was miscalled. Fix the downstream step and keep using the collected bundle already produced for that run.
- Keep SDM review mandatory before final delivery.
- After generating and verifying a draft artifact, read `references/company-profile.md` for `review delivery emails` and send the review mail through `messaging.send_review_email`.
- Treat the configured review email list as the default DemandScience SDM review handoff target.
- Validate Azure Blob TTL delivery after artifact generation.

## Packaging note

The overall Fleet design uses:

- a shared supervisor agent
- a DemandScience customer agent or sub-agent
- a shared orchestration skill
- a shared weekly report-family skill
- this customer skill overlay

This checked-in customer pack provides the DemandScience-specific pieces only.
