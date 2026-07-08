# Commentary And Quality Gates

Use this file for writing commentary and deciding whether a combined Nexon monthly report is ready for customer review.

## Commentary rules

- Commentary must interpret the evidence.
- Commentary must not simply restate the chart title or visible numbers.
- Keep commentary short, factual, and directional.
- Anchor every important statement in a metric, count, percent, or clearly described operational event.
- Name why the customer should care:
  - risk
  - progress
  - backlog pressure
  - service improvement
  - dependency
  - next step

## Commentary pattern

For each meaningful section, aim to answer:

1. What changed?
2. Is it good, bad, mixed, or inconclusive?
3. Why does it matter operationally?
4. What should happen next, if anything?

## Good commentary behaviors

- quantify the change
- highlight exceptions
- state caveats when the data is partial
- connect operational evidence across sources when useful
- remain calm and professional even when reporting poor outcomes

## Avoid

- generic filler such as "overall performance remained important"
- vague judgment without numbers
- long paragraphs
- repeating every value already visible in the graphic
- hiding weak or incomplete data behind optimistic language

## Examples Of Useful Commentary

Good:

- Response SLA fell to 2.6%, with 38 breaches in the reporting window, indicating that backlog age rather than intake volume is now the main service risk.
- Backup posture remained strong at 100% success across 29 jobs, so backup risk did not contribute materially to this month's customer actions.
- Alert volume was stable, but one device remained in critical state at period end, so infrastructure risk is concentrated rather than widespread.

Weak:

- SLA performance was low and should be monitored.
- Backups looked good this month.
- Monitoring showed some results.

## Cross-source commentary rules

Use combined commentary only when the evidence supports it.

Good cross-source examples:

- ticket backlog remained high while infrastructure alerts stayed low, suggesting the main delivery pressure this month was service workflow rather than platform instability
- backup success remained strong, so current operational risk is driven more by service backlog and SLA breaches than data protection failures

Do not force cross-source conclusions when the sources are unrelated or incomplete.

## Standards-style quality gates

Before a report is considered ready for customer review, verify:

- report title, customer, and reporting period are correct
- every major metric has a defined timeframe
- units and percentages are labeled consistently
- charts and tables are readable at presentation scale
- the main body contains visuals, not only prose and raw tables
- appendix content is clearly separated from the main story
- caveats and data notes are visible where needed
- no unsupported claims, compliance claims, or speculative root-cause claims are included

## Combined-report readiness checks

Treat the report as materially weak or incomplete if any of these are true:

- the executive summary is only prose and has no KPI posture
- a major source section has chartable data but no visual
- a section contains "pending collection" style placeholder language without a clear draft-state warning
- a module is present but lacks enough evidence to support its commentary
- appendix material has crowded out the main narrative

## Recommended review checklist

1. Is the report customer-specific without becoming customer-fragile?
2. Can an executive understand the month quickly?
3. Can an operational lead find detailed evidence easily?
4. Are the highest-risk items visible?
5. Are actions or watch items explicit where needed?
6. Is any main claim unsupported by visible evidence?
7. Would this feel credible if delivered directly to the customer tomorrow?

## Delivery-state labels

Use explicit state labels when needed:

- `draft`
- `draft with data caveats`
- `review-ready`
- `final`

Do not label a report `final` when source completeness or chart completeness still has known gaps.
