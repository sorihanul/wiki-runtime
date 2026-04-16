from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LOAD_TEST_BASE = ROOT.parent / ".wiki_runtime_load_tests"
REPORTS_ROOT = ROOT / "reports"

THEMES = [
    "memory",
    "workflow",
    "retrieval",
    "repair",
    "conflict",
    "staleness",
    "promotion",
    "canon",
]

SCALE_PRESETS = {
    "s": {"raw_count": 32, "canon_healthy": 12, "canon_conflict_pairs": 4, "canon_stale": 4, "canon_superseded": 4},
    "m": {"raw_count": 320, "canon_healthy": 120, "canon_conflict_pairs": 20, "canon_stale": 20, "canon_superseded": 20},
    "l": {"raw_count": 3200, "canon_healthy": 1200, "canon_conflict_pairs": 200, "canon_stale": 200, "canon_superseded": 200},
}


@dataclass
class RunPaths:
    run_root: Path
    runtime_root: Path


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def starter_retrieval_candidate_paths() -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for base in [ROOT, *ROOT.parents]:
        candidate = base / "Jarvis_Starter_Pack" / "IVK2_Improved" / "ivk2_improved.py"
        if candidate not in seen:
            candidates.append(candidate)
            seen.add(candidate)
    return candidates


def original_retrieval_script() -> Path:
    preferred_env = os.environ.get("WIKI_RETRIEVAL_SCRIPT") or os.environ.get("WIKI_IVK2_SCRIPT")
    candidates = [Path(preferred_env) if preferred_env else None, ROOT / "vendor" / "ivk2_improved.py"]
    candidates.extend(starter_retrieval_candidate_paths())
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise FileNotFoundError("Retrieval backend script not found for load test")


def clone_runtime() -> RunPaths:
    LOAD_TEST_BASE.mkdir(parents=True, exist_ok=True)
    run_root = LOAD_TEST_BASE / f"run_{now_stamp()}"
    runtime_root = run_root / "runtime"

    def ignore(path: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        basename = Path(path).name
        if basename == "__pycache__":
            ignored.update(names)
        for name in names:
            if name in {"sandbox", "__pycache__"}:
                ignored.add(name)
        return ignored

    shutil.copytree(ROOT, runtime_root, ignore=ignore)
    return RunPaths(run_root=run_root, runtime_root=runtime_root)


def clear_markdown_files(root: Path) -> None:
    if not root.exists():
        return
    for path in root.rglob("*.md"):
        if path.name.lower() == "readme.md":
            continue
        path.unlink()
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            try:
                path.rmdir()
            except OSError:
                continue


def clear_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError:
                continue


def reset_runtime_data(runtime_root: Path) -> None:
    for relative in [
        Path("wiki_lite") / "RAW",
        Path("wiki_lite") / "WIKI",
        Path("wiki_lite") / "LOG",
        Path("wiki") / "topics",
        Path("wiki") / "entities",
        Path("wiki") / "concepts",
        Path("wiki") / "syntheses",
    ]:
        clear_markdown_files(runtime_root / relative)

    for path in [
        runtime_root / "wiki" / "index.md",
        runtime_root / "wiki" / "log.md",
    ]:
        if path.exists():
            path.unlink()

    retrieval_data = runtime_root / "retrieval" / "data"
    for target in [
        retrieval_data / "hot.sqlite",
        retrieval_data / "cold.sqlite",
        retrieval_data / "hot_root.txt",
        retrieval_data / "cold_root.txt",
        retrieval_data / "_hot_build",
        retrieval_data / "_cold_build",
        retrieval_data / "_cold_sources",
    ]:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()

    clear_tree(runtime_root / "_runtime_state")
    clear_tree(runtime_root / "reports")
    (runtime_root / "reports" / "archive").mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def refresh_latest_surfaces() -> None:
    env = os.environ.copy()
    env["WIKI_RETRIEVAL_SCRIPT"] = str(original_retrieval_script())
    command = ["python", str(ROOT / "scripts" / "wiki_runtime.py"), "operator-summary"]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True, env=env)


