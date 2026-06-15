# DemandScience Agent Wiring - Fleet

## Supervisor agent

Recommended name:

- `nexon-reporting-agent`

Attach:

- `customer-report-orchestrator`
- `weekly-service-review`
- shared LogicMonitor MCP tools
- shared rendering and delivery MCP tools

Responsibility:

- accept the report request
- resolve `DemandScience`
- resolve `template_key`
- delegate execution to the DemandScience customer agent
- manage SDM review and final delivery steps
- ensure the generated draft is sent to the configured review delivery emails through `messaging_send_review_email` when SDM review is required

## Customer agent

Recommended name:

- `demandscience-report-agent`

Attach:

- `demandscience-reporting`
- shared LogicMonitor MCP tools
- shared rendering and delivery MCP tools

Responsibility:

- load the selected weekly report guide and HTML template
- invoke the LogicMonitor collector tool once per resolved report run
- reuse the same collected bundle for drafting and rendering
- verify the draft artifact exists at the expected path or preview URL before returning success
- draft the report sections
- return the draft for SDM review
- pass back the draft artifact details needed by the supervisor to send the review mail
