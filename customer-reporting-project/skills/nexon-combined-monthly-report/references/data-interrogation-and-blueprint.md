# Data Interrogation And Blueprint

Use this reference when performing the mandatory pre-drafting phases for a combined Nexon monthly report.

These two phases — Data Interrogation and Report Blueprint — must complete before any section of the report is written.

## Why these phases exist

A report creator who starts writing without first auditing what they have will:
- miss populated source sections
- default to only the merged bundle summary and lose section-level depth
- write sections without knowing what lead message they are building toward
- produce a report shaped by convenience rather than by the data's strongest signals

The Data Interrogation and Report Blueprint phases force explicit thinking before writing. Every senior report author does this instinctively. This reference formalises it.

---

## Phase 1: Data Interrogation

### Goal

Audit every section file from every source bundle. Know what data you have, what its shape is, what the strongest signals are, and what is too sparse to include before you write a single word.

### Steps

**Step 1 — Read every individual section file**

Do not read only the merged `bundle.json`. Read each individual section file for every source.

ServiceNow section files:
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

LogicMonitor section files:
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

BackupRadar section files:
- `run/sections/br_backup_summary.json`
- `run/sections/br_backup_trends.json`
- `run/sections/br_backup_exceptions.json`

**Step 2 — Classify each section**

For each section file, assign one of:

| Classification | Meaning |
|----------------|---------|
| `chartable` | Enough trend, breakdown, or ranking data to render a meaningful chart |
| `card_only` | One or a few KPI values — enough for a card, not for a chart |
| `table_only` | Row-level data better suited to a table than a chart |
| `appendix_candidate` | Data worth keeping for reference but not main-body depth |
| `empty` | No usable data — exclude with a reason |

**Step 3 — Extract key metrics per section**

For each populated section, extract the headline metrics and any values that stand out.

Look for:
- values that are materially high or low
- values that have changed significantly vs prior period if prior data is present
- values that indicate risk (SLA breach, failed backup, critical device, aged backlog)
- values that indicate positive news (strong availability, backup success, low incident count)

**Step 4 — Identify top signals**

From all extracted metrics, identify the 3–5 strongest operational signals for this customer this month.

A signal qualifies if it is:
- materially better or worse than expected or prior period
- a risk the customer should know about
- a result that should drive a customer action or watch item

**Step 5 — Write the Data Signal Report**

Write `run/data_signal_report.json` with this structure:

```json
{
  "customer": "Customer Name",
  "period": "June 2026",
  "generated_at": "2026-07-01T00:00:00Z",
  "sources": {
    "servicenow": {
      "available": true,
      "populated_sections": ["sn_ticket_summary", "sn_sla_summary", "sn_sla_trends", "sn_aged_backlog", "sn_incident_summary"],
      "empty_sections": ["sn_fcr"],
      "card_only_sections": ["sn_change_summary", "sn_problem_summary"],
      "chartable_sections": ["sn_ticket_summary", "sn_sla_trends"],
      "table_sections": ["sn_aged_backlog", "sn_dimensions", "sn_critical_incidents"],
      "key_metrics": {
        "total_tickets": 142,
        "incidents": 89,
        "requests": 53,
        "response_sla_pct": 72.4,
        "resolution_sla_pct": 88.1,
        "response_breaches": 38,
        "open_backlog": 24,
        "aged_over_30_days": 9
      },
      "anomalies": [
        "Response SLA dropped from 90.2% in May to 72.4% in June — 18pp decline",
        "Aged backlog over 30 days increased from 4 to 9 items"
      ]
    },
    "logicmonitor": {
      "available": true,
      "populated_sections": ["lm_availability_summary", "lm_alert_trends", "lm_resource_health", "lm_device_availability"],
      "empty_sections": ["lm_website_experience", "lm_network_interface_throughput"],
      "card_only_sections": ["lm_monitoring_coverage"],
      "chartable_sections": ["lm_availability_summary", "lm_alert_trends"],
      "table_sections": ["lm_resource_health", "lm_device_availability"],
      "key_metrics": {
        "overall_availability_pct": 99.6,
        "monitored_devices": 47,
        "critical_devices_at_period_end": 1,
        "total_alerts_in_window": 312,
        "critical_alerts": 8
      },
      "anomalies": [
        "One device (SRV-PROD-04) remained in critical state at period end for 18 days"
      ]
    },
    "backupradar": {
      "available": true,
      "populated_sections": ["br_backup_summary", "br_backup_trends", "br_backup_exceptions"],
      "empty_sections": [],
      "card_only_sections": [],
      "chartable_sections": ["br_backup_trends"],
      "table_sections": ["br_backup_exceptions"],
      "key_metrics": {
        "success_pct": 97.2,
        "total_jobs": 29,
        "failed_jobs": 1,
        "warning_jobs": 2,
        "protected_devices": 18
      },
      "anomalies": []
    }
  },
  "top_signals": [
    {
      "rank": 1,
      "source": "servicenow",
      "signal": "Response SLA at 72.4% — 18pp decline vs May, 38 breaches concentrated in P2 incidents",
      "risk_level": "high",
      "customer_action_needed": true
    },
    {
      "rank": 2,
      "source": "servicenow",
      "signal": "Aged backlog over 30 days grew from 4 to 9 items — open backlog pressure increasing",
      "risk_level": "medium",
      "customer_action_needed": true
    },
    {
      "rank": 3,
      "source": "logicmonitor",
      "signal": "SRV-PROD-04 remained in critical state for 18 days at period end",
      "risk_level": "medium",
      "customer_action_needed": true
    },
    {
      "rank": 4,
      "source": "backupradar",
      "signal": "Backup success at 97.2% across 29 jobs — strong posture, not a risk area this month",
      "risk_level": "low",
      "customer_action_needed": false
    }
  ]
}
```

Do not proceed to the blueprint until this file is written and all three sources are assessed.

---

## Phase 2: Report Blueprint

### Goal

Make all section inclusion, exclusion, and visualisation decisions explicitly before drafting. Write the lead message for every included section before writing the section. Use the blueprint as the decision record that downstream validation passes can check the report against.

### Rules

- Every non-empty source section must appear in `sections`, `excluded_sections`, or `appendix_sections`. No silent omissions.
- For each excluded section, write a specific reason — not just "not relevant."
- For each included section, name the individual section files that will be consumed during drafting.
- Write the `lead_message` before drafting. It must capture what the section is saying, not what it contains.
- `visual_type` must be specific — not just "chart." Name the chart type.