def raw_note_body(index: int) -> str:
    theme = THEMES[index % len(THEMES)]
    judgment = "adopt" if index % 4 != 0 else "hold"
    source_scope = "outside" if index % 3 == 0 else "inside"
    return "\n".join(
        [
            f"# load-raw-{index:04d}",
            "",
            f"- captured_at: `{today()} 09:{index % 60:02d}:00`",
            f"- source_scope: `{source_scope}`",
            f"- source_path: `./fixtures/{theme}/source-{index:04d}.md`",
            f"- intended_axis: `{theme if theme in {'memory', 'skill', 'coordination'} else 'coordination'}`",
            f"- initial_judgment: `{judgment}`",
            "",
            "## raw",
            "",
            f"- This is synthetic raw note {index} for the {theme} theme.",
            f"- It checks whether the {theme} axis is retrievable across query, lint, and repair flows.",
            "",
            "## caution",
            "",
            f"- {theme} note {index} is synthetic test data.",
        ]
    )


def canon_note_body(title: str, promoted_from: str, canon_kind: str, freshness: str, confidence: str, supersession: str, stale_flag: str, conflict_with: str, body_line: str) -> str:
    return "\n".join(
        [
            f"# {title}",
            "",
            f"- promoted_from: `{promoted_from}`",
            "- claim_state: `fact`",
            f"- evidence: `{promoted_from}`",
            f"- freshness: `{freshness}`",
            f"- confidence: `{confidence}`",
            f"- supersession: `{supersession}`",
            "- scope: `load test fixture`",
            f"- stale_flag: `{stale_flag}`",
            f"- conflict_with: `{conflict_with}`",
            "- source_count: `1`",
            f"- last_reviewed: `{freshness}`",
            f"- temporal_state: `{'stale-sensitive' if freshness < '2026-01-01' else 'current'}`",
            f"- canon_kind: `{canon_kind}`",
            "",
            "## canon",
            f"- {body_line}",
            "",
            "## evidence",
            f"- evidence: `{promoted_from}`",
            f"- built_from: `{promoted_from}`",
            "- source_status: `adopt`",
            "- source_surface: `coordination`",
            f"- source_reviewed_at: `{freshness}`",
            "",
            "## supersession",
            f"- {supersession}",
        ]
    )


def seed_raw_notes(runtime_root: Path, raw_count: int) -> None:
    raw_root = runtime_root / "wiki_lite" / "RAW"
    for index in range(raw_count):
        write_text(raw_root / f"load-raw-{index:04d}.md", raw_note_body(index))


