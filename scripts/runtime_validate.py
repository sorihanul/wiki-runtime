from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


CHECK_GUIDANCE: dict[str, dict[str, Any]] = {
    "doc_alignment": {
        "first_files": ["README.md", "START_HERE.md", "MAP.md", "RETRIEVAL_POLICY.md"],
        "first_command": None,
        "why": "Entry documents and entry-surface language are out of sync.",
    },
    "basis_policy": {
        "first_files": ["RETRIEVAL_POLICY.md"],
        "first_command": None,
        "why": "Metadata reliability policy terms are missing or weakened.",
    },
    "load_test": {
        "first_files": ["reports/load_test_m_*.md"],
        "first_command": './scripts/load_test.ps1 -Scale m',
        "why": "Load-test freshness or performance expectations are broken.",
    },
    "artifact_hygiene": {
        "first_files": ["wiki_lite/RAW", "wiki_lite/WIKI", "wiki_lite/LOG", "wiki/syntheses"],
        "first_command": None,
        "why": "Test residue or unnecessary runtime artifacts remain.",
    },
    "operator_alignment": {
        "first_files": ["reports/operator_latest.md", "reports/supervisor_latest.md", "MODE_SURFACE.md"],
        "first_command": './scripts/operator_summary.ps1',
        "why": "Operator, mode, and supervisor surfaces use inconsistent state language.",
    },
    "operator_state_model": {
        "first_files": ["scripts/wiki_runtime.py"],
        "first_command": None,
        "why": "The state branching model does not emit the expected labels.",
    },
    "surface_state_rendering": {
        "first_files": ["scripts/wiki_runtime.py", "reports/operator_latest.md", "reports/supervisor_latest.md"],
        "first_command": './scripts/operator_summary.ps1',
        "why": "State may be computed, but it is not rendered correctly on the document surface.",
    },
    "temp_surface_sandbox": {
        "first_files": ["scripts/runtime_validate.py", "scripts/wiki_runtime.py"],
        "first_command": 'python "./scripts/runtime_validate.py"',
        "why": "Temporary-path surface reads and writes are out of sync.",
    },
    "lock_sandbox": {
        "first_files": ["scripts/wiki_runtime.py", "LOCK_RUNTIME_POLICY.md"],
        "first_command": './scripts/lock_status.ps1',
        "why": "Lock transitions between stale, running, and absent do not match expectation.",
    },
    "archive_sandbox": {
        "first_files": ["scripts/wiki_runtime.py", "REPORT_ARCHIVE_POLICY.md", "reports"],
        "first_command": './scripts/archive_reports.ps1',
        "why": "Protected archive surfaces and movable candidates are out of sync.",
    },
    "latest_surface_sync": {
        "first_files": ["reports/operator_latest.md", "reports/supervisor_latest.md", "reports/governance_latest.md"],
        "first_command": './scripts/operator_summary.ps1',
        "why": "Core latest surfaces are out of sync with the current renderer or cache state.",
    },
    "daily_surface_sync": {
        "first_files": ["reports/governance_daily_YYYYMMDD.md", "reports/supervisor_daily_YYYYMMDD.md"],
        "first_command": './scripts/governance_cycle.ps1',
        "why": "Daily aggregate headers or latest entries are out of sync with the current cache state.",
    },
    "cycle_artifact_suppression": {
        "first_files": ["scripts/wiki_runtime.py", "reports/governance_daily_YYYYMMDD.md", "reports/supervisor_daily_YYYYMMDD.md"],
        "first_command": './scripts/governance_cycle.ps1',
        "why": "Cycle reports or daily entries are growing again even under the same input.",
    },
    "cycle_snapshot_sensitivity": {
        "first_files": ["scripts/wiki_runtime.py", "reports/governance_daily_YYYYMMDD.md", "reports/supervisor_daily_YYYYMMDD.md"],
        "first_command": './scripts/supervisor_cycle.ps1 -Mode intake',
        "why": "Meaningful input changes occur, but new cycle or daily latest entries are not created.",
    },
    "day_boundary_stability": {
        "first_files": ["scripts/wiki_runtime.py", "reports/governance_daily_YYYYMMDD.md", "reports/supervisor_daily_YYYYMMDD.md"],
        "first_command": './scripts/governance_cycle.ps1',
        "why": "When only the date changes, new daily or latest surfaces should update, but identical cycle artifacts should not multiply.",
    },
    "snapshot_precision": {
        "first_files": ["scripts/wiki_runtime.py"],
        "first_command": 'python "./scripts/runtime_validate.py"',
        "why": "The snapshot scope is too wide or too narrow, causing unnecessary regeneration or omission.",
    },
    "queue_field_policy": {
        "first_files": ["scripts/wiki_runtime.py"],
        "first_command": 'python "./scripts/runtime_validate.py"',
        "why": "Queue snapshots react to irrelevant field changes or miss important ones.",
    },
    "lint_field_policy": {
        "first_files": ["scripts/wiki_runtime.py"],
        "first_command": 'python "./scripts/runtime_validate.py"',
        "why": "Lint snapshots react to irrelevant changes or miss signals that matter for lint, maintenance, conflict, or staleness.",
    },
    "lint": {
        "first_files": ["reports/governance_latest.md", "scripts/wiki_runtime.py"],
        "first_command": './scripts/lint.ps1',
        "why": "The current wiki state itself is not clean.",
    },
    "generated_example_sync": {
        "first_files": ["validation/VALIDATION_FAILURE_EXAMPLE.md", "scripts/runtime_validate.py"],
        "first_command": './scripts/generate_validation_failure_example.ps1',
        "why": "The validation-failure example document is out of sync with the current renderer.",
    },
}

CHECK_FOCUS: dict[str, dict[str, str]] = {
    "doc_alignment": {
        "focus": "docs_entry",
        "summary": "Realign entry documents and entry-surface language first.",
    },
    "basis_policy": {
        "focus": "policy_basis",
        "summary": "Realign metadata reliability policy terms and retrieval criteria first.",
    },
    "load_test": {
        "focus": "performance_load",
        "summary": "Recheck the latest load-test run and performance expectations first.",
    },
    "artifact_hygiene": {
        "focus": "artifact_cleanup",
        "summary": "Clean test residue and unnecessary artifacts first.",
    },
    "operator_alignment": {
        "focus": "state_surface",
        "summary": "Realign operator, mode, and supervisor state language.",
    },
    "operator_state_model": {
        "focus": "state_surface",
        "summary": "Realign the state branching model and surface language.",
    },
    "surface_state_rendering": {
        "focus": "state_surface",
        "summary": "Check whether computed state is rendered correctly on surface documents.",
    },
    "temp_surface_sandbox": {
        "focus": "state_surface",
        "summary": "Review temporary-path-based state surface reads and writes.",
    },
    "lock_sandbox": {
        "focus": "lock_runtime",
        "summary": "Restore stale, running, and absent lock transitions first.",
    },
    "archive_sandbox": {
        "focus": "archive_runtime",
        "summary": "Restore the boundary between protected archive surfaces and movable candidates first.",
    },
    "latest_surface_sync": {
        "focus": "state_surface",
        "summary": "Realign operator, supervisor, and governance latest surfaces with the current renderer.",
    },
    "daily_surface_sync": {
        "focus": "state_surface",
        "summary": "Realign governance and supervisor daily headers and latest entries.",
    },
    "cycle_artifact_suppression": {
        "focus": "artifact_cleanup",
        "summary": "Prevent cycle artifacts and daily aggregates from growing again under the same input.",
    },
    "cycle_snapshot_sensitivity": {
        "focus": "artifact_cleanup",
        "summary": "Ensure new cycle artifacts and daily latest entries are created when input changes.",
    },
    "day_boundary_stability": {
        "focus": "artifact_cleanup",
        "summary": "When only the date changes, refresh daily and latest surfaces without regenerating identical cycle artifacts.",
    },
    "snapshot_precision": {
        "focus": "artifact_cleanup",
        "summary": "Align snapshot inputs with real processing scope to reduce unnecessary regeneration and omission.",
    },
    "queue_field_policy": {
        "focus": "artifact_cleanup",
        "summary": "Ensure snapshotting reflects only the fields actually used in queue decisions.",
    },
    "lint_field_policy": {
        "focus": "artifact_cleanup",
        "summary": "Ensure lint snapshots reflect only signals that matter for lint, maintenance, conflict, and staleness.",
    },
    "lint": {
        "focus": "content_quality",
        "summary": "Recover the current wiki state and lint cleanliness first.",
    },
    "generated_example_sync": {
        "focus": "validation_surface",
        "summary": "Realign the derived validation example document with the current renderer.",
    },
}


