#!/usr/bin/env python3
"""Validate that an HTML report preserves the shared Nexon template shell."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_PATTERNS = {
    "header_class": r'<header[^>]+class=["\'][^"\']*\bheader\b',
    "body_offset": r'class=["\'][^"\']*\bbody-offset\b',
    "hero_section": r'<section[^>]+class=["\'][^"\']*\bhero\b',
    "hero_meta": r'class=["\'][^"\']*\bhero-meta\b',
    "tab_bar_wrap": r'class=["\'][^"\']*\btab-bar-wrap\b',
    "tab_bar": r'class=["\'][^"\']*\btab-bar\b',
    "tab_button": r'<button[^>]+class=["\'][^"\']*\btab-btn\b',
    "tab_button_data": r'data-tab=["\'][^"\']+["\']',
    "tab_panel": r'class=["\'][^"\']*\btab-panel\b',
    "tab_panel_data": r'data-tab-panel\b',
    "footer_class": r'class=["\'][^"\']*\bfooter\b',
    "inter_font": r'family=Inter|font-family:\s*["\']?Inter',
    "tab_script": r'setActiveTab\s*\(|aria-label=["\']Report sections["\']',
}

FORBIDDEN_PATTERNS = {
    "dummy_tabs": r'dummy-overview|dummy-detail|Dummy overview|Dummy detail',
    "template_placeholders": r'\{\{[A-Z0-9_]+\}\}',
    "anchor_tabs": r'<a[^>]+href="#tab-',
}


def _count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE | re.MULTILINE))


def validate_html(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")

    checks: dict[str, dict[str, object]] = {}
    blockers: list[str] = []
    warnings: list[str] = []

    for name, pattern in REQUIRED_PATTERNS.items():
        matched = bool(re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE))
        checks[name] = {"passed": matched}
        if not matched:
            blockers.append(f"Missing required template-shell marker: {name}")

    tab_button_count = _count(REQUIRED_PATTERNS["tab_button"], text)
    tab_panel_count = _count(r'<section[^>]+class=["\'][^"\']*\btab-panel\b', text)
    checks["tab_button_count"] = {"passed": tab_button_count >= 2, "count": tab_button_count}
    checks["tab_panel_count"] = {"passed": tab_panel_count >= 2, "count": tab_panel_count}
    if tab_button_count < 2:
        blockers.append("Expected at least 2 tab buttons in the shared template shell.")
    if tab_panel_count < 2:
        blockers.append("Expected at least 2 tab panels in the shared template shell.")

    for name, pattern in FORBIDDEN_PATTERNS.items():
        matched = bool(re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE))
        checks[name] = {"passed": not matched}
        if matched:
            if name == "anchor_tabs":
                blockers.append("Tabs are implemented as anchor links instead of real tab buttons/panels.")
            else:
                blockers.append(f"Forbidden template-shell content present: {name}")

    if "Monthly Infrastructure Report" in text and "tab-bar-wrap" not in text:
        warnings.append("Infrastructure report title detected without the shared tab shell.")

    verdict = "pass" if not blockers else "fail"
    return {
        "html_path": str(path),
        "verdict": verdict,
        "template_compliant": verdict == "pass",
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", required=True, help="Path to the HTML report to validate.")
    parser.add_argument(
        "--output",
        help="Optional path for a JSON validation artifact. Defaults to sibling *.template-shell-validation.json.",
    )
    args = parser.parse_args()

    html_path = Path(args.html).expanduser().resolve()
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else html_path.with_suffix(".template-shell-validation.json")
    )

    result = validate_html(html_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["template_compliant"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