def seed_canon_notes(runtime_root: Path, preset: dict[str, int]) -> None:
    topics = runtime_root / "wiki" / "topics"
    concepts = runtime_root / "wiki" / "concepts"
    entities = runtime_root / "wiki" / "entities"
    syntheses = runtime_root / "wiki" / "syntheses"

    for index in range(preset["canon_healthy"]):
        theme = THEMES[index % len(THEMES)]
        folder = [topics, concepts, entities, syntheses][index % 4]
        title = f"healthy-{theme}-{index:04d}"
        promoted_from = f"wiki_lite/WIKI/load-raw-{index:04d}.md"
        write_text(
            folder / f"{title}.md",
            canon_note_body(
                title=title,
                promoted_from=promoted_from,
                canon_kind=folder.name,
                freshness=today(),
                confidence="high" if index % 2 == 0 else "medium",
                supersession="none",
                stale_flag="false",
                conflict_with="none",
                body_line=f"{theme} healthy canon fixture {index}. Includes runtime query, compile, lint, and repair context.",
            ),
        )

    for index in range(preset["canon_conflict_pairs"]):
        title = f"conflict-shared-title-{index:04d}"
        promoted_from = f"wiki_lite/WIKI/load-raw-{index:04d}.md"
        left_path = topics / "duplicates" / f"{title}-left.md"
        right_path = concepts / "duplicates" / f"{title}-right.md"
        right_rel = right_path.relative_to(runtime_root).as_posix()
        left_rel = left_path.relative_to(runtime_root).as_posix()
        write_text(
            left_path,
            canon_note_body(
                title=title,
                promoted_from=promoted_from,
                canon_kind="topics",
                freshness=today(),
                confidence="medium",
                supersession="none",
                stale_flag="false",
                conflict_with=right_rel,
                body_line=f"left conflict fixture {index}. duplicate title source conflict canonical mismatch case.",
            ),
        )
        write_text(
            right_path,
            canon_note_body(
                title=title,
                promoted_from=promoted_from,
                canon_kind="concepts",
                freshness=today(),
                confidence="medium",
                supersession="none",
                stale_flag="false",
                conflict_with=left_rel,
                body_line=f"right conflict fixture {index}. duplicate title source conflict canonical mismatch case.",
            ),
        )

    for index in range(preset["canon_stale"]):
        title = f"stale-note-{index:04d}"
        promoted_from = f"wiki_lite/WIKI/load-raw-{(index + 40):04d}.md"
        write_text(
            syntheses / "stale" / f"{title}.md",
            canon_note_body(
                title=title,
                promoted_from=promoted_from,
                canon_kind="syntheses",
                freshness="2025-01-01",
                confidence="medium",
                supersession="none",
                stale_flag="false",
                conflict_with="none",
                body_line=f"stale fixture {index}. stale review overdue repair candidate.",
            ),
        )

    for index in range(preset["canon_superseded"]):
        title = f"superseded-note-{index:04d}"
        replacement = f"wiki/topics/replacement-note-{index:04d}.md"
        promoted_from = f"wiki_lite/WIKI/load-raw-{(index + 80):04d}.md"
        write_text(
            topics / "superseded" / f"{title}.md",
            canon_note_body(
                title=title,
                promoted_from=promoted_from,
                canon_kind="topics",
                freshness="2025-06-01",
                confidence="medium",
                supersession=replacement,
                stale_flag="false",
                conflict_with="none",
                body_line=f"superseded fixture {index}. supersession stale repair candidate.",
            ),
        )
        write_text(
            topics / f"replacement-note-{index:04d}.md",
            canon_note_body(
                title=f"replacement-note-{index:04d}",
                promoted_from=promoted_from,
                canon_kind="topics",
                freshness=today(),
                confidence="high",
                supersession="none",
                stale_flag="false",
                conflict_with="none",
                body_line=f"replacement fixture {index}. replacement canon for supersession chain.",
            ),
        )