### Blueprint structure

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
      "sources": ["servicenow", "logicmonitor", "backupradar"],
      "section_files_used": [
        "sn_ticket_summary", "sn_sla_summary",
        "lm_availability_summary",
        "br_backup_summary"
      ],
      "visual_type": "kpi_cards_row + 3_to_5_observations_list",
      "lead_message": "SLA breach pressure is the dominant operational risk this month; infrastructure and backup posture are stable",
      "body_or_appendix": "body"
    },
    {
      "id": "service_desk_overview",
      "title": "Service Desk Overview",
      "sources": ["servicenow"],
      "section_files_used": ["sn_ticket_summary", "sn_incident_summary", "sn_request_summary"],
      "visual_type": "kpi_cards + clustered_bar_chart_opened_vs_closed + breakdown_table",
      "lead_message": "142 tickets in June with incident volume unchanged; workload composition is stable",
      "body_or_appendix": "body"
    },
    {
      "id": "sla_performance",
      "title": "SLA Performance",
      "sources": ["servicenow"],
      "section_files_used": ["sn_sla_summary", "sn_sla_trends"],
      "visual_type": "kpi_cards + line_trend_chart_response_and_resolution + breach_summary_table",
      "lead_message": "Response SLA dropped 18pp to 72.4% — P2 incident backlog is the primary driver",
      "body_or_appendix": "body"
    },
    {
      "id": "backlog_health",
      "title": "Backlog and Incident Health",
      "sources": ["servicenow"],
      "section_files_used": ["sn_aged_backlog", "sn_critical_incidents"],
      "visual_type": "kpi_cards + horizontal_bar_aged_by_priority",
      "lead_message": "Open backlog aging is worsening — 9 items over 30 days, up from 4 in May",
      "body_or_appendix": "body"
    },
    {
      "id": "infrastructure_monitoring",
      "title": "Infrastructure and Monitoring",
      "sources": ["logicmonitor"],
      "section_files_used": ["lm_availability_summary", "lm_alert_trends", "lm_resource_health", "lm_device_availability"],
      "visual_type": "kpi_cards + column_alert_trend_chart + resource_health_table",
      "lead_message": "Overall availability strong at 99.6%; one device in critical state for 18 days needs resolution",
      "body_or_appendix": "body"
    },
    {
      "id": "backup_protection",
      "title": "Backup and Data Protection",
      "sources": ["backupradar"],
      "section_files_used": ["br_backup_summary", "br_backup_trends", "br_backup_exceptions"],
      "visual_type": "kpi_cards + stacked_bar_job_outcomes_trend + exceptions_table",
      "lead_message": "Backup posture strong at 97.2% success; 3 exceptions warrant monitoring but not urgent action",
      "body_or_appendix": "body"
    }
  ],
  "appendix_sections": [
    {
      "id": "aged_backlog_detail",
      "title": "Aged Backlog Detail",
      "sources": ["servicenow"],
      "section_files_used": ["sn_aged_backlog"],
      "visual_type": "detail_table",
      "body_or_appendix": "appendix"
    },
    {
      "id": "top_callers_categories",
      "title": "Top Callers and Categories",
      "sources": ["servicenow"],
      "section_files_used": ["sn_dimensions"],
      "visual_type": "horizontal_bar + detail_table",
      "body_or_appendix": "appendix"
    },
    {
      "id": "capacity_utilization",
      "title": "Capacity and Utilisation Detail",
      "sources": ["logicmonitor"],
      "section_files_used": ["lm_cpu_memory_utilization", "lm_disk_capacity_utilization"],
      "visual_type": "detail_table",
      "body_or_appendix": "appendix"
    }
  ],
  "excluded_sections": [
    {
      "id": "sn_fcr",
      "source": "servicenow",
      "reason": "First-contact resolution data empty for June 2026 reporting window"
    },
    {
      "id": "lm_website_experience",
      "source": "logicmonitor",
      "reason": "Website experience monitoring not configured for this customer"
    },
    {
      "id": "lm_network_interface_throughput",
      "source": "logicmonitor",
      "reason": "No network throughput data returned — likely no network devices in scope"
    },
    {
      "id": "sn_change_summary",
      "source": "servicenow",
      "reason": "Change count is 3 for the month — card_only, included in executive summary KPIs only; does not warrant a dedicated section"
    }
  ]
}
```

### Blueprint quality checks

Before moving to drafting, verify:

- every non-empty source section file appears in `sections`, `appendix_sections`, or `excluded_sections`
- every `visual_type` names a specific chart or component — not just "chart"
- every `lead_message` describes what the section is saying, not what data it contains
- the `sections` list follows a logical flow: opening → operational evidence → infrastructure → backup → actions
- the top signal from the Data Signal Report is reflected in at least one section's `lead_message`
- the executive summary `section_files_used` spans all available sources

---

## Checklist before drafting

- [ ] `run/data_signal_report.json` exists and all three sources are assessed
- [ ] Every individual section file has been read (not just the merged bundle)
- [ ] Every non-empty section is classified as chartable, card_only, table_only, appendix_candidate, or empty
- [ ] Top signals are identified and ranked
- [ ] `run/report_blueprint.json` exists with all sections, appendix sections, and excluded sections
- [ ] Every included section has a specific `visual_type` and a `lead_message`
- [ ] No non-empty source section is missing from the blueprint without an `excluded_sections` entry
