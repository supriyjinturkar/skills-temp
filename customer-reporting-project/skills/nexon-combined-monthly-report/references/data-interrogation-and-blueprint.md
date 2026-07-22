# Data Interrogation And Blueprint

Use this reference before drafting a combined Nexon monthly report.

Two artifacts are mandatory before writing report content:

- `run/data_signal_report.json`
- `run/report_blueprint.json`

## Phase 1: Data Interrogation

### Goal

Audit every available section file, identify the strongest signals, and record what is usable, sparse, or empty before drafting.

### Read every section file

Do not rely only on merged bundles.

ServiceNow:
- `run/sections/sn_ticket_summary.json`
- `run/sections/sn_incident_summary.json`
- `run/sections/sn_request_summary.json`
- `run/sections/sn_change_summary.json`
- `run/sections/sn_problem_summary.json`
- `run/sections/sn_sla_summary.json`
- `run/sections/sn_sla_trends.json`
- `run/sections/sn_aged_backlog.json`
- `run/sections/sn_dimensions.json`
- `run/sections/sn_fcr.json`
- `run/sections/sn_critical_incidents.json`

LogicMonitor:
- `run/sections/lm_availability_summary.json`
- `run/sections/lm_alert_trends.json`
- `run/sections/lm_resource_health.json`
- `run/sections/lm_monitoring_coverage.json`
- `run/sections/lm_website_experience.json`
- `run/sections/lm_device_availability.json`
- `run/sections/lm_cpu_memory_utilization.json`
- `run/sections/lm_disk_capacity_utilization.json`
- `run/sections/lm_network_interface_throughput.json`
- `run/sections/lm_inventory_exceptions.json`

BackupRadar:
- `run/sections/br_backup_summary.json`
- `run/sections/br_backup_trends.json`
- `run/sections/br_backup_exceptions.json`

N-central:
- read the normalized section files produced for the run, including inventory, issue, health, posture, and site-rollup outputs

### Classify each section

Assign one label per section:

- `chartable`
- `card_only`
- `table_only`
- `appendix_candidate`
- `empty`

### Extract key metrics

For each populated section, note the metrics or facts most worth surfacing:

- materially high/low values
- meaningful change vs prior period
- risks, breaches, failures, exceptions, or backlog pressure
- strong positive posture worth highlighting

### Identify top signals

Select the 3 to 5 strongest cross-report signals. A top signal should matter to the customer and ideally imply risk, opportunity, or a follow-up action.

### Write `run/data_signal_report.json`

Use this shape:

```json
{
  "customer": "Customer Name",
  "period": "June 2026",
  "generated_at": "2026-07-01T00:00:00Z",
  "sources": {
    "servicenow": {
      "available": true,
      "populated_sections": [],
      "empty_sections": [],
      "card_only_sections": [],
      "chartable_sections": [],
      "table_sections": [],
      "key_metrics": {},
      "anomalies": []
    },
    "logicmonitor": {
      "available": true,
      "populated_sections": [],
      "empty_sections": [],
      "card_only_sections": [],
      "chartable_sections": [],
      "table_sections": [],
      "key_metrics": {},
      "anomalies": []
    },
    "backupradar": {
      "available": true,
      "populated_sections": [],
      "empty_sections": [],
      "card_only_sections": [],
      "chartable_sections": [],
      "table_sections": [],
      "key_metrics": {},
      "anomalies": []
    },
    "ncentral": {
      "available": true,
      "populated_sections": [],
      "empty_sections": [],
      "card_only_sections": [],
      "chartable_sections": [],
      "table_sections": [],
      "key_metrics": {},
      "anomalies": []
    }
  },
  "top_signals": [
    {
      "rank": 1,
      "source": "servicenow",
      "signal": "Short statement of the strongest finding",
      "risk_level": "high",
      "customer_action_needed": true
    }
  ]
}
```

Do not proceed to drafting until this file exists and every attempted source is accounted for.

## Phase 2: Report Blueprint

### Goal

Make inclusion, exclusion, appendix, and visualisation decisions before drafting.

### Rules

- Every non-empty source section must be included, excluded with a reason, or placed in the appendix.
- For each included section, list the exact section files used.
- Write a `lead_message` before drafting the section.
- `visual_type` must be specific, not just `chart`.
- The blueprint is the decision record for later validation passes.

### Write `run/report_blueprint.json`

Use this shape:

```json
{
  "customer": "Customer Name",
  "period": "June 2026",
  "report_family": "monthly-service-review",
  "template_key": "operations-v1",
  "generated_at": "2026-07-01T00:00:00Z",
  "sections": [
    {
      "id": "executive_summary",
      "title": "Executive Summary",
      "sources": ["servicenow", "logicmonitor"],
      "section_files_used": ["sn_ticket_summary", "lm_availability_summary"],
      "visual_type": "kpi_cards_row + observations_list",
      "lead_message": "Write what the section is saying, not what it contains",
      "body_or_appendix": "body"
    }
  ],
  "excluded_sections": [
    {
      "section_file": "lm_website_experience",
      "reason": "No usable data in the reporting window"
    }
  ],
  "appendix_sections": [
    {
      "section_file": "sn_dimensions",
      "reason": "Reference detail supports the main story but does not need body placement"
    }
  ]
}
```

Do not begin drafting until the blueprint is complete.

## Drafting reminder

- Draft from the blueprint and the named section files.
- If the evidence changes, update the blueprint first.
- Keep the strongest signal early.
- Use visuals for chartable data.
- Call out data gaps explicitly.