def run_json(runtime_root: Path, *args: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["WIKI_RETRIEVAL_SCRIPT"] = str(original_retrieval_script())
    command = ["python", str(runtime_root / "scripts" / "wiki_runtime.py"), *args]
    result = subprocess.run(command, cwd=runtime_root, check=True, capture_output=True, text=True, env=env)
    return json.loads(result.stdout)


def run_json_timed(runtime_root: Path, *args: str) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    payload = run_json(runtime_root, *args)
    elapsed = round(time.perf_counter() - started, 3)
    return payload, elapsed


def count_repair_items(report_path: Path) -> int:
    if not report_path.exists():
        return 0
    return sum(1 for line in report_path.read_text(encoding="utf-8").splitlines() if line.startswith("- type:"))


def top_hits(payload: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for hit in payload.get("hits", [])[:limit]:
        hits.append(
            {
                "path": hit.get("path"),
                "layer": hit.get("layer"),
                "policy_score": hit.get("policy_score"),
                "metadata": hit.get("metadata"),
            }
        )
    return hits


def evaluate_query_focus(question: str, payload: dict[str, Any]) -> dict[str, Any]:
    expected_map = {
        "recent workflow compile query policy": ["healthy-workflow", "healthy-repair", "healthy-canon", "healthy-promotion"],
        "conflict duplicate title source": ["duplicates", "conflict-shared-title"],
        "stale supersession repair": ["stale", "superseded", "replacement-note", "healthy-staleness", "healthy-repair"],
    }
    expected_tokens = expected_map.get(question, [])
    hits = top_hits(payload, 3)
    matched = 0
    for hit in hits:
        path = str(hit.get("path", "")).lower()
        if any(token.lower() in path for token in expected_tokens):
            matched += 1
    return {
        "expected_tokens": expected_tokens,
        "top3_matched": matched,
        "pass": matched >= 1 if expected_tokens else None,
    }


def build_report_body(scale: str, seeded: dict[str, int], ingest: dict[str, Any], compile_payload: dict[str, Any], compile_repeat_payload: dict[str, Any], lint: dict[str, Any], mark_conflicts: dict[str, Any], mark_stale: dict[str, Any], repair: dict[str, Any], queries: dict[str, dict[str, Any]], query_checks: dict[str, dict[str, Any]], timings: dict[str, Any], run_paths: RunPaths) -> str:
    repair_path = Path(repair["repair_queue"]["report_path"])
    lines = [
        f"# runtime-load-test-{now_stamp()}",
        "",
        f"- scale: `{scale}`",
        f"- sandbox_run: `{run_paths.run_root}`",
        f"- sandbox_runtime: `{run_paths.runtime_root}`",
        f"- seeded_raw: `{seeded['raw']}`",
        f"- seeded_canon: `{seeded['canon']}`",
        f"- ingest_processed: `{ingest['processed_count']}`",
        f"- ingest_skipped: `{ingest['skipped_count']}`",
        f"- lint_conflicts: `{len(lint['conflict']['duplicate_titles']) + len(lint['conflict']['explicit_conflicts']) + len(lint['conflict']['shared_sources']) + len(lint['conflict']['divergent_duplicates'])}`",
        f"- lint_stale: `{len(lint['staleness']['canon_age_stale']) + len(lint['staleness']['forced_stale']) + len(lint['staleness']['canon_review_overdue'])}`",
        f"- mark_conflicts_modified: `{mark_conflicts['modified_count']}`",
        f"- mark_stale_modified: `{mark_stale['modified_count']}`",
        f"- repair_queue_items: `{count_repair_items(repair_path)}`",
        f"- total_runtime_sec: `{timings['total']}`",
        "",
        "## compile",
        f"- hot_root: `{compile_payload['hot_root']}`",
        f"- cold_root: `{compile_payload['cold_root']}`",
        f"- compile_sec: `{timings['compile']}`",
        f"- compile_repeat_sec: `{timings['compile_repeat']}`",
        "",
        "## timings",
        f"- ingest_sec: `{timings['ingest']}`",
        f"- compile_sec: `{timings['compile']}`",
        f"- compile_repeat_sec: `{timings['compile_repeat']}`",
        f"- lint_sec: `{timings['lint']}`",
        f"- mark_conflicts_sec: `{timings['mark_conflicts']}`",
        f"- mark_stale_sec: `{timings['mark_stale']}`",
        f"- repair_sec: `{timings['repair']}`",
        "",
        "## lint summary",
        f"- duplicate_titles: `{len(lint['conflict']['duplicate_titles'])}`",
        f"- explicit_conflicts: `{len(lint['conflict']['explicit_conflicts'])}`",
        f"- shared_sources: `{len(lint['conflict']['shared_sources'])}`",
        f"- divergent_duplicates: `{len(lint['conflict']['divergent_duplicates'])}`",
        f"- forced_stale: `{len(lint['staleness']['forced_stale'])}`",
        f"- canon_age_stale: `{len(lint['staleness']['canon_age_stale'])}`",
        f"- canon_review_overdue: `{len(lint['staleness']['canon_review_overdue'])}`",
        "",
        "## query summary",
    ]
    for question, payload in queries.items():
        hits = top_hits(payload, 3)
        check = query_checks[question]
        lines.append(f"### {question}")
        if check["pass"] is not None:
            lines.append(f"- query_focus: `{'pass' if check['pass'] else 'fail'}`")
            lines.append(f"- top3_matched: `{check['top3_matched']}`")
        if not hits:
            lines.append("- no hits")
            continue
        for hit in hits:
            lines.append(
                f"- `{hit['layer']}` | `{hit['policy_score']}` | `{hit['path']}`"
            )
    lines.extend(
        [
            "",
            "## result",
            "- This report was generated from a sandbox clone.",
            "- The goal is to check whether ingest, compile, lint, repair, and query all remain stable under large synthetic similarity pressure.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="clone-based runtime load test for wiki retrieval runtime v2")
    parser.add_argument("--scale", choices=sorted(SCALE_PRESETS.keys()), default="s")
    args = parser.parse_args()

    preset = SCALE_PRESETS[args.scale]
    total_started = time.perf_counter()
    run_paths = clone_runtime()
    reset_runtime_data(run_paths.runtime_root)
    seed_raw_notes(run_paths.runtime_root, preset["raw_count"])
    seed_canon_notes(run_paths.runtime_root, preset)

    ingest, ingest_sec = run_json_timed(run_paths.runtime_root, "workflow-ingest")
    compile_payload, compile_sec = run_json_timed(run_paths.runtime_root, "workflow-compile")
    compile_repeat_payload, compile_repeat_sec = run_json_timed(run_paths.runtime_root, "workflow-compile")
    lint, lint_sec = run_json_timed(run_paths.runtime_root, "workflow-lint")
    mark_conflicts, mark_conflicts_sec = run_json_timed(run_paths.runtime_root, "mark-conflicts")
    mark_stale, mark_stale_sec = run_json_timed(run_paths.runtime_root, "mark-stale")
    repair, repair_sec = run_json_timed(run_paths.runtime_root, "workflow-repair")
    queries = {
        "recent workflow compile query policy": run_json(run_paths.runtime_root, "query", "recent workflow compile query policy", "-k", "8"),
        "conflict duplicate title source": run_json(run_paths.runtime_root, "query", "conflict duplicate title source", "-k", "8"),
        "stale supersession repair": run_json(run_paths.runtime_root, "query", "stale supersession repair", "-k", "8"),
    }
    query_checks = {question: evaluate_query_focus(question, payload) for question, payload in queries.items()}
    total_sec = round(time.perf_counter() - total_started, 3)
    timings = {
        "ingest": ingest_sec,
        "compile": compile_sec,
        "compile_repeat": compile_repeat_sec,
        "lint": lint_sec,
        "mark_conflicts": mark_conflicts_sec,
        "mark_stale": mark_stale_sec,
        "repair": repair_sec,
        "total": total_sec,
    }

    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    report_basename = f"load_test_{args.scale}_{now_stamp()}"
    report_path = REPORTS_ROOT / f"{report_basename}.md"
    json_path = REPORTS_ROOT / f"{report_basename}.json"

    seeded_canon = preset["canon_healthy"] + (preset["canon_conflict_pairs"] * 2) + preset["canon_stale"] + (preset["canon_superseded"] * 2)
    report_body = build_report_body(
        scale=args.scale,
        seeded={"raw": preset["raw_count"], "canon": seeded_canon},
        ingest=ingest,
        compile_payload=compile_payload,
        compile_repeat_payload=compile_repeat_payload,
        lint=lint,
        mark_conflicts=mark_conflicts,
        mark_stale=mark_stale,
        repair=repair,
        queries=queries,
        query_checks=query_checks,
        timings=timings,
        run_paths=run_paths,
    )
    write_text(report_path, report_body)
    write_text(
        json_path,
        json.dumps(
            {
                "scale": args.scale,
                "run_root": str(run_paths.run_root),
                "runtime_root": str(run_paths.runtime_root),
                "seeded_raw": preset["raw_count"],
                "seeded_canon": seeded_canon,
                "ingest": ingest,
                "compile": compile_payload,
                "compile_repeat": compile_repeat_payload,
                "lint": lint,
                "mark_conflicts": mark_conflicts,
                "mark_stale": mark_stale,
                "repair": repair,
                "queries": queries,
                "query_checks": query_checks,
                "timings": timings,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    refresh_latest_surfaces()

    print(
        json.dumps(
            {
                "ok": True,
                "scale": args.scale,
                "run_root": str(run_paths.run_root),
                "runtime_root": str(run_paths.runtime_root),
                "report_path": str(report_path),
                "json_path": str(json_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