def load_profile(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def enrich_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for finding in findings:
        updated = dict(finding)
        check = str(finding.get("check", ""))
        guidance = CHECK_GUIDANCE.get(check)
        if guidance is not None:
            updated["guidance"] = {
                "why": guidance["why"],
                "first_files": guidance["first_files"],
                "first_command": guidance["first_command"],
            }
        enriched.append(updated)
    return enriched


def build_next_steps(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for finding in findings:
        check = str(finding.get("check", ""))
        if check in seen:
            continue
        seen.add(check)
        guidance = CHECK_GUIDANCE.get(check)
        if guidance is None:
            continue
        steps.append(
            {
                "check": check,
                "why": guidance["why"],
                "first_files": guidance["first_files"],
                "first_command": guidance["first_command"],
            }
        )
    return steps


def build_repair_focus(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    focus_items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for finding in findings:
        check = str(finding.get("check", ""))
        focus_meta = CHECK_FOCUS.get(check)
        if focus_meta is None:
            continue
        focus = focus_meta["focus"]
        if focus in seen:
            continue
        seen.add(focus)
        related_checks = sorted({str(item.get("check", "")) for item in findings if CHECK_FOCUS.get(str(item.get("check", "")), {}).get("focus") == focus})
        focus_items.append(
            {
                "focus": focus,
                "summary": focus_meta["summary"],
                "related_checks": related_checks,
            }
        )
    return focus_items


def build_synthetic_failure_payload() -> dict[str, Any]:
    synthetic_findings = [
        {"check": "operator_alignment", "path": "reports/supervisor_latest.md", "message": "synthetic mismatch"},
        {"check": "archive_sandbox", "path": "reports/", "message": "synthetic archive drift"},
        {"check": "doc_alignment", "path": "README.md", "message": "synthetic doc drift"},
    ]
    enriched = enrich_findings(synthetic_findings)
    return {
        "profile": "synthetic",
        "status": "fail",
        "finding_count": len(synthetic_findings),
        "findings": enriched,
        "next_steps": build_next_steps(enriched),
        "repair_focus": build_repair_focus(enriched),
    }


def render_validation_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = [
        "# validation-report",
        "",
        f"- profile: `{payload.get('profile', 'unknown')}`",
        f"- status: `{payload.get('status', 'unknown')}`",
        f"- finding_count: `{payload.get('finding_count', 0)}`",
        "",
    ]

    repair_focus = payload.get("repair_focus", [])
    if isinstance(repair_focus, list):
        lines.append("## repair focus")
        if repair_focus:
            for item in repair_focus:
                lines.append(f"- focus: `{item.get('focus', 'unknown')}`")
                lines.append(f"  summary: `{item.get('summary', 'unknown')}`")
                related = item.get("related_checks", [])
                if isinstance(related, list) and related:
                    lines.append(f"  related_checks: `{', '.join(str(value) for value in related)}`")
        else:
            lines.append("- none")
        lines.append("")

    next_steps = payload.get("next_steps", [])
    if isinstance(next_steps, list):
        lines.append("## next steps")
        if next_steps:
            for step in next_steps:
                lines.append(f"- check: `{step.get('check', 'unknown')}`")
                lines.append(f"  why: `{step.get('why', 'unknown')}`")
                first_files = step.get("first_files", [])
                if isinstance(first_files, list) and first_files:
                    lines.append(f"  first_files: `{', '.join(str(value) for value in first_files)}`")
                if step.get("first_command"):
                    lines.append(f"  first_command: `{step.get('first_command')}`")
        else:
            lines.append("- none")
        lines.append("")

    findings = payload.get("findings", [])
    if isinstance(findings, list):
        lines.append("## findings")
        if findings:
            for finding in findings:
                lines.append(f"- check: `{finding.get('check', 'unknown')}`")
                lines.append(f"  path: `{finding.get('path', 'unknown')}`")
                lines.append(f"  message: `{finding.get('message', 'unknown')}`")
                guidance = finding.get("guidance", {})
                if isinstance(guidance, dict) and guidance:
                    lines.append(f"  why: `{guidance.get('why', 'unknown')}`")
                    first_files = guidance.get("first_files", [])
                    if isinstance(first_files, list) and first_files:
                        lines.append(f"  first_files: `{', '.join(str(value) for value in first_files)}`")
                    if guidance.get("first_command"):
                        lines.append(f"  first_command: `{guidance.get('first_command')}`")
        else:
            lines.append("- none")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_payload(payload: dict[str, Any], output_format: str) -> str:
    if output_format == "markdown":
        return render_validation_markdown(payload)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def emit_payload(payload: dict[str, Any], output_format: str, output_path: str | None) -> None:
    text = render_payload(payload, output_format)
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text)


def run_lint() -> dict[str, Any]:
    result = subprocess.run(
        ["python", str(ROOT / "scripts" / "wiki_runtime.py"), "workflow-lint"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def run_json_command(*args: str) -> dict[str, Any]:
    result = subprocess.run(
        ["python", str(ROOT / "scripts" / "wiki_runtime.py"), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def load_wiki_runtime_module() -> Any:
    sys.path.insert(0, str(ROOT / "scripts"))
    import wiki_runtime  # type: ignore

    return wiki_runtime


def latest_matching_report(glob_pattern: str) -> Path | None:
    matches = sorted(ROOT.glob(glob_pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def normalized_text(text: str) -> str:
    return text.replace("`", "").replace("\r", "").lower()


def normalize_surface_text(text: str) -> str:
    lines = []
    for line in text.replace("\r", "").splitlines():
        stripped = line.strip()
        if stripped.startswith("- refreshed_at: `"):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def split_daily_sections(text: str) -> list[list[str]]:
    sections: list[list[str]] = []
    current: list[str] = []
    for raw_line in text.replace("\r", "").splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            if current:
                sections.append(current)
            current = [line]
            continue
        if current:
            current.append(line)
    if current:
        sections.append(current)
    return sections


def normalize_daily_entry(lines: list[str]) -> str:
    trimmed = [line.rstrip() for line in lines]
    while trimmed and trimmed[-1] == "":
        trimmed.pop()
    return "\n".join(trimmed).strip()


def check_doc_alignment(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    doc_cfg = profile["doc_alignment"]
    required_terms = [term.lower() for term in doc_cfg["required_terms"]]
    for relative in doc_cfg["files"]:
        path = ROOT / relative
        text = normalized_text(path.read_text(encoding="utf-8"))
        missing = [term for term in required_terms if term not in text]
        if missing:
            findings.append({"check": "doc_alignment", "path": relative, "message": f"missing terms: {', '.join(missing)}"})
    return findings


def check_basis_policy(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    text = (ROOT / "RETRIEVAL_POLICY.md").read_text(encoding="utf-8")
    for term in profile["basis_policy"]["required_terms"]:
        if term not in text:
            findings.append({"check": "basis_policy", "path": "RETRIEVAL_POLICY.md", "message": f"missing term: {term}"})
    return findings


def check_latest_surface_sync(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    wiki_runtime = load_wiki_runtime_module()

    governance_cached = wiki_runtime.read_state(wiki_runtime.GOVERNANCE_CYCLE_CACHE)
    governance_payload = governance_cached.get("payload")
    governance_report_paths = governance_cached.get("report_paths")
    if not isinstance(governance_payload, dict) or not isinstance(governance_report_paths, dict):
        findings.append(
            {
                "check": "latest_surface_sync",
                "path": "reports/governance_latest.md",
                "message": "governance cache payload or report paths are missing",
            }
        )
    else:
        expected_governance = wiki_runtime.build_governance_latest_body(governance_payload, governance_report_paths)
        actual_governance = wiki_runtime.GOVERNANCE_LATEST.read_text(encoding="utf-8")
        if normalize_surface_text(actual_governance) != normalize_surface_text(expected_governance):
            findings.append(
                {
                    "check": "latest_surface_sync",
                    "path": "reports/governance_latest.md",
                    "message": "governance_latest is out of sync with current renderer output",
                }
            )

    supervisor_cached = wiki_runtime.read_state(wiki_runtime.SUPERVISOR_CYCLE_CACHE)
    supervisor_payload = supervisor_cached.get("payload")
    if not isinstance(supervisor_payload, dict):
        findings.append(
            {
                "check": "latest_surface_sync",
                "path": "reports/supervisor_latest.md",
                "message": "supervisor cache payload is missing",
            }
        )
    else:
        expected_supervisor = wiki_runtime.build_supervisor_latest_body(supervisor_payload)
        actual_supervisor = wiki_runtime.SUPERVISOR_LATEST.read_text(encoding="utf-8")
        if normalize_surface_text(actual_supervisor) != normalize_surface_text(expected_supervisor):
            findings.append(
                {
                    "check": "latest_surface_sync",
                    "path": "reports/supervisor_latest.md",
                    "message": "supervisor_latest is out of sync with current renderer output",
                }
            )

    governance = wiki_runtime.read_cycle_payload(wiki_runtime.GOVERNANCE_CYCLE_CACHE, ["report_path"])
    supervisor = wiki_runtime.read_cycle_payload(wiki_runtime.SUPERVISOR_CYCLE_CACHE, ["report_path"])
    status = wiki_runtime.status_payload()
    operator_payload = {
        "generated_at": status.get("generated_at", "unknown"),
        "report_path": str(wiki_runtime.OPERATOR_LATEST),
        "status": status,
        "governance": governance or {},
        "supervisor": supervisor or {},
    }
    action_plan = wiki_runtime.operator_action_plan(status, governance)
    operator_payload["action_plan"] = action_plan
    operator_payload["actions"] = action_plan.get("actions", [])
    expected_operator = wiki_runtime.build_operator_latest_body(operator_payload)
    actual_operator = wiki_runtime.OPERATOR_LATEST.read_text(encoding="utf-8")
    if normalize_surface_text(actual_operator) != normalize_surface_text(expected_operator):
        findings.append(
            {
                "check": "latest_surface_sync",
                "path": "reports/operator_latest.md",
                "message": "operator_latest is out of sync with current renderer output",
            }
        )

    return findings


def check_daily_surface_sync(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    wiki_runtime = load_wiki_runtime_module()

    governance_cached = wiki_runtime.read_state(wiki_runtime.GOVERNANCE_CYCLE_CACHE)
    governance_payload = governance_cached.get("payload")
    governance_report_paths = governance_cached.get("report_paths")
    if not isinstance(governance_payload, dict) or not isinstance(governance_report_paths, dict):
        findings.append(
            {
                "check": "daily_surface_sync",
                "path": "reports/governance_daily_YYYYMMDD.md",
                "message": "governance cache payload or report paths are missing",
            }
        )
    else:
        daily_path = wiki_runtime.governance_daily_path(governance_payload)
        if not daily_path.exists():
            findings.append(
                {
                    "check": "daily_surface_sync",
                    "path": str(daily_path.relative_to(ROOT)),
                    "message": "governance daily file is missing",
                }
            )
        else:
            text = daily_path.read_text(encoding="utf-8")
            expected_header = f"# governance-daily-{wiki_runtime.governance_generated_date(governance_payload)}"
            expected_day = f"- day: `{wiki_runtime.governance_generated_date(governance_payload)}`"
            if expected_header not in text:
                findings.append(
                    {
                        "check": "daily_surface_sync",
                        "path": str(daily_path.relative_to(ROOT)),
                        "message": "governance daily header is missing or drifted",
                    }
                )
            if expected_day not in text:
                findings.append(
                    {
                        "check": "daily_surface_sync",
                        "path": str(daily_path.relative_to(ROOT)),
                        "message": "governance daily day marker is missing or drifted",
                    }
                )
            governance_name = Path(str(governance_payload.get("report_path", ""))).name
            matching_sections = [
                section
                for section in split_daily_sections(text)
                if any(line == f"- governance: [{governance_name}]({governance_name})" for line in section)
            ]
            if len(matching_sections) != 1:
                findings.append(
                    {
                        "check": "daily_surface_sync",
                        "path": str(daily_path.relative_to(ROOT)),
                        "message": f"expected exactly one governance daily entry for {governance_name}, got {len(matching_sections)}",
                    }
                )
            else:
                expected_entry = normalize_daily_entry(wiki_runtime.build_governance_daily_entry(governance_payload, governance_report_paths))
                actual_entry = normalize_daily_entry(matching_sections[0])
                if actual_entry != expected_entry:
                    findings.append(
                        {
                            "check": "daily_surface_sync",
                            "path": str(daily_path.relative_to(ROOT)),
                            "message": "governance daily latest entry is out of sync with current renderer output",
                        }
                    )

    supervisor_cached = wiki_runtime.read_state(wiki_runtime.SUPERVISOR_CYCLE_CACHE)
    supervisor_payload = supervisor_cached.get("payload")
    if not isinstance(supervisor_payload, dict):
        findings.append(
            {
                "check": "daily_surface_sync",
                "path": "reports/supervisor_daily_YYYYMMDD.md",
                "message": "supervisor cache payload is missing",
            }
        )
    else:
        daily_path = wiki_runtime.supervisor_daily_path(supervisor_payload)
        if not daily_path.exists():
            findings.append(
                {
                    "check": "daily_surface_sync",
                    "path": str(daily_path.relative_to(ROOT)),
                    "message": "supervisor daily file is missing",
                }
            )
        else:
            text = daily_path.read_text(encoding="utf-8")
            expected_header = f"# supervisor-daily-{wiki_runtime.supervisor_generated_date(supervisor_payload)}"
            expected_day = f"- day: `{wiki_runtime.supervisor_generated_date(supervisor_payload)}`"
            if expected_header not in text:
                findings.append(
                    {
                        "check": "daily_surface_sync",
                        "path": str(daily_path.relative_to(ROOT)),
                        "message": "supervisor daily header is missing or drifted",
                    }
                )
            if expected_day not in text:
                findings.append(
                    {
                        "check": "daily_surface_sync",
                        "path": str(daily_path.relative_to(ROOT)),
                        "message": "supervisor daily day marker is missing or drifted",
                    }
                )
            supervisor_name = Path(str(supervisor_payload.get("report_path", ""))).name
            matching_sections = [
                section
                for section in split_daily_sections(text)
                if any(line == f"- supervisor: [{supervisor_name}]({supervisor_name})" for line in section)
            ]
            if len(matching_sections) != 1:
                findings.append(
                    {
                        "check": "daily_surface_sync",
                        "path": str(daily_path.relative_to(ROOT)),
                        "message": f"expected exactly one supervisor daily entry for {supervisor_name}, got {len(matching_sections)}",
                    }
                )
            else:
                expected_entry = normalize_daily_entry(wiki_runtime.build_supervisor_daily_entry(supervisor_payload))
                actual_entry = normalize_daily_entry(matching_sections[0])
                if actual_entry != expected_entry:
                    findings.append(
                        {
                            "check": "daily_surface_sync",
                            "path": str(daily_path.relative_to(ROOT)),
                            "message": "supervisor daily latest entry is out of sync with current renderer output",
                        }
                    )

    return findings


def check_cycle_artifact_suppression(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    wiki_runtime = load_wiki_runtime_module()

    originals = {
        "ROOT": wiki_runtime.ROOT,
        "REPORTS_ROOT": wiki_runtime.REPORTS_ROOT,
        "STATE_ROOT": wiki_runtime.STATE_ROOT,
        "REPORT_ARCHIVE_ROOT": wiki_runtime.REPORT_ARCHIVE_ROOT,
        "GOVERNANCE_CYCLE_CACHE": wiki_runtime.GOVERNANCE_CYCLE_CACHE,
        "SUPERVISOR_CYCLE_CACHE": wiki_runtime.SUPERVISOR_CYCLE_CACHE,
        "GOVERNANCE_LATEST": wiki_runtime.GOVERNANCE_LATEST,
        "SUPERVISOR_LATEST": wiki_runtime.SUPERVISOR_LATEST,
        "OPERATOR_LATEST": wiki_runtime.OPERATOR_LATEST,
        "ensure_dirs": wiki_runtime.ensure_dirs,
        "timestamp": wiki_runtime.timestamp,
        "current_date": wiki_runtime.current_date,
        "slug_timestamp": wiki_runtime.slug_timestamp,
        "governance_input_snapshot": wiki_runtime.governance_input_snapshot,
        "maintenance_report": wiki_runtime.maintenance_report,
        "conflict_report": wiki_runtime.conflict_report,
        "staleness_report": wiki_runtime.staleness_report,
        "build_promotion_queue_entries": wiki_runtime.build_promotion_queue_entries,
        "build_update_queue_entries": wiki_runtime.build_update_queue_entries,
        "generate_repair_queue": wiki_runtime.generate_repair_queue,
        "generate_promotion_queue": wiki_runtime.generate_promotion_queue,
        "generate_update_queue": wiki_runtime.generate_update_queue,
        "archive_advisory": wiki_runtime.archive_advisory,
        "status_payload": wiki_runtime.status_payload,
        "workflow_ingest": wiki_runtime.workflow_ingest,
        "workflow_compile": wiki_runtime.workflow_compile,
    }

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            sandbox_root = Path(temp_dir)
            reports_root = sandbox_root / "reports"
            state_root = sandbox_root / "_runtime_state"
            archive_root = reports_root / "archive"
            reports_root.mkdir(parents=True, exist_ok=True)
            state_root.mkdir(parents=True, exist_ok=True)

            wiki_runtime.ROOT = sandbox_root
            wiki_runtime.REPORTS_ROOT = reports_root
            wiki_runtime.STATE_ROOT = state_root
            wiki_runtime.REPORT_ARCHIVE_ROOT = archive_root
            wiki_runtime.GOVERNANCE_CYCLE_CACHE = state_root / "governance_cycle_cache.json"
            wiki_runtime.SUPERVISOR_CYCLE_CACHE = state_root / "supervisor_cycle_cache.json"
            wiki_runtime.GOVERNANCE_LATEST = reports_root / "governance_latest.md"
            wiki_runtime.SUPERVISOR_LATEST = reports_root / "supervisor_latest.md"
            wiki_runtime.OPERATOR_LATEST = reports_root / "operator_latest.md"
            wiki_runtime.ensure_dirs = lambda: None
            wiki_runtime.timestamp = lambda: "2026-04-15 00:00:00"
            wiki_runtime.current_date = lambda: "2026-04-15"
            slug_counter = {"value": 0}

            def next_slug() -> str:
                slug_counter["value"] += 1
                return f"20260415_00000{slug_counter['value']}"

            wiki_runtime.slug_timestamp = next_slug
            wiki_runtime.governance_input_snapshot = lambda: "stable-governance-snapshot"
            wiki_runtime.maintenance_report = lambda: {
                "generated_at": "2026-04-15 00:00:00",
                "canon_missing_metadata": [],
                "lite_missing_metadata": [],
                "stale_candidates": [],
                "review_candidates": [],
                "basis_review_candidates": [],
                "superseded_notes": [],
                "conflict_candidates": [],
                "duplicate_titles": [],
                "static_lint": {
                    "generated_at": "2026-04-15 00:00:00",
                    "broken_wikilinks": [],
                    "broken_evidence_refs": [],
                    "empty_core_sections": [],
                },
            }
            wiki_runtime.conflict_report = lambda: {
                "generated_at": "2026-04-15 00:00:00",
                "explicit_conflicts": [],
                "duplicate_titles": [],
                "divergent_duplicates": [],
                "shared_sources": [],
            }
            wiki_runtime.staleness_report = lambda: {
                "generated_at": "2026-04-15 00:00:00",
                "thresholds": {"canon_days": 90, "lite_days": 7, "review_days": 30},
                "forced_stale": [],
                "canon_age_stale": [],
                "lite_review_overdue": [],
                "canon_review_overdue": [],
            }
            wiki_runtime.build_promotion_queue_entries = lambda: []
            wiki_runtime.build_update_queue_entries = lambda: []
            wiki_runtime.generate_repair_queue = lambda bundle: {
                "report_path": str(reports_root / "repair_queue_fixed.md"),
                "item_count": 0,
            }
            wiki_runtime.generate_promotion_queue = lambda entries: {
                "report_path": str(reports_root / "promotion_queue_fixed.md"),
                "ready_count": 0,
                "review_count": 0,
                "blocked_count": 0,
            }
            wiki_runtime.generate_update_queue = lambda entries: {
                "report_path": str(reports_root / "update_queue_fixed.md"),
                "refresh_existing_count": 0,
                "review_merge_count": 0,
            }
            wiki_runtime.archive_advisory = lambda threshold=10: {
                "generated_at": "2026-04-15 00:00:00",
                "archive_root": str(archive_root),
                "protected_count": 0,
                "candidate_count": 0,
                "should_archive": False,
                "threshold": threshold,
                "sample_candidates": [],
            }
            wiki_runtime.status_payload = lambda: {
                "generated_at": "2026-04-15 00:00:00",
                "lock_running_count": 0,
                "lock_stale_count": 0,
                "archive_candidate_count": 0,
                "archive_should_run": False,
            }
            wiki_runtime.workflow_ingest = lambda: {
                "workflow": "ingest",
                "generated_at": "2026-04-15 00:00:00",
                "processed_count": 0,
                "skipped_count": 0,
                "processed": [],
                "skipped": [],
            }
            wiki_runtime.workflow_compile = lambda: {
                "workflow": "compile",
                "generated_at": "2026-04-15 00:00:00",
                "built": [],
            }

            for fixed_report in [
                reports_root / "repair_queue_fixed.md",
                reports_root / "promotion_queue_fixed.md",
                reports_root / "update_queue_fixed.md",
            ]:
                fixed_report.write_text("# fixed\n", encoding="utf-8")

            governance_first = wiki_runtime.generate_governance_cycle()
            governance_second = wiki_runtime.generate_governance_cycle()
            if governance_first.get("report_path") != governance_second.get("report_path"):
                findings.append(
                    {
                        "check": "cycle_artifact_suppression",
                        "path": "generate_governance_cycle",
                        "message": "governance cycle reused input but created a different report path",
                    }
                )

            governance_reports = sorted(reports_root.glob("governance_cycle_*.md"))
            if len(governance_reports) != 1:
                findings.append(
                    {
                        "check": "cycle_artifact_suppression",
                        "path": "reports/governance_cycle_*.md",
                        "message": f"expected exactly one governance cycle report, got {len(governance_reports)}",
                    }
                )

            governance_daily = wiki_runtime.governance_daily_path(governance_first)
            governance_text = governance_daily.read_text(encoding="utf-8")
            governance_name = Path(str(governance_first.get("report_path", ""))).name
            governance_sections = [
                section for section in split_daily_sections(governance_text)
                if any(line == f"- governance: [{governance_name}]({governance_name})" for line in section)
            ]
            if len(governance_sections) != 1:
                findings.append(
                    {
                        "check": "cycle_artifact_suppression",
                        "path": str(governance_daily.relative_to(sandbox_root)),
                        "message": f"expected one governance daily entry after repeated cycle, got {len(governance_sections)}",
                    }
                )

            wiki_runtime.archive_advisory = lambda threshold=10: {
                "generated_at": "2026-04-15 00:05:00",
                "archive_root": str(archive_root),
                "protected_count": 0,
                "candidate_count": 9,
                "candidate_family_counts": {"governance_cycle": 9},
                "root_retained_count": 0,
                "root_retained_family_counts": {},
                "root_retention_budget": {"governance_cycle": 2},
                "should_archive": False,
                "threshold": threshold,
                "sample_candidates": [],
            }
            wiki_runtime.status_payload = lambda: {
                "generated_at": "2026-04-15 00:05:00",
                "lock_running_count": 0,
                "lock_stale_count": 0,
                "archive_candidate_count": 9,
                "archive_candidate_family_counts": {"governance_cycle": 9},
                "archive_should_run": False,
            }
            governance_third = wiki_runtime.generate_governance_cycle()
            if governance_first.get("report_path") != governance_third.get("report_path"):
                findings.append(
                    {
                        "check": "cycle_artifact_suppression",
                        "path": "generate_governance_cycle",
                        "message": "governance cycle created a new report from archive-only advisory drift",
                    }
                )

            supervisor_first = wiki_runtime.run_supervisor_cycle("intake")
            supervisor_second = wiki_runtime.run_supervisor_cycle("intake")
            if supervisor_first.get("report_path") != supervisor_second.get("report_path"):
                findings.append(
                    {
                        "check": "cycle_artifact_suppression",
                        "path": "run_supervisor_cycle",
                        "message": "supervisor cycle reused input but created a different report path",
                    }
                )

            supervisor_reports = sorted(reports_root.glob("supervisor_cycle_*.md"))
            if len(supervisor_reports) != 1:
                findings.append(
                    {
                        "check": "cycle_artifact_suppression",
                        "path": "reports/supervisor_cycle_*.md",
                        "message": f"expected exactly one supervisor cycle report, got {len(supervisor_reports)}",
                    }
                )

            supervisor_daily = wiki_runtime.supervisor_daily_path(supervisor_first)
            supervisor_text = supervisor_daily.read_text(encoding="utf-8")
            supervisor_name = Path(str(supervisor_first.get("report_path", ""))).name
            supervisor_sections = [
                section for section in split_daily_sections(supervisor_text)
                if any(line == f"- supervisor: [{supervisor_name}]({supervisor_name})" for line in section)
            ]
            if len(supervisor_sections) != 1:
                findings.append(
                    {
                        "check": "cycle_artifact_suppression",
                        "path": str(supervisor_daily.relative_to(sandbox_root)),
                        "message": f"expected one supervisor daily entry after repeated cycle, got {len(supervisor_sections)}",
                    }
                )

            wiki_runtime.archive_advisory = lambda threshold=10: {
                "generated_at": "2026-04-15 00:05:00",
                "archive_root": str(archive_root),
                "protected_count": 0,
                "candidate_count": 7,
                "candidate_family_counts": {"supervisor_cycle": 7},
                "root_retained_count": 0,
                "root_retained_family_counts": {},
                "root_retention_budget": {"supervisor_cycle": 2},
                "should_archive": False,
                "threshold": threshold,
                "sample_candidates": [],
            }
            wiki_runtime.status_payload = lambda: {
                "generated_at": "2026-04-15 00:05:00",
                "lock_running_count": 0,
                "lock_stale_count": 0,
                "archive_candidate_count": 7,
                "archive_candidate_family_counts": {"supervisor_cycle": 7},
                "archive_should_run": False,
            }
            supervisor_third = wiki_runtime.run_supervisor_cycle("intake")
            if supervisor_first.get("report_path") != supervisor_third.get("report_path"):
                findings.append(
                    {
                        "check": "cycle_artifact_suppression",
                        "path": "run_supervisor_cycle",
                        "message": "supervisor cycle created a new report from archive-only advisory drift",
                    }
                )
    finally:
        wiki_runtime.ROOT = originals["ROOT"]
        wiki_runtime.REPORTS_ROOT = originals["REPORTS_ROOT"]
        wiki_runtime.STATE_ROOT = originals["STATE_ROOT"]
        wiki_runtime.REPORT_ARCHIVE_ROOT = originals["REPORT_ARCHIVE_ROOT"]
        wiki_runtime.GOVERNANCE_CYCLE_CACHE = originals["GOVERNANCE_CYCLE_CACHE"]
        wiki_runtime.SUPERVISOR_CYCLE_CACHE = originals["SUPERVISOR_CYCLE_CACHE"]
        wiki_runtime.GOVERNANCE_LATEST = originals["GOVERNANCE_LATEST"]
        wiki_runtime.SUPERVISOR_LATEST = originals["SUPERVISOR_LATEST"]
        wiki_runtime.OPERATOR_LATEST = originals["OPERATOR_LATEST"]
        wiki_runtime.ensure_dirs = originals["ensure_dirs"]
        wiki_runtime.timestamp = originals["timestamp"]
        wiki_runtime.current_date = originals["current_date"]
        wiki_runtime.slug_timestamp = originals["slug_timestamp"]
        wiki_runtime.governance_input_snapshot = originals["governance_input_snapshot"]
        wiki_runtime.maintenance_report = originals["maintenance_report"]
        wiki_runtime.conflict_report = originals["conflict_report"]
        wiki_runtime.staleness_report = originals["staleness_report"]
        wiki_runtime.build_promotion_queue_entries = originals["build_promotion_queue_entries"]
        wiki_runtime.build_update_queue_entries = originals["build_update_queue_entries"]
        wiki_runtime.generate_repair_queue = originals["generate_repair_queue"]
        wiki_runtime.generate_promotion_queue = originals["generate_promotion_queue"]
        wiki_runtime.generate_update_queue = originals["generate_update_queue"]
        wiki_runtime.archive_advisory = originals["archive_advisory"]
        wiki_runtime.status_payload = originals["status_payload"]
        wiki_runtime.workflow_ingest = originals["workflow_ingest"]
        wiki_runtime.workflow_compile = originals["workflow_compile"]

    return findings


def check_cycle_snapshot_sensitivity(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    wiki_runtime = load_wiki_runtime_module()

    originals = {
        "ROOT": wiki_runtime.ROOT,
        "REPORTS_ROOT": wiki_runtime.REPORTS_ROOT,
        "STATE_ROOT": wiki_runtime.STATE_ROOT,
        "REPORT_ARCHIVE_ROOT": wiki_runtime.REPORT_ARCHIVE_ROOT,
        "GOVERNANCE_CYCLE_CACHE": wiki_runtime.GOVERNANCE_CYCLE_CACHE,
        "SUPERVISOR_CYCLE_CACHE": wiki_runtime.SUPERVISOR_CYCLE_CACHE,
        "GOVERNANCE_LATEST": wiki_runtime.GOVERNANCE_LATEST,
        "SUPERVISOR_LATEST": wiki_runtime.SUPERVISOR_LATEST,
        "OPERATOR_LATEST": wiki_runtime.OPERATOR_LATEST,
        "ensure_dirs": wiki_runtime.ensure_dirs,
        "timestamp": wiki_runtime.timestamp,
        "current_date": wiki_runtime.current_date,
        "slug_timestamp": wiki_runtime.slug_timestamp,
        "governance_input_snapshot": wiki_runtime.governance_input_snapshot,
        "maintenance_report": wiki_runtime.maintenance_report,
        "conflict_report": wiki_runtime.conflict_report,
        "staleness_report": wiki_runtime.staleness_report,
        "build_promotion_queue_entries": wiki_runtime.build_promotion_queue_entries,
        "build_update_queue_entries": wiki_runtime.build_update_queue_entries,
        "generate_repair_queue": wiki_runtime.generate_repair_queue,
        "generate_promotion_queue": wiki_runtime.generate_promotion_queue,
        "generate_update_queue": wiki_runtime.generate_update_queue,
        "archive_advisory": wiki_runtime.archive_advisory,
        "status_payload": wiki_runtime.status_payload,
        "workflow_ingest": wiki_runtime.workflow_ingest,
        "workflow_compile": wiki_runtime.workflow_compile,
    }

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            sandbox_root = Path(temp_dir)
            reports_root = sandbox_root / "reports"
            state_root = sandbox_root / "_runtime_state"
            archive_root = reports_root / "archive"
            reports_root.mkdir(parents=True, exist_ok=True)
            state_root.mkdir(parents=True, exist_ok=True)

            wiki_runtime.ROOT = sandbox_root
            wiki_runtime.REPORTS_ROOT = reports_root
            wiki_runtime.STATE_ROOT = state_root
            wiki_runtime.REPORT_ARCHIVE_ROOT = archive_root
            wiki_runtime.GOVERNANCE_CYCLE_CACHE = state_root / "governance_cycle_cache.json"
            wiki_runtime.SUPERVISOR_CYCLE_CACHE = state_root / "supervisor_cycle_cache.json"
            wiki_runtime.GOVERNANCE_LATEST = reports_root / "governance_latest.md"
            wiki_runtime.SUPERVISOR_LATEST = reports_root / "supervisor_latest.md"
            wiki_runtime.OPERATOR_LATEST = reports_root / "operator_latest.md"
            wiki_runtime.ensure_dirs = lambda: None
            wiki_runtime.timestamp = lambda: "2026-04-15 00:00:00"
            wiki_runtime.current_date = lambda: "2026-04-15"
            slug_counter = {"value": 0}

            def next_slug() -> str:
                slug_counter["value"] += 1
                return f"20260415_10000{slug_counter['value']}"

            wiki_runtime.slug_timestamp = next_slug
            state = {
                "governance_snapshot": "stable-governance-snapshot",
                "ingest_processed": 0,
            }
            wiki_runtime.governance_input_snapshot = lambda: state["governance_snapshot"]
            wiki_runtime.maintenance_report = lambda: {
                "generated_at": "2026-04-15 00:00:00",
                "canon_missing_metadata": [],
                "lite_missing_metadata": [],
                "stale_candidates": [],
                "review_candidates": [],
                "basis_review_candidates": [],
                "superseded_notes": [],
                "conflict_candidates": [],
                "duplicate_titles": [],
                "static_lint": {
                    "generated_at": "2026-04-15 00:00:00",
                    "broken_wikilinks": [],
                    "broken_evidence_refs": [],
                    "empty_core_sections": [],
                },
            }
            wiki_runtime.conflict_report = lambda: {
                "generated_at": "2026-04-15 00:00:00",
                "explicit_conflicts": [],
                "duplicate_titles": [],
                "divergent_duplicates": [],
                "shared_sources": [],
            }
            wiki_runtime.staleness_report = lambda: {
                "generated_at": "2026-04-15 00:00:00",
                "thresholds": {"canon_days": 90, "lite_days": 7, "review_days": 30},
                "forced_stale": [],
                "canon_age_stale": [],
                "lite_review_overdue": [],
                "canon_review_overdue": [],
            }
            wiki_runtime.build_promotion_queue_entries = lambda: []
            wiki_runtime.build_update_queue_entries = lambda: []
            wiki_runtime.generate_repair_queue = lambda bundle: {
                "report_path": str(reports_root / "repair_queue_fixed.md"),
                "item_count": 0,
            }
            wiki_runtime.generate_promotion_queue = lambda entries: {
                "report_path": str(reports_root / "promotion_queue_fixed.md"),
                "ready_count": 0,
                "review_count": 0,
                "blocked_count": 0,
            }
            wiki_runtime.generate_update_queue = lambda entries: {
                "report_path": str(reports_root / "update_queue_fixed.md"),
                "refresh_existing_count": 0,
                "review_merge_count": 0,
            }
            wiki_runtime.archive_advisory = lambda threshold=10: {
                "generated_at": "2026-04-15 00:00:00",
                "archive_root": str(archive_root),
                "protected_count": 0,
                "candidate_count": 0,
                "should_archive": False,
                "threshold": threshold,
                "sample_candidates": [],
            }
            wiki_runtime.status_payload = lambda: {
                "generated_at": "2026-04-15 00:00:00",
                "lock_running_count": 0,
                "lock_stale_count": 0,
                "archive_candidate_count": 0,
                "archive_should_run": False,
            }
            wiki_runtime.workflow_ingest = lambda: {
                "workflow": "ingest",
                "generated_at": "2026-04-15 00:00:00",
                "processed_count": state["ingest_processed"],
                "skipped_count": 0,
                "processed": [],
                "skipped": [],
            }
            wiki_runtime.workflow_compile = lambda: {
                "workflow": "compile",
                "generated_at": "2026-04-15 00:00:00",
                "built": [],
            }

            for fixed_report in [
                reports_root / "repair_queue_fixed.md",
                reports_root / "promotion_queue_fixed.md",
                reports_root / "update_queue_fixed.md",
            ]:
                fixed_report.write_text("# fixed\n", encoding="utf-8")

            governance_before = wiki_runtime.generate_governance_cycle()
            state["governance_snapshot"] = "changed-governance-snapshot"
            governance_after = wiki_runtime.generate_governance_cycle()
            if governance_before.get("report_path") == governance_after.get("report_path"):
                findings.append(
                    {
                        "check": "cycle_snapshot_sensitivity",
                        "path": "generate_governance_cycle",
                        "message": "governance snapshot changed but report path did not rotate",
                    }
                )

            governance_reports = sorted(reports_root.glob("governance_cycle_*.md"))
            if len(governance_reports) != 2:
                findings.append(
                    {
                        "check": "cycle_snapshot_sensitivity",
                        "path": "reports/governance_cycle_*.md",
                        "message": f"expected two governance cycle reports after snapshot change, got {len(governance_reports)}",
                    }
                )

            governance_daily = wiki_runtime.governance_daily_path(governance_after)
            governance_text = governance_daily.read_text(encoding="utf-8")
            governance_before_name = Path(str(governance_before.get("report_path", ""))).name
            governance_after_name = Path(str(governance_after.get("report_path", ""))).name
            governance_before_sections = [
                section for section in split_daily_sections(governance_text)
                if any(line == f"- governance: [{governance_before_name}]({governance_before_name})" for line in section)
            ]
            governance_after_sections = [
                section for section in split_daily_sections(governance_text)
                if any(line == f"- governance: [{governance_after_name}]({governance_after_name})" for line in section)
            ]
            if len(governance_before_sections) != 1 or len(governance_after_sections) != 1:
                findings.append(
                    {
                        "check": "cycle_snapshot_sensitivity",
                        "path": str(governance_daily.relative_to(sandbox_root)),
                        "message": "governance daily did not keep one old entry and one new entry after snapshot change",
                    }
                )

            supervisor_before = wiki_runtime.run_supervisor_cycle("intake")
            state["ingest_processed"] = 1
            supervisor_after = wiki_runtime.run_supervisor_cycle("intake")
            if supervisor_before.get("report_path") == supervisor_after.get("report_path"):
                findings.append(
                    {
                        "check": "cycle_snapshot_sensitivity",
                        "path": "run_supervisor_cycle",
                        "message": "supervisor input changed but report path did not rotate",
                    }
                )

            supervisor_reports = sorted(reports_root.glob("supervisor_cycle_*.md"))
            if len(supervisor_reports) != 2:
                findings.append(
                    {
                        "check": "cycle_snapshot_sensitivity",
                        "path": "reports/supervisor_cycle_*.md",
                        "message": f"expected two supervisor cycle reports after supervisor input change, got {len(supervisor_reports)}",
                    }
                )

            supervisor_daily = wiki_runtime.supervisor_daily_path(supervisor_after)
            supervisor_text = supervisor_daily.read_text(encoding="utf-8")
            supervisor_before_name = Path(str(supervisor_before.get("report_path", ""))).name
            supervisor_after_name = Path(str(supervisor_after.get("report_path", ""))).name
            supervisor_before_sections = [
                section for section in split_daily_sections(supervisor_text)
                if any(line == f"- supervisor: [{supervisor_before_name}]({supervisor_before_name})" for line in section)
            ]
            supervisor_after_sections = [
                section for section in split_daily_sections(supervisor_text)
                if any(line == f"- supervisor: [{supervisor_after_name}]({supervisor_after_name})" for line in section)
            ]
            if len(supervisor_before_sections) != 1 or len(supervisor_after_sections) != 1:
                findings.append(
                    {
                        "check": "cycle_snapshot_sensitivity",
                        "path": str(supervisor_daily.relative_to(sandbox_root)),
                        "message": "supervisor daily did not keep one old entry and one new entry after input change",
                    }
                )
    finally:
        wiki_runtime.ROOT = originals["ROOT"]
        wiki_runtime.REPORTS_ROOT = originals["REPORTS_ROOT"]
        wiki_runtime.STATE_ROOT = originals["STATE_ROOT"]
        wiki_runtime.REPORT_ARCHIVE_ROOT = originals["REPORT_ARCHIVE_ROOT"]
        wiki_runtime.GOVERNANCE_CYCLE_CACHE = originals["GOVERNANCE_CYCLE_CACHE"]
        wiki_runtime.SUPERVISOR_CYCLE_CACHE = originals["SUPERVISOR_CYCLE_CACHE"]
        wiki_runtime.GOVERNANCE_LATEST = originals["GOVERNANCE_LATEST"]
        wiki_runtime.SUPERVISOR_LATEST = originals["SUPERVISOR_LATEST"]
        wiki_runtime.OPERATOR_LATEST = originals["OPERATOR_LATEST"]
        wiki_runtime.ensure_dirs = originals["ensure_dirs"]
        wiki_runtime.timestamp = originals["timestamp"]
        wiki_runtime.current_date = originals["current_date"]
        wiki_runtime.slug_timestamp = originals["slug_timestamp"]
        wiki_runtime.governance_input_snapshot = originals["governance_input_snapshot"]
        wiki_runtime.maintenance_report = originals["maintenance_report"]
        wiki_runtime.conflict_report = originals["conflict_report"]
        wiki_runtime.staleness_report = originals["staleness_report"]
        wiki_runtime.build_promotion_queue_entries = originals["build_promotion_queue_entries"]
        wiki_runtime.build_update_queue_entries = originals["build_update_queue_entries"]
        wiki_runtime.generate_repair_queue = originals["generate_repair_queue"]
        wiki_runtime.generate_promotion_queue = originals["generate_promotion_queue"]
        wiki_runtime.generate_update_queue = originals["generate_update_queue"]
        wiki_runtime.archive_advisory = originals["archive_advisory"]
        wiki_runtime.status_payload = originals["status_payload"]
        wiki_runtime.workflow_ingest = originals["workflow_ingest"]
        wiki_runtime.workflow_compile = originals["workflow_compile"]

    return findings


def check_day_boundary_stability(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    wiki_runtime = load_wiki_runtime_module()

    originals = {
        "ROOT": wiki_runtime.ROOT,
        "REPORTS_ROOT": wiki_runtime.REPORTS_ROOT,
        "STATE_ROOT": wiki_runtime.STATE_ROOT,
        "REPORT_ARCHIVE_ROOT": wiki_runtime.REPORT_ARCHIVE_ROOT,
        "GOVERNANCE_CYCLE_CACHE": wiki_runtime.GOVERNANCE_CYCLE_CACHE,
        "SUPERVISOR_CYCLE_CACHE": wiki_runtime.SUPERVISOR_CYCLE_CACHE,
        "GOVERNANCE_LATEST": wiki_runtime.GOVERNANCE_LATEST,
        "SUPERVISOR_LATEST": wiki_runtime.SUPERVISOR_LATEST,
        "OPERATOR_LATEST": wiki_runtime.OPERATOR_LATEST,
        "ensure_dirs": wiki_runtime.ensure_dirs,
        "timestamp": wiki_runtime.timestamp,
        "current_date": wiki_runtime.current_date,
        "slug_timestamp": wiki_runtime.slug_timestamp,
        "governance_input_snapshot": wiki_runtime.governance_input_snapshot,
        "maintenance_report": wiki_runtime.maintenance_report,
        "conflict_report": wiki_runtime.conflict_report,
        "staleness_report": wiki_runtime.staleness_report,
        "build_promotion_queue_entries": wiki_runtime.build_promotion_queue_entries,
        "build_update_queue_entries": wiki_runtime.build_update_queue_entries,
        "generate_repair_queue": wiki_runtime.generate_repair_queue,
        "generate_promotion_queue": wiki_runtime.generate_promotion_queue,
        "generate_update_queue": wiki_runtime.generate_update_queue,
        "archive_advisory": wiki_runtime.archive_advisory,
        "status_payload": wiki_runtime.status_payload,
        "workflow_ingest": wiki_runtime.workflow_ingest,
        "workflow_compile": wiki_runtime.workflow_compile,
    }

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            sandbox_root = Path(temp_dir)
            reports_root = sandbox_root / "reports"
            state_root = sandbox_root / "_runtime_state"
            archive_root = reports_root / "archive"
            reports_root.mkdir(parents=True, exist_ok=True)
            state_root.mkdir(parents=True, exist_ok=True)

            wiki_runtime.ROOT = sandbox_root
            wiki_runtime.REPORTS_ROOT = reports_root
            wiki_runtime.STATE_ROOT = state_root
            wiki_runtime.REPORT_ARCHIVE_ROOT = archive_root
            wiki_runtime.GOVERNANCE_CYCLE_CACHE = state_root / "governance_cycle_cache.json"
            wiki_runtime.SUPERVISOR_CYCLE_CACHE = state_root / "supervisor_cycle_cache.json"
            wiki_runtime.GOVERNANCE_LATEST = reports_root / "governance_latest.md"
            wiki_runtime.SUPERVISOR_LATEST = reports_root / "supervisor_latest.md"
            wiki_runtime.OPERATOR_LATEST = reports_root / "operator_latest.md"
            wiki_runtime.ensure_dirs = lambda: None

            clock = {
                "day": "2026-04-15",
                "ts": "2026-04-15 00:00:00",
            }
            wiki_runtime.timestamp = lambda: clock["ts"]
            wiki_runtime.current_date = lambda: clock["day"]
            slug_counter = {"value": 0}

            def next_slug() -> str:
                slug_counter["value"] += 1
                return f"20260415_20000{slug_counter['value']}"

            wiki_runtime.slug_timestamp = next_slug
            wiki_runtime.governance_input_snapshot = lambda: "stable-governance-snapshot"
            wiki_runtime.maintenance_report = lambda: {
                "generated_at": clock["ts"],
                "canon_missing_metadata": [],
                "lite_missing_metadata": [],
                "stale_candidates": [],
                "review_candidates": [],
                "basis_review_candidates": [],
                "superseded_notes": [],
                "conflict_candidates": [],
                "duplicate_titles": [],
                "static_lint": {
                    "generated_at": clock["ts"],
                    "broken_wikilinks": [],
                    "broken_evidence_refs": [],
                    "empty_core_sections": [],
                },
            }
            wiki_runtime.conflict_report = lambda: {
                "generated_at": clock["ts"],
                "explicit_conflicts": [],
                "duplicate_titles": [],
                "divergent_duplicates": [],
                "shared_sources": [],
            }
            wiki_runtime.staleness_report = lambda: {
                "generated_at": clock["ts"],
                "thresholds": {"canon_days": 90, "lite_days": 7, "review_days": 30},
                "forced_stale": [],
                "canon_age_stale": [],
                "lite_review_overdue": [],
                "canon_review_overdue": [],
            }
            wiki_runtime.build_promotion_queue_entries = lambda: []
            wiki_runtime.build_update_queue_entries = lambda: []
            wiki_runtime.generate_repair_queue = lambda bundle: {
                "report_path": str(reports_root / "repair_queue_fixed.md"),
                "item_count": 0,
            }
            wiki_runtime.generate_promotion_queue = lambda entries: {
                "report_path": str(reports_root / "promotion_queue_fixed.md"),
                "ready_count": 0,
                "review_count": 0,
                "blocked_count": 0,
            }
            wiki_runtime.generate_update_queue = lambda entries: {
                "report_path": str(reports_root / "update_queue_fixed.md"),
                "refresh_existing_count": 0,
                "review_merge_count": 0,
            }
            wiki_runtime.archive_advisory = lambda threshold=10: {
                "generated_at": clock["ts"],
                "archive_root": str(archive_root),
                "protected_count": 0,
                "candidate_count": 0,
                "should_archive": False,
                "threshold": threshold,
                "sample_candidates": [],
            }
            wiki_runtime.status_payload = lambda: {
                "generated_at": clock["ts"],
                "lock_running_count": 0,
                "lock_stale_count": 0,
                "archive_candidate_count": 0,
                "archive_should_run": False,
            }
            wiki_runtime.workflow_ingest = lambda: {
                "workflow": "ingest",
                "generated_at": clock["ts"],
                "processed_count": 0,
                "skipped_count": 0,
                "processed": [],
                "skipped": [],
            }
            wiki_runtime.workflow_compile = lambda: {
                "workflow": "compile",
                "generated_at": clock["ts"],
                "built": [],
            }

            for fixed_report in [
                reports_root / "repair_queue_fixed.md",
                reports_root / "promotion_queue_fixed.md",
                reports_root / "update_queue_fixed.md",
            ]:
                fixed_report.write_text("# fixed\n", encoding="utf-8")

            governance_day1 = wiki_runtime.generate_governance_cycle()
            supervisor_day1 = wiki_runtime.run_supervisor_cycle("intake")

            clock["day"] = "2026-04-16"
            clock["ts"] = "2026-04-16 00:00:00"

            governance_day2 = wiki_runtime.generate_governance_cycle()
            supervisor_day2 = wiki_runtime.run_supervisor_cycle("intake")

            if governance_day1.get("report_path") != governance_day2.get("report_path"):
                findings.append(
                    {
                        "check": "day_boundary_stability",
                        "path": "generate_governance_cycle",
                        "message": "day rollover with same governance snapshot created a new governance report",
                    }
                )
            if supervisor_day1.get("report_path") != supervisor_day2.get("report_path"):
                findings.append(
                    {
                        "check": "day_boundary_stability",
                        "path": "run_supervisor_cycle",
                        "message": "day rollover with same supervisor inputs created a new supervisor report",
                    }
                )

            governance_reports = sorted(reports_root.glob("governance_cycle_*.md"))
            if len(governance_reports) != 1:
                findings.append(
                    {
                        "check": "day_boundary_stability",
                        "path": "reports/governance_cycle_*.md",
                        "message": f"expected one governance cycle report across day rollover, got {len(governance_reports)}",
                    }
                )
            supervisor_reports = sorted(reports_root.glob("supervisor_cycle_*.md"))
            if len(supervisor_reports) != 1:
                findings.append(
                    {
                        "check": "day_boundary_stability",
                        "path": "reports/supervisor_cycle_*.md",
                        "message": f"expected one supervisor cycle report across day rollover, got {len(supervisor_reports)}",
                    }
                )

            governance_daily_day1 = reports_root / "governance_daily_20260415.md"
            governance_daily_day2 = reports_root / "governance_daily_20260416.md"
            supervisor_daily_day1 = reports_root / "supervisor_daily_20260415.md"
            supervisor_daily_day2 = reports_root / "supervisor_daily_20260416.md"
            for path in [governance_daily_day1, governance_daily_day2, supervisor_daily_day1, supervisor_daily_day2]:
                if not path.exists():
                    findings.append(
                        {
                            "check": "day_boundary_stability",
                            "path": str(path.relative_to(sandbox_root)),
                            "message": "expected daily file missing after day rollover",
                        }
                    )

            if governance_daily_day2.exists():
                text = governance_daily_day2.read_text(encoding="utf-8")
                governance_name = Path(str(governance_day2.get("report_path", ""))).name
                sections = [
                    section
                    for section in split_daily_sections(text)
                    if any(line == f"- governance: [{governance_name}]({governance_name})" for line in section)
                ]
                if len(sections) != 1:
                    findings.append(
                        {
                            "check": "day_boundary_stability",
                            "path": str(governance_daily_day2.relative_to(sandbox_root)),
                            "message": f"expected one governance daily entry after day rollover, got {len(sections)}",
                        }
                    )
                if "# governance-daily-2026-04-16" not in text or "- day: `2026-04-16`" not in text:
                    findings.append(
                        {
                            "check": "day_boundary_stability",
                            "path": str(governance_daily_day2.relative_to(sandbox_root)),
                            "message": "governance day-2 daily header drifted",
                        }
                    )

            if supervisor_daily_day2.exists():
                text = supervisor_daily_day2.read_text(encoding="utf-8")
                supervisor_name = Path(str(supervisor_day2.get("report_path", ""))).name
                sections = [
                    section
                    for section in split_daily_sections(text)
                    if any(line == f"- supervisor: [{supervisor_name}]({supervisor_name})" for line in section)
                ]
                if len(sections) != 1:
                    findings.append(
                        {
                            "check": "day_boundary_stability",
                            "path": str(supervisor_daily_day2.relative_to(sandbox_root)),
                            "message": f"expected one supervisor daily entry after day rollover, got {len(sections)}",
                        }
                    )
                if "# supervisor-daily-2026-04-16" not in text or "- day: `2026-04-16`" not in text:
                    findings.append(
                        {
                            "check": "day_boundary_stability",
                            "path": str(supervisor_daily_day2.relative_to(sandbox_root)),
                            "message": "supervisor day-2 daily header drifted",
                        }
                    )

            governance_latest_text = wiki_runtime.GOVERNANCE_LATEST.read_text(encoding="utf-8")
            if "governance_daily_20260416.md" not in governance_latest_text:
                findings.append(
                    {
                        "check": "day_boundary_stability",
                        "path": str(wiki_runtime.GOVERNANCE_LATEST.relative_to(sandbox_root)),
                        "message": "governance latest did not point to day-2 daily summary",
                    }
                )
            if "- last_cycle_at: `2026-04-15 00:00:00`" not in governance_latest_text:
                findings.append(
                    {
                        "check": "day_boundary_stability",
                        "path": str(wiki_runtime.GOVERNANCE_LATEST.relative_to(sandbox_root)),
                        "message": "governance latest did not preserve original cycle timestamp after day rollover",
                    }
                )

            supervisor_latest_text = wiki_runtime.SUPERVISOR_LATEST.read_text(encoding="utf-8")
            if "supervisor_daily_20260416.md" not in supervisor_latest_text:
                findings.append(
                    {
                        "check": "day_boundary_stability",
                        "path": str(wiki_runtime.SUPERVISOR_LATEST.relative_to(sandbox_root)),
                        "message": "supervisor latest did not point to day-2 daily summary",
                    }
                )
            if "- last_cycle_at: `2026-04-15 00:00:00`" not in supervisor_latest_text:
                findings.append(
                    {
                        "check": "day_boundary_stability",
                        "path": str(wiki_runtime.SUPERVISOR_LATEST.relative_to(sandbox_root)),
                        "message": "supervisor latest did not preserve original cycle timestamp after day rollover",
                    }
                )

            governance_day2_repeat = wiki_runtime.generate_governance_cycle()
            supervisor_day2_repeat = wiki_runtime.run_supervisor_cycle("intake")
            if governance_day2_repeat.get("report_path") != governance_day2.get("report_path"):
                findings.append(
                    {
                        "check": "day_boundary_stability",
                        "path": "generate_governance_cycle",
                        "message": "same day-2 governance rerun changed report path",
                    }
                )
            if supervisor_day2_repeat.get("report_path") != supervisor_day2.get("report_path"):
                findings.append(
                    {
                        "check": "day_boundary_stability",
                        "path": "run_supervisor_cycle",
                        "message": "same day-2 supervisor rerun changed report path",
                    }
                )

            governance_day2_text = governance_daily_day2.read_text(encoding="utf-8")
            governance_name = Path(str(governance_day2.get("report_path", ""))).name
            governance_sections = [
                section
                for section in split_daily_sections(governance_day2_text)
                if any(line == f"- governance: [{governance_name}]({governance_name})" for line in section)
            ]
            if len(governance_sections) != 1:
                findings.append(
                    {
                        "check": "day_boundary_stability",
                        "path": str(governance_daily_day2.relative_to(sandbox_root)),
                        "message": f"expected one governance day-2 entry after repeat rerun, got {len(governance_sections)}",
                    }
                )

            supervisor_day2_text = supervisor_daily_day2.read_text(encoding="utf-8")
            supervisor_name = Path(str(supervisor_day2.get("report_path", ""))).name
            supervisor_sections = [
                section
                for section in split_daily_sections(supervisor_day2_text)
                if any(line == f"- supervisor: [{supervisor_name}]({supervisor_name})" for line in section)
            ]
            if len(supervisor_sections) != 1:
                findings.append(
                    {
                        "check": "day_boundary_stability",
                        "path": str(supervisor_daily_day2.relative_to(sandbox_root)),
                        "message": f"expected one supervisor day-2 entry after repeat rerun, got {len(supervisor_sections)}",
                    }
                )
    finally:
        wiki_runtime.ROOT = originals["ROOT"]
        wiki_runtime.REPORTS_ROOT = originals["REPORTS_ROOT"]
        wiki_runtime.STATE_ROOT = originals["STATE_ROOT"]
        wiki_runtime.REPORT_ARCHIVE_ROOT = originals["REPORT_ARCHIVE_ROOT"]
        wiki_runtime.GOVERNANCE_CYCLE_CACHE = originals["GOVERNANCE_CYCLE_CACHE"]
        wiki_runtime.SUPERVISOR_CYCLE_CACHE = originals["SUPERVISOR_CYCLE_CACHE"]
        wiki_runtime.GOVERNANCE_LATEST = originals["GOVERNANCE_LATEST"]
        wiki_runtime.SUPERVISOR_LATEST = originals["SUPERVISOR_LATEST"]
        wiki_runtime.OPERATOR_LATEST = originals["OPERATOR_LATEST"]
        wiki_runtime.ensure_dirs = originals["ensure_dirs"]
        wiki_runtime.timestamp = originals["timestamp"]
        wiki_runtime.current_date = originals["current_date"]
        wiki_runtime.slug_timestamp = originals["slug_timestamp"]
        wiki_runtime.governance_input_snapshot = originals["governance_input_snapshot"]
        wiki_runtime.maintenance_report = originals["maintenance_report"]
        wiki_runtime.conflict_report = originals["conflict_report"]
        wiki_runtime.staleness_report = originals["staleness_report"]
        wiki_runtime.build_promotion_queue_entries = originals["build_promotion_queue_entries"]
        wiki_runtime.build_update_queue_entries = originals["build_update_queue_entries"]
        wiki_runtime.generate_repair_queue = originals["generate_repair_queue"]
        wiki_runtime.generate_promotion_queue = originals["generate_promotion_queue"]
        wiki_runtime.generate_update_queue = originals["generate_update_queue"]
        wiki_runtime.archive_advisory = originals["archive_advisory"]
        wiki_runtime.status_payload = originals["status_payload"]
        wiki_runtime.workflow_ingest = originals["workflow_ingest"]
        wiki_runtime.workflow_compile = originals["workflow_compile"]

    return findings


def check_snapshot_precision(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    wiki_runtime = load_wiki_runtime_module()

    originals = {
        "ROOT": wiki_runtime.ROOT,
        "WIKI_ROOT": wiki_runtime.WIKI_ROOT,
        "WIKI_TOPICS": wiki_runtime.WIKI_TOPICS,
        "WIKI_ENTITIES": wiki_runtime.WIKI_ENTITIES,
        "WIKI_CONCEPTS": wiki_runtime.WIKI_CONCEPTS,
        "WIKI_SYNTHESES": wiki_runtime.WIKI_SYNTHESES,
        "LITE_ROOT": wiki_runtime.LITE_ROOT,
        "LITE_WIKI": wiki_runtime.LITE_WIKI,
        "LITE_QUERY_RESIDUE": wiki_runtime.LITE_QUERY_RESIDUE,
        "CANON_FOLDERS": wiki_runtime.CANON_FOLDERS,
        "datetime": wiki_runtime.datetime,
    }

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            sandbox_root = Path(temp_dir)
            wiki_root = sandbox_root / "wiki"
            lite_root = sandbox_root / "wiki_lite"
            lite_wiki = lite_root / "WIKI"
            residue_root = lite_wiki / "query_residue"
            topics_root = wiki_root / "topics"
            entities_root = wiki_root / "entities"
            concepts_root = wiki_root / "concepts"
            syntheses_root = wiki_root / "syntheses"
            for path in [wiki_root, lite_root, lite_wiki, residue_root, topics_root, entities_root, concepts_root, syntheses_root]:
                path.mkdir(parents=True, exist_ok=True)

            wiki_runtime.ROOT = sandbox_root
            wiki_runtime.WIKI_ROOT = wiki_root
            wiki_runtime.WIKI_TOPICS = topics_root
            wiki_runtime.WIKI_ENTITIES = entities_root
            wiki_runtime.WIKI_CONCEPTS = concepts_root
            wiki_runtime.WIKI_SYNTHESES = syntheses_root
            wiki_runtime.LITE_ROOT = lite_root
            wiki_runtime.LITE_WIKI = lite_wiki
            wiki_runtime.LITE_QUERY_RESIDUE = residue_root
            wiki_runtime.CANON_FOLDERS = [topics_root, entities_root, concepts_root, syntheses_root]

            class FixedDateTime(datetime):
                current = datetime(2026, 4, 20, 0, 0, 0)

                @classmethod
                def now(cls, tz=None):
                    if tz is not None:
                        return cls.current.replace(tzinfo=tz)
                    return cls.current

            wiki_runtime.datetime = FixedDateTime

            root_doc = sandbox_root / "README.md"
            root_doc.write_text("# root-doc\n", encoding="utf-8")
            lite_note = lite_wiki / "alpha.md"
            lite_note.write_text(
                "\n".join(
                    [
                        "# alpha",
                        "",
                        "- built_from: `raw/alpha.md`",
                        "- status: `hold`",
                        "- reviewed_at: `2026-04-15`",
                        "- claim_state: `draft`",
                        "- freshness: `2026-04-15`",
                        "- confidence: `medium`",
                        "",
                        "## distilled",
                        "- alpha distilled",
                        "",
                        "## reusable rule",
                        "- alpha reusable",
                        "",
                        "## evidence",
                        "- `raw/alpha.md`",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            residue_note = residue_root / "residue.md"
            residue_note.write_text(
                "\n".join(
                    [
                        "# residue",
                        "",
                        "- built_from: `query://alpha`",
                        "- status: `hold`",
                        "- reviewed_at: `2026-04-15`",
                        "- claim_state: `unknown`",
                        "- freshness: `2026-04-15`",
                        "- confidence: `low`",
                        "",
                        "## distilled",
                        "- residue distilled",
                        "",
                        "## reusable rule",
                        "- residue reusable",
                        "",
                        "## evidence",
                        "- no evidence",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            canon_note = topics_root / "canon.md"
            canon_note.write_text(
                "\n".join(
                    [
                        "# canon",
                        "",
                        "- promoted_from: `wiki_lite/WIKI/alpha.md`",
                        "- claim_state: `draft`",
                        "- freshness: `2026-04-15`",
                        "- confidence: `medium`",
                        "- supersession: `none`",
                        "- scope: `topic`",
                        "",
                        "## canon",
                        "- canon body",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            lint_base = wiki_runtime.lint_input_snapshot()
            queue_base = wiki_runtime.queue_input_snapshot()
            governance_base = wiki_runtime.governance_input_snapshot()

            touch_ts = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc).timestamp()
            os.utime(lite_note, (touch_ts, touch_ts))
            lint_after_touch = wiki_runtime.lint_input_snapshot()
            queue_after_touch = wiki_runtime.queue_input_snapshot()
            governance_after_touch = wiki_runtime.governance_input_snapshot()
            if lint_after_touch != lint_base:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "wiki_lite/WIKI/alpha.md",
                        "message": "mtime-only touch rotated lint snapshot",
                    }
                )
            if queue_after_touch != queue_base:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "wiki_lite/WIKI/alpha.md",
                        "message": "mtime-only touch rotated queue snapshot",
                    }
                )
            if governance_after_touch != governance_base:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "wiki_lite/WIKI/alpha.md",
                        "message": "mtime-only touch rotated governance snapshot",
                    }
                )

            root_doc.write_text("# root-doc\n\nchanged\n", encoding="utf-8")
            lint_after_doc = wiki_runtime.lint_input_snapshot()
            queue_after_doc = wiki_runtime.queue_input_snapshot()
            governance_after_doc = wiki_runtime.governance_input_snapshot()
            if lint_after_doc != lint_base:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "README.md",
                        "message": "root docs changed but lint snapshot rotated",
                    }
                )
            if queue_after_doc != queue_base:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "README.md",
                        "message": "root docs changed but queue snapshot rotated",
                    }
                )
            if governance_after_doc != governance_base:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "README.md",
                        "message": "root docs changed but governance snapshot rotated",
                    }
                )

            residue_note.write_text(
                residue_note.read_text(encoding="utf-8").replace("- no evidence", "- `missing/residue.md`"),
                encoding="utf-8",
            )
            lint_after_residue = wiki_runtime.lint_input_snapshot()
            queue_after_residue = wiki_runtime.queue_input_snapshot()
            if lint_after_residue == lint_base:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "wiki_lite/WIKI/query_residue/residue.md",
                        "message": "lint-relevant query residue changed but lint snapshot did not rotate",
                    }
                )
            if queue_after_residue != queue_base:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "wiki_lite/WIKI/query_residue/residue.md",
                        "message": "query residue changed and queue snapshot rotated",
                    }
                )

            lite_note.write_text(
                lite_note.read_text(encoding="utf-8").replace("- status: `hold`", "- status: `adopt`"),
                encoding="utf-8",
            )
            lint_after_lite = wiki_runtime.lint_input_snapshot()
            queue_after_lite = wiki_runtime.queue_input_snapshot()
            governance_after_lite = wiki_runtime.governance_input_snapshot()
            if lint_after_lite == lint_after_residue:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "wiki_lite/WIKI/alpha.md",
                        "message": "lint-relevant lite note changed but lint snapshot did not rotate",
                    }
                )
            if queue_after_lite == queue_after_residue:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "wiki_lite/WIKI/alpha.md",
                        "message": "queue-relevant lite note changed but queue snapshot did not rotate",
                    }
                )
            if governance_after_lite == governance_after_doc:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "wiki_lite/WIKI/alpha.md",
                        "message": "lint/queue-relevant lite note changed but governance snapshot did not rotate",
                    }
                )

            time_lite = lite_wiki / "time-rollover.md"
            time_lite.write_text(
                "\n".join(
                    [
                        "# time-rollover",
                        "",
                        "- built_from: `raw/time-rollover.md`",
                        "- status: `hold`",
                        "- reviewed_at: `2026-04-15`",
                        "- claim_state: `draft`",
                        "- freshness: `2026-04-15`",
                        "- confidence: `medium`",
                        "",
                        "## distilled",
                        "- rollover distilled",
                        "",
                        "## reusable rule",
                        "- rollover reusable",
                        "",
                        "## evidence",
                        "- `raw/time-rollover.md`",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            FixedDateTime.current = datetime(2026, 4, 20, 0, 0, 0)
            lint_before_time_rollover = wiki_runtime.lint_input_snapshot()
            queue_before_time_rollover = wiki_runtime.queue_input_snapshot()
            governance_before_time_rollover = wiki_runtime.governance_input_snapshot()

            FixedDateTime.current = datetime(2026, 4, 25, 0, 0, 0)
            lint_after_time_rollover = wiki_runtime.lint_input_snapshot()
            queue_after_time_rollover = wiki_runtime.queue_input_snapshot()
            governance_after_time_rollover = wiki_runtime.governance_input_snapshot()
            if lint_after_time_rollover == lint_before_time_rollover:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "wiki_lite/WIKI/time-rollover.md",
                        "message": "time-only review threshold rollover did not rotate lint snapshot",
                    }
                )
            if queue_after_time_rollover != queue_before_time_rollover:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "wiki_lite/WIKI/time-rollover.md",
                        "message": "time-only review threshold rollover rotated queue snapshot",
                    }
                )
            if governance_after_time_rollover == governance_before_time_rollover:
                findings.append(
                    {
                        "check": "snapshot_precision",
                        "path": "wiki_lite/WIKI/time-rollover.md",
                        "message": "time-only review threshold rollover did not rotate governance snapshot",
                    }
                )
    finally:
        wiki_runtime.ROOT = originals["ROOT"]
        wiki_runtime.WIKI_ROOT = originals["WIKI_ROOT"]
        wiki_runtime.WIKI_TOPICS = originals["WIKI_TOPICS"]
        wiki_runtime.WIKI_ENTITIES = originals["WIKI_ENTITIES"]
        wiki_runtime.WIKI_CONCEPTS = originals["WIKI_CONCEPTS"]
        wiki_runtime.WIKI_SYNTHESES = originals["WIKI_SYNTHESES"]
        wiki_runtime.LITE_ROOT = originals["LITE_ROOT"]
        wiki_runtime.LITE_WIKI = originals["LITE_WIKI"]
        wiki_runtime.LITE_QUERY_RESIDUE = originals["LITE_QUERY_RESIDUE"]
        wiki_runtime.CANON_FOLDERS = originals["CANON_FOLDERS"]
        wiki_runtime.datetime = originals["datetime"]

    return findings


def check_queue_field_policy(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    wiki_runtime = load_wiki_runtime_module()

    originals = {
        "ROOT": wiki_runtime.ROOT,
        "WIKI_ROOT": wiki_runtime.WIKI_ROOT,
        "WIKI_TOPICS": wiki_runtime.WIKI_TOPICS,
        "WIKI_ENTITIES": wiki_runtime.WIKI_ENTITIES,
        "WIKI_CONCEPTS": wiki_runtime.WIKI_CONCEPTS,
        "WIKI_SYNTHESES": wiki_runtime.WIKI_SYNTHESES,
        "LITE_ROOT": wiki_runtime.LITE_ROOT,
        "LITE_WIKI": wiki_runtime.LITE_WIKI,
        "LITE_QUERY_RESIDUE": wiki_runtime.LITE_QUERY_RESIDUE,
        "CANON_FOLDERS": wiki_runtime.CANON_FOLDERS,
        "datetime": wiki_runtime.datetime,
    }

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            sandbox_root = Path(temp_dir)
            wiki_root = sandbox_root / "wiki"
            lite_root = sandbox_root / "wiki_lite"
            lite_wiki = lite_root / "WIKI"
            residue_root = lite_wiki / "query_residue"
            topics_root = wiki_root / "topics"
            entities_root = wiki_root / "entities"
            concepts_root = wiki_root / "concepts"
            syntheses_root = wiki_root / "syntheses"
            for path in [wiki_root, lite_root, lite_wiki, residue_root, topics_root, entities_root, concepts_root, syntheses_root]:
                path.mkdir(parents=True, exist_ok=True)

            wiki_runtime.ROOT = sandbox_root
            wiki_runtime.WIKI_ROOT = wiki_root
            wiki_runtime.WIKI_TOPICS = topics_root
            wiki_runtime.WIKI_ENTITIES = entities_root
            wiki_runtime.WIKI_CONCEPTS = concepts_root
            wiki_runtime.WIKI_SYNTHESES = syntheses_root
            wiki_runtime.LITE_ROOT = lite_root
            wiki_runtime.LITE_WIKI = lite_wiki
            wiki_runtime.LITE_QUERY_RESIDUE = residue_root
            wiki_runtime.CANON_FOLDERS = [topics_root, entities_root, concepts_root, syntheses_root]

            class FixedDateTime(datetime):
                current = datetime(2026, 4, 20, 0, 0, 0)

                @classmethod
                def now(cls, tz=None):
                    if tz is not None:
                        return cls.current.replace(tzinfo=tz)
                    return cls.current

            wiki_runtime.datetime = FixedDateTime

            lite_note = lite_wiki / "alpha.md"
            lite_note.write_text(
                "\n".join(
                    [
                        "# alpha",
                        "",
                        "- built_from: `raw/alpha.md`",
                        "- status: `hold`",
                        "- reviewed_at: `2026-04-15`",
                        "- freshness: `2026-04-15`",
                        "- claim_state: `inference`",
                        "- confidence: `medium`",
                        "- scope: `alpha scope`",
                        "- source_count: `2`",
                        "- surface: `coordination`",
                        "",
                        "## distilled",
                        "- alpha distilled",
                        "- second line",
                        "",
                        "## reusable rule",
                        "- alpha reusable",
                        "",
                        "## evidence",
                        "- `raw/alpha.md`",
                        "- `raw/support.md`",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            canon_note = topics_root / "canon.md"
            canon_note.write_text(
                "\n".join(
                    [
                        "# canon",
                        "",
                        "- promoted_from: `wiki_lite/WIKI/alpha.md`",
                        "- claim_state: `inference`",
                        "- evidence: `raw/alpha.md; raw/support.md`",
                        "- evidence_mode: `listed`",
                        "- freshness: `2026-04-15`",
                        "- confidence: `medium`",
                        "- confidence_basis: `source_count`",
                        "- scope: `alpha scope`",
                        "- source_count: `2`",
                        "- source_count_basis: `evidence_refs`",
                        "- last_reviewed: `2026-04-15`",
                        "- supersession: `none`",
                        "- stale_flag: `false`",
                        "- conflict_with: `none`",
                        "",
                        "## canon",
                        "- canon body",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            lite_base = wiki_runtime.queue_note_snapshot_text(lite_note)
            canon_base = wiki_runtime.queue_note_snapshot_text(canon_note)

            lite_note.write_text(lite_note.read_text(encoding="utf-8").replace("2026-04-15", "2026-04-16", 1), encoding="utf-8")
            lite_after_reviewed = wiki_runtime.queue_note_snapshot_text(lite_note)
            if lite_after_reviewed != lite_base:
                findings.append(
                    {
                        "check": "queue_field_policy",
                        "path": "wiki_lite/WIKI/alpha.md",
                        "message": "reviewed_at changed despite explicit freshness, but queue snapshot rotated",
                    }
                )

            lite_note.write_text(lite_note.read_text(encoding="utf-8").replace("- status: `hold`", "- status: `adopt`"), encoding="utf-8")
            lite_after_status = wiki_runtime.queue_note_snapshot_text(lite_note)
            if lite_after_status == lite_after_reviewed:
                findings.append(
                    {
                        "check": "queue_field_policy",
                        "path": "wiki_lite/WIKI/alpha.md",
                        "message": "status changed but queue snapshot did not rotate",
                    }
                )

            canon_note.write_text(canon_note.read_text(encoding="utf-8").replace("- last_reviewed: `2026-04-15`", "- last_reviewed: `2026-04-16`"), encoding="utf-8")
            canon_after_review = wiki_runtime.queue_note_snapshot_text(canon_note)
            if canon_after_review != canon_base:
                findings.append(
                    {
                        "check": "queue_field_policy",
                        "path": "wiki/topics/canon.md",
                        "message": "canon last_reviewed changed but queue snapshot rotated",
                    }
                )

            canon_note.write_text(canon_note.read_text(encoding="utf-8").replace("- supersession: `none`", "- supersession: `replaced`"), encoding="utf-8")
            canon_after_supersession = wiki_runtime.queue_note_snapshot_text(canon_note)
            if canon_after_supersession != canon_base:
                findings.append(
                    {
                        "check": "queue_field_policy",
                        "path": "wiki/topics/canon.md",
                        "message": "canon supersession changed but queue snapshot rotated",
                    }
                )

            canon_note.write_text(canon_note.read_text(encoding="utf-8").replace("- canon body", "- canon body changed"), encoding="utf-8")
            canon_after_body = wiki_runtime.queue_note_snapshot_text(canon_note)
            if canon_after_body == canon_after_supersession:
                findings.append(
                    {
                        "check": "queue_field_policy",
                        "path": "wiki/topics/canon.md",
                        "message": "canon body changed but queue snapshot did not rotate",
                    }
                )
    finally:
        wiki_runtime.ROOT = originals["ROOT"]
        wiki_runtime.WIKI_ROOT = originals["WIKI_ROOT"]
        wiki_runtime.WIKI_TOPICS = originals["WIKI_TOPICS"]
        wiki_runtime.WIKI_ENTITIES = originals["WIKI_ENTITIES"]
        wiki_runtime.WIKI_CONCEPTS = originals["WIKI_CONCEPTS"]
        wiki_runtime.WIKI_SYNTHESES = originals["WIKI_SYNTHESES"]
        wiki_runtime.LITE_ROOT = originals["LITE_ROOT"]
        wiki_runtime.LITE_WIKI = originals["LITE_WIKI"]
        wiki_runtime.LITE_QUERY_RESIDUE = originals["LITE_QUERY_RESIDUE"]
        wiki_runtime.CANON_FOLDERS = originals["CANON_FOLDERS"]

    return findings


def check_lint_field_policy(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    wiki_runtime = load_wiki_runtime_module()

    originals = {
        "ROOT": wiki_runtime.ROOT,
        "WIKI_ROOT": wiki_runtime.WIKI_ROOT,
        "WIKI_TOPICS": wiki_runtime.WIKI_TOPICS,
        "WIKI_ENTITIES": wiki_runtime.WIKI_ENTITIES,
        "WIKI_CONCEPTS": wiki_runtime.WIKI_CONCEPTS,
        "WIKI_SYNTHESES": wiki_runtime.WIKI_SYNTHESES,
        "LITE_ROOT": wiki_runtime.LITE_ROOT,
        "LITE_WIKI": wiki_runtime.LITE_WIKI,
        "LITE_QUERY_RESIDUE": wiki_runtime.LITE_QUERY_RESIDUE,
        "CANON_FOLDERS": wiki_runtime.CANON_FOLDERS,
        "datetime": wiki_runtime.datetime,
    }

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            sandbox_root = Path(temp_dir)
            wiki_root = sandbox_root / "wiki"
            lite_root = sandbox_root / "wiki_lite"
            lite_wiki = lite_root / "WIKI"
            residue_root = lite_wiki / "query_residue"
            topics_root = wiki_root / "topics"
            entities_root = wiki_root / "entities"
            concepts_root = wiki_root / "concepts"
            syntheses_root = wiki_root / "syntheses"
            for path in [wiki_root, lite_root, lite_wiki, residue_root, topics_root, entities_root, concepts_root, syntheses_root]:
                path.mkdir(parents=True, exist_ok=True)

            wiki_runtime.ROOT = sandbox_root
            wiki_runtime.WIKI_ROOT = wiki_root
            wiki_runtime.WIKI_TOPICS = topics_root
            wiki_runtime.WIKI_ENTITIES = entities_root
            wiki_runtime.WIKI_CONCEPTS = concepts_root
            wiki_runtime.WIKI_SYNTHESES = syntheses_root
            wiki_runtime.LITE_ROOT = lite_root
            wiki_runtime.LITE_WIKI = lite_wiki
            wiki_runtime.LITE_QUERY_RESIDUE = residue_root
            wiki_runtime.CANON_FOLDERS = [topics_root, entities_root, concepts_root, syntheses_root]

            class FixedDateTime(datetime):
                current = datetime(2026, 4, 20, 0, 0, 0)

                @classmethod
                def now(cls, tz=None):
                    if tz is not None:
                        return cls.current.replace(tzinfo=tz)
                    return cls.current

            wiki_runtime.datetime = FixedDateTime

            lite_note = lite_wiki / "alpha.md"
            lite_note.write_text(
                "\n".join(
                    [
                        "# alpha",
                        "",
                        "- built_from: `raw/alpha.md`",
                        "- status: `hold`",
                        "- reviewed_at: `2026-04-15`",
                        "- claim_state: `inference`",
                        "- freshness: `2026-04-15`",
                        "- confidence: `medium`",
                        "",
                        "## distilled",
                        "- alpha distilled",
                        "",
                        "## reusable rule",
                        "- alpha reusable",
                        "",
                        "## evidence",
                        "- no evidence",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            canon_note = topics_root / "canon.md"
            canon_note.write_text(
                "\n".join(
                    [
                        "# canon",
                        "",
                        "- promoted_from: `wiki_lite/WIKI/alpha.md`",
                        "- claim_state: `inference`",
                        "- evidence: `unknown`",
                        "- evidence_mode: `trace`",
                        "- freshness: `2026-04-15`",
                        "- confidence: `medium`",
                        "- confidence_basis: `conservative_default`",
                        "- scope: `topic`",
                        "- source_count_basis: `trace_only`",
                        "- last_reviewed: `2026-04-15`",
                        "- supersession: `none`",
                        "- stale_flag: `false`",
                        "- conflict_with: `none`",
                        "",
                        "## canon",
                        "- canon body",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            lite_base = wiki_runtime.lint_note_snapshot_text(lite_note)
            canon_base = wiki_runtime.lint_note_snapshot_text(canon_note)

            lite_note.write_text(
                lite_note.read_text(encoding="utf-8").replace("- reviewed_at: `2026-04-15`", "- reviewed_at: `2026-04-16`"),
                encoding="utf-8",
            )
            lite_after_reviewed = wiki_runtime.lint_note_snapshot_text(lite_note)
            if lite_after_reviewed != lite_base:
                findings.append(
                    {
                        "check": "lint_field_policy",
                        "path": "wiki_lite/WIKI/alpha.md",
                        "message": "lite reviewed_at changed without threshold crossover, but lint snapshot rotated",
                    }
                )

            lite_note.write_text(
                lite_note.read_text(encoding="utf-8").replace("- confidence: `medium`", "- confidence: `high`"),
                encoding="utf-8",
            )
            lite_after_confidence = wiki_runtime.lint_note_snapshot_text(lite_note)
            if lite_after_confidence != lite_base:
                findings.append(
                    {
                        "check": "lint_field_policy",
                        "path": "wiki_lite/WIKI/alpha.md",
                        "message": "lite confidence value changed but lint snapshot rotated",
                    }
                )

            lite_note.write_text(
                lite_note.read_text(encoding="utf-8").replace("- status: `hold`", "- status: `adopt`"),
                encoding="utf-8",
            )
            lite_after_status = wiki_runtime.lint_note_snapshot_text(lite_note)
            if lite_after_status == lite_after_confidence:
                findings.append(
                    {
                        "check": "lint_field_policy",
                        "path": "wiki_lite/WIKI/alpha.md",
                        "message": "lite status changed but lint snapshot did not rotate",
                    }
                )

            lite_note.write_text(
                lite_note.read_text(encoding="utf-8").replace("- alpha distilled", "- alpha distilled [[missing-page]]"),
                encoding="utf-8",
            )
            lite_after_broken_link = wiki_runtime.lint_note_snapshot_text(lite_note)
            if lite_after_broken_link == lite_after_status:
                findings.append(
                    {
                        "check": "lint_field_policy",
                        "path": "wiki_lite/WIKI/alpha.md",
                        "message": "lite broken wikilink changed but lint snapshot did not rotate",
                    }
                )

            canon_note.write_text(
                canon_note.read_text(encoding="utf-8").replace("- confidence: `medium`", "- confidence: `high`"),
                encoding="utf-8",
            )
            canon_after_confidence = wiki_runtime.lint_note_snapshot_text(canon_note)
            if canon_after_confidence != canon_base:
                findings.append(
                    {
                        "check": "lint_field_policy",
                        "path": "wiki/topics/canon.md",
                        "message": "canon confidence value changed but lint snapshot rotated",
                    }
                )

            canon_note.write_text(
                canon_note.read_text(encoding="utf-8").replace("- last_reviewed: `2026-04-15`", "- last_reviewed: `2026-04-16`"),
                encoding="utf-8",
            )
            canon_after_review = wiki_runtime.lint_note_snapshot_text(canon_note)
            if canon_after_review != canon_after_confidence:
                findings.append(
                    {
                        "check": "lint_field_policy",
                        "path": "wiki/topics/canon.md",
                        "message": "canon last_reviewed changed without threshold crossover, but lint snapshot rotated",
                    }
                )

            canon_note.write_text(
                canon_note.read_text(encoding="utf-8").replace("- supersession: `none`", "- supersession: `replaced`"),
                encoding="utf-8",
            )
            canon_after_supersession = wiki_runtime.lint_note_snapshot_text(canon_note)
            if canon_after_supersession == canon_after_review:
                findings.append(
                    {
                        "check": "lint_field_policy",
                        "path": "wiki/topics/canon.md",
                        "message": "canon supersession changed but lint snapshot did not rotate",
                    }
                )

            canon_note.write_text(
                canon_note.read_text(encoding="utf-8").replace("- canon body", "- canon body changed"),
                encoding="utf-8",
            )
            canon_after_body = wiki_runtime.lint_note_snapshot_text(canon_note)
            if canon_after_body == canon_after_supersession:
                findings.append(
                    {
                        "check": "lint_field_policy",
                        "path": "wiki/topics/canon.md",
                        "message": "canon body changed but lint snapshot did not rotate",
                    }
                )
    finally:
        wiki_runtime.ROOT = originals["ROOT"]
        wiki_runtime.WIKI_ROOT = originals["WIKI_ROOT"]
        wiki_runtime.WIKI_TOPICS = originals["WIKI_TOPICS"]
        wiki_runtime.WIKI_ENTITIES = originals["WIKI_ENTITIES"]
        wiki_runtime.WIKI_CONCEPTS = originals["WIKI_CONCEPTS"]
        wiki_runtime.WIKI_SYNTHESES = originals["WIKI_SYNTHESES"]
        wiki_runtime.LITE_ROOT = originals["LITE_ROOT"]
        wiki_runtime.LITE_WIKI = originals["LITE_WIKI"]
        wiki_runtime.LITE_QUERY_RESIDUE = originals["LITE_QUERY_RESIDUE"]
        wiki_runtime.CANON_FOLDERS = originals["CANON_FOLDERS"]
        wiki_runtime.datetime = originals["datetime"]

    return findings


def check_load_test(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    cfg = profile["load_test"]
    report_path = latest_matching_report(cfg["report_glob"])
    if report_path is None:
        return [{"check": "load_test", "path": cfg["report_glob"], "message": "no matching report"}]

    text = report_path.read_text(encoding="utf-8")

    def extract_float(prefix: str) -> float | None:
        for line in text.splitlines():
            if line.startswith(prefix):
                raw = line.split("`")[1]
                try:
                    return float(raw)
                except ValueError:
                    return None
        return None

    total_runtime = extract_float("- total_runtime_sec: ")
    compile_repeat = extract_float("- compile_repeat_sec: ")
    report_age_hours = (datetime.now(timezone.utc).timestamp() - report_path.stat().st_mtime) / 3600

    if total_runtime is None or total_runtime > float(cfg["max_total_runtime_sec"]):
        findings.append(
            {
                "check": "load_test",
                "path": str(report_path.relative_to(ROOT)),
                "message": f"total_runtime_sec exceeds limit: {total_runtime}",
            }
        )
    if compile_repeat is None or compile_repeat > float(cfg["max_compile_repeat_sec"]):
        findings.append(
            {
                "check": "load_test",
                "path": str(report_path.relative_to(ROOT)),
                "message": f"compile_repeat_sec exceeds limit: {compile_repeat}",
            }
        )
    if report_age_hours > float(cfg["max_report_age_hours"]):
        findings.append(
            {
                "check": "load_test",
                "path": str(report_path.relative_to(ROOT)),
                "message": f"latest report too old: {report_age_hours:.2f}h",
            }
        )
    for marker_key in ["require_recent_query_focus", "require_conflict_query_focus"]:
        marker = cfg[marker_key]
        if marker not in text:
            findings.append(
                {
                    "check": "load_test",
                    "path": str(report_path.relative_to(ROOT)),
                    "message": f"missing marker: {marker}",
                }
            )

    return findings


def check_artifact_hygiene(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    cfg = profile["artifact_hygiene"]
    for glob_pattern in cfg["forbidden_globs"]:
        matches = sorted(ROOT.glob(glob_pattern))
        for path in matches:
            findings.append(
                {
                    "check": "artifact_hygiene",
                    "path": str(path.relative_to(ROOT)),
                    "message": f"forbidden residual artifact matched: {glob_pattern}",
                }
            )
    return findings


def markdown_field(text: str, label: str) -> str | None:
    prefix = f"- {label}: `"
    for line in text.splitlines():
        if line.startswith(prefix) and line.endswith("`"):
            return line[len(prefix):-1]
    return None


def check_operator_alignment(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    cfg = profile["operator_alignment"]
    required_states = set(cfg["required_states"])

    operator_payload = run_json_command("operator-summary")
    supervisor_payload = run_json_command("workflow-supervisor", "--mode", str(cfg["supervisor_mode"]))
    mode_payload = run_json_command("mode-brief", "--mode", str(cfg["mode"]))

    operator_plan = operator_payload.get("action_plan", {})
    operator_state = operator_plan.get("state")
    operator_summary = operator_plan.get("summary")
    supervisor_state = supervisor_payload.get("operator_state")
    supervisor_summary = supervisor_payload.get("operator_summary")
    mode_state = mode_payload.get("current_operator_state")
    mode_summary = mode_payload.get("current_operator_summary")

    if operator_state not in required_states:
        findings.append(
            {
                "check": "operator_alignment",
                "path": "operator-summary",
                "message": f"unexpected operator state: {operator_state}",
            }
        )

    state_values = [operator_state, supervisor_state, mode_state]
    if len(set(state_values)) != 1:
        findings.append(
            {
                "check": "operator_alignment",
                "path": "operator-summary/workflow-supervisor/mode-brief",
                "message": f"state mismatch: operator={operator_state}, supervisor={supervisor_state}, mode={mode_state}",
            }
        )

    summary_values = [operator_summary, supervisor_summary, mode_summary]
    if len(set(summary_values)) != 1:
        findings.append(
            {
                "check": "operator_alignment",
                "path": "operator-summary/workflow-supervisor/mode-brief",
                "message": "summary mismatch across operator surfaces",
            }
        )

    supervisor_latest = (ROOT / "reports" / "supervisor_latest.md").read_text(encoding="utf-8")
    latest_state = markdown_field(supervisor_latest, "state")
    latest_summary = markdown_field(supervisor_latest, "summary")
    if latest_state != operator_state:
        findings.append(
            {
                "check": "operator_alignment",
                "path": "reports/supervisor_latest.md",
                "message": f"supervisor_latest state mismatch: {latest_state} != {operator_state}",
            }
        )
    if latest_summary != operator_summary:
        findings.append(
            {
                "check": "operator_alignment",
                "path": "reports/supervisor_latest.md",
                "message": "supervisor_latest summary mismatch",
            }
        )

    return findings


def check_operator_state_model(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    wiki_runtime = load_wiki_runtime_module()

    cases = {
        "sync_runtime": wiki_runtime.operator_action_plan(
            {"lock_stale_count": 0, "archive_should_run": False},
            None,
        ),
        "repair_runtime": wiki_runtime.operator_action_plan(
            {"lock_stale_count": 0, "archive_should_run": False},
            {"maintenance_clean": False, "static_lint_clean": True, "ready_count": 0, "refresh_existing_count": 0},
        ),
        "apply_knowledge_changes": wiki_runtime.operator_action_plan(
            {"lock_stale_count": 0, "archive_should_run": False},
            {"maintenance_clean": True, "static_lint_clean": True, "ready_count": 2, "refresh_existing_count": 1},
        ),
        "idle_watch": wiki_runtime.operator_action_plan(
            {"lock_stale_count": 0, "archive_should_run": False},
            {"maintenance_clean": True, "static_lint_clean": True, "ready_count": 0, "refresh_existing_count": 0},
        ),
    }

    for case_name in profile["operator_state_model"]["cases"]:
        payload = cases.get(case_name)
        if not isinstance(payload, dict):
            findings.append(
                {
                    "check": "operator_state_model",
                    "path": "operator_action_plan",
                    "message": f"unknown validation case: {case_name}",
                }
            )
            continue
        actual_state = payload.get("state")
        if actual_state != case_name:
            findings.append(
                {
                    "check": "operator_state_model",
                    "path": "operator_action_plan",
                    "message": f"case {case_name} returned {actual_state}",
                }
            )
        if not payload.get("summary"):
            findings.append(
                {
                    "check": "operator_state_model",
                    "path": "operator_action_plan",
                    "message": f"case {case_name} missing summary",
                }
            )
        actions = payload.get("actions")
        if not isinstance(actions, list) or not actions:
            findings.append(
                {
                    "check": "operator_state_model",
                    "path": "operator_action_plan",
                    "message": f"case {case_name} missing actions",
                }
            )

    return findings


def synthetic_governance(case_name: str) -> dict[str, Any] | None:
    if case_name == "sync_runtime":
        return None
    if case_name == "repair_runtime":
        return {
            "report_path": str(ROOT / "reports" / "governance_cycle_case.md"),
            "maintenance_clean": False,
            "static_lint_clean": True,
            "ready_count": 0,
            "refresh_existing_count": 0,
        }
    if case_name == "apply_knowledge_changes":
        return {
            "report_path": str(ROOT / "reports" / "governance_cycle_case.md"),
            "maintenance_clean": True,
            "static_lint_clean": True,
            "ready_count": 2,
            "refresh_existing_count": 1,
        }
    if case_name == "idle_watch":
        return {
            "report_path": str(ROOT / "reports" / "governance_cycle_case.md"),
            "maintenance_clean": True,
            "static_lint_clean": True,
            "ready_count": 0,
            "refresh_existing_count": 0,
        }
    return None


def check_surface_state_rendering(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    wiki_runtime = load_wiki_runtime_module()

    base_status = {
        "lock_running_count": 0,
        "lock_stale_count": 0,
        "archive_candidate_count": 0,
        "archive_should_run": False,
    }
    base_supervisor = {
        "generated_at": "2026-04-15 00:00:00",
        "mode": "intake",
        "report_path": str(ROOT / "reports" / "supervisor_cycle_case.md"),
        "governance_report_path": str(ROOT / "reports" / "governance_cycle_case.md"),
        "step_count": 3,
        "ingest_processed": 0,
        "lint_clean": "not_run",
        "promotion_ready_count": 0,
        "update_refresh_count": 0,
        "archive_advisory": {"candidate_count": 0, "threshold": 10, "should_archive": False},
    }

    for case_name in profile["surface_state_rendering"]["cases"]:
        governance = synthetic_governance(case_name)
        action_plan = wiki_runtime.operator_action_plan(base_status, governance)

        operator_payload = {
            "generated_at": "2026-04-15 00:00:00",
            "status": base_status,
            "governance": governance or {},
            "supervisor": {"report_path": str(ROOT / "reports" / "supervisor_cycle_case.md")},
            "action_plan": action_plan,
        }
        operator_body = wiki_runtime.build_operator_latest_body(operator_payload)
        expected_state_line = f"- state: `{case_name}`"
        expected_summary_line = f"- summary: `{action_plan['summary']}`"
        if expected_state_line not in operator_body:
            findings.append(
                {
                    "check": "surface_state_rendering",
                    "path": "build_operator_latest_body",
                    "message": f"{case_name} state not rendered in operator body",
                }
            )
        if expected_summary_line not in operator_body:
            findings.append(
                {
                    "check": "surface_state_rendering",
                    "path": "build_operator_latest_body",
                    "message": f"{case_name} summary not rendered in operator body",
                }
            )

        supervisor_payload = dict(base_supervisor)
        supervisor_payload["action_plan"] = action_plan
        if governance is not None:
            supervisor_payload["promotion_ready_count"] = int(governance["ready_count"])
            supervisor_payload["update_refresh_count"] = int(governance["refresh_existing_count"])
        supervisor_body = wiki_runtime.build_supervisor_latest_body(supervisor_payload)
        if expected_state_line not in supervisor_body:
            findings.append(
                {
                    "check": "surface_state_rendering",
                    "path": "build_supervisor_latest_body",
                    "message": f"{case_name} state not rendered in supervisor body",
                }
            )
        if expected_summary_line not in supervisor_body:
            findings.append(
                {
                    "check": "surface_state_rendering",
                    "path": "build_supervisor_latest_body",
                    "message": f"{case_name} summary not rendered in supervisor body",
                }
            )

    return findings


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sandbox_governance_payload(root: Path, case_name: str) -> dict[str, Any] | None:
    report_path = root / "reports" / "governance_cycle_case.md"
    if case_name == "sync_runtime":
        return None
    if case_name == "repair_runtime":
        return {
            "generated_at": "2026-04-15 00:00:00",
            "report_path": str(report_path),
            "maintenance_clean": False,
            "static_lint_clean": True,
            "ready_count": 0,
            "refresh_existing_count": 0,
        }
    if case_name == "apply_knowledge_changes":
        return {
            "generated_at": "2026-04-15 00:00:00",
            "report_path": str(report_path),
            "maintenance_clean": True,
            "static_lint_clean": True,
            "ready_count": 2,
            "refresh_existing_count": 1,
        }
    if case_name == "idle_watch":
        return {
            "generated_at": "2026-04-15 00:00:00",
            "report_path": str(report_path),
            "maintenance_clean": True,
            "static_lint_clean": True,
            "ready_count": 0,
            "refresh_existing_count": 0,
        }
    return None


def sandbox_supervisor_payload(root: Path, case_name: str, action_plan: dict[str, Any]) -> dict[str, Any]:
    governance_report = root / "reports" / "governance_cycle_case.md"
    supervisor_report = root / "reports" / "supervisor_cycle_case.md"
    payload = {
        "generated_at": "2026-04-15 00:00:00",
        "mode": "intake",
        "report_path": str(supervisor_report),
        "governance_report_path": str(governance_report),
        "step_count": 3,
        "ingest_processed": 0,
        "lint_clean": "not_run",
        "promotion_ready_count": 0,
        "update_refresh_count": 0,
        "archive_advisory": {"candidate_count": 0, "threshold": 10, "should_archive": False},
        "action_plan": action_plan,
    }
    governance = sandbox_governance_payload(root, case_name)
    if governance is not None:
        payload["promotion_ready_count"] = int(governance["ready_count"])
        payload["update_refresh_count"] = int(governance["refresh_existing_count"])
    return payload


def check_temp_surface_sandbox(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    wiki_runtime = load_wiki_runtime_module()

    originals = {
        "ROOT": wiki_runtime.ROOT,
        "REPORTS_ROOT": wiki_runtime.REPORTS_ROOT,
        "STATE_ROOT": wiki_runtime.STATE_ROOT,
        "GOVERNANCE_CYCLE_CACHE": wiki_runtime.GOVERNANCE_CYCLE_CACHE,
        "SUPERVISOR_CYCLE_CACHE": wiki_runtime.SUPERVISOR_CYCLE_CACHE,
        "GOVERNANCE_LATEST": wiki_runtime.GOVERNANCE_LATEST,
        "SUPERVISOR_LATEST": wiki_runtime.SUPERVISOR_LATEST,
        "OPERATOR_LATEST": wiki_runtime.OPERATOR_LATEST,
        "ensure_dirs": wiki_runtime.ensure_dirs,
        "status_payload": wiki_runtime.status_payload,
        "run_supervisor_cycle": wiki_runtime.run_supervisor_cycle,
    }

    try:
        for case_name in profile["temp_surface_sandbox"]["cases"]:
            with tempfile.TemporaryDirectory() as temp_dir:
                sandbox_root = Path(temp_dir)
                reports_root = sandbox_root / "reports"
                state_root = sandbox_root / "_runtime_state"
                reports_root.mkdir(parents=True, exist_ok=True)
                state_root.mkdir(parents=True, exist_ok=True)

                governance_report = reports_root / "governance_cycle_case.md"
                governance_report.write_text("# governance-case\n", encoding="utf-8")
                supervisor_report = reports_root / "supervisor_cycle_case.md"
                supervisor_report.write_text("# supervisor-case\n", encoding="utf-8")

                governance_payload = sandbox_governance_payload(sandbox_root, case_name)
                if governance_payload is not None:
                    write_json(
                        state_root / "governance_cycle_cache.json",
                        {"payload": governance_payload},
                    )

                wiki_runtime.ROOT = sandbox_root
                wiki_runtime.REPORTS_ROOT = reports_root
                wiki_runtime.STATE_ROOT = state_root
                wiki_runtime.GOVERNANCE_CYCLE_CACHE = state_root / "governance_cycle_cache.json"
                wiki_runtime.SUPERVISOR_CYCLE_CACHE = state_root / "supervisor_cycle_cache.json"
                wiki_runtime.GOVERNANCE_LATEST = reports_root / "governance_latest.md"
                wiki_runtime.SUPERVISOR_LATEST = reports_root / "supervisor_latest.md"
                wiki_runtime.OPERATOR_LATEST = reports_root / "operator_latest.md"
                wiki_runtime.ensure_dirs = lambda: None
                wiki_runtime.status_payload = lambda: {
                    "lock_running_count": 0,
                    "lock_stale_count": 0,
                    "archive_candidate_count": 0,
                    "archive_should_run": False,
                }

                operator_payload = wiki_runtime.operator_summary_payload()
                mode_payload = wiki_runtime.mode_brief("runtime")
                supervisor_cycle_payload = sandbox_supervisor_payload(
                    sandbox_root,
                    case_name,
                    operator_payload.get("action_plan", {}),
                )
                write_json(
                    state_root / "supervisor_cycle_cache.json",
                    {"payload": supervisor_cycle_payload},
                )
                wiki_runtime.sync_supervisor_summary_views(supervisor_cycle_payload)
                wiki_runtime.run_supervisor_cycle = lambda mode, payload=supervisor_cycle_payload: payload
                workflow_supervisor_payload = wiki_runtime.workflow_supervisor("intake")
                operator_state = operator_payload.get("action_plan", {}).get("state")
                mode_state = mode_payload.get("current_operator_state")
                if operator_state != case_name:
                    findings.append(
                        {
                            "check": "temp_surface_sandbox",
                            "path": "operator_summary_payload",
                            "message": f"{case_name} produced {operator_state}",
                        }
                    )
                if mode_state != case_name:
                    findings.append(
                        {
                            "check": "temp_surface_sandbox",
                            "path": "mode_brief",
                            "message": f"{case_name} mode snapshot produced {mode_state}",
                        }
                    )
                supervisor_state = workflow_supervisor_payload.get("operator_state")
                if supervisor_state != case_name:
                    findings.append(
                        {
                            "check": "temp_surface_sandbox",
                            "path": "workflow_supervisor",
                            "message": f"{case_name} workflow-supervisor produced {supervisor_state}",
                        }
                    )

                operator_latest = (reports_root / "operator_latest.md").read_text(encoding="utf-8")
                summary = operator_payload.get("action_plan", {}).get("summary", "")
                if f"- state: `{case_name}`" not in operator_latest:
                    findings.append(
                        {
                            "check": "temp_surface_sandbox",
                            "path": "reports/operator_latest.md",
                            "message": f"{case_name} state not written in sandbox operator_latest",
                        }
                    )
                if summary and f"- summary: `{summary}`" not in operator_latest:
                    findings.append(
                        {
                            "check": "temp_surface_sandbox",
                            "path": "reports/operator_latest.md",
                            "message": f"{case_name} summary not written in sandbox operator_latest",
                        }
                    )
                supervisor_latest = (reports_root / "supervisor_latest.md").read_text(encoding="utf-8")
                if f"- state: `{case_name}`" not in supervisor_latest:
                    findings.append(
                        {
                            "check": "temp_surface_sandbox",
                            "path": "reports/supervisor_latest.md",
                            "message": f"{case_name} state not written in sandbox supervisor_latest",
                        }
                    )
                if summary and f"- summary: `{summary}`" not in supervisor_latest:
                    findings.append(
                        {
                            "check": "temp_surface_sandbox",
                            "path": "reports/supervisor_latest.md",
                            "message": f"{case_name} summary not written in sandbox supervisor_latest",
                        }
                    )
    finally:
        wiki_runtime.ROOT = originals["ROOT"]
        wiki_runtime.REPORTS_ROOT = originals["REPORTS_ROOT"]
        wiki_runtime.STATE_ROOT = originals["STATE_ROOT"]
        wiki_runtime.GOVERNANCE_CYCLE_CACHE = originals["GOVERNANCE_CYCLE_CACHE"]
        wiki_runtime.SUPERVISOR_CYCLE_CACHE = originals["SUPERVISOR_CYCLE_CACHE"]
        wiki_runtime.GOVERNANCE_LATEST = originals["GOVERNANCE_LATEST"]
        wiki_runtime.SUPERVISOR_LATEST = originals["SUPERVISOR_LATEST"]
        wiki_runtime.OPERATOR_LATEST = originals["OPERATOR_LATEST"]
        wiki_runtime.ensure_dirs = originals["ensure_dirs"]
        wiki_runtime.status_payload = originals["status_payload"]
        wiki_runtime.run_supervisor_cycle = originals["run_supervisor_cycle"]

    return findings


def write_lock(path: Path, pid: int, loop: str, mode: str | None = None, owner: str | None = None) -> None:
    payload: dict[str, Any] = {
        "pid": pid,
        "started_at": "2026-04-15 00:00:00",
        "loop": loop,
    }
    if mode:
        payload["mode"] = mode
    if owner:
        payload["owner"] = owner
    write_json(path, payload)


def check_lock_sandbox(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    wiki_runtime = load_wiki_runtime_module()

    originals = {
        "ROOT": wiki_runtime.ROOT,
        "STATE_ROOT": wiki_runtime.STATE_ROOT,
        "AUTOPILOT_LOCK": wiki_runtime.AUTOPILOT_LOCK,
        "WIKI_ROOT": wiki_runtime.WIKI_ROOT,
        "LITE_ROOT": wiki_runtime.LITE_ROOT,
        "HOT_DB": wiki_runtime.HOT_DB,
        "COLD_DB": wiki_runtime.COLD_DB,
        "HOT_BUILD_POINTER": wiki_runtime.HOT_BUILD_POINTER,
        "COLD_BUILD_POINTER": wiki_runtime.COLD_BUILD_POINTER,
        "MAINTENANCE_AUTORUN_STATE": wiki_runtime.MAINTENANCE_AUTORUN_STATE,
        "COMPILE_STATE_CACHE": wiki_runtime.COMPILE_STATE_CACHE,
        "LINT_BUNDLE_CACHE": wiki_runtime.LINT_BUNDLE_CACHE,
        "PROMOTION_ENTRIES_CACHE": wiki_runtime.PROMOTION_ENTRIES_CACHE,
        "UPDATE_ENTRIES_CACHE": wiki_runtime.UPDATE_ENTRIES_CACHE,
        "REPAIR_QUEUE_REPORT_CACHE": wiki_runtime.REPAIR_QUEUE_REPORT_CACHE,
        "PROMOTION_QUEUE_REPORT_CACHE": wiki_runtime.PROMOTION_QUEUE_REPORT_CACHE,
        "UPDATE_QUEUE_REPORT_CACHE": wiki_runtime.UPDATE_QUEUE_REPORT_CACHE,
        "GOVERNANCE_CYCLE_CACHE": wiki_runtime.GOVERNANCE_CYCLE_CACHE,
        "archive_advisory": wiki_runtime.archive_advisory,
        "process_is_alive": wiki_runtime.process_is_alive,
    }

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            sandbox_root = Path(temp_dir)
            state_root = sandbox_root / "_runtime_state"
            state_root.mkdir(parents=True, exist_ok=True)

            wiki_runtime.ROOT = sandbox_root
            wiki_runtime.STATE_ROOT = state_root
            wiki_runtime.AUTOPILOT_LOCK = state_root / "autopilot.lock"
            wiki_runtime.WIKI_ROOT = sandbox_root / "wiki"
            wiki_runtime.LITE_ROOT = sandbox_root / "wiki_lite"
            wiki_runtime.HOT_DB = sandbox_root / "retrieval" / "data" / "hot.sqlite"
            wiki_runtime.COLD_DB = sandbox_root / "retrieval" / "data" / "cold.sqlite"
            wiki_runtime.HOT_BUILD_POINTER = sandbox_root / "retrieval" / "data" / "hot_root.txt"
            wiki_runtime.COLD_BUILD_POINTER = sandbox_root / "retrieval" / "data" / "cold_root.txt"
            wiki_runtime.MAINTENANCE_AUTORUN_STATE = state_root / "maintenance_autorun_state.json"
            wiki_runtime.COMPILE_STATE_CACHE = state_root / "compile_state_cache.json"
            wiki_runtime.LINT_BUNDLE_CACHE = state_root / "lint_bundle_cache.json"
            wiki_runtime.PROMOTION_ENTRIES_CACHE = state_root / "promotion_entries_cache.json"
            wiki_runtime.UPDATE_ENTRIES_CACHE = state_root / "update_entries_cache.json"
            wiki_runtime.REPAIR_QUEUE_REPORT_CACHE = state_root / "repair_queue_report_cache.json"
            wiki_runtime.PROMOTION_QUEUE_REPORT_CACHE = state_root / "promotion_queue_report_cache.json"
            wiki_runtime.UPDATE_QUEUE_REPORT_CACHE = state_root / "update_queue_report_cache.json"
            wiki_runtime.GOVERNANCE_CYCLE_CACHE = state_root / "governance_cycle_cache.json"
            wiki_runtime.archive_advisory = lambda threshold=10: {
                "generated_at": "2026-04-15 00:00:00",
                "archive_root": str(sandbox_root / "reports" / "archive"),
                "protected_count": 0,
                "candidate_count": 0,
                "should_archive": False,
                "threshold": threshold,
                "sample_candidates": [],
            }

            autopilot_lock = wiki_runtime.AUTOPILOT_LOCK
            watch_lock = autopilot_lock.with_name("watch.lock")
            intake_scope_lock = wiki_runtime.intake_scope_lock_path()

            wiki_runtime.process_is_alive = lambda pid: False
            write_lock(autopilot_lock, 11111, "autopilot")
            write_lock(watch_lock, 22222, "watch")

            stale_status = wiki_runtime.lock_status()
            if stale_status.get("stale_count") != 2:
                findings.append(
                    {
                        "check": "lock_sandbox",
                        "path": "_runtime_state/*.lock",
                        "message": f"expected stale_count=2, got {stale_status.get('stale_count')}",
                    }
                )

            stale_payload = wiki_runtime.status_payload()
            if stale_payload.get("lock_stale_count") != 2:
                findings.append(
                    {
                        "check": "lock_sandbox",
                        "path": "status_payload",
                        "message": f"expected status lock_stale_count=2, got {stale_payload.get('lock_stale_count')}",
                    }
                )

            cleared = wiki_runtime.clear_stale_locks()
            if cleared.get("removed_count") != 2:
                findings.append(
                    {
                        "check": "lock_sandbox",
                        "path": "clear_stale_locks",
                        "message": f"expected removed_count=2, got {cleared.get('removed_count')}",
                    }
                )

            absent_status = wiki_runtime.lock_status()
            if absent_status.get("stale_count") != 0:
                findings.append(
                    {
                        "check": "lock_sandbox",
                        "path": "_runtime_state/*.lock",
                        "message": f"expected stale_count=0 after clear, got {absent_status.get('stale_count')}",
                    }
                )
            if any(item.get("state") != "absent" for item in absent_status.get("locks", [])):
                findings.append(
                    {
                        "check": "lock_sandbox",
                        "path": "_runtime_state/*.lock",
                        "message": "expected all locks to be absent after clearing stale locks",
                    }
                )

            wiki_runtime.process_is_alive = lambda pid: True
            write_lock(autopilot_lock, 33333, "autopilot", "full")
            running_status = wiki_runtime.lock_status()
            running_states = {item["lock"]: item["state"] for item in running_status.get("locks", [])}
            if running_states.get("autopilot") != "running":
                findings.append(
                    {
                        "check": "lock_sandbox",
                        "path": str(autopilot_lock),
                        "message": f"expected autopilot lock to be running, got {running_states.get('autopilot')}",
                    }
                )

            cleared_running = wiki_runtime.clear_stale_locks()
            if cleared_running.get("removed_count") != 0:
                findings.append(
                    {
                        "check": "lock_sandbox",
                        "path": "clear_stale_locks",
                        "message": "running lock should not be removed",
                    }
                )
            if not autopilot_lock.exists():
                findings.append(
                    {
                        "check": "lock_sandbox",
                        "path": str(autopilot_lock),
                        "message": "running autopilot lock disappeared after clear_stale_locks",
                    }
                )

            try:
                wiki_runtime.enforce_loop_start_compatibility("watch", "intake")
                findings.append(
                    {
                        "check": "lock_sandbox",
                        "path": str(watch_lock),
                        "message": "watch start was not blocked while autopilot full lock was running",
                    }
                )
            except RuntimeError as exc:
                if "autopilot full" not in str(exc):
                    findings.append(
                        {
                            "check": "lock_sandbox",
                            "path": str(watch_lock),
                        "message": f"unexpected watch contention error: {exc}",
                    }
                )

            autopilot_lock.unlink()
            write_lock(watch_lock, 44444, "watch", "intake")
            try:
                wiki_runtime.enforce_loop_start_compatibility("autopilot", "full")
                findings.append(
                    {
                        "check": "lock_sandbox",
                        "path": str(autopilot_lock),
                        "message": "autopilot full start was not blocked while watch lock was running",
                    }
                )
            except RuntimeError as exc:
                if "watch intake" not in str(exc):
                    findings.append(
                        {
                            "check": "lock_sandbox",
                            "path": str(autopilot_lock),
                        "message": f"unexpected autopilot contention error: {exc}",
                    }
                )

            try:
                wiki_runtime.enforce_loop_start_compatibility("autopilot", "maintenance")
            except RuntimeError as exc:
                findings.append(
                    {
                        "check": "lock_sandbox",
                        "path": str(autopilot_lock),
                        "message": f"autopilot maintenance should remain compatible with watch lock, got: {exc}",
                    }
                )

            watch_lock.unlink()
            write_lock(intake_scope_lock, 55555, "intake_scope", "raw_intake", "watch")
            try:
                wiki_runtime.enforce_loop_start_compatibility("autopilot", "full")
                findings.append(
                    {
                        "check": "lock_sandbox",
                        "path": str(intake_scope_lock),
                        "message": "autopilot full start was not blocked while intake scope lock was held by watch",
                    }
                )
            except RuntimeError as exc:
                if "raw intake scope" not in str(exc):
                    findings.append(
                        {
                            "check": "lock_sandbox",
                            "path": str(intake_scope_lock),
                            "message": f"unexpected intake scope contention error for autopilot full: {exc}",
                        }
                    )

            intake_scope_lock.unlink()
            write_lock(intake_scope_lock, 66666, "intake_scope", "raw_intake", "autopilot")
            try:
                wiki_runtime.enforce_loop_start_compatibility("watch", "intake")
                findings.append(
                    {
                        "check": "lock_sandbox",
                        "path": str(intake_scope_lock),
                        "message": "watch start was not blocked while intake scope lock was held by autopilot",
                    }
                )
            except RuntimeError as exc:
                if "raw intake scope" not in str(exc):
                    findings.append(
                        {
                            "check": "lock_sandbox",
                            "path": str(intake_scope_lock),
                            "message": f"unexpected intake scope contention error for watch: {exc}",
                        }
                    )
    finally:
        wiki_runtime.ROOT = originals["ROOT"]
        wiki_runtime.STATE_ROOT = originals["STATE_ROOT"]
        wiki_runtime.AUTOPILOT_LOCK = originals["AUTOPILOT_LOCK"]
        wiki_runtime.WIKI_ROOT = originals["WIKI_ROOT"]
        wiki_runtime.LITE_ROOT = originals["LITE_ROOT"]
        wiki_runtime.HOT_DB = originals["HOT_DB"]
        wiki_runtime.COLD_DB = originals["COLD_DB"]
        wiki_runtime.HOT_BUILD_POINTER = originals["HOT_BUILD_POINTER"]
        wiki_runtime.COLD_BUILD_POINTER = originals["COLD_BUILD_POINTER"]
        wiki_runtime.MAINTENANCE_AUTORUN_STATE = originals["MAINTENANCE_AUTORUN_STATE"]
        wiki_runtime.COMPILE_STATE_CACHE = originals["COMPILE_STATE_CACHE"]
        wiki_runtime.LINT_BUNDLE_CACHE = originals["LINT_BUNDLE_CACHE"]
        wiki_runtime.PROMOTION_ENTRIES_CACHE = originals["PROMOTION_ENTRIES_CACHE"]
        wiki_runtime.UPDATE_ENTRIES_CACHE = originals["UPDATE_ENTRIES_CACHE"]
        wiki_runtime.REPAIR_QUEUE_REPORT_CACHE = originals["REPAIR_QUEUE_REPORT_CACHE"]
        wiki_runtime.PROMOTION_QUEUE_REPORT_CACHE = originals["PROMOTION_QUEUE_REPORT_CACHE"]
        wiki_runtime.UPDATE_QUEUE_REPORT_CACHE = originals["UPDATE_QUEUE_REPORT_CACHE"]
        wiki_runtime.GOVERNANCE_CYCLE_CACHE = originals["GOVERNANCE_CYCLE_CACHE"]
        wiki_runtime.archive_advisory = originals["archive_advisory"]
        wiki_runtime.process_is_alive = originals["process_is_alive"]

    return findings


def check_archive_sandbox(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    wiki_runtime = load_wiki_runtime_module()

    originals = {
        "ROOT": wiki_runtime.ROOT,
        "REPORTS_ROOT": wiki_runtime.REPORTS_ROOT,
        "STATE_ROOT": wiki_runtime.STATE_ROOT,
        "REPORT_ARCHIVE_ROOT": wiki_runtime.REPORT_ARCHIVE_ROOT,
        "GOVERNANCE_LATEST": wiki_runtime.GOVERNANCE_LATEST,
        "SUPERVISOR_LATEST": wiki_runtime.SUPERVISOR_LATEST,
        "OPERATOR_LATEST": wiki_runtime.OPERATOR_LATEST,
        "ensure_dirs": wiki_runtime.ensure_dirs,
    }

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            sandbox_root = Path(temp_dir)
            reports_root = sandbox_root / "reports"
            state_root = sandbox_root / "_runtime_state"
            archive_root = reports_root / "archive"
            reports_root.mkdir(parents=True, exist_ok=True)
            state_root.mkdir(parents=True, exist_ok=True)

            wiki_runtime.ROOT = sandbox_root
            wiki_runtime.REPORTS_ROOT = reports_root
            wiki_runtime.STATE_ROOT = state_root
            wiki_runtime.REPORT_ARCHIVE_ROOT = archive_root
            wiki_runtime.GOVERNANCE_LATEST = reports_root / "governance_latest.md"
            wiki_runtime.SUPERVISOR_LATEST = reports_root / "supervisor_latest.md"
            wiki_runtime.OPERATOR_LATEST = reports_root / "operator_latest.md"
            wiki_runtime.ensure_dirs = lambda: None

            protected_governance = reports_root / "governance_cycle_20260415_010101.md"
            protected_governance.write_text("# governance detail\n", encoding="utf-8")
            retained_governance_recent = reports_root / "governance_cycle_20260415_020202.md"
            retained_governance_recent.write_text("# governance recent\n", encoding="utf-8")
            archived_governance_old = reports_root / "governance_cycle_20260414_020202.md"
            archived_governance_old.write_text("# governance old\n", encoding="utf-8")
            protected_supervisor = reports_root / "supervisor_cycle_20260415_010101.md"
            protected_supervisor.write_text("# supervisor detail\n", encoding="utf-8")
            retained_supervisor_recent = reports_root / "supervisor_cycle_20260415_020202.md"
            retained_supervisor_recent.write_text("# supervisor recent\n", encoding="utf-8")
            archived_supervisor_old = reports_root / "supervisor_cycle_20260414_020202.md"
            archived_supervisor_old.write_text("# supervisor old\n", encoding="utf-8")
            protected_repair = reports_root / "repair_queue_20260415_010101.md"
            protected_repair.write_text("# repair detail\n", encoding="utf-8")
            retained_repair_recent = reports_root / "repair_queue_20260415_020202.md"
            retained_repair_recent.write_text("# repair recent\n", encoding="utf-8")
            archived_candidate = reports_root / "repair_queue_20260414_010101.md"
            archived_candidate.write_text("# old repair detail\n", encoding="utf-8")
            retained_promotion_recent = reports_root / "promotion_queue_20260415_020202.md"
            retained_promotion_recent.write_text("# promotion recent\n", encoding="utf-8")
            archived_candidate_two = reports_root / "promotion_queue_20260414_010101.md"
            archived_candidate_two.write_text("# old promotion detail\n", encoding="utf-8")
            load_test_old = reports_root / "load_test_m_20260414_010101.md"
            load_test_old.write_text("# old load test\n", encoding="utf-8")
            load_test_old.with_suffix(".json").write_text("{}", encoding="utf-8")
            load_test_latest = reports_root / "load_test_m_20260415_010101.md"
            load_test_latest.write_text("# latest load test\n", encoding="utf-8")
            load_test_latest.with_suffix(".json").write_text("{}", encoding="utf-8")
            old_root_ts = datetime(2026, 4, 14, 2, 2, 2, tzinfo=timezone.utc).timestamp()
            recent_root_ts = datetime(2026, 4, 15, 2, 2, 2, tzinfo=timezone.utc).timestamp()
            old_ts = datetime(2026, 4, 14, 1, 1, 1, tzinfo=timezone.utc).timestamp()
            latest_ts = datetime(2026, 4, 15, 1, 1, 1, tzinfo=timezone.utc).timestamp()
            for path in [retained_governance_recent, retained_supervisor_recent, retained_repair_recent, retained_promotion_recent]:
                os.utime(path, (recent_root_ts, recent_root_ts))
            for path in [archived_governance_old, archived_supervisor_old, archived_candidate, archived_candidate_two]:
                os.utime(path, (old_root_ts, old_root_ts))
            os.utime(load_test_old, (old_ts, old_ts))
            os.utime(load_test_old.with_suffix(".json"), (old_ts, old_ts))
            os.utime(load_test_latest, (latest_ts, latest_ts))
            os.utime(load_test_latest.with_suffix(".json"), (latest_ts, latest_ts))
            stray_txt = reports_root / "_runtime_smoke.txt"
            stray_txt.write_text("smoke\n", encoding="utf-8")
            stray_bucket = datetime.fromtimestamp(stray_txt.stat().st_mtime).strftime("%Y%m%d")

            wiki_runtime.GOVERNANCE_LATEST.write_text(
                "\n".join(
                    [
                        "# governance-latest",
                        "",
                        f"- governance: [{protected_governance.name}]({protected_governance.name})",
                        f"- repair_queue: [{protected_repair.name}]({protected_repair.name})",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            governance_daily = reports_root / "governance_daily_20260415.md"
            governance_daily.write_text(
                "\n".join(
                    [
                        "# governance-daily",
                        "",
                        f"- governance: [{archived_governance_old.name}]({archived_governance_old.name})",
                        f"- governance_recent: [{retained_governance_recent.name}]({retained_governance_recent.name})",
                        f"- repair_queue: [{archived_candidate.name}]({archived_candidate.name})",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            wiki_runtime.SUPERVISOR_LATEST.write_text(
                "\n".join(
                    [
                        "# supervisor-latest",
                        "",
                        f"- supervisor: [{protected_supervisor.name}]({protected_supervisor.name})",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            supervisor_daily = reports_root / "supervisor_daily_20260415.md"
            supervisor_daily.write_text(
                "\n".join(
                    [
                        "# supervisor-daily",
                        "",
                        f"- supervisor: [{archived_supervisor_old.name}]({archived_supervisor_old.name})",
                        f"- supervisor_recent: [{retained_supervisor_recent.name}]({retained_supervisor_recent.name})",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            wiki_runtime.OPERATOR_LATEST.write_text("# operator-latest\n", encoding="utf-8")

            write_json(
                state_root / "governance_cycle_cache.json",
                {"payload": {"report_path": str(protected_governance)}},
            )
            write_json(
                state_root / "repair_queue_report_cache.json",
                {"payload": {"report_path": str(protected_repair)}},
            )
            write_json(
                state_root / "supervisor_cycle_cache.json",
                {"payload": {"report_path": str(protected_supervisor)}},
            )

            advisory = wiki_runtime.archive_advisory(threshold=1)
            candidate_names = set(advisory.get("sample_candidates", []))
            if advisory.get("candidate_count") != 8:
                findings.append(
                    {
                        "check": "archive_sandbox",
                        "path": "archive_advisory",
                        "message": f"expected candidate_count=8, got {advisory.get('candidate_count')}",
                    }
                )
            expected_family_counts = {
                "governance_cycle": 1,
                "supervisor_cycle": 1,
                "repair_queue": 2,
                "promotion_queue": 1,
                "load_test_m": 2,
                "runtime_text": 1,
            }
            if advisory.get("candidate_family_counts") != expected_family_counts:
                findings.append(
                    {
                        "check": "archive_sandbox",
                        "path": "archive_advisory",
                        "message": f"unexpected candidate_family_counts: {advisory.get('candidate_family_counts')}",
                    }
                )
            expected_retained_counts = {
                "governance_cycle": 1,
                "supervisor_cycle": 1,
                "promotion_queue": 1,
            }
            if advisory.get("root_retained_family_counts") != expected_retained_counts:
                findings.append(
                    {
                        "check": "archive_sandbox",
                        "path": "archive_advisory",
                        "message": f"unexpected root_retained_family_counts: {advisory.get('root_retained_family_counts')}",
                    }
                )
            expected_candidates = {
                archived_governance_old.name,
                archived_supervisor_old.name,
                retained_repair_recent.name,
                archived_candidate.name,
                archived_candidate_two.name,
                load_test_old.name,
                load_test_old.with_suffix('.json').name,
                stray_txt.name,
            }
            if not candidate_names.issubset(expected_candidates):
                findings.append(
                    {
                        "check": "archive_sandbox",
                        "path": "archive_advisory",
                        "message": f"unexpected sample candidates: {sorted(candidate_names)}",
                    }
                )

            archive_result = wiki_runtime.archive_reports(apply=True)
            if archive_result.get("candidate_count") != 8:
                findings.append(
                    {
                        "check": "archive_sandbox",
                        "path": "archive_reports",
                        "message": f"expected moved candidate_count=8, got {archive_result.get('candidate_count')}",
                    }
                )

            for protected_path in [
                protected_governance,
                retained_governance_recent,
                protected_supervisor,
                retained_supervisor_recent,
                protected_repair,
                retained_promotion_recent,
                load_test_latest,
                load_test_latest.with_suffix(".json"),
            ]:
                if not protected_path.exists():
                    findings.append(
                        {
                            "check": "archive_sandbox",
                            "path": str(protected_path),
                            "message": "protected report should remain in reports root",
                        }
                    )

            moved_targets = [
                archive_root / "20260414" / archived_governance_old.name,
                archive_root / "20260414" / archived_supervisor_old.name,
                archive_root / "20260415" / retained_repair_recent.name,
                archive_root / "20260414" / archived_candidate.name,
                archive_root / "20260414" / archived_candidate_two.name,
                archive_root / "20260414" / load_test_old.name,
                archive_root / "20260414" / load_test_old.with_suffix(".json").name,
                archive_root / stray_bucket / stray_txt.name,
            ]
            for moved in moved_targets:
                if not moved.exists():
                    findings.append(
                        {
                            "check": "archive_sandbox",
                            "path": str(moved),
                            "message": "archive candidate was not moved to archive bucket",
                        }
                    )

            if (
                archived_governance_old.exists()
                or archived_supervisor_old.exists()
                or archived_candidate.exists()
                or archived_candidate_two.exists()
                or load_test_old.exists()
                or load_test_old.with_suffix(".json").exists()
                or stray_txt.exists()
            ):
                findings.append(
                    {
                        "check": "archive_sandbox",
                        "path": "reports/",
                        "message": "archive candidates still remain in reports root after apply",
                    }
                )

            governance_daily_text = governance_daily.read_text(encoding="utf-8")
            if f"(archive/20260414/{archived_governance_old.name})" not in governance_daily_text:
                findings.append(
                    {
                        "check": "archive_sandbox",
                        "path": str(governance_daily),
                        "message": "governance daily link was not rewritten to archive path",
                    }
                )
            supervisor_daily_text = supervisor_daily.read_text(encoding="utf-8")
            if f"(archive/20260414/{archived_supervisor_old.name})" not in supervisor_daily_text:
                findings.append(
                    {
                        "check": "archive_sandbox",
                        "path": str(supervisor_daily),
                        "message": "supervisor daily link was not rewritten to archive path",
                    }
                )
    finally:
        wiki_runtime.ROOT = originals["ROOT"]
        wiki_runtime.REPORTS_ROOT = originals["REPORTS_ROOT"]
        wiki_runtime.STATE_ROOT = originals["STATE_ROOT"]
        wiki_runtime.REPORT_ARCHIVE_ROOT = originals["REPORT_ARCHIVE_ROOT"]
        wiki_runtime.GOVERNANCE_LATEST = originals["GOVERNANCE_LATEST"]
        wiki_runtime.SUPERVISOR_LATEST = originals["SUPERVISOR_LATEST"]
        wiki_runtime.OPERATOR_LATEST = originals["OPERATOR_LATEST"]
        wiki_runtime.ensure_dirs = originals["ensure_dirs"]

    return findings


def check_failure_guidance_model(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    payload = build_synthetic_failure_payload()
    enriched = payload["findings"]
    next_steps = build_next_steps(enriched)

    if len(enriched) != 3:
        findings.append(
            {
                "check": "failure_guidance_model",
                "path": "enrich_findings",
                "message": f"expected enriched finding count=3, got {len(enriched)}",
            }
        )

    for item in enriched:
        guidance = item.get("guidance")
        if not isinstance(guidance, dict):
            findings.append(
                {
                    "check": "failure_guidance_model",
                    "path": "enrich_findings",
                    "message": f"missing guidance for check={item.get('check')}",
                }
            )
            continue
        if not guidance.get("why"):
            findings.append(
                {
                    "check": "failure_guidance_model",
                    "path": "enrich_findings",
                    "message": f"missing guidance.why for check={item.get('check')}",
                }
            )
        first_files = guidance.get("first_files")
        if not isinstance(first_files, list) or not first_files:
            findings.append(
                {
                    "check": "failure_guidance_model",
                    "path": "enrich_findings",
                    "message": f"missing guidance.first_files for check={item.get('check')}",
                }
            )

    step_checks = [str(step.get("check")) for step in next_steps]
    if step_checks != ["operator_alignment", "archive_sandbox", "doc_alignment"]:
        findings.append(
            {
                "check": "failure_guidance_model",
                "path": "build_next_steps",
                "message": f"unexpected next_steps order: {step_checks}",
            }
        )

    for step in next_steps:
        if not step.get("why"):
            findings.append(
                {
                    "check": "failure_guidance_model",
                    "path": "build_next_steps",
                    "message": f"missing why for next step check={step.get('check')}",
                }
            )
        if not isinstance(step.get("first_files"), list) or not step.get("first_files"):
            findings.append(
                {
                    "check": "failure_guidance_model",
                    "path": "build_next_steps",
                    "message": f"missing first_files for next step check={step.get('check')}",
                }
            )

    if not payload["findings"] or not payload["next_steps"]:
        findings.append(
            {
                "check": "failure_guidance_model",
                "path": "validation_payload",
                "message": "synthetic fail payload did not include findings and next_steps together",
            }
        )
    focus_names = [str(item.get("focus")) for item in payload["repair_focus"]]
    if focus_names != ["state_surface", "archive_runtime", "docs_entry"]:
        findings.append(
            {
                "check": "failure_guidance_model",
                "path": "build_repair_focus",
                "message": f"unexpected repair_focus order: {focus_names}",
            }
        )
    markdown = render_validation_markdown(payload)
    for marker in ["## repair focus", "## next steps", "## findings", "focus: `state_surface`", "check: `operator_alignment`"]:
        if marker not in markdown:
            findings.append(
                {
                    "check": "failure_guidance_model",
                    "path": "render_validation_markdown",
                    "message": f"missing markdown marker: {marker}",
                }
            )

    return findings


def check_generated_example_sync(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    cfg = profile["generated_example"]
    target = ROOT / cfg["path"]
    expected = render_validation_markdown(build_synthetic_failure_payload())

    if not target.exists():
        return [
            {
                "check": "generated_example_sync",
                "path": cfg["path"],
                "message": "generated example file is missing",
            }
        ]

    actual = target.read_text(encoding="utf-8")
    if actual != expected:
        findings.append(
            {
                "check": "generated_example_sync",
                "path": cfg["path"],
                "message": "generated example file is out of sync with current renderer",
            }
        )

    for marker in cfg["required_markers"]:
        if marker not in actual:
            findings.append(
                {
                    "check": "generated_example_sync",
                    "path": cfg["path"],
                    "message": f"missing marker: {marker}",
                }
            )

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(prog="runtime_validate", description="runtime validation surface")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--synthetic-fail", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.synthetic_fail:
        payload = build_synthetic_failure_payload()
        emit_payload(payload, args.format, args.output)
        return

    profile_path = ROOT / "validation" / "RUNTIME_VALIDATION_PROFILE_v0.1.toml"
    profile = load_profile(profile_path)
    findings: list[dict[str, Any]] = []

    if profile["checks"].get("require_clean_lint"):
        lint = run_lint()
        if any(lint["maintenance"][key] for key in ["canon_missing_metadata", "lite_missing_metadata", "stale_candidates", "review_candidates", "basis_review_candidates", "superseded_notes", "conflict_candidates", "duplicate_titles"]):
            findings.append({"check": "lint", "path": "workflow-lint", "message": "maintenance report not clean"})
        if any(lint["conflict"][key] for key in ["explicit_conflicts", "duplicate_titles", "divergent_duplicates", "shared_sources"]):
            findings.append({"check": "lint", "path": "workflow-lint", "message": "conflict report not clean"})
        if any(lint["staleness"][key] for key in ["forced_stale", "canon_age_stale", "lite_review_overdue", "canon_review_overdue"]):
            findings.append({"check": "lint", "path": "workflow-lint", "message": "staleness report not clean"})
        if any(lint["static_lint"][key] for key in ["broken_wikilinks", "broken_evidence_refs", "empty_core_sections"]):
            findings.append({"check": "lint", "path": "workflow-lint", "message": "static lint report not clean"})

    if profile["checks"].get("require_doc_alignment"):
        findings.extend(check_doc_alignment(profile))
    if profile["checks"].get("require_basis_policy"):
        findings.extend(check_basis_policy(profile))
    if profile["checks"].get("require_latest_surface_sync"):
        findings.extend(check_latest_surface_sync(profile))
    if profile["checks"].get("require_daily_surface_sync"):
        findings.extend(check_daily_surface_sync(profile))
    if profile["checks"].get("require_cycle_artifact_suppression"):
        findings.extend(check_cycle_artifact_suppression(profile))
    if profile["checks"].get("require_cycle_snapshot_sensitivity"):
        findings.extend(check_cycle_snapshot_sensitivity(profile))
    if profile["checks"].get("require_day_boundary_stability"):
        findings.extend(check_day_boundary_stability(profile))
    if profile["checks"].get("require_snapshot_precision"):
        findings.extend(check_snapshot_precision(profile))
    if profile["checks"].get("require_queue_field_policy"):
        findings.extend(check_queue_field_policy(profile))
    if profile["checks"].get("require_lint_field_policy"):
        findings.extend(check_lint_field_policy(profile))
    if profile["checks"].get("require_load_test_report"):
        findings.extend(check_load_test(profile))
    if profile["checks"].get("require_artifact_hygiene"):
        findings.extend(check_artifact_hygiene(profile))
    if profile["checks"].get("require_operator_alignment"):
        findings.extend(check_operator_alignment(profile))
    if profile["checks"].get("require_operator_state_model"):
        findings.extend(check_operator_state_model(profile))
    if profile["checks"].get("require_surface_state_rendering"):
        findings.extend(check_surface_state_rendering(profile))
    if profile["checks"].get("require_temp_surface_sandbox"):
        findings.extend(check_temp_surface_sandbox(profile))
    if profile["checks"].get("require_lock_sandbox"):
        findings.extend(check_lock_sandbox(profile))
    if profile["checks"].get("require_archive_sandbox"):
        findings.extend(check_archive_sandbox(profile))
    if profile["checks"].get("require_failure_guidance_model"):
        findings.extend(check_failure_guidance_model(profile))
    if profile["checks"].get("require_generated_example_sync"):
        findings.extend(check_generated_example_sync(profile))

    enriched_findings = enrich_findings(findings)
    payload = {
        "profile": str(profile_path),
        "status": "pass" if not findings else "fail",
        "finding_count": len(findings),
        "findings": enriched_findings,
        "next_steps": build_next_steps(enriched_findings),
        "repair_focus": build_repair_focus(enriched_findings),
    }
    emit_payload(payload, args.format, args.output)


if __name__ == "__main__":
    main()
