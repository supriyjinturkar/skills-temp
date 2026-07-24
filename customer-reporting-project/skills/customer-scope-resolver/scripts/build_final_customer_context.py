from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = CURRENT_DIR.parent
PROJECT_ROOT = SKILL_ROOT.parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the final customer_context.json using fixed seed + resolver scripts."
    )
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--customer-name", default="")
    parser.add_argument("--customer-id", default="")
    parser.add_argument("--period-start", required=True)
    parser.add_argument("--period-end", required=True)
    parser.add_argument("--period-label", default="")
    parser.add_argument("--report-family", default="monthly-service-review")
    parser.add_argument("--template-key", default="operations-v1")
    parser.add_argument("--servicenow-sys-id", required=True)
    parser.add_argument("--servicenow-period-months", type=int, default=0)
    parser.add_argument("--logicmonitor-account-name", default="nexon")
    parser.add_argument("--backupradar-base-url", default="https://api.backupradar.com")
    parser.add_argument("--run-dir", default="run")
    parser.add_argument("--output", default="")
    return parser.parse_args(argv)


def slugify(value: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return lowered.strip("-") or "unknown-customer"


def to_iso(value: str, field_name: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 date string.") from exc
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def derive_period_label(start_iso: str, end_iso: str, explicit_label: str) -> str:
    if explicit_label.strip():
        return explicit_label.strip()
    return f"{start_iso[:10]} to {end_iso[:10]}"


def derive_period_months(start_iso: str, end_iso: str) -> int:
    start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    delta_days = max(1, (end - start).days)
    return max(1, min(24, math.ceil(delta_days / 30)))


def ensure_run_dirs(run_dir: Path) -> None:
    for relative in ("source_snapshots", "normalized", "render", "evidence"):
        (run_dir / relative).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_seed_context(args: argparse.Namespace) -> dict:
    period_start = to_iso(args.period_start, "period-start")
    period_end = to_iso(args.period_end, "period-end")
    customer_name = args.customer_name.strip() or args.company_name.strip()
    customer_id = args.customer_id.strip() or slugify(customer_name)
    period_label = derive_period_label(period_start, period_end, args.period_label)
    period_months = args.servicenow_period_months or derive_period_months(period_start, period_end)
    return {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "company_name": args.company_name.strip(),
        "report_family": args.report_family.strip() or "monthly-service-review",
        "template_key": args.template_key.strip() or "operations-v1",
        "period": {
            "start": period_start,
            "end": period_end,
            "label": period_label,
        },
        "source_scope": {
            "servicenow": {
                "customer_sys_id": args.servicenow_sys_id.strip(),
                "period_months": period_months,
            },
            "logicmonitor": {
                "account_name": args.logicmonitor_account_name.strip() or "nexon",
            },
            "backupradar": {
                "base_url": args.backupradar_base_url.strip() or "https://api.backupradar.com",
            },
            "ncentral": {},
        },
    }


def parse_json_line(text: str) -> dict | None:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def run_resolver(script_name: str, context_path: Path, run_dir: Path) -> dict:
    script_path = CURRENT_DIR / script_name
    completed = subprocess.run(
        [sys.executable, str(script_path), "--context", str(context_path), "--run-dir", str(run_dir)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        error_text = " ".join(completed.stderr.split()).strip() or f"{script_name} failed"
        raise RuntimeError(error_text)
    return parse_json_line(completed.stdout) or {}


def merge_scope(seed_context: dict, run_dir: Path) -> tuple[dict, dict]:
    resolved_files = {
        "logicmonitor": run_dir / "resolved_logicmonitor_scope.json",
        "backupradar": run_dir / "resolved_backupradar_scope.json",
        "ncentral": run_dir / "resolved_ncentral_scope.json",
    }

    merged = json.loads(json.dumps(seed_context))
    confidence = {}

    for source, path in resolved_files.items():
        payload = read_json(path)
        confidence[source] = payload.get("match_confidence", "")
        resolved_scope = (payload.get("resolved_scope") or {}).get(source) or {}
        merged["source_scope"].setdefault(source, {})
        merged["source_scope"][source].update(resolved_scope)

    return merged, confidence


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = Path(args.run_dir).resolve()
    ensure_run_dirs(run_dir)

    context_path = Path(args.output).resolve() if args.output else run_dir / "customer_context.json"
    seed_context = build_seed_context(args)
    write_json(context_path, seed_context)

    lm_result = run_resolver("resolve_logicmonitor_scope.py", context_path, run_dir)
    br_result = run_resolver("resolve_backupradar_scope.py", context_path, run_dir)
    nc_result = run_resolver("resolve_ncentral_scope.py", context_path, run_dir)

    final_context, confidence = merge_scope(seed_context, run_dir)
    write_json(context_path, final_context)

    payload = {
        "ok": True,
        "context_path": str(context_path),
        "resolved_scope_files": {
            "logicmonitor": str(run_dir / "resolved_logicmonitor_scope.json"),
            "backupradar": str(run_dir / "resolved_backupradar_scope.json"),
            "ncentral": str(run_dir / "resolved_ncentral_scope.json"),
        },
        "match_confidence": {
            "logicmonitor": confidence.get("logicmonitor") or lm_result.get("match_confidence", ""),
            "backupradar": confidence.get("backupradar") or br_result.get("match_confidence", ""),
            "ncentral": confidence.get("ncentral") or nc_result.get("match_confidence", ""),
        },
        "selected_scope": {
            "servicenow": final_context["source_scope"]["servicenow"],
            "logicmonitor": {
                "group_identifiers": final_context["source_scope"]["logicmonitor"].get("group_identifiers", []),
                "root_device_group_id": final_context["source_scope"]["logicmonitor"].get("root_device_group_id"),
                "root_website_group_id": final_context["source_scope"]["logicmonitor"].get("root_website_group_id"),
            },
            "backupradar": {
                "customer_id": final_context["source_scope"]["backupradar"].get("customer_id"),
            },
            "ncentral": {
                "customer_id": final_context["source_scope"]["ncentral"].get("customer_id"),
                "org_unit_id": final_context["source_scope"]["ncentral"].get("org_unit_id"),
                "site_ids": final_context["source_scope"]["ncentral"].get("site_ids", []),
            },
        },
    }
    sys.stdout.write(f"{json.dumps(payload)}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1) from error
