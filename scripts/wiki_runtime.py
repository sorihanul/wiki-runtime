from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WIKI_ROOT = ROOT / "wiki"
WIKI_INDEX = WIKI_ROOT / "index.md"
WIKI_LOG = WIKI_ROOT / "log.md"
WIKI_TOPICS = WIKI_ROOT / "topics"
WIKI_ENTITIES = WIKI_ROOT / "entities"
WIKI_CONCEPTS = WIKI_ROOT / "concepts"
WIKI_SYNTHESES = WIKI_ROOT / "syntheses"

LITE_ROOT = ROOT / "wiki_lite"
LITE_RAW = LITE_ROOT / "RAW"
LITE_WIKI = LITE_ROOT / "WIKI"
LITE_QUERY_RESIDUE = LITE_WIKI / "query_residue"
LITE_LOG = LITE_ROOT / "LOG"
LITE_INDEX = LITE_ROOT / "_index"
REPORTS_ROOT = ROOT / "reports"
STATE_ROOT = ROOT / "_runtime_state"
MAINTENANCE_AUTORUN_STATE = STATE_ROOT / "maintenance_autorun_state.json"
AUTOPILOT_LOCK = STATE_ROOT / "autopilot.lock"
LINT_BUNDLE_CACHE = STATE_ROOT / "lint_bundle_cache.json"
LINT_BUNDLE_CACHE_VERSION = "v5"
PROMOTION_ENTRIES_CACHE = STATE_ROOT / "promotion_entries_cache.json"
UPDATE_ENTRIES_CACHE = STATE_ROOT / "update_entries_cache.json"
QUEUE_ENTRIES_CACHE_VERSION = "v3"
REPAIR_QUEUE_REPORT_CACHE = STATE_ROOT / "repair_queue_report_cache.json"
PROMOTION_QUEUE_REPORT_CACHE = STATE_ROOT / "promotion_queue_report_cache.json"
UPDATE_QUEUE_REPORT_CACHE = STATE_ROOT / "update_queue_report_cache.json"
REPORT_CACHE_VERSION = "v1"
GOVERNANCE_CYCLE_CACHE = STATE_ROOT / "governance_cycle_cache.json"
GOVERNANCE_CYCLE_CACHE_VERSION = "v2"
GOVERNANCE_LATEST = REPORTS_ROOT / "governance_latest.md"
SUPERVISOR_CYCLE_CACHE = STATE_ROOT / "supervisor_cycle_cache.json"
SUPERVISOR_CYCLE_CACHE_VERSION = "v1"
SUPERVISOR_LATEST = REPORTS_ROOT / "supervisor_latest.md"
OPERATOR_LATEST = REPORTS_ROOT / "operator_latest.md"
REPORT_ARCHIVE_ROOT = REPORTS_ROOT / "archive"
REPORT_FAMILY_ROOT_RETENTION: dict[str, int] = {
    "governance_cycle": 2,
    "supervisor_cycle": 2,
    "repair_queue": 1,
    "promotion_queue": 1,
    "canon_update_queue": 1,
}
COMPILE_STATE_CACHE = STATE_ROOT / "compile_state_cache.json"
COMPILE_STATE_CACHE_VERSION = "v1"

RETRIEVAL_ROOT = ROOT / "retrieval"
RETRIEVAL_DATA = RETRIEVAL_ROOT / "data"
HOT_DB = RETRIEVAL_DATA / "hot.sqlite"
COLD_DB = RETRIEVAL_DATA / "cold.sqlite"
HOT_BUILD_BASE = RETRIEVAL_DATA / "_hot_build"
HOT_BUILD_POINTER = RETRIEVAL_DATA / "hot_root.txt"
COLD_BUILD_BASE = RETRIEVAL_DATA / "_cold_build"
COLD_BUILD_POINTER = RETRIEVAL_DATA / "cold_root.txt"
CANON_FOLDERS = [WIKI_TOPICS, WIKI_ENTITIES, WIKI_CONCEPTS, WIKI_SYNTHESES]
CANON_REQUIRED_METADATA = ["claim_state", "evidence", "freshness", "confidence", "supersession", "scope"]
LITE_REQUIRED_METADATA = ["claim_state", "freshness", "confidence"]


def starter_retrieval_candidate_paths() -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for base in [ROOT, *ROOT.parents]:
        candidate = base / "Jarvis_Starter_Pack" / "IVK2_Improved" / "ivk2_improved.py"
        if candidate not in seen:
            candidates.append(candidate)
            seen.add(candidate)
    return candidates


def candidate_retrieval_paths() -> list[Path]:
    env_path = os.environ.get("WIKI_RETRIEVAL_SCRIPT") or os.environ.get("WIKI_IVK2_SCRIPT")
    candidates: list[Path] = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(ROOT / "vendor" / "ivk2_improved.py")
    candidates.extend(starter_retrieval_candidate_paths())
    return candidates


def resolve_retrieval_script() -> Path | None:
    for candidate in candidate_retrieval_paths():
        if candidate.exists():
            return candidate
    return None


@dataclass(frozen=True)
class Paths:
    root: Path
    wiki_root: Path
    lite_root: Path
    hot_db: Path
    cold_db: Path


PATHS = Paths(
    root=ROOT,
    wiki_root=WIKI_ROOT,
    lite_root=LITE_ROOT,
    hot_db=HOT_DB,
    cold_db=COLD_DB,
)


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stable_payload(value: object) -> object:
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            if key in {"generated_at", "report_path", "cache_meta"}:
                continue
            cleaned[str(key)] = stable_payload(item)
        return cleaned
    if isinstance(value, list):
        return [stable_payload(item) for item in value]
    return value


def fingerprint_payload(value: object) -> str:
    serialized = json.dumps(stable_payload(value), ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


def read_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_dirs() -> None:
    for path in [
        ROOT,
        WIKI_ROOT,
        WIKI_TOPICS,
        WIKI_ENTITIES,
        WIKI_CONCEPTS,
        WIKI_SYNTHESES,
        LITE_ROOT,
        LITE_RAW,
        LITE_WIKI,
        LITE_QUERY_RESIDUE,
        LITE_LOG,
        LITE_INDEX,
        REPORTS_ROOT,
        STATE_ROOT,
        RETRIEVAL_ROOT,
        RETRIEVAL_DATA,
        ROOT / "scripts",
        ROOT / "templates",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def count_markdown_files(root: Path) -> int:
    return sum(1 for _ in root.rglob("*.md"))


def count_files(root: Path, pattern: str = "*") -> int:
    return sum(1 for _ in root.rglob(pattern))


def file_content_signature(path: Path) -> str:
    return content_fingerprint(path.read_text(encoding="utf-8"))


def run_ivk(args: list[str]) -> subprocess.CompletedProcess[str]:
    retrieval_script = resolve_retrieval_script()
    if retrieval_script is None:
        raise FileNotFoundError(
            "Retrieval backend script not found. Set WIKI_RETRIEVAL_SCRIPT or WIKI_IVK2_SCRIPT, "
            "or place ivk2_improved.py in "
            f"{ROOT / 'vendor'}"
        )
    command = ["python", str(retrieval_script), *args]
    return subprocess.run(command, check=True, capture_output=True, text=True)


def build_index(target_root: Path, db_path: Path) -> None:
    ensure_dirs()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    run_ivk(["build", str(target_root), "--db", str(db_path)])


def current_build_root(pointer_file: Path) -> Path | None:
    if not pointer_file.exists():
        return None
    pointer = pointer_file.read_text(encoding="utf-8").strip()
    if not pointer:
        return None
    path = Path(pointer)
    if path.exists():
        return path
    return None


def current_hot_build_root() -> Path | None:
    return current_build_root(HOT_BUILD_POINTER)


def current_cold_build_root() -> Path | None:
    return current_build_root(COLD_BUILD_POINTER)


def hot_compile_artifacts_ready() -> bool:
    hot_root = current_hot_build_root()
    return HOT_DB.exists() and hot_root is not None and hot_root.exists()


def cold_compile_artifacts_ready() -> bool:
    cold_root = current_cold_build_root()
    return COLD_DB.exists() and cold_root is not None and cold_root.exists()


def file_copy_needed(source: Path, target: Path) -> bool:
    if not target.exists():
        return True
    try:
        src_stat = source.stat()
        dst_stat = target.stat()
    except OSError:
        return True
    if src_stat.st_size != dst_stat.st_size:
        return True
    if abs(src_stat.st_mtime - dst_stat.st_mtime) > 1e-6:
        return True
    return False


def prune_empty_dirs(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            try:
                path.rmdir()
            except OSError:
                continue


def prepare_build_root(base_dir: Path, pointer_file: Path, source_root: Path, exclude_readme: bool = True) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    build_root = base_dir / "current"
    build_root.mkdir(parents=True, exist_ok=True)
    seen_relatives: set[Path] = set()
    for source in sorted(source_root.rglob("*.md")):
        if exclude_readme and source.name.lower() == "readme.md":
            continue
        relative = source.relative_to(source_root)
        seen_relatives.add(relative)
        target = build_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if file_copy_needed(source, target):
            shutil.copy2(source, target)
    pointer_file.write_text(str(build_root), encoding="utf-8")
    for target in sorted(build_root.rglob("*.md")):
        relative = target.relative_to(build_root)
        if relative not in seen_relatives:
            target.unlink()
    prune_empty_dirs(build_root)
    return build_root


def prepare_hot_build_root() -> Path:
    return prepare_build_root(HOT_BUILD_BASE, HOT_BUILD_POINTER, LITE_WIKI)


def prepare_cold_build_root() -> Path:
    cold_sources_root = RETRIEVAL_DATA / "_cold_sources"
    if cold_sources_root.exists():
        shutil.rmtree(cold_sources_root, ignore_errors=True)
    cold_sources_root.mkdir(parents=True, exist_ok=True)
    for folder in CANON_FOLDERS:
        target_folder = cold_sources_root / folder.name
        target_folder.mkdir(parents=True, exist_ok=True)
        for source in sorted(folder.rglob("*.md")):
            if source.name.lower() == "readme.md":
                continue
            relative = source.relative_to(folder)
            target = target_folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return prepare_build_root(COLD_BUILD_BASE, COLD_BUILD_POINTER, cold_sources_root)


def query_dual(question: str, k: int, domain: str | None, reliability_min: float | None, hot_weight: float | None) -> dict:
    args = [
        "query-dual",
        question,
        "--hot-db",
        str(HOT_DB),
        "--cold-db",
        str(COLD_DB),
        "-k",
        str(k),
    ]
    if domain:
        args.extend(["--domain", domain])
    if reliability_min is not None:
        args.extend(["--reliability-min", str(reliability_min)])
    if hot_weight is not None:
        args.extend(["--hot-weight", str(hot_weight)])
    result = run_ivk(args)
    payload = json.loads(result.stdout)
    for hit in payload.get("hits", []):
        raw_path = hit.get("path")
        if not raw_path:
            continue
        path = Path(raw_path)
        hot_build_root = current_hot_build_root()
        if hot_build_root is not None:
            try:
                relative = path.relative_to(hot_build_root)
                hit["path"] = str(LITE_WIKI / relative)
                continue
            except ValueError:
                pass
        cold_build_root = current_cold_build_root()
        if cold_build_root is not None:
            try:
                relative = path.relative_to(cold_build_root)
                hit["path"] = str(WIKI_ROOT / relative)
                continue
            except ValueError:
                pass
    return apply_retrieval_policy(payload, question)


def find_lite_note(name: str) -> Path:
    exact = LITE_WIKI / name
    if exact.exists():
        return exact
    if not name.endswith(".md"):
        exact_md = LITE_WIKI / f"{name}.md"
        if exact_md.exists():
            return exact_md
    for path in LITE_WIKI.rglob("*.md"):
        if path.stem == name:
            return path
    raise FileNotFoundError(f"lite note not found: {name}")


def resolve_canon_folder(kind: str) -> Path:
    mapping = {
        "topics": WIKI_TOPICS,
        "entities": WIKI_ENTITIES,
        "concepts": WIKI_CONCEPTS,
        "syntheses": WIKI_SYNTHESES,
    }
    try:
        return mapping[kind]
    except KeyError as exc:
        raise ValueError(f"unsupported canon kind: {kind}") from exc


def append_if_missing(path: Path, line: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if line not in existing:
        with path.open("a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            handle.write(line + "\n")


def rel_from_root(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def rel_from(path: Path, start: Path) -> str:
    return path.relative_to(start).as_posix()


def parse_metadata_value(raw: str) -> str:
    value = raw.strip()
    if value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value


def parse_date_value(raw: str) -> datetime | None:
    value = raw.strip()
    if value.lower() in {"", "none", "unknown", "n/a"}:
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", value)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d")
    except ValueError:
        return None


def days_since(raw: str) -> int | None:
    parsed = parse_date_value(raw)
    if parsed is None:
        return None
    return (datetime.now() - parsed).days


def nonempty_metadata_value(metadata: dict[str, str], key: str, default: str = "") -> str:
    value = metadata.get(key, "").strip()
    if value:
        return value
    return default


def is_none_like(value: str) -> bool:
    return value.strip().lower() in {"", "none", "unknown", "n/a"}


def parse_note(text: str) -> tuple[str, dict[str, str], dict[str, list[str]]]:
    title = "untitled"
    metadata: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    in_metadata = False

    for index, raw_line in enumerate(text.splitlines()):
        line = raw_line.lstrip("\ufeff") if index == 0 else raw_line
        if line.startswith("# "):
            title = line[2:].strip()
            in_metadata = True
            current_section = None
            continue
        if in_metadata and line.startswith("- ") and ":" in line:
            key, value = line[2:].split(":", 1)
            metadata[key.strip()] = parse_metadata_value(value)
            continue
        if line.startswith("## "):
            current_section = line[3:].strip().lower()
            sections[current_section] = []
            in_metadata = False
            continue
        if current_section is not None:
            sections[current_section].append(line)
        elif line.strip():
            in_metadata = False

    return title, metadata, sections


def load_note(path: Path) -> tuple[str, dict[str, str], dict[str, list[str]]]:
    return parse_note(path.read_text(encoding="utf-8"))


def metadata_for_path(path: Path) -> dict[str, str]:
    if not path.exists() or path.suffix.lower() != ".md":
        return {}
    _, metadata, _ = load_note(path)
    return metadata


def title_for_path(path: Path) -> str:
    if not path.exists() or path.suffix.lower() != ".md":
        return path.stem
    title, _, _ = load_note(path)
    return title


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def format_metadata_line(key: str, value: str) -> str:
    return f"- {key}: `{value}`"


def parse_metadata_line(line: str) -> tuple[str, str] | None:
    if not (line.startswith("- ") and ":" in line):
        return None
    key, value = line[2:].split(":", 1)
    return key.strip(), parse_metadata_value(value)


def set_note_metadata(path: Path, updates: dict[str, str]) -> bool:
    lines = read_lines(path)
    if not lines:
        return False

    title_line = lines[0]
    body_start = 1
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1

    meta_start = body_start
    meta_end = meta_start
    existing_values: dict[str, str] = {}
    key_order: list[str] = []

    while meta_end < len(lines):
        parsed = parse_metadata_line(lines[meta_end])
        if parsed is None:
            break
        key, value = parsed
        existing_values[key] = value
        key_order.append(key)
        meta_end += 1

    merged = existing_values.copy()
    merged.update(updates)
    for key in updates:
        if key not in key_order:
            key_order.append(key)

    metadata_lines = [format_metadata_line(key, merged[key]) for key in key_order]

    body_lines = lines[meta_end:]
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)

    new_lines = [title_line, "", *metadata_lines]
    if body_lines:
        new_lines.extend(["", *body_lines])

    new_text = "\n".join(new_lines).rstrip() + "\n"
    old_text = path.read_text(encoding="utf-8")
    if new_text == old_text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def merge_path_values(existing: str, additions: list[str]) -> str:
    values: list[str] = []
    if not is_none_like(existing):
        for part in existing.split(";"):
            item = part.strip()
            if item and item not in values:
                values.append(item)
    for addition in additions:
        item = addition.strip()
        if item and item not in values:
            values.append(item)
    if not values:
        return "none"
    return "; ".join(values)


def slug_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def current_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def clean_section_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("# "):
            continue
        if stripped.startswith("## "):
            continue
        if stripped.startswith("- built_from:"):
            continue
        if stripped.startswith("- status:"):
            continue
        if stripped.startswith("- surface:"):
            continue
        if stripped.startswith("- reviewed_at:"):
            continue
        cleaned.append(stripped)
    while cleaned and not cleaned[0]:
        cleaned.pop(0)
    while cleaned and not cleaned[-1]:
        cleaned.pop()
    return cleaned


def normalize_bullets(lines: list[str]) -> list[str]:
    normalized: list[str] = []
    for line in clean_section_lines(lines):
        if not line:
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            normalized.append(stripped)
        else:
            normalized.append(f"- {stripped}")
    return normalized


def normalize_evidence_ref(raw: str) -> str:
    text = raw.strip()
    if text.startswith("- "):
        text = text[2:].strip()
    if ":" in text:
        key, value = text.split(":", 1)
        if key.strip().lower() in {"evidence", "source", "built_from", "path", "trace"}:
            text = value.strip()
    text = text.strip().strip("`").strip()
    return parse_metadata_value(text)


def merge_safe_evidence_refs(path: Path, metadata: dict[str, str], sections: dict[str, list[str]], include_self: bool = True) -> list[str]:
    refs: list[str] = []

    def add_ref_value(raw_value: str) -> None:
        for part in raw_value.split(";"):
            ref = normalize_evidence_ref(part)
            if ref and ref not in refs:
                refs.append(ref)

    seed_candidates: list[str] = []
    evidence_value = metadata.get("evidence", "")
    if evidence_value:
        seed_candidates.extend(part.strip() for part in evidence_value.split(";"))
    seed_candidates.append(metadata.get("built_from", ""))
    if include_self:
        seed_candidates.append(rel_from_root(path))

    for candidate in seed_candidates:
        add_ref_value(candidate)

    for line in sections.get("evidence", []):
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        body = stripped[2:].strip()
        if not body:
            continue
        if body.startswith("`") and body.endswith("`"):
            raw_value = parse_metadata_value(body)
        elif ":" in body:
            key, value = body.split(":", 1)
            if key.strip().lower() not in {"evidence", "source", "built_from", "path", "trace"}:
                continue
            raw_value = parse_metadata_value(value)
        else:
            continue
        add_ref_value(raw_value)
    return refs


def collect_evidence_refs(source: Path, source_metadata: dict[str, str], evidence_lines: list[str]) -> list[str]:
    refs: list[str] = []

    def add_ref_value(raw_value: str) -> None:
        for part in raw_value.split(";"):
            ref = normalize_evidence_ref(part)
            if not ref:
                continue
            if ref not in refs:
                refs.append(ref)

    for candidate in [source_metadata.get("evidence", ""), *evidence_lines, source_metadata.get("built_from", ""), rel_from_root(source)]:
        add_ref_value(candidate)
    return refs


def infer_claim_state(source_metadata: dict[str, str]) -> str:
    explicit = nonempty_metadata_value(source_metadata, "claim_state")
    if explicit:
        return explicit
    status = source_metadata.get("status", "").strip()
    if status == "already-covered":
        return "fact"
    return "inference"


def infer_confidence(source_metadata: dict[str, str]) -> str:
    explicit = nonempty_metadata_value(source_metadata, "confidence")
    if explicit:
        return explicit
    return "low"


def infer_confidence_bundle(source_metadata: dict[str, str], source_count_value: str) -> tuple[str, str]:
    explicit = nonempty_metadata_value(source_metadata, "confidence")
    explicit_basis = nonempty_metadata_value(source_metadata, "confidence_basis")
    if explicit:
        return explicit, explicit_basis or "explicit"
    try:
        source_count = int(source_count_value)
    except ValueError:
        source_count = 0
    claim_state = infer_claim_state(source_metadata)
    if source_count >= 2 and claim_state in {"fact", "inference"}:
        return "medium", "source_count"
    return "low", "conservative_default"


def infer_temporal_state(source_metadata: dict[str, str]) -> str:
    reviewed_at = source_metadata.get("reviewed_at", "") or source_metadata.get("freshness", "")
    if re.match(r"^\d{4}-\d{2}-\d{2}$", reviewed_at):
        return "current"
    return "stale-sensitive"


def infer_freshness(source_metadata: dict[str, str]) -> str:
    explicit = nonempty_metadata_value(source_metadata, "freshness")
    if explicit:
        return explicit
    reviewed_at = nonempty_metadata_value(source_metadata, "reviewed_at")
    if reviewed_at:
        return reviewed_at
    return datetime.now().strftime("%Y-%m-%d")


def infer_scope(source_metadata: dict[str, str]) -> str:
    explicit = nonempty_metadata_value(source_metadata, "scope")
    if explicit:
        return explicit
    surface = nonempty_metadata_value(source_metadata, "surface")
    if surface:
        return f"{surface} surface note"
    return "unspecified"


def infer_source_count(source_metadata: dict[str, str]) -> str:
    explicit = nonempty_metadata_value(source_metadata, "source_count")
    if explicit:
        return explicit
    return "unknown"


def infer_source_count_bundle(source_metadata: dict[str, str], evidence_refs: list[str]) -> tuple[str, str]:
    explicit = nonempty_metadata_value(source_metadata, "source_count")
    explicit_basis = nonempty_metadata_value(source_metadata, "source_count_basis")
    if explicit:
        return explicit, explicit_basis or "explicit"
    if evidence_refs:
        if len(evidence_refs) == 1 and evidence_refs[0] == nonempty_metadata_value(source_metadata, "built_from"):
            return "1", "trace_only"
        return str(len(evidence_refs)), "evidence_refs"
    built_from = nonempty_metadata_value(source_metadata, "built_from")
    if built_from:
        return "1", "trace_only"
    return "unknown", "unknown"


def infer_evidence(source: Path, source_metadata: dict[str, str]) -> str:
    explicit = nonempty_metadata_value(source_metadata, "evidence")
    if explicit:
        return explicit
    built_from = nonempty_metadata_value(source_metadata, "built_from")
    if built_from:
        return built_from
    return rel_from_root(source)


def infer_evidence_bundle(source: Path, source_metadata: dict[str, str], evidence_lines: list[str]) -> tuple[str, str]:
    explicit = nonempty_metadata_value(source_metadata, "evidence")
    explicit_mode = nonempty_metadata_value(source_metadata, "evidence_mode")
    if explicit:
        return explicit, explicit_mode or "explicit"
    refs = collect_evidence_refs(source, source_metadata, evidence_lines)
    if len(refs) >= 2:
        return "; ".join(refs[:3]), "listed"
    if refs:
        if refs[0] == rel_from_root(source) or refs[0] == nonempty_metadata_value(source_metadata, "built_from"):
            return refs[0], "trace"
        return refs[0], "listed"
    return rel_from_root(source), "trace"


def infer_supersession(source_metadata: dict[str, str]) -> str:
    return nonempty_metadata_value(source_metadata, "supersession", "none") or "none"


def infer_last_reviewed(source_metadata: dict[str, str]) -> str:
    explicit = nonempty_metadata_value(source_metadata, "last_reviewed")
    if explicit:
        return explicit
    reviewed_at = nonempty_metadata_value(source_metadata, "reviewed_at")
    if reviewed_at:
        return reviewed_at
    return datetime.now().strftime("%Y-%m-%d")


def infer_stale_flag(source_metadata: dict[str, str]) -> str:
    explicit = nonempty_metadata_value(source_metadata, "stale_flag")
    if explicit:
        return explicit
    return "true" if not is_none_like(infer_supersession(source_metadata)) else "false"


def infer_conflict_with(source_metadata: dict[str, str]) -> str:
    return nonempty_metadata_value(source_metadata, "conflict_with", "none") or "none"


def normalize_status(value: str) -> str:
    normalized = value.strip().lower()
    allowed = {"adopt", "already-covered", "hold", "reject"}
    if normalized in allowed:
        return normalized
    return "hold"


def normalize_surface(value: str) -> str:
    normalized = value.strip().lower()
    allowed = {"memory", "governance", "skill", "coordination"}
    if normalized in allowed:
        return normalized
    return "coordination"


def derive_freshness_from_raw(metadata: dict[str, str]) -> str:
    for key in ["freshness", "captured_at", "reviewed_at"]:
        raw = nonempty_metadata_value(metadata, key)
        parsed = parse_date_value(raw)
        if parsed is not None:
            return parsed.strftime("%Y-%m-%d")
    return current_date()


def derive_confidence_from_status(status: str) -> str:
    return "low"


def derive_next_action(status: str) -> str:
    mapping = {
        "adopt": "review whether this note is ready for canon promotion.",
        "already-covered": "check overlap or supersession against an existing note.",
        "hold": "re-evaluate promotion after more validation.",
        "reject": "keep it for reference only and do not promote.",
    }
    return mapping[status]


def is_dated_value(value: str) -> bool:
    if parse_date_value(value) is not None:
        return True
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}\s*~\s*\d{4}-\d{2}-\d{2}$", value.strip()))


def promotion_assessment(source: Path, kind: str, target_name: str | None = None) -> dict[str, object]:
    original = source.read_text(encoding="utf-8")
    _, metadata, sections = parse_note(original)
    final_name = target_name or source.name
    if not final_name.endswith(".md"):
        final_name = f"{final_name}.md"
    target = resolve_canon_folder(kind) / final_name

    status = normalize_status(nonempty_metadata_value(metadata, "status", "hold"))
    claim_state = nonempty_metadata_value(metadata, "claim_state", "unknown")
    confidence = nonempty_metadata_value(metadata, "confidence", "low")
    freshness = nonempty_metadata_value(metadata, "freshness", nonempty_metadata_value(metadata, "reviewed_at", ""))
    scope = nonempty_metadata_value(metadata, "scope", "unspecified")
    source_count_value = int_or_zero(nonempty_metadata_value(metadata, "source_count", "0"))
    evidence_refs = sorted(set(collect_evidence_refs(source, metadata, normalize_bullets(sections.get("evidence", [])))))
    distilled_lines = normalize_bullets(sections.get("distilled", []))
    reusable_lines = normalize_bullets(sections.get("reusable rule", []))

    checks = [
        {
            "name": "adopt_status",
            "passed": status == "adopt",
            "detail": "status must be adopt",
        },
        {
            "name": "supported_evidence",
            "passed": len(evidence_refs) >= 2 or source_count_value >= 2,
            "detail": "at least two independent evidence signals or source_count >= 2",
        },
        {
            "name": "dated_freshness",
            "passed": bool(freshness) and is_dated_value(freshness),
            "detail": "freshness or reviewed_at should carry a date",
        },
        {
            "name": "reusable_rule_present",
            "passed": len(reusable_lines) >= 1,
            "detail": "reusable rule section should exist",
        },
        {
            "name": "repeatable_knowledge_shape",
            "passed": claim_state in {"fact", "inference"} and scope not in {"", "unspecified"},
            "detail": "claim should look reusable and scoped",
        },
        {
            "name": "surface_quality",
            "passed": confidence in {"medium", "high"} and len(distilled_lines) >= 2,
            "detail": "confidence should not be low and distilled section should have enough signal",
        },
    ]

    blockers: list[str] = []
    if status != "adopt":
        blockers.append(f"status={status} is not promotable")
    if claim_state == "opinion":
        blockers.append("claim_state=opinion should stay in wiki_lite")
    if not distilled_lines:
        blockers.append("distilled section is empty")
    if target.exists():
        blockers.append(f"target already exists: {rel_from_root(target)}")

    passed_count = sum(1 for item in checks if item["passed"])
    if blockers:
        decision = "blocked"
    elif passed_count >= 5:
        decision = "ready"
    elif passed_count >= 3:
        decision = "review"
    else:
        decision = "blocked"

    if decision == "ready":
        recommendation = "promote"
    elif decision == "review":
        recommendation = "strengthen evidence or metadata before promote"
    else:
        recommendation = "do not promote"

    return {
        "source": rel_from_root(source),
        "kind": kind,
        "target": rel_from_root(target),
        "decision": decision,
        "recommendation": recommendation,
        "passed_count": passed_count,
        "total_checks": len(checks),
        "status": status,
        "claim_state": claim_state,
        "confidence": confidence,
        "freshness": freshness or "unknown",
        "scope": scope,
        "source_count": source_count_value,
        "evidence_ref_count": len(evidence_refs),
        "checks": checks,
        "blockers": blockers,
    }


def recommended_canon_kind(source: Path) -> tuple[str, str]:
    _, metadata, sections = load_note(source)
    title = title_for_path(source).lower()
    surface = nonempty_metadata_value(metadata, "surface", "coordination")
    scope = nonempty_metadata_value(metadata, "scope", "").lower()
    reusable_lines = normalize_bullets(sections.get("reusable rule", []))

    if any(token in title for token in ["who", "person", "company", "tool", "service", "model", "agent"]) and surface != "governance":
        return "entities", "title looks entity-like"
    if any(token in title for token in ["system", "architecture", "workflow", "runtime", "stack", "hybrid", "pattern"]):
        return "syntheses", "title looks system-like"
    if surface == "governance":
        return "topics", "governance surface usually lands in topics"
    if reusable_lines:
        return "concepts", "reusable rule exists and concept extraction is plausible"
    if "rule" in scope or "policy" in scope:
        return "concepts", "scope reads like reusable rule or policy"
    return "topics", "default topic landing"


def promotion_priority(assessment: dict[str, object]) -> tuple[str, int, str]:
    decision = str(assessment["decision"])
    blockers = [str(item) for item in assessment.get("blockers", [])]
    status = str(assessment.get("status", "unknown"))
    claim_state = str(assessment.get("claim_state", "unknown"))

    if decision == "ready":
        return ("high", 90, "already passes promotion checks and can be treated as a direct canon candidate")
    if any("target already exists:" in item for item in blockers):
        return ("medium", 62, "check whether the existing canon note should be refreshed before creating a new one")
    if decision == "review" and status == "adopt":
        return ("medium", 58, "close to promotable, but evidence or metadata still needs reinforcement")
    if claim_state == "opinion":
        return ("low", 20, "opinion-oriented notes should usually stay in wiki_lite")
    if status != "adopt":
        return ("low", 24, "classification should be stabilized before promotion")
    return ("low", 18, "not ready for canon yet")


def promotion_action_text(assessment: dict[str, object]) -> str:
    decision = str(assessment["decision"])
    blockers = [str(item) for item in assessment.get("blockers", [])]
    kind = str(assessment["kind"])
    target = str(assessment["target"])
    checks = assessment.get("checks", [])
    failed_checks = [str(item["name"]) for item in checks if not bool(item["passed"])]

    if decision == "ready":
        return f"promote to {kind}: {target}"
    if any("target already exists:" in item for item in blockers):
        return "decide whether to refresh the existing canon note or fork to a new target name first"
    if "adopt_status" in failed_checks:
        return "check whether there is enough basis to move status to adopt"
    if "supported_evidence" in failed_checks:
        return "add at least one more independent evidence item"
    if "reusable_rule_present" in failed_checks:
        return "add at least one reusable rule line"
    if "surface_quality" in failed_checks:
        return "strengthen the distilled signal and reassess confidence"
    if "repeatable_knowledge_shape" in failed_checks:
        return "rewrite scope and claim_state into a reusable knowledge shape"
    return str(assessment["recommendation"])


def build_promotion_queue_entries() -> list[dict[str, object]]:
    snapshot = queue_input_snapshot()
    cached = read_cached_entries(PROMOTION_ENTRIES_CACHE, snapshot)
    if cached is not None:
        return cached

    entries: list[dict[str, object]] = []
    for path in iter_runtime_notes(LITE_WIKI):
        if is_query_residue_note(path):
            continue
        kind, kind_reason = recommended_canon_kind(path)
        assessment = promotion_assessment(path, kind)
        update_assessment = canon_update_assessment(path, kind)
        if update_assessment is not None and update_assessment["decision"] == "aligned":
            entries.append(
                {
                    "source": assessment["source"],
                    "recommended_kind": kind,
                    "kind_reason": kind_reason,
                    "decision": "covered",
                    "priority": "low",
                    "priority_score": 8,
                    "why_now": "the existing canon note already matches the current lite note, so no new promotion is needed",
                    "action": "keep current canon",
                    "status": assessment["status"],
                    "claim_state": assessment["claim_state"],
                    "confidence": assessment["confidence"],
                    "freshness": assessment["freshness"],
                    "scope": assessment["scope"],
                    "source_count": assessment["source_count"],
                    "evidence_ref_count": assessment["evidence_ref_count"],
                    "target": assessment["target"],
                    "passed_count": assessment["passed_count"],
                    "total_checks": assessment["total_checks"],
                    "blockers": [],
                    "assessment": assessment,
                }
            )
            continue
        priority, score, why_now = promotion_priority(assessment)
        entries.append(
            {
                "source": assessment["source"],
                "recommended_kind": kind,
                "kind_reason": kind_reason,
                "decision": assessment["decision"],
                "priority": priority,
                "priority_score": score,
                "why_now": why_now,
                "action": promotion_action_text(assessment),
                "status": assessment["status"],
                "claim_state": assessment["claim_state"],
                "confidence": assessment["confidence"],
                "freshness": assessment["freshness"],
                "scope": assessment["scope"],
                "source_count": assessment["source_count"],
                "evidence_ref_count": assessment["evidence_ref_count"],
                "target": assessment["target"],
                "passed_count": assessment["passed_count"],
                "total_checks": assessment["total_checks"],
                "blockers": assessment["blockers"],
                "assessment": assessment,
            }
        )
    entries.sort(key=lambda item: (-int_or_zero(item["priority_score"]), str(item["source"])))
    write_cached_entries(PROMOTION_ENTRIES_CACHE, snapshot, entries)
    return entries


def build_promotion_queue_body_from_entries(entries: list[dict[str, object]]) -> str:
    ready = [item for item in entries if item["decision"] == "ready"]
    review = [item for item in entries if item["decision"] == "review"]
    blocked = [item for item in entries if item["decision"] == "blocked"]
    lines: list[str] = [
        f"# promotion-queue-{slug_timestamp()}",
        "",
        f"- generated_at: `{timestamp()}`",
        "- queue_type: `promotion-queue`",
        "- source_workspace: `wiki_lite/WIKI`",
        "",
        "## summary",
        f"- total_candidates: `{len(entries)}`",
        f"- ready: `{len(ready)}`",
        f"- review: `{len(review)}`",
        f"- blocked: `{len(blocked)}`",
        f"- high_priority: `{len([item for item in entries if item['priority'] == 'high'])}`",
        f"- medium_priority: `{len([item for item in entries if item['priority'] == 'medium'])}`",
        f"- low_priority: `{len([item for item in entries if item['priority'] == 'low'])}`",
        "",
        "## promote now",
    ]

    if entries:
        for item in entries[:7]:
            lines.extend(
                [
                    f"- priority: `{item['priority']}`",
                    f"  decision: `{item['decision']}`",
                    f"  source: `{item['source']}`",
                    f"  recommended_kind: `{item['recommended_kind']}`",
                    f"  why_now: `{item['why_now']}`",
                    f"  action: `{item['action']}`",
                ]
            )
    else:
        lines.append("- no promotion candidates to process")

    lines.extend(["", "## ready queue"])
    if ready:
        for item in ready:
            lines.extend(
                [
                    f"- source: `{item['source']}`",
                    f"  priority: `{item['priority']}`",
                    f"  recommended_kind: `{item['recommended_kind']}`",
                    f"  kind_reason: `{item['kind_reason']}`",
                    f"  target: `{item['target']}`",
                    f"  confidence: `{item['confidence']}`",
                    f"  evidence_ref_count: `{item['evidence_ref_count']}`",
                    f"  action: `{item['action']}`",
                ]
            )
    else:
        lines.append("- no ready candidates to process")

    lines.extend(["", "## review queue"])
    if review:
        for item in review:
            lines.extend(
                [
                    f"- source: `{item['source']}`",
                    f"  priority: `{item['priority']}`",
                    f"  recommended_kind: `{item['recommended_kind']}`",
                    f"  blockers: `{'; '.join(item['blockers']) if item['blockers'] else 'none'}`",
                    f"  why_now: `{item['why_now']}`",
                    f"  action: `{item['action']}`",
                ]
            )
    else:
        lines.append("- no review candidates to process")

    lines.extend(["", "## blocked queue"])
    if blocked:
        for item in blocked:
            lines.extend(
                [
                    f"- source: `{item['source']}`",
                    f"  priority: `{item['priority']}`",
                    f"  status: `{item['status']}`",
                    f"  claim_state: `{item['claim_state']}`",
                    f"  blockers: `{'; '.join(item['blockers']) if item['blockers'] else 'none'}`",
                    f"  action: `{item['action']}`",
                ]
            )
    else:
        lines.append("- no blocked candidates to process")

    lines.extend(
        [
            "",
            "## next step",
            "- resolve canon promotion from the ready queue first.",
            "- revisit the review queue after reinforcing evidence, scope, and reusable rules.",
            "- keep blocked items in lite classification or redirect them to canon refresh review.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_promotion_queue_body() -> str:
    return build_promotion_queue_body_from_entries(build_promotion_queue_entries())


def summarize_promotion_entries(entries: list[dict[str, object]]) -> dict[str, int]:
    return {
        "total_candidates": len(entries),
        "ready_count": len([item for item in entries if item["decision"] == "ready"]),
        "review_count": len([item for item in entries if item["decision"] == "review"]),
        "blocked_count": len([item for item in entries if item["decision"] == "blocked"]),
        "covered_count": len([item for item in entries if item["decision"] == "covered"]),
    }


def generate_promotion_queue(entries: list[dict[str, object]] | None = None) -> dict[str, object]:
    ensure_dirs()
    if entries is None:
        entries = build_promotion_queue_entries()
    cache_key = fingerprint_payload(entries)
    cached = read_cached_report(PROMOTION_QUEUE_REPORT_CACHE, cache_key)
    if cached is not None:
        return cached
    report_path = REPORTS_ROOT / f"promotion_queue_{slug_timestamp()}.md"
    report_path.write_text(build_promotion_queue_body_from_entries(entries), encoding="utf-8")
    payload = {
        "generated_at": timestamp(),
        "report_path": str(report_path),
        **summarize_promotion_entries(entries),
    }
    write_cached_report(PROMOTION_QUEUE_REPORT_CACHE, cache_key, payload)
    return payload


def compare_note_sections(existing_text: str, generated_text: str) -> tuple[list[str], list[str], list[str]]:
    _, existing_metadata, existing_sections = parse_note(existing_text)
    _, generated_metadata, generated_sections = parse_note(generated_text)
    existing_canon = normalize_bullets(existing_sections.get("canon", []))
    generated_canon = normalize_bullets(generated_sections.get("canon", []))
    missing_keys = [
        key
        for key in ["evidence_mode", "confidence_basis", "source_count_basis", "source_count", "evidence"]
        if key not in existing_metadata or not existing_metadata.get(key, "").strip()
    ]
    drift_keys = [
        key
        for key in [
            "claim_state",
            "evidence",
            "evidence_mode",
            "freshness",
            "confidence",
            "confidence_basis",
            "scope",
            "source_count",
            "source_count_basis",
        ]
        if existing_metadata.get(key, "") != generated_metadata.get(key, "")
    ]
    canon_diff = [] if existing_canon == generated_canon else ["canon_body"]
    return missing_keys, drift_keys, canon_diff


def canon_overlap_ratio(existing_text: str, generated_text: str) -> float:
    _, _, existing_sections = parse_note(existing_text)
    _, _, generated_sections = parse_note(generated_text)
    existing_canon = {line.strip() for line in normalize_bullets(existing_sections.get("canon", [])) if line.strip()}
    generated_canon = {line.strip() for line in normalize_bullets(generated_sections.get("canon", [])) if line.strip()}
    if not existing_canon and not generated_canon:
        return 1.0
    denominator = max(len(existing_canon), len(generated_canon), 1)
    return len(existing_canon & generated_canon) / denominator


def merge_suggestion_payload(
    same_origin: bool,
    missing_keys: list[str],
    drift_keys: list[str],
    canon_diff: list[str],
    overlap_ratio: float,
) -> tuple[str, str]:
    if same_origin:
        return ("refresh_existing", "when the source is the same, refreshing existing canon should come before merging")
    if not canon_diff and not missing_keys and not drift_keys:
        return ("keep_existing", "the existing canon note and the new candidate are effectively the same")
    if not canon_diff and (missing_keys or drift_keys):
        return ("keep_existing", "content matches and only metadata differs, so keeping existing canon is safer")
    if overlap_ratio >= 0.67:
        return ("merge_into_existing", "content overlap is high enough that merging into existing canon is more natural than creating a new file")
    if overlap_ratio <= 0.25:
        return ("fork_new_target", "content overlap is weak, so a new canon branch is safer than sharing the same target")
    return ("review_manually", "overlap and difference are ambiguous enough to require human review")


def merge_unique_bullets(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for line in normalize_bullets(group):
            if line not in merged:
                merged.append(line)
    return merged


def choose_latest_date(*values: str) -> str:
    dated = [(parse_date_value(value), value) for value in values if value]
    dated = [(parsed, raw) for parsed, raw in dated if parsed is not None]
    if not dated:
        return next((value for value in values if value), current_date())
    return max(dated, key=lambda item: item[0])[1]


def confidence_rank(value: str) -> int:
    mapping = {"low": 1, "medium": 2, "high": 3}
    return mapping.get(value, 0)


def choose_confidence(*values: str) -> str:
    candidates = [value for value in values if value]
    if not candidates:
        return "low"
    return max(candidates, key=confidence_rank)


def choose_confidence_basis(*values: str) -> str:
    ordered = ["explicit", "source_count", "evidence_refs", "conservative_default", "unknown"]
    for candidate in ordered:
        if candidate in values:
            return candidate
    return next((value for value in values if value), "unknown")


def choose_evidence_mode(refs: list[str], *values: str) -> str:
    if len(refs) >= 2:
        return "listed"
    ordered = ["explicit", "listed", "trace"]
    for candidate in ordered:
        if candidate in values:
            return candidate
    return "trace"


def render_canon_note(
    title: str,
    metadata: dict[str, str],
    canon_lines: list[str],
    evidence_lines: list[str],
    supersession_lines: list[str],
) -> str:
    key_order = [
        "promoted_from",
        "promoted_at",
        "merged_from",
        "merged_at",
        "claim_state",
        "evidence",
        "evidence_mode",
        "freshness",
        "confidence",
        "confidence_basis",
        "scope",
        "supersession",
        "stale_flag",
        "conflict_with",
        "source_count",
        "source_count_basis",
        "last_reviewed",
        "temporal_state",
        "canon_kind",
    ]
    metadata_lines = [format_metadata_line(key, metadata[key]) for key in key_order if key in metadata]
    for key in metadata:
        if key not in key_order:
            metadata_lines.append(format_metadata_line(key, metadata[key]))

    body = [
        f"# {title}",
        "",
        *metadata_lines,
        "",
        "## canon",
        *(canon_lines or ["- canon content is derived from the source note."]),
        "",
        "## evidence",
        *(evidence_lines or ["- no evidence listed"]),
        "",
        "## supersession",
        *(supersession_lines or ["- none"]),
    ]
    return "\n".join(body).rstrip() + "\n"


def canon_update_assessment(source: Path, kind: str, target_name: str | None = None) -> dict[str, object] | None:
    assessment = promotion_assessment(source, kind, target_name)
    target_path = ROOT / Path(assessment["target"])
    if not target_path.exists():
        return None

    source_text = source.read_text(encoding="utf-8")
    generated_text = build_canon_body(source, kind, target_path.name, source_text)
    existing_text = target_path.read_text(encoding="utf-8")
    missing_keys, drift_keys, canon_diff = compare_note_sections(existing_text, generated_text)
    overlap_ratio = canon_overlap_ratio(existing_text, generated_text)

    existing_metadata = metadata_for_path(target_path)
    same_origin = nonempty_metadata_value(existing_metadata, "promoted_from") == rel_from_root(source)
    merge_suggestion, merge_reason = merge_suggestion_payload(
        same_origin=same_origin,
        missing_keys=missing_keys,
        drift_keys=drift_keys,
        canon_diff=canon_diff,
        overlap_ratio=overlap_ratio,
    )
    if same_origin and (missing_keys or drift_keys or canon_diff):
        decision = "refresh_existing"
        priority = "high"
        score = 88
        why_now = "canon derived from the same source has drifted from the current lite note and is worth refreshing"
        action = "rebuild the existing canon note from the current lite note and review the refresh"
    elif missing_keys or drift_keys or canon_diff:
        decision = "review_merge"
        priority = "medium"
        score = 60
        why_now = "existing canon is present, but metadata or content differences require a merge decision"
        action = "decide between keeping existing canon, merging, or forking to a new target"
    else:
        decision = "aligned"
        priority = "low"
        score = 10
        why_now = "existing canon does not differ meaningfully from the current lite note"
        action = "keep current canon"

    return {
        "source": rel_from_root(source),
        "target": rel_from_root(target_path),
        "kind": kind,
        "decision": decision,
        "priority": priority,
        "priority_score": score,
        "why_now": why_now,
        "action": action,
        "same_origin": same_origin,
        "missing_keys": missing_keys,
        "drift_keys": drift_keys,
        "canon_diff": canon_diff,
        "overlap_ratio": round(overlap_ratio, 3),
        "merge_suggestion": merge_suggestion,
        "merge_reason": merge_reason,
    }


def build_update_queue_entries() -> list[dict[str, object]]:
    snapshot = queue_input_snapshot()
    cached = read_cached_entries(UPDATE_ENTRIES_CACHE, snapshot)
    if cached is not None:
        return cached

    entries: list[dict[str, object]] = []
    for path in iter_runtime_notes(LITE_WIKI):
        if is_query_residue_note(path):
            continue
        kind, _ = recommended_canon_kind(path)
        assessment = canon_update_assessment(path, kind)
        if assessment is None or assessment["decision"] == "aligned":
            continue
        entries.append(assessment)
    entries.sort(key=lambda item: (-int_or_zero(item["priority_score"]), str(item["source"])))
    write_cached_entries(UPDATE_ENTRIES_CACHE, snapshot, entries)
    return entries


def build_update_queue_body_from_entries(entries: list[dict[str, object]]) -> str:
    refresh_items = [item for item in entries if item["decision"] == "refresh_existing"]
    merge_items = [item for item in entries if item["decision"] == "review_merge"]
    lines: list[str] = [
        f"# canon-update-queue-{slug_timestamp()}",
        "",
        f"- generated_at: `{timestamp()}`",
        "- queue_type: `canon-update-queue`",
        "",
        "## summary",
        f"- total_items: `{len(entries)}`",
        f"- refresh_existing: `{len(refresh_items)}`",
        f"- review_merge: `{len(merge_items)}`",
        "",
        "## update now",
    ]

    if entries:
        for item in entries[:7]:
            lines.extend(
                [
                    f"- priority: `{item['priority']}`",
                    f"  decision: `{item['decision']}`",
                    f"  source: `{item['source']}`",
                    f"  target: `{item['target']}`",
                    f"  why_now: `{item['why_now']}`",
                    f"  action: `{item['action']}`",
                ]
            )
    else:
        lines.append("- no canon update items to process")

    lines.extend(["", "## refresh existing queue"])
    if refresh_items:
        for item in refresh_items:
            lines.extend(
                [
                    f"- source: `{item['source']}`",
                    f"  target: `{item['target']}`",
                    f"  same_origin: `{str(item['same_origin']).lower()}`",
                    f"  missing_keys: `{'; '.join(item['missing_keys']) if item['missing_keys'] else 'none'}`",
                    f"  drift_keys: `{'; '.join(item['drift_keys']) if item['drift_keys'] else 'none'}`",
                    f"  canon_diff: `{'; '.join(item['canon_diff']) if item['canon_diff'] else 'none'}`",
                    f"  merge_suggestion: `{item['merge_suggestion']}`",
                    f"  action: `{item['action']}`",
                ]
            )
    else:
        lines.append("- no refresh-existing items to process")

    lines.extend(["", "## review merge queue"])
    if merge_items:
        for item in merge_items:
            lines.extend(
                [
                    f"- source: `{item['source']}`",
                    f"  target: `{item['target']}`",
                    f"  same_origin: `{str(item['same_origin']).lower()}`",
                    f"  missing_keys: `{'; '.join(item['missing_keys']) if item['missing_keys'] else 'none'}`",
                    f"  drift_keys: `{'; '.join(item['drift_keys']) if item['drift_keys'] else 'none'}`",
                    f"  canon_diff: `{'; '.join(item['canon_diff']) if item['canon_diff'] else 'none'}`",
                    f"  overlap_ratio: `{item['overlap_ratio']}`",
                    f"  merge_suggestion: `{item['merge_suggestion']}`",
                    f"  merge_reason: `{item['merge_reason']}`",
                    f"  action: `{item['action']}`",
                ]
            )
    else:
        lines.append("- no review-merge items to process")

    lines.extend(
        [
            "",
            "## next step",
            "- treat the refresh-existing queue as the first canon refresh candidate set.",
            "- resolve the review-merge queue by merging, forking, or keeping existing canon.",
            "- revisit the promotion queue after finishing update work.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_update_queue_body() -> str:
    return build_update_queue_body_from_entries(build_update_queue_entries())


def summarize_update_entries(entries: list[dict[str, object]]) -> dict[str, int]:
    return {
        "total_items": len(entries),
        "refresh_existing_count": len([item for item in entries if item["decision"] == "refresh_existing"]),
        "review_merge_count": len([item for item in entries if item["decision"] == "review_merge"]),
    }


def generate_update_queue(entries: list[dict[str, object]] | None = None) -> dict[str, object]:
    ensure_dirs()
    if entries is None:
        entries = build_update_queue_entries()
    cache_key = fingerprint_payload(entries)
    cached = read_cached_report(UPDATE_QUEUE_REPORT_CACHE, cache_key)
    if cached is not None:
        return cached
    report_path = REPORTS_ROOT / f"canon_update_queue_{slug_timestamp()}.md"
    report_path.write_text(build_update_queue_body_from_entries(entries), encoding="utf-8")
    payload = {
        "generated_at": timestamp(),
        "report_path": str(report_path),
        **summarize_update_entries(entries),
    }
    write_cached_report(UPDATE_QUEUE_REPORT_CACHE, cache_key, payload)
    return payload


def build_governance_cycle_body_from_entries(
    repair_queue: dict[str, object],
    promotion_queue: dict[str, object],
    update_queue: dict[str, object],
    maintenance: dict[str, object],
    conflict: dict[str, object],
    staleness: dict[str, object],
    promotion_entries: list[dict[str, object]],
    update_entries: list[dict[str, object]],
) -> str:
    static_lint = maintenance["static_lint"]

    ready_entries = [item for item in promotion_entries if item["decision"] == "ready"]
    review_entries = [item for item in promotion_entries if item["decision"] == "review"]
    blocked_entries = [item for item in promotion_entries if item["decision"] == "blocked"]
    covered_entries = [item for item in promotion_entries if item["decision"] == "covered"]
    refresh_entries = [item for item in update_entries if item["decision"] == "refresh_existing"]
    merge_entries = [item for item in update_entries if item["decision"] == "review_merge"]

    next_actions: list[str] = []
    if refresh_entries:
        next_actions.append("process refresh-existing items from the update queue first")
    if ready_entries:
        next_actions.append("promote ready items from the promotion queue into canon")
    if static_lint["broken_evidence_refs"]:
        next_actions.append("fix broken evidence refs first to restore trace reliability")
    if static_lint["broken_wikilinks"]:
        next_actions.append("repair broken wikilinks to restore the document graph")
    if merge_entries:
        next_actions.append("resolve review-merge items with merge preview/apply")
    if review_entries:
        next_actions.append("reinforce evidence and reusable rules for promotion-review items")
    if not next_actions:
        next_actions.append("the runtime is stable, so stay focused on new raw ingest or query work")

    lines: list[str] = [
        f"# governance-cycle-{slug_timestamp()}",
        "",
        f"- generated_at: `{timestamp()}`",
        "- cycle_type: `governance-runtime`",
        f"- repair_queue: `{Path(repair_queue['report_path']).name}`",
        f"- promotion_queue: `{Path(promotion_queue['report_path']).name}`",
        f"- update_queue: `{Path(update_queue['report_path']).name}`",
        "",
        "## system state",
        f"- maintenance_clean: `{str(not any(maintenance[key] for key in ['canon_missing_metadata', 'lite_missing_metadata', 'stale_candidates', 'review_candidates', 'basis_review_candidates', 'superseded_notes', 'conflict_candidates', 'duplicate_titles'])).lower()}`",
        f"- conflict_clean: `{str(not any(conflict[key] for key in ['explicit_conflicts', 'duplicate_titles', 'divergent_duplicates', 'shared_sources'])).lower()}`",
        f"- staleness_clean: `{str(not any(staleness[key] for key in ['forced_stale', 'canon_age_stale', 'lite_review_overdue', 'canon_review_overdue'])).lower()}`",
        f"- static_lint_clean: `{str(not any(static_lint[key] for key in ['broken_wikilinks', 'broken_evidence_refs', 'empty_core_sections'])).lower()}`",
        "",
        "## queue summary",
        f"- repair_followups: `{len(refresh_entries) + len(merge_entries)}`",
        f"- promotion_ready: `{len(ready_entries)}`",
        f"- promotion_review: `{len(review_entries)}`",
        f"- promotion_blocked: `{len(blocked_entries)}`",
        f"- promotion_covered: `{len(covered_entries)}`",
        f"- update_refresh_existing: `{len(refresh_entries)}`",
        f"- update_review_merge: `{len(merge_entries)}`",
        f"- broken_wikilinks: `{len(static_lint['broken_wikilinks'])}`",
        f"- broken_evidence_refs: `{len(static_lint['broken_evidence_refs'])}`",
        f"- empty_core_sections: `{len(static_lint['empty_core_sections'])}`",
        "",
        "## next actions",
    ]

    for action in next_actions[:5]:
        lines.append(f"- {action}")

    lines.extend(["", "## top promotion items"])
    if promotion_entries:
        for item in promotion_entries[:5]:
            lines.extend(
                [
                    f"- decision: `{item['decision']}`",
                    f"  source: `{item['source']}`",
                    f"  priority: `{item['priority']}`",
                    f"  action: `{item['action']}`",
                ]
            )
    else:
        lines.append("- no promotion items to process")

    lines.extend(["", "## top update items"])
    if update_entries:
        for item in update_entries[:5]:
            lines.extend(
                [
                    f"- decision: `{item['decision']}`",
                    f"  source: `{item['source']}`",
                    f"  target: `{item['target']}`",
                    f"  merge_suggestion: `{item['merge_suggestion']}`",
                    f"  action: `{item['action']}`",
                ]
            )
    else:
        lines.append("- no update items to process")

    return "\n".join(lines).rstrip() + "\n"


def build_governance_cycle_body() -> str:
    maintenance = maintenance_report()
    conflict = conflict_report()
    staleness = staleness_report()
    promotion_entries = build_promotion_queue_entries()
    update_entries = build_update_queue_entries()
    static_lint = maintenance["static_lint"]
    bundle = {
        "maintenance": maintenance,
        "conflict": conflict,
        "staleness": staleness,
        "static_lint": static_lint,
    }
    repair_queue = generate_repair_queue(bundle)
    promotion_queue = generate_promotion_queue(promotion_entries)
    update_queue = generate_update_queue(update_entries)
    return build_governance_cycle_body_from_entries(
        repair_queue,
        promotion_queue,
        update_queue,
        maintenance,
        conflict,
        staleness,
        promotion_entries,
        update_entries,
    )


def generate_governance_cycle() -> dict[str, object]:
    ensure_dirs()
    snapshot = governance_input_snapshot()
    cached = read_state(GOVERNANCE_CYCLE_CACHE)
    if cached.get("version") == GOVERNANCE_CYCLE_CACHE_VERSION and cached.get("snapshot") == snapshot:
        payload = cached.get("payload")
        report_paths = cached.get("report_paths", {})
        if isinstance(payload, dict) and isinstance(report_paths, dict):
            required = [
                report_paths.get("governance"),
                report_paths.get("repair"),
                report_paths.get("promotion"),
                report_paths.get("update"),
            ]
            if all(isinstance(path, str) and Path(path).exists() for path in required):
                current_day = current_date()
                if governance_generated_date(payload) != current_day:
                    payload = dict(payload)
                    payload["cycle_generated_at"] = str(payload.get("cycle_generated_at", payload.get("generated_at", "unknown")))
                    payload["generated_at"] = timestamp()
                    write_state(
                        GOVERNANCE_CYCLE_CACHE,
                        {
                            "version": GOVERNANCE_CYCLE_CACHE_VERSION,
                            "snapshot": snapshot,
                            "payload": payload,
                            "report_paths": report_paths,
                            "updated_at": timestamp(),
                        },
                    )
                sync_governance_summary_views(payload, report_paths)
                operator_summary_payload()
                return payload

    maintenance = maintenance_report()
    conflict = conflict_report()
    staleness = staleness_report()
    promotion_entries = build_promotion_queue_entries()
    update_entries = build_update_queue_entries()
    static_lint = maintenance["static_lint"]
    bundle = {
        "maintenance": maintenance,
        "conflict": conflict,
        "staleness": staleness,
        "static_lint": static_lint,
    }
    repair_queue = generate_repair_queue(bundle)
    promotion_queue = generate_promotion_queue(promotion_entries)
    update_queue = generate_update_queue(update_entries)
    report_path = REPORTS_ROOT / f"governance_cycle_{slug_timestamp()}.md"
    report_path.write_text(
        build_governance_cycle_body_from_entries(
            repair_queue,
            promotion_queue,
            update_queue,
            maintenance,
            conflict,
            staleness,
            promotion_entries,
            update_entries,
        ),
        encoding="utf-8",
    )
    archive = archive_advisory()
    cycle_generated_at = timestamp()
    payload = {
        "generated_at": cycle_generated_at,
        "cycle_generated_at": cycle_generated_at,
        "report_path": str(report_path),
        "maintenance_clean": not any(maintenance[key] for key in ["canon_missing_metadata", "lite_missing_metadata", "stale_candidates", "review_candidates", "basis_review_candidates", "superseded_notes", "conflict_candidates", "duplicate_titles"]),
        "conflict_clean": not any(conflict[key] for key in ["explicit_conflicts", "duplicate_titles", "divergent_duplicates", "shared_sources"]),
        "staleness_clean": not any(staleness[key] for key in ["forced_stale", "canon_age_stale", "lite_review_overdue", "canon_review_overdue"]),
        "static_lint_clean": not any(static_lint[key] for key in ["broken_wikilinks", "broken_evidence_refs", "empty_core_sections"]),
        "broken_wikilinks": len(static_lint["broken_wikilinks"]),
        "broken_evidence_refs": len(static_lint["broken_evidence_refs"]),
        "empty_core_sections": len(static_lint["empty_core_sections"]),
        "archive_advisory": archive,
        **summarize_promotion_entries(promotion_entries),
        **summarize_update_entries(update_entries),
    }
    report_paths = {
        "governance": str(report_path),
        "repair": str(repair_queue["report_path"]),
        "promotion": str(promotion_queue["report_path"]),
        "update": str(update_queue["report_path"]),
    }
    write_state(
        GOVERNANCE_CYCLE_CACHE,
        {
            "version": GOVERNANCE_CYCLE_CACHE_VERSION,
            "snapshot": snapshot,
            "payload": payload,
            "report_paths": report_paths,
            "updated_at": timestamp(),
        },
    )
    sync_governance_summary_views(payload, report_paths)
    operator_summary_payload()
    return payload


def build_supervisor_report_body(mode: str, steps: list[dict[str, object]]) -> str:
    lines: list[str] = [
        f"# supervisor-cycle-{slug_timestamp()}",
        "",
        f"- generated_at: `{timestamp()}`",
        f"- cycle_mode: `{mode}`",
        f"- step_count: `{len(steps)}`",
        "",
        "## executed steps",
    ]

    for step in steps:
        summary_parts: list[str] = []
        if step.get("workflow") == "ingest":
            summary_parts.append(f"processed={step.get('processed_count', 0)}")
            summary_parts.append(f"skipped={step.get('skipped_count', 0)}")
        if step.get("workflow") == "promotion":
            summary_parts.append(f"ready={step.get('ready_count', 0)}")
            summary_parts.append(f"review={step.get('review_count', 0)}")
            summary_parts.append(f"blocked={step.get('blocked_count', 0)}")
        if step.get("workflow") == "update":
            summary_parts.append(f"refresh={step.get('refresh_existing_count', 0)}")
            summary_parts.append(f"review_merge={step.get('review_merge_count', 0)}")
        if step.get("workflow") == "governance":
            summary_parts.append(f"promotion_ready={step.get('promotion_ready_count', 0)}")
            summary_parts.append(f"update_refresh={step.get('update_refresh_count', 0)}")

        summary = ", ".join(summary_parts) if summary_parts else "completed"
        lines.extend(
            [
                f"- workflow: `{step.get('workflow', 'unknown')}`",
                f"  summary: `{summary}`",
            ]
        )

    governance_step = next((step for step in reversed(steps) if step.get("workflow") == "governance"), None)
    if governance_step is not None:
        lines.extend(
            [
                "",
                "## governance output",
                f"- report: `{Path(str(governance_step['governance_cycle']['report_path'])).name}`",
                f"- promotion_ready_count: `{governance_step.get('promotion_ready_count', 0)}`",
                f"- promotion_review_count: `{governance_step.get('promotion_review_count', 0)}`",
                f"- update_refresh_count: `{governance_step.get('update_refresh_count', 0)}`",
                f"- update_merge_count: `{governance_step.get('update_merge_count', 0)}`",
            ]
        )

    lines.extend(
        [
            "",
            "## next step",
            "- read the next actions at the top of the governance report first.",
            "- in intake mode, run again after new raw intake settles.",
            "- in maintenance mode, review governance again after handling the repair queue.",
            "- in full mode, use it to close the current operations state for the day.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def supervisor_cache_key_payload(mode: str, steps: list[dict[str, object]]) -> dict[str, object]:
    normalized_steps: list[dict[str, object]] = []
    for step in steps:
        if not isinstance(step, dict):
            normalized_steps.append({"value": step})
            continue
        normalized_step = dict(step)
        if normalized_step.get("workflow") == "governance":
            governance_cycle = normalized_step.get("governance_cycle")
            if isinstance(governance_cycle, dict):
                normalized_cycle = dict(governance_cycle)
                normalized_cycle.pop("archive_advisory", None)
                normalized_step["governance_cycle"] = normalized_cycle
        normalized_steps.append(normalized_step)
    return {"mode": mode, "steps": normalized_steps}


def run_supervisor_cycle(mode: str) -> dict[str, object]:
    ensure_dirs()
    if mode not in {"intake", "maintenance", "full"}:
        raise ValueError(f"unsupported supervisor mode: {mode}")

    steps: list[dict[str, object]] = []
    if mode in {"intake", "full"}:
        steps.append(workflow_ingest())
        steps.append(workflow_compile())
    if mode in {"maintenance", "full"}:
        steps.append(workflow_lint())
        steps.append(workflow_repair())

    steps.append(workflow_governance())
    cache_key = fingerprint_payload(supervisor_cache_key_payload(mode, steps))
    cached = read_state(SUPERVISOR_CYCLE_CACHE)
    if cached.get("version") == SUPERVISOR_CYCLE_CACHE_VERSION and cached.get("cache_key") == cache_key:
        payload = cached.get("payload")
        if isinstance(payload, dict):
            report_path = payload.get("report_path")
            if isinstance(report_path, str) and Path(report_path).exists():
                current_day = current_date()
                if supervisor_generated_date(payload) != current_day:
                    payload = dict(payload)
                    payload["cycle_generated_at"] = str(payload.get("cycle_generated_at", payload.get("generated_at", "unknown")))
                    payload["generated_at"] = timestamp()
                    write_state(
                        SUPERVISOR_CYCLE_CACHE,
                        {
                            "version": SUPERVISOR_CYCLE_CACHE_VERSION,
                            "cache_key": cache_key,
                            "payload": payload,
                            "updated_at": timestamp(),
                        },
                    )
                sync_supervisor_summary_views(payload)
                operator_summary_payload()
                return payload

    report_path = REPORTS_ROOT / f"supervisor_cycle_{slug_timestamp()}.md"
    report_path.write_text(build_supervisor_report_body(mode, steps), encoding="utf-8")
    governance_step = next((step for step in reversed(steps) if step.get("workflow") == "governance"), None)
    lint_step = next((step for step in reversed(steps) if step.get("workflow") == "lint"), None)
    ingest_step = next((step for step in steps if step.get("workflow") == "ingest"), None)
    governance_cycle = governance_step["governance_cycle"] if isinstance(governance_step, dict) else None
    action_plan = operator_action_plan(status_payload(), governance_cycle if isinstance(governance_cycle, dict) else None)
    cycle_generated_at = timestamp()
    payload = {
        "generated_at": cycle_generated_at,
        "cycle_generated_at": cycle_generated_at,
        "mode": mode,
        "report_path": str(report_path),
        "steps": steps,
        "step_count": len(steps),
        "ingest_processed": int_or_zero(ingest_step.get("processed_count", 0)) if isinstance(ingest_step, dict) else 0,
        "lint_clean": lint_step.get("clean", "not_run") if isinstance(lint_step, dict) else "not_run",
        "promotion_ready_count": int_or_zero(governance_step.get("promotion_ready_count", 0)) if isinstance(governance_step, dict) else 0,
        "update_refresh_count": int_or_zero(governance_step.get("update_refresh_count", 0)) if isinstance(governance_step, dict) else 0,
        "governance_report_path": str(governance_step["governance_cycle"]["report_path"]) if isinstance(governance_step, dict) else "",
        "archive_advisory": archive_advisory(),
        "action_plan": action_plan,
    }
    write_state(
        SUPERVISOR_CYCLE_CACHE,
        {
            "version": SUPERVISOR_CYCLE_CACHE_VERSION,
            "cache_key": cache_key,
            "payload": payload,
            "updated_at": timestamp(),
        },
    )
    sync_supervisor_summary_views(payload)
    operator_summary_payload()
    return payload


def merge_preview(source_name: str, kind: str, target_name: str | None = None) -> dict[str, object]:
    ensure_dirs()
    source = find_lite_note(source_name)
    assessment = canon_update_assessment(source, kind, target_name)
    if assessment is None:
        return {
            "ok": False,
            "message": "no existing canon target found for merge preview",
        }
    return {
        "ok": True,
        "source": assessment["source"],
        "target": assessment["target"],
        "decision": assessment["decision"],
        "same_origin": assessment["same_origin"],
        "overlap_ratio": assessment["overlap_ratio"],
        "merge_suggestion": assessment["merge_suggestion"],
        "merge_reason": assessment["merge_reason"],
        "missing_keys": assessment["missing_keys"],
        "drift_keys": assessment["drift_keys"],
        "canon_diff": assessment["canon_diff"],
        "action": assessment["action"],
    }


def merge_apply(
    source_name: str,
    kind: str,
    target_name: str,
    decision: str,
    new_target_name: str | None = None,
    force: bool = False,
) -> dict[str, object]:
    ensure_dirs()
    source = find_lite_note(source_name)
    assessment = canon_update_assessment(source, kind, target_name)
    if assessment is None:
        return {"ok": False, "message": "no existing canon target found for merge apply"}

    allowed = {"merge_into_existing", "fork_new_target", "keep_existing"}
    if decision not in allowed:
        return {"ok": False, "message": f"unsupported merge decision: {decision}"}

    suggested = str(assessment["merge_suggestion"])
    if decision != suggested and not force:
        return {
            "ok": False,
            "message": f"merge decision differs from suggestion: suggested={suggested}",
            "assessment": assessment,
        }

    target = ROOT / Path(assessment["target"])
    if decision == "keep_existing":
        append_if_missing(WIKI_LOG, f"- `{timestamp()}` kept existing `{rel_from_root(target)}` for `{source.name}`")
        return {
            "ok": True,
            "applied_decision": decision,
            "target": str(target),
            "assessment": assessment,
        }

    if decision == "fork_new_target":
        canon_dir = resolve_canon_folder(kind)
        preferred_name = new_target_name or source.name
        if not preferred_name.endswith(".md"):
            preferred_name = f"{preferred_name}.md"
        fork_target = unique_target_path(canon_dir, preferred_name)
        fork_assessment = promotion_assessment(source, kind, fork_target.name)
        if fork_assessment["decision"] != "ready" and not force:
            return {
                "ok": False,
                "message": "fork target is not promotable without force",
                "assessment": fork_assessment,
            }
        original = source.read_text(encoding="utf-8")
        fork_target.write_text(build_canon_body(source, kind, fork_target.name, original), encoding="utf-8")
        update_index(kind, fork_target)
        append_if_missing(
            WIKI_LOG,
            f"- `{timestamp()}` forked `{source.name}` -> `{rel_from_root(fork_target)}` from merge target `{rel_from_root(target)}`",
        )
        return {
            "ok": True,
            "applied_decision": decision,
            "target": str(fork_target),
            "assessment": assessment,
        }

    existing_title, existing_metadata, existing_sections = load_note(target)
    _, source_metadata, source_sections = load_note(source)
    generated_text = build_canon_body(source, kind, target.name, source.read_text(encoding="utf-8"))
    _, generated_metadata, generated_sections = parse_note(generated_text)

    merged_refs = merge_safe_evidence_refs(target, existing_metadata, existing_sections, include_self=False)
    for ref in merge_safe_evidence_refs(source, source_metadata, source_sections, include_self=True):
        if ref not in merged_refs:
            merged_refs.append(ref)
    evidence_value = "; ".join(merged_refs[:6]) if merged_refs else rel_from_root(source)
    evidence_mode = choose_evidence_mode(merged_refs, existing_metadata.get("evidence_mode", ""), generated_metadata.get("evidence_mode", ""))
    merged_metadata = existing_metadata.copy()
    merged_metadata.update(
        {
            "evidence": evidence_value,
            "evidence_mode": evidence_mode,
            "freshness": choose_latest_date(existing_metadata.get("freshness", ""), generated_metadata.get("freshness", "")),
            "confidence": choose_confidence(existing_metadata.get("confidence", ""), generated_metadata.get("confidence", "")),
            "confidence_basis": choose_confidence_basis(
                existing_metadata.get("confidence_basis", ""),
                generated_metadata.get("confidence_basis", ""),
            ),
            "scope": merge_path_values(existing_metadata.get("scope", "none"), [generated_metadata.get("scope", "")]),
            "source_count": str(max(int_or_zero(existing_metadata.get("source_count", "0")), len(merged_refs))),
            "source_count_basis": "evidence_refs" if len(merged_refs) >= 2 else existing_metadata.get("source_count_basis", "unknown"),
            "last_reviewed": current_date(),
            "merged_from": merge_path_values(existing_metadata.get("merged_from", "none"), [rel_from_root(source)]),
            "merged_at": timestamp(),
        }
    )

    canon_lines = merge_unique_bullets(existing_sections.get("canon", []), generated_sections.get("canon", []))
    evidence_lines = [f"- `{ref}`" for ref in merged_refs] if merged_refs else [f"- `{rel_from_root(source)}`"]
    supersession_lines = merge_unique_bullets(existing_sections.get("supersession", []), generated_sections.get("supersession", []))
    target.write_text(
        render_canon_note(existing_title, merged_metadata, canon_lines, evidence_lines, supersession_lines),
        encoding="utf-8",
    )
    update_index(kind, target)
    append_if_missing(WIKI_LOG, f"- `{timestamp()}` merged `{source.name}` into `{rel_from_root(target)}`")
    return {
        "ok": True,
        "applied_decision": decision,
        "target": str(target),
        "assessment": assessment,
    }


def refresh_existing_canon(source_name: str, kind: str, target_name: str | None = None, force: bool = False) -> dict[str, object]:
    ensure_dirs()
    source = find_lite_note(source_name)
    assessment = canon_update_assessment(source, kind, target_name)
    if assessment is None:
        return {
            "ok": False,
            "message": "no existing canon target found for refresh",
        }
    if assessment["decision"] == "aligned":
        return {
            "ok": True,
            "message": "existing canon already aligned",
            "target": str(ROOT / Path(assessment["target"])),
            "assessment": assessment,
        }
    if assessment["decision"] != "refresh_existing" and not force:
        return {
            "ok": False,
            "message": "refresh blocked; review_merge requires explicit force",
            "assessment": assessment,
        }

    target = ROOT / Path(assessment["target"])
    original = source.read_text(encoding="utf-8")
    target.write_text(build_canon_body(source, kind, target.name, original), encoding="utf-8")
    update_index(kind, target)
    append_if_missing(WIKI_LOG, f"- `{timestamp()}` refreshed `{rel_from_root(target)}` from `{source.name}`")
    return {
        "ok": True,
        "forced": force and assessment["decision"] != "refresh_existing",
        "target": str(target),
        "assessment": assessment,
    }


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(r'[<>:"/\\\\|?*]+', "-", name).strip()
    sanitized = re.sub(r"\s+", "-", sanitized)
    sanitized = sanitized.strip(".-")
    return sanitized or f"note-{slug_timestamp()}"


def slugify_text(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"[`'\"“”‘’]+", "", lowered)
    lowered = re.sub(r"[^0-9a-zA-Z가-힣]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered)
    lowered = lowered.strip("-")
    return lowered or f"query-{slug_timestamp()}"


def unique_target_path(base_dir: Path, name: str) -> Path:
    candidate = base_dir / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        numbered = base_dir / f"{stem}-{index}{suffix}"
        if not numbered.exists():
            return numbered
        index += 1


def find_lite_note_by_built_from(built_from: str) -> Path | None:
    for path in sorted(LITE_WIKI.rglob("*.md")):
        metadata = metadata_for_path(path)
        if nonempty_metadata_value(metadata, "built_from") == built_from:
            return path
    return None


def build_lite_built_from_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in sorted(LITE_WIKI.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        metadata = metadata_for_path(path)
        built_from = nonempty_metadata_value(metadata, "built_from")
        if built_from and built_from not in index:
            index[built_from] = path
    return index


def build_lite_note_from_raw(source: Path) -> str:
    original = source.read_text(encoding="utf-8")
    title, metadata, sections = parse_note(original)
    built_from = rel_from_root(source)
    status = normalize_status(nonempty_metadata_value(metadata, "initial_judgment", "hold"))
    surface = normalize_surface(nonempty_metadata_value(metadata, "intended_axis", "coordination"))
    reviewed_at = current_date()
    freshness = derive_freshness_from_raw(metadata)
    source_scope = nonempty_metadata_value(metadata, "source_scope", "unknown")
    source_path = nonempty_metadata_value(metadata, "source_path", built_from)

    distilled_lines = normalize_bullets(sections.get("raw", []))
    if not distilled_lines:
        distilled_lines = ["- raw section is empty, so the source material needs review."]

    caution_lines = normalize_bullets(sections.get("caution", []))
    reusable_lines = normalize_bullets(sections.get("reusable rule", []))
    if not reusable_lines:
        reusable_lines = ["- if the same topic appears again, check for overlap with existing notes first."]

    body = [
        f"# {title}",
        "",
        f"- built_from: `{built_from}`",
        f"- status: `{status}`",
        f"- surface: `{surface}`",
        f"- reviewed_at: `{reviewed_at}`",
        "- claim_state: `inference`",
        f"- freshness: `{freshness}`",
        f"- confidence: `{derive_confidence_from_status(status)}`",
        "- confidence_basis: `conservative_default`",
        f"- scope: `{surface} surface from {source_scope} raw`",
        "- source_count: `1`",
        "- source_count_basis: `trace_only`",
        "- evidence_mode: `trace`",
        "",
        "## distilled",
        *distilled_lines,
        "",
        "## reusable rule",
        *reusable_lines,
        "",
        "## next action",
        f"- {derive_next_action(status)}",
        "",
        "## evidence",
        f"- `{source_path}`",
        f"- `{built_from}`",
    ]
    if caution_lines:
        body.extend(["", "## caution", *caution_lines])
    return "\n".join(body).rstrip() + "\n"


def build_lite_log_body(raw_path: Path, wiki_path: Path, judgment: str) -> str:
    slug = wiki_path.stem
    return "\n".join(
        [
            f"# {slug}",
            "",
            f"- raw: `{rel_from_root(raw_path)}`",
            f"- wiki: `{rel_from_root(wiki_path)}`",
            f"- judgment: `{judgment}`",
            "- change: converted raw input into a lite note.",
            "",
        ]
    )


def ingest_raw_notes() -> dict:
    ensure_dirs()
    processed: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    existing_index = build_lite_built_from_index()

    raw_files = sorted(path for path in LITE_RAW.rglob("*.md") if path.name.lower() != "readme.md")
    for raw_path in raw_files:
        raw_metadata = metadata_for_path(raw_path)
        built_from = rel_from_root(raw_path)
        already_target = nonempty_metadata_value(raw_metadata, "ingested_to")
        if already_target:
            target_path = ROOT / Path(already_target)
            if target_path.exists():
                skipped.append({"raw": built_from, "reason": "already_ingested", "target": already_target})
                continue

        existing = existing_index.get(built_from)
        if existing is not None:
            updates = {"ingested_to": rel_from_root(existing), "ingested_at": timestamp()}
            set_note_metadata(raw_path, updates)
            skipped.append({"raw": built_from, "reason": "existing_target", "target": rel_from_root(existing)})
            continue

        filename = sanitize_filename(raw_path.stem)
        if not filename.endswith(".md"):
            filename = f"{filename}.md"
        target_path = unique_target_path(LITE_WIKI, filename)
        note_text = build_lite_note_from_raw(raw_path)
        target_path.write_text(note_text, encoding="utf-8")
        existing_index[built_from] = target_path

        judgment = metadata_for_path(target_path).get("status", "hold")
        log_path = LITE_LOG / f"{target_path.stem}.md"
        log_path.write_text(build_lite_log_body(raw_path, target_path, judgment), encoding="utf-8")

        set_note_metadata(raw_path, {"ingested_to": rel_from_root(target_path), "ingested_at": timestamp()})
        processed.append(
            {
                "raw": built_from,
                "wiki": rel_from_root(target_path),
                "log": rel_from_root(log_path),
                "judgment": judgment,
            }
        )

    return {
        "raw_total": len(raw_files),
        "processed_count": len(processed),
        "skipped_count": len(skipped),
        "processed": processed,
        "skipped": skipped,
    }


def layer_for_path(path: Path) -> str:
    try:
        path.relative_to(WIKI_ROOT)
        return "wiki"
    except ValueError:
        pass
    try:
        path.relative_to(LITE_WIKI)
        return "wiki_lite"
    except ValueError:
        pass
    return "external"


def required_keys_for_layer(layer: str) -> list[str]:
    if layer == "wiki":
        return CANON_REQUIRED_METADATA
    if layer == "wiki_lite":
        return LITE_REQUIRED_METADATA
    return []


def missing_metadata_keys(metadata: dict[str, str], layer: str) -> list[str]:
    missing: list[str] = []
    for key in required_keys_for_layer(layer):
        if not metadata.get(key, "").strip():
            missing.append(key)
    return missing


def parse_score(hit: dict, index: int) -> float:
    raw = hit.get("score")
    if isinstance(raw, (int, float)):
        return float(raw)
    return max(0.0, 100.0 - index)


def extract_query_keywords(question: str) -> list[str]:
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "after",
        "before",
        "recent",
        "query",
        "policy",
        "질문",
        "정책",
        "최근",
    }
    keywords: list[str] = []
    for token in re.findall(r"[a-zA-Z가-힣0-9_-]+", question.lower()):
        if len(token) < 3:
            continue
        if token in stopwords:
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords


def detect_query_intent(question: str) -> dict[str, bool]:
    lowered = question.lower()
    return {
        "conflict": any(token in lowered for token in ["conflict", "duplicate", "mismatch", "충돌", "중복"]),
        "stale": any(token in lowered for token in ["stale", "supersession", "superseded", "replacement", "review overdue", "노후", "오래", "대체"]),
    }


def basis_action_text(item: dict[str, str | list[str]]) -> str:
    reasons = set(item.get("reasons", []))
    evidence_mode = str(item.get("evidence_mode", "unknown"))
    confidence_basis = str(item.get("confidence_basis", "unknown"))
    source_count_basis = str(item.get("source_count_basis", "unknown"))

    actions: list[str] = []
    if evidence_mode == "trace":
        actions.append("add at least one direct evidence item beyond the source trace")
    elif evidence_mode == "listed":
        actions.append("select one listed item as the actual primary evidence basis")

    if confidence_basis == "conservative_default":
        actions.append("replace automatic confidence with a human-reviewed value")
    elif confidence_basis == "source_count":
        actions.append("check whether confidence came only from evidence count or also from content quality")

    if source_count_basis == "trace_only":
        actions.append("recalculate source_count using real independent evidence items")
    elif source_count_basis == "evidence_refs":
        actions.append("recalculate independent evidence count after excluding duplicate traces")

    if not actions:
        actions.append("review the evidence-strength metadata again")
    return "; ".join(actions)


def int_or_zero(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def classify_repair_priority(item: dict[str, object]) -> tuple[str, int, str]:
    item_type = str(item.get("type", "unknown"))
    if item_type == "broken_wikilink":
        return ("high", 88, "broken document links immediately destabilize retrieval and navigation")
    if item_type == "broken_evidence_ref":
        return ("high", 84, "broken evidence paths immediately reduce traceability and verification")
    if item_type == "empty_core_section":
        section = str(item.get("section", ""))
        if section in {"canon", "distilled"}:
            return ("medium", 57, "a core section is empty, which lowers the value of the note")
        return ("low", 26, "needs reinforcement, but it is not an immediate failure")
    if item_type == "explicit_conflict":
        return ("high", 90, "canon notes are explicitly marked as conflicting and need a baseline decision first")
    if item_type == "divergent_duplicate":
        return ("high", 95, "canon notes with the same title carry different content and pose a serious conflict risk")
    if item_type == "shared_source":
        return ("high", 85, "multiple canon notes from one source suggest duplicate promotion risk")
    if item_type == "forced_stale":
        return ("high", 80, "a replacement note already exists, so the role of the current note needs review")
    if item_type == "canon_age_stale":
        age_days = int_or_zero(item.get("age_days"))
        if age_days >= 180:
            return ("high", 78, "canon is old enough that freshness risk is material")
        return ("medium", 60, "canon freshness needs review")
    if item_type == "canon_review_overdue":
        review_days = int_or_zero(item.get("review_age_days"))
        if review_days >= 90:
            return ("medium", 58, "canon review cadence is significantly overdue")
        return ("low", 35, "review cadence needs a check")
    if item_type == "lite_review_overdue":
        review_days = int_or_zero(item.get("review_age_days"))
        if review_days >= 21:
            return ("medium", 52, "lite note has stayed unclassified long enough to delay promotion or discard decisions")
        return ("low", 30, "lite note needs reclassification")
    if item_type == "basis_review":
        reasons = set(str(reason) for reason in item.get("reasons", []))
        if len(reasons) >= 2:
            return ("medium", 55, "evidence-strength metadata is weak enough to undermine canon trust")
        return ("low", 28, "automatically inferred metadata should be confirmed by human review")
    return ("low", 10, "general review item")


def repair_item_anchor(item: dict[str, object]) -> str:
    if item.get("path"):
        return str(item["path"])
    if item.get("title"):
        return f"title:{item['title']}"
    if item.get("source"):
        return f"source:{item['source']}"
    return str(item.get("type", "unknown"))


def render_repair_item(item: dict[str, object]) -> list[str]:
    priority = str(item["priority"])
    score = int(item["priority_score"])
    why_now = str(item["why_now"])
    lines = [
        f"- type: `{item['type']}`",
        f"  priority: `{priority}`",
        f"  priority_score: `{score}`",
        f"  why_now: `{why_now}`",
    ]
    for key in ["path", "target", "title", "paths", "source", "supersession", "age_days", "review_age_days", "reasons", "action"]:
        value = item.get(key)
        if value in (None, ""):
            continue
        if isinstance(value, list):
            rendered = "; ".join(str(part) for part in value)
        else:
            rendered = str(value)
        lines.append(f"  {key}: `{rendered}`")
    return lines


def repair_queue_entries(conflict: dict, staleness: dict, maintenance: dict) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    static_lint = maintenance.get("static_lint", {})

    for item in conflict["explicit_conflicts"]:
        entries.append(
            {
                "type": "explicit_conflict",
                "path": item["path"],
                "target": item["conflict_with"],
                "action": "check target existence and decide whether one canon note should remain",
            }
        )
    for item in conflict["divergent_duplicates"]:
        entries.append(
            {
                "type": "divergent_duplicate",
                "title": item["title"],
                "paths": item["paths"],
                "action": "choose a baseline note and decide whether the remaining content should be merged",
            }
        )
    for item in conflict["shared_sources"]:
        entries.append(
            {
                "type": "shared_source",
                "source": item["promoted_from"],
                "paths": item["paths"],
                "action": "review why one source produced multiple canon notes",
            }
        )
    for item in staleness["forced_stale"]:
        entries.append(
            {
                "type": "forced_stale",
                "path": item["path"],
                "supersession": item["supersession"],
                "action": "treat the replacement note as baseline and decide whether this note becomes support or archive",
            }
        )
    for item in staleness["canon_age_stale"]:
        entries.append(
            {
                "type": "canon_age_stale",
                "path": item["path"],
                "age_days": item["age_days"],
                "action": "review freshness and evidence again",
            }
        )
    for item in staleness["canon_review_overdue"]:
        entries.append(
            {
                "type": "canon_review_overdue",
                "path": item["path"],
                "review_age_days": item["review_age_days"],
                "action": "review canonical note again",
            }
        )
    for item in staleness["lite_review_overdue"]:
        entries.append(
            {
                "type": "lite_review_overdue",
                "path": item["path"],
                "review_age_days": item["review_age_days"],
                "action": "reclassify as promote, hold, or discard",
            }
        )
    for item in maintenance["basis_review_candidates"]:
        entries.append(
            {
                "type": "basis_review",
                "path": item["path"],
                "reasons": item["reasons"],
                "action": basis_action_text(item),
            }
        )
    for item in static_lint.get("broken_wikilinks", []):
        entries.append(
            {
                "type": "broken_wikilink",
                "path": item["path"],
                "target": item["target"],
                "line": item["line"],
                "action": "create the wikilink target or align the link title with the real note title",
            }
        )
    for item in static_lint.get("broken_evidence_refs", []):
        entries.append(
            {
                "type": "broken_evidence_ref",
                "path": item["path"],
                "target": item["reference"],
                "action": "replace the evidence path with a real source or note path",
            }
        )
    for item in static_lint.get("empty_core_sections", []):
        entries.append(
            {
                "type": "empty_core_section",
                "path": item["path"],
                "section": item["section"],
                "action": "fill the core section or decide whether the note should remain",
            }
        )

    for entry in entries:
        priority, score, why_now = classify_repair_priority(entry)
        entry["priority"] = priority
        entry["priority_score"] = score
        entry["why_now"] = why_now

    entries.sort(
        key=lambda item: (
            -int_or_zero(item.get("priority_score")),
            repair_item_anchor(item),
        )
    )
    return entries


def apply_retrieval_policy(payload: dict, question: str | None = None) -> dict:
    hits = payload.get("hits", [])
    policy_warnings: list[str] = []
    reranked: list[dict] = []
    question_text = question or ""
    intent = detect_query_intent(question_text)
    keywords = extract_query_keywords(question_text)

    for index, hit in enumerate(hits):
        raw_path = hit.get("path")
        if not raw_path:
            reranked.append(hit)
            continue

        path = Path(raw_path)
        metadata = metadata_for_path(path)
        title = title_for_path(path).lower()
        layer = layer_for_path(path)
        base_score = parse_score(hit, index)
        policy_score = base_score
        reasons: list[str] = []
        searchable_text = f"{path.as_posix().lower()} {title}"

        freshness_value = nonempty_metadata_value(metadata, "freshness")
        freshness_days = days_since(freshness_value) if freshness_value else None
        confidence = nonempty_metadata_value(metadata, "confidence", "unknown")
        confidence_basis = nonempty_metadata_value(metadata, "confidence_basis", "unknown")
        claim_state = nonempty_metadata_value(metadata, "claim_state", "unknown")
        supersession = nonempty_metadata_value(metadata, "supersession", "none")
        conflict_with = nonempty_metadata_value(metadata, "conflict_with", "none")
        evidence_mode = nonempty_metadata_value(metadata, "evidence_mode", "unknown")
        source_count_basis = nonempty_metadata_value(metadata, "source_count_basis", "unknown")
        stale_flag = nonempty_metadata_value(metadata, "stale_flag", "false").lower() == "true"

        if layer == "wiki":
            policy_score += 20.0
            reasons.append("canon priority")
        if layer == "wiki_lite" and freshness_days is not None and freshness_days <= 30:
            policy_score += 12.0
            reasons.append("recent lite boost")
        if layer == "wiki" and confidence == "high":
            policy_score += 8.0
            reasons.append("high confidence")
        elif layer == "wiki" and confidence == "medium":
            policy_score += 4.0
            reasons.append("medium confidence")
        if layer == "wiki_lite" and claim_state == "opinion":
            policy_score += 5.0
            reasons.append("opinion stays in lite")
        if layer == "wiki" and evidence_mode == "explicit":
            policy_score += 4.0
            reasons.append("explicit evidence")
        elif layer == "wiki" and evidence_mode == "listed":
            policy_score += 1.5
            reasons.append("listed evidence")
        elif layer == "wiki" and evidence_mode == "trace":
            policy_score -= 8.0
            reasons.append("trace evidence penalty")
        if layer == "wiki" and confidence_basis == "explicit":
            policy_score += 2.0
            reasons.append("explicit confidence basis")
        elif layer == "wiki" and confidence_basis == "conservative_default":
            policy_score -= 6.0
            reasons.append("conservative confidence penalty")
        if layer == "wiki" and source_count_basis == "trace_only":
            policy_score -= 4.0
            reasons.append("trace-only source count penalty")
        elif layer == "wiki" and source_count_basis == "evidence_refs":
            policy_score += 1.0
            reasons.append("evidence-ref source count")
        if stale_flag:
            policy_score -= 15.0
            reasons.append("stale penalty")
        if not is_none_like(supersession):
            policy_score -= 20.0
            reasons.append("superseded")
            policy_warnings.append(f"superseded: {path} -> {supersession}")
        if not is_none_like(conflict_with):
            policy_score -= 10.0
            reasons.append("conflict warning")
            policy_warnings.append(f"conflict: {path} <-> {conflict_with}")
        if intent["conflict"] and not is_none_like(conflict_with):
            policy_score += 22.0
            reasons.append("query conflict boost")
        if intent["conflict"] and "duplicates" in path.as_posix().lower():
            policy_score += 8.0
            reasons.append("duplicate path boost")
        if intent["stale"] and stale_flag:
            policy_score += 18.0
            reasons.append("query stale boost")
        if intent["stale"] and not is_none_like(supersession):
            policy_score += 10.0
            reasons.append("supersession boost")
        if intent["stale"] and any(token in path.as_posix().lower() for token in ["stale", "superseded", "replacement"]):
            policy_score += 6.0
            reasons.append("stale path boost")
        token_matches = [token for token in keywords if token in searchable_text]
        if token_matches:
            lexical_boost = min(12.0, 6.0 + max(0, len(token_matches) - 1) * 2.0)
            policy_score += lexical_boost
            reasons.append(f"keyword boost: {', '.join(token_matches[:3])}")
        if not intent["conflict"] and any(marker in searchable_text for marker in ["healthy-conflict", "duplicates", "conflict-shared-title"]):
            policy_score -= 10.0
            reasons.append("non-conflict penalty")
        if not intent["stale"] and any(marker in searchable_text for marker in ["healthy-staleness", "/stale/", "stale-note", "superseded", "replacement-note"]):
            policy_score -= 10.0
            reasons.append("non-stale penalty")

        hit["layer"] = layer
        hit["metadata"] = {
            "claim_state": claim_state,
            "freshness": freshness_value or "unknown",
            "confidence": confidence,
            "confidence_basis": confidence_basis,
            "evidence_mode": evidence_mode,
            "source_count_basis": source_count_basis,
            "supersession": supersession,
            "conflict_with": conflict_with,
            "stale_flag": str(stale_flag).lower(),
        }
        hit["policy_score"] = round(policy_score, 3)
        hit["policy_reasons"] = reasons
        reranked.append(hit)

    reranked.sort(key=lambda item: item.get("policy_score", 0.0), reverse=True)
    payload["hits"] = reranked
    payload["policy"] = {
        "canon_priority": True,
        "recent_lite_window_days": 30,
        "query_intent": intent,
        "warnings": policy_warnings,
    }
    return payload


def iter_runtime_notes(root: Path) -> list[Path]:
    notes: list[Path] = []
    for path in sorted(root.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        notes.append(path)
    return notes


def iter_canon_notes() -> list[Path]:
    notes: list[Path] = []
    for folder in CANON_FOLDERS:
        notes.extend(iter_runtime_notes(folder))
    return sorted(notes)


WIKILINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")


def iter_all_runtime_notes() -> list[Path]:
    notes = iter_runtime_notes(LITE_WIKI)
    notes.extend(iter_canon_notes())
    unique: dict[str, Path] = {}
    for path in notes:
        unique[str(path)] = path
    return sorted(unique.values())


def page_aliases(path: Path) -> set[str]:
    aliases = {path.stem.strip().lower()}
    title = title_for_path(path).strip().lower()
    if title:
        aliases.add(title)
    return {alias for alias in aliases if alias}


def build_page_alias_set() -> set[str]:
    aliases: set[str] = set()
    for path in iter_all_runtime_notes():
        aliases.update(page_aliases(path))
    return aliases


def note_body_sections(path: Path) -> dict[str, list[str]]:
    _, _, sections = load_note(path)
    return sections


def extract_wikilinks(path: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for match in WIKILINK_PATTERN.finditer(line):
            findings.append({"target": match.group(1).strip(), "line": line_number})
    return findings


def looks_like_reference(value: str) -> bool:
    stripped = value.strip()
    if not stripped or stripped.lower() in {"none", "unknown", "n/a"}:
        return False
    if stripped.startswith("query://"):
        return False
    return (
        "/" in stripped
        or "\\" in stripped
        or stripped.endswith(".md")
        or stripped.startswith("wiki/")
        or stripped.startswith("wiki_lite/")
        or stripped.startswith("README")
    )


def resolve_reference_path(raw: str) -> Path | None:
    candidate = raw.strip()
    if not candidate or candidate.startswith("query://"):
        return None
    path = Path(candidate)
    if path.is_absolute():
        return path if path.exists() else None
    rooted = ROOT / path
    if rooted.exists():
        return rooted
    return None


def static_lint_report() -> dict[str, object]:
    ensure_dirs()
    report: dict[str, object] = {
        "generated_at": timestamp(),
        "broken_wikilinks": [],
        "broken_evidence_refs": [],
        "empty_core_sections": [],
    }
    aliases = build_page_alias_set()

    for path in iter_all_runtime_notes():
        rel_path = rel_from_root(path)
        title, metadata, sections = load_note(path)

        for link in extract_wikilinks(path):
            target = str(link["target"]).strip().lower()
            if target not in aliases:
                report["broken_wikilinks"].append(
                    {
                        "path": rel_path,
                        "line": int(link["line"]),
                        "target": str(link["target"]),
                    }
                )

        evidence_lines = normalize_bullets(sections.get("evidence", []))
        refs = sorted(set(collect_evidence_refs(path, metadata, evidence_lines)))
        checked_refs: list[str] = []
        for ref in refs:
            if not looks_like_reference(ref):
                continue
            checked_refs.append(ref)
            resolved = resolve_reference_path(ref)
            if resolved is None:
                report["broken_evidence_refs"].append({"path": rel_path, "reference": ref})

        if nonempty_metadata_value(metadata, "built_from") and looks_like_reference(nonempty_metadata_value(metadata, "built_from")):
            built_from = nonempty_metadata_value(metadata, "built_from")
            if built_from not in checked_refs and resolve_reference_path(built_from) is None:
                report["broken_evidence_refs"].append({"path": rel_path, "reference": built_from})

        if path.is_relative_to(LITE_WIKI):
            distilled = normalize_bullets(sections.get("distilled", []))
            reusable = normalize_bullets(sections.get("reusable rule", []))
            if not distilled:
                report["empty_core_sections"].append({"path": rel_path, "section": "distilled"})
            if not reusable:
                report["empty_core_sections"].append({"path": rel_path, "section": "reusable rule"})
        else:
            canon_lines = normalize_bullets(sections.get("canon", []))
            if not canon_lines:
                report["empty_core_sections"].append({"path": rel_path, "section": "canon"})

    return report


def canon_body_signature(path: Path) -> str:
    _, _, sections = load_note(path)
    lines = normalize_bullets(sections.get("canon", []))
    return "\n".join(lines).strip()


def maintenance_report() -> dict:
    ensure_dirs()
    report = {
        "generated_at": timestamp(),
        "canon_missing_metadata": [],
        "lite_missing_metadata": [],
        "stale_candidates": [],
        "review_candidates": [],
        "basis_review_candidates": [],
        "superseded_notes": [],
        "conflict_candidates": [],
        "duplicate_titles": [],
        "static_lint": static_lint_report(),
    }
    canon_title_map: dict[str, list[str]] = {}

    for root, layer in [*[(folder, "wiki") for folder in CANON_FOLDERS], (LITE_WIKI, "wiki_lite")]:
        for path in iter_runtime_notes(root):
            metadata = metadata_for_path(path)
            rel_path = rel_from_root(path)
            missing = missing_metadata_keys(metadata, layer)
            if missing:
                report_key = "canon_missing_metadata" if layer == "wiki" else "lite_missing_metadata"
                report[report_key].append({"path": rel_path, "missing": missing})

            title = title_for_path(path).strip().lower()
            if layer == "wiki":
                canon_title_map.setdefault(title, []).append(rel_path)

            freshness_value = nonempty_metadata_value(metadata, "freshness", nonempty_metadata_value(metadata, "reviewed_at"))
            last_reviewed = nonempty_metadata_value(metadata, "last_reviewed", nonempty_metadata_value(metadata, "reviewed_at"))
            stale_flag = nonempty_metadata_value(metadata, "stale_flag", "false").lower() == "true"
            supersession = nonempty_metadata_value(metadata, "supersession", "none")
            conflict_with = nonempty_metadata_value(metadata, "conflict_with", "none")
            evidence_mode = nonempty_metadata_value(metadata, "evidence_mode", "unknown")
            confidence_basis = nonempty_metadata_value(metadata, "confidence_basis", "unknown")
            source_count_basis = nonempty_metadata_value(metadata, "source_count_basis", "unknown")
            freshness_days = days_since(freshness_value) if freshness_value else None
            review_days = days_since(last_reviewed) if last_reviewed else None

            if stale_flag or (freshness_days is not None and freshness_days > 90):
                report["stale_candidates"].append(
                    {"path": rel_path, "freshness": freshness_value or "unknown", "stale_flag": stale_flag}
                )

            if not is_none_like(supersession):
                report["superseded_notes"].append({"path": rel_path, "supersession": supersession})

            if not is_none_like(conflict_with):
                report["conflict_candidates"].append({"path": rel_path, "conflict_with": conflict_with})

            if layer == "wiki" and (review_days is None or review_days > 30):
                report["review_candidates"].append({"path": rel_path, "last_reviewed": last_reviewed or "unknown"})
            if layer == "wiki_lite" and nonempty_metadata_value(metadata, "status") in {"adopt", "hold"}:
                if review_days is None or review_days > 7:
                    report["review_candidates"].append({"path": rel_path, "last_reviewed": last_reviewed or "unknown"})
            if layer == "wiki":
                basis_reasons: list[str] = []
                if evidence_mode == "trace":
                    basis_reasons.append("evidence_mode=trace")
                if confidence_basis == "conservative_default":
                    basis_reasons.append("confidence_basis=conservative_default")
                if source_count_basis == "trace_only":
                    basis_reasons.append("source_count_basis=trace_only")
                if basis_reasons:
                    report["basis_review_candidates"].append(
                        {
                            "path": rel_path,
                            "reasons": basis_reasons,
                            "evidence_mode": evidence_mode,
                            "confidence_basis": confidence_basis,
                            "source_count_basis": source_count_basis,
                        }
                    )

    for title, paths in sorted(canon_title_map.items()):
        if len(paths) > 1:
            report["duplicate_titles"].append({"title": title, "paths": paths})

    return report


def staleness_report(canon_days: int = 90, lite_days: int = 7, review_days: int = 30) -> dict:
    ensure_dirs()
    report = {
        "generated_at": timestamp(),
        "thresholds": {
            "canon_days": canon_days,
            "lite_days": lite_days,
            "review_days": review_days,
        },
        "forced_stale": [],
        "canon_age_stale": [],
        "lite_review_overdue": [],
        "canon_review_overdue": [],
    }

    for path in iter_canon_notes():
        metadata = metadata_for_path(path)
        rel_path = rel_from_root(path)
        freshness_value = nonempty_metadata_value(metadata, "freshness")
        last_reviewed = nonempty_metadata_value(metadata, "last_reviewed")
        freshness_days = days_since(freshness_value) if freshness_value else None
        review_age = days_since(last_reviewed) if last_reviewed else None
        supersession = nonempty_metadata_value(metadata, "supersession", "none")
        stale_flag = nonempty_metadata_value(metadata, "stale_flag", "false").lower() == "true"

        if stale_flag or not is_none_like(supersession):
            report["forced_stale"].append(
                {"path": rel_path, "stale_flag": stale_flag, "supersession": supersession}
            )
        elif freshness_days is not None and freshness_days > canon_days:
            report["canon_age_stale"].append({"path": rel_path, "age_days": freshness_days})

        if review_age is None or review_age > review_days:
            report["canon_review_overdue"].append({"path": rel_path, "review_age_days": review_age})

    for path in iter_runtime_notes(LITE_WIKI):
        metadata = metadata_for_path(path)
        rel_path = rel_from_root(path)
        status = nonempty_metadata_value(metadata, "status")
        last_reviewed = nonempty_metadata_value(metadata, "reviewed_at")
        review_age = days_since(last_reviewed) if last_reviewed else None
        if status in {"adopt", "hold"} and (review_age is None or review_age > lite_days):
            report["lite_review_overdue"].append({"path": rel_path, "review_age_days": review_age})

    return report


def conflict_report() -> dict:
    ensure_dirs()
    report = {
        "generated_at": timestamp(),
        "explicit_conflicts": [],
        "duplicate_titles": [],
        "divergent_duplicates": [],
        "shared_sources": [],
    }

    title_map: dict[str, list[Path]] = {}
    source_map: dict[str, list[Path]] = {}

    for path in iter_canon_notes():
        metadata = metadata_for_path(path)
        rel_path = rel_from_root(path)
        title = title_for_path(path).strip().lower()
        title_map.setdefault(title, []).append(path)

        promoted_from = nonempty_metadata_value(metadata, "promoted_from")
        if promoted_from:
            source_map.setdefault(promoted_from, []).append(path)

        conflict_with = nonempty_metadata_value(metadata, "conflict_with", "none")
        if not is_none_like(conflict_with):
            conflict_target = ROOT / Path(conflict_with)
            report["explicit_conflicts"].append(
                {
                    "path": rel_path,
                    "conflict_with": conflict_with,
                    "target_exists": conflict_target.exists(),
                }
            )

    for title, paths in sorted(title_map.items()):
        if len(paths) <= 1:
            continue
        rel_paths = [rel_from_root(path) for path in paths]
        report["duplicate_titles"].append({"title": title, "paths": rel_paths})

        signatures = {canon_body_signature(path) for path in paths}
        if len(signatures) > 1:
            report["divergent_duplicates"].append({"title": title, "paths": rel_paths})

    for promoted_from, paths in sorted(source_map.items()):
        if len(paths) > 1:
            report["shared_sources"].append(
                {"promoted_from": promoted_from, "paths": [rel_from_root(path) for path in paths]}
            )

    return report


def mark_conflicts() -> dict:
    report = conflict_report()
    conflict_map: dict[Path, set[str]] = {}

    for item in report["divergent_duplicates"]:
        paths = [ROOT / Path(rel_path) for rel_path in item["paths"]]
        rel_paths = [rel_from_root(path) for path in paths]
        for path in paths:
            others = [rel for rel in rel_paths if rel != rel_from_root(path)]
            if others:
                conflict_map.setdefault(path, set()).update(others)

    for item in report["shared_sources"]:
        paths = [ROOT / Path(rel_path) for rel_path in item["paths"]]
        rel_paths = [rel_from_root(path) for path in paths]
        for path in paths:
            others = [rel for rel in rel_paths if rel != rel_from_root(path)]
            if others:
                conflict_map.setdefault(path, set()).update(others)

    for item in report["explicit_conflicts"]:
        path = ROOT / Path(item["path"])
        conflict_with = item["conflict_with"]
        if not is_none_like(conflict_with):
            target_path = ROOT / Path(conflict_with)
            if target_path.exists():
                conflict_map.setdefault(path, set()).add(rel_from_root(target_path))
                conflict_map.setdefault(target_path, set()).add(rel_from_root(path))

    modified: list[str] = []
    for path, additions in sorted(conflict_map.items(), key=lambda item: str(item[0])):
        metadata = metadata_for_path(path)
        merged = merge_path_values(nonempty_metadata_value(metadata, "conflict_with", "none"), sorted(additions))
        if set_note_metadata(path, {"conflict_with": merged}):
            modified.append(rel_from_root(path))

    return {
        "generated_at": timestamp(),
        "modified": modified,
        "modified_count": len(modified),
        "source_report": report,
    }


def mark_stale() -> dict:
    report = staleness_report()
    candidate_paths: set[Path] = set()

    for item in report["forced_stale"]:
        candidate_paths.add(ROOT / Path(item["path"]))
    for item in report["canon_age_stale"]:
        candidate_paths.add(ROOT / Path(item["path"]))

    modified: list[str] = []
    for path in sorted(candidate_paths):
        metadata = metadata_for_path(path)
        updates = {"stale_flag": "true"}
        freshness_value = nonempty_metadata_value(metadata, "freshness")
        if freshness_value and not nonempty_metadata_value(metadata, "last_reviewed"):
            updates["last_reviewed"] = freshness_value
        if set_note_metadata(path, updates):
            modified.append(rel_from_root(path))

    return {
        "generated_at": timestamp(),
        "modified": modified,
        "modified_count": len(modified),
        "source_report": report,
    }


def build_repair_queue_body_from_bundle(
    conflict: dict[str, object],
    staleness: dict[str, object],
    maintenance: dict[str, object],
) -> str:
    static_lint = maintenance["static_lint"]
    queue_items = repair_queue_entries(conflict, staleness, maintenance)
    high_items = [item for item in queue_items if item["priority"] == "high"]
    medium_items = [item for item in queue_items if item["priority"] == "medium"]
    low_items = [item for item in queue_items if item["priority"] == "low"]
    lines: list[str] = [
        f"# repair-queue-{slug_timestamp()}",
        "",
        f"- generated_at: `{timestamp()}`",
        "- queue_type: `repair-queue`",
        "- source_reports: `conflict + staleness + maintenance`",
        "",
        "## summary",
        f"- total_items: `{len(queue_items)}`",
        f"- high_priority: `{len(high_items)}`",
        f"- medium_priority: `{len(medium_items)}`",
        f"- low_priority: `{len(low_items)}`",
        f"- explicit_conflicts: `{len(conflict['explicit_conflicts'])}`",
        f"- duplicate_titles: `{len(conflict['duplicate_titles'])}`",
        f"- divergent_duplicates: `{len(conflict['divergent_duplicates'])}`",
        f"- shared_sources: `{len(conflict['shared_sources'])}`",
        f"- forced_stale: `{len(staleness['forced_stale'])}`",
        f"- canon_age_stale: `{len(staleness['canon_age_stale'])}`",
        f"- canon_review_overdue: `{len(staleness['canon_review_overdue'])}`",
        f"- lite_review_overdue: `{len(staleness['lite_review_overdue'])}`",
        f"- basis_review_candidates: `{len(maintenance['basis_review_candidates'])}`",
        f"- broken_wikilinks: `{len(static_lint['broken_wikilinks'])}`",
        f"- broken_evidence_refs: `{len(static_lint['broken_evidence_refs'])}`",
        f"- empty_core_sections: `{len(static_lint['empty_core_sections'])}`",
        "",
        "## priority now",
    ]

    if queue_items:
        for item in queue_items[:7]:
            anchor = repair_item_anchor(item)
            lines.extend(
                [
                    f"- priority: `{item['priority']}`",
                    f"  type: `{item['type']}`",
                    f"  anchor: `{anchor}`",
                    f"  why_now: `{item['why_now']}`",
                    f"  action: `{item['action']}`",
                ]
            )
    else:
        lines.append("- no repair items to process")

    lines.extend(["", "## prioritized queue"])

    if queue_items:
        for section_name, section_items in [("high", high_items), ("medium", medium_items), ("low", low_items)]:
            lines.extend(["", f"### {section_name}"])
            if section_items:
                for item in section_items:
                    lines.extend(render_repair_item(item))
            else:
                lines.append(f"- no {section_name} priority items to process")
    else:
        lines.append("- no prioritized queue items to process")

    lines.extend(["", "## conflict queue"])
    if conflict["explicit_conflicts"] or conflict["divergent_duplicates"] or conflict["shared_sources"]:
        for item in conflict["explicit_conflicts"]:
            lines.extend(
                [
                    f"- type: `explicit_conflict`",
                    f"  path: `{item['path']}`",
                    f"  target: `{item['conflict_with']}`",
                    f"  action: `check target existence and decide whether one canon note should remain`",
                ]
            )
        for item in conflict["divergent_duplicates"]:
            lines.extend(
                [
                    f"- type: `divergent_duplicate`",
                    f"  title: `{item['title']}`",
                    f"  paths: `{'; '.join(item['paths'])}`",
                    "  action: `choose a baseline note and decide whether the remaining content should be merged`",
                ]
            )
        for item in conflict["shared_sources"]:
            lines.extend(
                [
                    f"- type: `shared_source`",
                    f"  source: `{item['promoted_from']}`",
                    f"  paths: `{'; '.join(item['paths'])}`",
                    "  action: `review why one source produced multiple canon notes`",
                ]
            )
    else:
        lines.append("- no conflict queue items to process")

    lines.extend(["", "## staleness queue"])
    if staleness["forced_stale"] or staleness["canon_age_stale"] or staleness["canon_review_overdue"] or staleness["lite_review_overdue"]:
        for item in staleness["forced_stale"]:
            lines.extend(
                [
                    "- type: `forced_stale`",
                    f"  path: `{item['path']}`",
                    f"  supersession: `{item['supersession']}`",
                    "  action: `treat the replacement note as baseline and decide whether this note becomes support or archive`",
                ]
            )
        for item in staleness["canon_age_stale"]:
            lines.extend(
                [
                    "- type: `canon_age_stale`",
                    f"  path: `{item['path']}`",
                    f"  age_days: `{item['age_days']}`",
                    "  action: `review freshness and evidence again`",
                ]
            )
        for item in staleness["canon_review_overdue"]:
            lines.extend(
                [
                    "- type: `canon_review_overdue`",
                    f"  path: `{item['path']}`",
                    f"  review_age_days: `{item['review_age_days']}`",
                    "  action: `review canonical note again`",
                ]
            )
        for item in staleness["lite_review_overdue"]:
            lines.extend(
                [
                    "- type: `lite_review_overdue`",
                    f"  path: `{item['path']}`",
                    f"  review_age_days: `{item['review_age_days']}`",
                    "  action: `reclassify as promote, hold, or discard`",
                ]
            )
    else:
        lines.append("- no staleness queue items to process")

    lines.extend(["", "## metadata confidence queue"])
    if maintenance["basis_review_candidates"]:
        for item in maintenance["basis_review_candidates"]:
            lines.extend(
                [
                    "- type: `basis_review`",
                    f"  path: `{item['path']}`",
                    f"  reasons: `{'; '.join(item['reasons'])}`",
                    f"  action: `{basis_action_text(item)}`",
                ]
            )
    else:
        lines.append("- no metadata-confidence queue items to process")

    lines.extend(["", "## static lint queue"])
    if static_lint["broken_wikilinks"] or static_lint["broken_evidence_refs"] or static_lint["empty_core_sections"]:
        for item in static_lint["broken_wikilinks"]:
            lines.extend(
                [
                    "- type: `broken_wikilink`",
                    f"  path: `{item['path']}`",
                    f"  line: `{item['line']}`",
                    f"  target: `{item['target']}`",
                    "  action: `create the wikilink target or align the link title with the real note title`",
                ]
            )
        for item in static_lint["broken_evidence_refs"]:
            lines.extend(
                [
                    "- type: `broken_evidence_ref`",
                    f"  path: `{item['path']}`",
                    f"  target: `{item['reference']}`",
                    "  action: `replace the evidence path with a real source or note path`",
                ]
            )
        for item in static_lint["empty_core_sections"]:
            lines.extend(
                [
                    "- type: `empty_core_section`",
                    f"  path: `{item['path']}`",
                    f"  section: `{item['section']}`",
                    "  action: `fill the core section or decide whether the note should remain`",
                ]
            )
    else:
        lines.append("- no static-lint queue items to process")

    lines.extend(
        [
            "",
            "## next step",
            "- decide whether `mark_conflicts.ps1` or `mark_stale.ps1` should run.",
            "- read only queued items and then resolve canon refresh or supersession cleanup.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def build_repair_queue_body() -> str:
    bundle = build_runtime_lint_bundle()
    return build_repair_queue_body_from_bundle(
        bundle["conflict"],
        bundle["staleness"],
        bundle["maintenance"],
    )


def generate_repair_queue(bundle: dict[str, object] | None = None) -> dict:
    ensure_dirs()
    if bundle is None:
        bundle = build_runtime_lint_bundle()
    cache_key = fingerprint_payload(bundle)
    cached = read_cached_report(REPAIR_QUEUE_REPORT_CACHE, cache_key)
    if cached is not None:
        return cached
    report_path = REPORTS_ROOT / f"repair_queue_{slug_timestamp()}.md"
    report_path.write_text(
        build_repair_queue_body_from_bundle(
            bundle["conflict"],
            bundle["staleness"],
            bundle["maintenance"],
        ),
        encoding="utf-8",
    )
    payload = {
        "generated_at": timestamp(),
        "report_path": str(report_path),
    }
    write_cached_report(REPAIR_QUEUE_REPORT_CACHE, cache_key, payload)
    return payload


def build_canon_body(source: Path, kind: str, final_name: str, original: str) -> str:
    source_title, source_metadata, sections = parse_note(original)
    final_title = Path(final_name).stem or source_title
    canon_lines = normalize_bullets(sections.get("distilled", []))
    reusable_lines = normalize_bullets(sections.get("reusable rule", []))
    evidence_lines = normalize_bullets(sections.get("evidence", []))
    evidence_value, evidence_mode = infer_evidence_bundle(source, source_metadata, evidence_lines)
    evidence_refs = collect_evidence_refs(source, source_metadata, evidence_lines)
    source_count_value, source_count_basis = infer_source_count_bundle(source_metadata, evidence_refs)
    confidence_value, confidence_basis = infer_confidence_bundle(source_metadata, source_count_value)
    supersession_value = infer_supersession(source_metadata)

    canon_body: list[str] = [
        f"# {final_title}",
        "",
        f"- promoted_from: `{rel_from_root(source)}`",
        f"- promoted_at: `{timestamp()}`",
        f"- claim_state: `{infer_claim_state(source_metadata)}`",
        f"- evidence: `{evidence_value}`",
        f"- evidence_mode: `{evidence_mode}`",
        f"- freshness: `{infer_freshness(source_metadata)}`",
        f"- confidence: `{confidence_value}`",
        f"- confidence_basis: `{confidence_basis}`",
        f"- scope: `{infer_scope(source_metadata)}`",
        f"- supersession: `{supersession_value}`",
        f"- stale_flag: `{infer_stale_flag(source_metadata)}`",
        f"- conflict_with: `{infer_conflict_with(source_metadata)}`",
        f"- source_count: `{source_count_value}`",
        f"- source_count_basis: `{source_count_basis}`",
        f"- last_reviewed: `{infer_last_reviewed(source_metadata)}`",
        f"- temporal_state: `{infer_temporal_state(source_metadata)}`",
        f"- canon_kind: `{kind}`",
        "",
        "## canon",
    ]

    if canon_lines:
        canon_body.extend(canon_lines)
    else:
        canon_body.append("- canon content is derived from the source note.")

    if reusable_lines:
        canon_body.extend(["", "### reusable rule", *reusable_lines])

    canon_body.extend(
        [
            "",
            "## evidence",
            f"- evidence: `{evidence_value}`",
            f"- evidence_mode: `{evidence_mode}`",
            f"- built_from: `{source_metadata.get('built_from', rel_from_root(source))}`",
            f"- source_status: `{source_metadata.get('status', 'unknown')}`",
            f"- source_surface: `{source_metadata.get('surface', 'unknown')}`",
            f"- source_reviewed_at: `{source_metadata.get('reviewed_at', 'unknown')}`",
            f"- source_count_basis: `{source_count_basis}`",
            f"- confidence_basis: `{confidence_basis}`",
            "",
            "## supersession",
            f"- {supersession_value}",
            "",
        ]
    )
    if evidence_lines:
        evidence_insert_at = canon_body.index("## supersession")
        canon_body[evidence_insert_at:evidence_insert_at] = evidence_lines + [""]
    return "\n".join(canon_body)


def update_index(kind: str, target: Path) -> None:
    sections: list[tuple[str, list[str]]] = []
    current_header: str | None = None
    current_lines: list[str] = []
    existing_lines = WIKI_INDEX.read_text(encoding="utf-8").splitlines() if WIKI_INDEX.exists() else []

    def flush() -> None:
        nonlocal current_header, current_lines
        if current_header is not None:
            sections.append((current_header, current_lines))

    for line in existing_lines:
        if line.startswith("## "):
            flush()
            current_header = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    flush()

    section_map = {header: lines[:] for header, lines in sections}
    for header in ["topics", "entities", "concepts", "syntheses"]:
        section_map.setdefault(header, [])

    entry = f"- `{kind}`: [{target.name}]({rel_from(target, WIKI_ROOT)})"
    filtered = [line for line in section_map[kind] if f"[{target.name}](" not in line]
    filtered.append(entry)
    filtered = sorted({line for line in filtered if line.strip()})
    section_map[kind] = filtered

    output: list[str] = ["# index", ""]
    for header in ["topics", "entities", "concepts", "syntheses"]:
        output.append(f"## {header}")
        output.extend(section_map[header])
        output.append("")
    WIKI_INDEX.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def promote(source_name: str, kind: str, target_name: str | None) -> Path:
    ensure_dirs()
    source = find_lite_note(source_name)
    assessment = promotion_assessment(source, kind, target_name)
    if assessment["decision"] != "ready":
        reasons = "; ".join(str(item) for item in assessment["blockers"]) or assessment["recommendation"]
        raise SystemExit(f"promotion blocked: {reasons}")
    canon_dir = resolve_canon_folder(kind)
    final_name = target_name or source.name
    if not final_name.endswith(".md"):
        final_name = f"{final_name}.md"
    target = canon_dir / final_name
    original = source.read_text(encoding="utf-8")
    target.write_text(build_canon_body(source, kind, final_name, original), encoding="utf-8")
    update_index(kind, target)
    append_if_missing(WIKI_LOG, f"- `{timestamp()}` promoted `{source.name}` -> `{rel_from_root(target)}`")
    return target


def promote_with_gate(source_name: str, kind: str, target_name: str | None, force: bool = False) -> dict[str, object]:
    ensure_dirs()
    source = find_lite_note(source_name)
    assessment = promotion_assessment(source, kind, target_name)
    if assessment["decision"] != "ready" and not force:
        return {
            "ok": False,
            "forced": False,
            "assessment": assessment,
            "message": "promotion blocked by gate",
        }
    if any("target already exists:" in str(item) for item in assessment["blockers"]):
        return {
            "ok": False,
            "forced": force,
            "assessment": assessment,
            "message": "target already exists; choose a new target name or update existing canon manually",
        }
    target = promote(source_name, kind, target_name) if assessment["decision"] == "ready" else _force_promote(source, kind, target_name)
    return {
        "ok": True,
        "forced": force and assessment["decision"] != "ready",
        "assessment": assessment,
        "target": str(target),
    }


def _force_promote(source: Path, kind: str, target_name: str | None) -> Path:
    canon_dir = resolve_canon_folder(kind)
    final_name = target_name or source.name
    if not final_name.endswith(".md"):
        final_name = f"{final_name}.md"
    target = canon_dir / final_name
    original = source.read_text(encoding="utf-8")
    target.write_text(build_canon_body(source, kind, final_name, original), encoding="utf-8")
    update_index(kind, target)
    append_if_missing(WIKI_LOG, f"- `{timestamp()}` force-promoted `{source.name}` -> `{rel_from_root(target)}`")
    return target


def status_payload() -> dict:
    retrieval_script = resolve_retrieval_script()
    archive = archive_advisory()
    locks = lock_status()
    archive_candidate_count = archive["candidate_count"]
    archive_candidate_by_type = archive.get("candidate_family_counts", {})
    kept_in_reports_count = archive.get("root_retained_count", 0)
    kept_in_reports_by_type = archive.get("root_retained_family_counts", {})
    cleanup_recommended_now = archive["should_archive"]
    cleanup_threshold = archive["threshold"]
    return {
        "root": str(ROOT),
        "state_root": str(STATE_ROOT),
        "wiki_markdown_count": count_markdown_files(WIKI_ROOT),
        "wiki_lite_markdown_count": count_markdown_files(LITE_ROOT),
        "hot_db_exists": HOT_DB.exists(),
        "cold_db_exists": COLD_DB.exists(),
        "hot_db_mtime": datetime.fromtimestamp(HOT_DB.stat().st_mtime).isoformat() if HOT_DB.exists() else None,
        "cold_db_mtime": datetime.fromtimestamp(COLD_DB.stat().st_mtime).isoformat() if COLD_DB.exists() else None,
        "hot_build_root": str(current_hot_build_root()) if current_hot_build_root() else None,
        "cold_build_root": str(current_cold_build_root()) if current_cold_build_root() else None,
        "retrieval_script": str(retrieval_script) if retrieval_script else None,
        "retrieval_script_candidates": [str(path) for path in candidate_retrieval_paths()],
        "retrieval_script_exists": retrieval_script is not None,
        "maintenance_report_available": True,
        "maintenance_autorun_state_exists": MAINTENANCE_AUTORUN_STATE.exists(),
        "autopilot_lock_exists": AUTOPILOT_LOCK.exists(),
        "compile_state_cache_exists": COMPILE_STATE_CACHE.exists(),
        "lint_bundle_cache_exists": LINT_BUNDLE_CACHE.exists(),
        "promotion_entries_cache_exists": PROMOTION_ENTRIES_CACHE.exists(),
        "update_entries_cache_exists": UPDATE_ENTRIES_CACHE.exists(),
        "repair_queue_report_cache_exists": REPAIR_QUEUE_REPORT_CACHE.exists(),
        "promotion_queue_report_cache_exists": PROMOTION_QUEUE_REPORT_CACHE.exists(),
        "update_queue_report_cache_exists": UPDATE_QUEUE_REPORT_CACHE.exists(),
        "governance_cycle_cache_exists": GOVERNANCE_CYCLE_CACHE.exists(),
        "archive_candidate_count": archive_candidate_count,
        "archive_candidate_family_counts": archive_candidate_by_type,
        "archive_root_retained_count": kept_in_reports_count,
        "archive_root_retained_family_counts": kept_in_reports_by_type,
        "archive_should_run": cleanup_recommended_now,
        "archive_threshold": cleanup_threshold,
        "cleanup_candidates_now": archive_candidate_count,
        "cleanup_candidates_by_type": archive_candidate_by_type,
        "kept_in_reports_now": kept_in_reports_count,
        "kept_in_reports_by_type": kept_in_reports_by_type,
        "cleanup_recommended_now": cleanup_recommended_now,
        "cleanup_threshold": cleanup_threshold,
        "lock_running_count": locks["running_count"],
        "lock_stale_count": locks["stale_count"],
        "locks": locks["locks"],
    }


def workflow_ingest() -> dict:
    ensure_dirs()
    ingest_result = ingest_raw_notes()
    raw_count = count_markdown_files(LITE_RAW)
    lite_count = count_markdown_files(LITE_WIKI)
    return {
        "workflow": "ingest",
        "generated_at": timestamp(),
        "raw_inbox": str(LITE_RAW),
        "lite_workspace": str(LITE_WIKI),
        "canon_workspace": str(WIKI_ROOT),
        "raw_count": raw_count,
        "lite_count": lite_count,
        "processed_count": ingest_result["processed_count"],
        "skipped_count": ingest_result["skipped_count"],
        "processed": ingest_result["processed"],
        "skipped": ingest_result["skipped"],
        "next_step": "review generated lite notes, then run compile",
    }


def workflow_compile() -> dict:
    ensure_dirs()
    hot_snapshot = hot_compile_input_snapshot()
    cold_snapshot = cold_compile_input_snapshot()
    cached = read_state(COMPILE_STATE_CACHE)
    hot_cached = (
        cached.get("version") == COMPILE_STATE_CACHE_VERSION
        and cached.get("hot_snapshot") == hot_snapshot
        and hot_compile_artifacts_ready()
    )
    cold_cached = (
        cached.get("version") == COMPILE_STATE_CACHE_VERSION
        and cached.get("cold_snapshot") == cold_snapshot
        and cold_compile_artifacts_ready()
    )

    if hot_cached:
        hot_root = current_hot_build_root()
    else:
        hot_root = prepare_hot_build_root()
        build_index(hot_root, HOT_DB)

    if cold_cached:
        cold_root = current_cold_build_root()
    else:
        cold_root = prepare_cold_build_root()
        build_index(cold_root, COLD_DB)

    write_state(
        COMPILE_STATE_CACHE,
        {
            "version": COMPILE_STATE_CACHE_VERSION,
            "hot_snapshot": hot_snapshot,
            "cold_snapshot": cold_snapshot,
            "hot_root": str(hot_root),
            "cold_root": str(cold_root),
            "updated_at": timestamp(),
        },
    )
    bundle = build_runtime_lint_bundle()
    return {
        "workflow": "compile",
        "generated_at": timestamp(),
        "built": [str(HOT_DB), str(COLD_DB)],
        "hot_root": str(hot_root),
        "cold_root": str(cold_root),
        "maintenance_snapshot": bundle["maintenance"],
        "compile_meta": {
            "hot_source": "cache" if hot_cached else "fresh",
            "cold_source": "cache" if cold_cached else "fresh",
            "hot_snapshot": hot_snapshot,
            "cold_snapshot": cold_snapshot,
        },
    }


def build_runtime_lint_bundle() -> dict[str, object]:
    snapshot = lint_input_snapshot()
    cached = read_state(LINT_BUNDLE_CACHE)
    if cached.get("snapshot") == snapshot and isinstance(cached.get("bundle"), dict):
        bundle = dict(cached["bundle"])
        bundle["cache_meta"] = {
            "source": "cache",
            "snapshot": snapshot,
        }
        return bundle

    maintenance = maintenance_report()
    bundle = {
        "maintenance": maintenance,
        "conflict": conflict_report(),
        "staleness": staleness_report(),
        "static_lint": maintenance["static_lint"],
        "cache_meta": {
            "source": "fresh",
            "snapshot": snapshot,
        },
    }
    write_state(
        LINT_BUNDLE_CACHE,
        {
            "version": LINT_BUNDLE_CACHE_VERSION,
            "snapshot": snapshot,
            "bundle": {key: value for key, value in bundle.items() if key != "cache_meta"},
            "updated_at": timestamp(),
        },
    )
    return bundle


def workflow_lint() -> dict:
    ensure_dirs()
    bundle = build_runtime_lint_bundle()
    return {
        "workflow": "lint",
        "generated_at": timestamp(),
        **bundle,
    }


def workflow_repair() -> dict:
    ensure_dirs()
    bundle = build_runtime_lint_bundle()
    queue = generate_repair_queue(bundle)
    return {
        "workflow": "repair",
        "generated_at": timestamp(),
        **bundle,
        "repair_queue": queue,
    }


def workflow_promotion() -> dict:
    ensure_dirs()
    entries = build_promotion_queue_entries()
    queue = generate_promotion_queue(entries)
    return {
        "workflow": "promotion",
        "generated_at": timestamp(),
        "ready_count": int_or_zero(queue.get("ready_count")),
        "review_count": int_or_zero(queue.get("review_count")),
        "blocked_count": int_or_zero(queue.get("blocked_count")),
        "promotion_queue": queue,
    }


def workflow_update() -> dict:
    ensure_dirs()
    entries = build_update_queue_entries()
    queue = generate_update_queue(entries)
    return {
        "workflow": "update",
        "generated_at": timestamp(),
        "refresh_existing_count": int_or_zero(queue.get("refresh_existing_count")),
        "review_merge_count": int_or_zero(queue.get("review_merge_count")),
        "update_queue": queue,
    }


def workflow_governance() -> dict:
    ensure_dirs()
    cycle = generate_governance_cycle()
    return {
        "workflow": "governance",
        "generated_at": timestamp(),
        "promotion_ready_count": int_or_zero(cycle.get("ready_count")),
        "promotion_review_count": int_or_zero(cycle.get("review_count")),
        "update_refresh_count": int_or_zero(cycle.get("refresh_existing_count")),
        "update_merge_count": int_or_zero(cycle.get("review_merge_count")),
        "governance_cycle": cycle,
    }


def lint_payload_is_clean(payload: dict[str, object]) -> bool:
    maintenance = payload.get("maintenance", {})
    conflict = payload.get("conflict", {})
    staleness = payload.get("staleness", {})
    static_lint = payload.get("static_lint", {})
    return (
        not any(maintenance.get(key, []) for key in ["canon_missing_metadata", "lite_missing_metadata", "stale_candidates", "review_candidates", "basis_review_candidates", "superseded_notes", "conflict_candidates", "duplicate_titles"])
        and not any(conflict.get(key, []) for key in ["explicit_conflicts", "duplicate_titles", "divergent_duplicates", "shared_sources"])
        and not any(staleness.get(key, []) for key in ["forced_stale", "canon_age_stale", "lite_review_overdue", "canon_review_overdue"])
        and not any(static_lint.get(key, []) for key in ["broken_wikilinks", "broken_evidence_refs", "empty_core_sections"])
    )


def build_query_residue_note(question: str, payload: dict[str, object]) -> str:
    hits = payload.get("hits", [])
    created_at = current_date()
    built_from = f"query://{slugify_text(question)}"
    top_hit_paths = [str(hit.get("path")) for hit in hits[:3] if hit.get("path")]
    canon_hits = [hit for hit in hits if hit.get("layer") == "wiki"]
    lite_hits = [hit for hit in hits if hit.get("layer") == "wiki_lite"]
    top_summary = top_hit_paths[0] if top_hit_paths else "no-hit"

    distilled_lines = [
        f"- question: `{question}`",
        f"- top retrieval count: `{len(hits)}`",
        f"- first candidate to read: `{top_summary}`",
    ]
    if canon_hits:
        distilled_lines.append(f"- there are `{len(canon_hits)}` canon hits, so you can read the canon layer first.")
    if lite_hits:
        distilled_lines.append(f"- there are `{len(lite_hits)}` recent lite hits, so you can compare against recent work signals.")
    if not hits:
        distilled_lines.append("- retrieval returned no hits, so query wording or corpus state should be checked.")

    reusable_lines = [
        "- if the same question repeats, check whether top hits and policy reasons stay stable.",
        "- if canon hits and lite hits both appear, read canon and recent layers separately.",
    ]
    next_action = [
        "- if needed, turn this residue into an explanatory note or a separate canon candidate.",
    ]
    evidence = [f"- `{path}`" for path in top_hit_paths] or ["- no evidence listed"]

    lines = [
        f"# query-residue-{slugify_text(question)}",
        "",
        f"- built_from: `{built_from}`",
        "- status: `hold`",
        "- surface: `memory`",
        f"- reviewed_at: `{created_at}`",
        "- claim_state: `unknown`",
        f"- freshness: `{created_at}`",
        "- confidence: `low`",
        "- scope: `query residue`",
        f"- source_count: `{max(len(top_hit_paths), 1)}`",
        "",
        "## distilled",
        *distilled_lines,
        "",
        "## reusable rule",
        *reusable_lines,
        "",
        "## next action",
        *next_action,
        "",
        "## evidence",
        *evidence,
    ]
    return "\n".join(lines).rstrip() + "\n"


def save_query_residue(question: str, payload: dict[str, object]) -> dict[str, object]:
    ensure_dirs()
    stem = f"query-residue-{slugify_text(question)}.md"
    target = unique_target_path(LITE_QUERY_RESIDUE, sanitize_filename(stem))
    target.write_text(build_query_residue_note(question, payload), encoding="utf-8")
    hot_root = prepare_hot_build_root()
    build_index(hot_root, HOT_DB)
    append_if_missing(
        WIKI_LOG,
        f"- `{timestamp()}` saved query residue `{rel_from_root(target)}` from `{question}`",
    )
    return {
        "ok": True,
        "saved_to": str(target),
        "relative_path": rel_from_root(target),
        "hot_root": str(hot_root),
        "hot_db": str(HOT_DB),
    }


def is_query_residue_note(path: Path) -> bool:
    try:
        path.relative_to(LITE_QUERY_RESIDUE)
        return True
    except ValueError:
        pass
    metadata = metadata_for_path(path)
    built_from = nonempty_metadata_value(metadata, "built_from")
    return built_from.startswith("query://")


def content_fingerprint(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def snapshot_rows(paths: list[Path], version: str) -> list[str]:
    rows: list[str] = [version]
    for path in sorted(paths):
        rows.append(f"{rel_from_root(path)}|{content_fingerprint(path.read_text(encoding='utf-8'))}")
    return rows


def queue_note_snapshot_text(path: Path) -> str:
    title, metadata, sections = load_note(path)
    if path.is_relative_to(WIKI_ROOT):
        lines = [f"title={title.strip()}"]
        for key in [
            "promoted_from",
            "claim_state",
            "evidence",
            "evidence_mode",
            "freshness",
            "confidence",
            "confidence_basis",
            "scope",
            "source_count",
            "source_count_basis",
        ]:
            lines.append(f"{key}={metadata.get(key, '').strip()}")
        lines.append("[canon]")
        lines.extend(normalize_bullets(sections.get("canon", [])))
        return "\n".join(lines)

    evidence_lines = normalize_bullets(sections.get("evidence", []))
    evidence_value, evidence_mode = infer_evidence_bundle(path, metadata, evidence_lines)
    evidence_refs = collect_evidence_refs(path, metadata, evidence_lines)
    source_count_value, source_count_basis = infer_source_count_bundle(metadata, evidence_refs)
    confidence_value, confidence_basis = infer_confidence_bundle(metadata, source_count_value)
    freshness_value = infer_freshness(metadata)
    scope_value = infer_scope(metadata)
    kind, _ = recommended_canon_kind(path)

    lines = [
        f"title={title.strip()}",
        f"recommended_kind={kind}",
        f"status={normalize_status(nonempty_metadata_value(metadata, 'status', 'hold'))}",
        f"claim_state={nonempty_metadata_value(metadata, 'claim_state', 'unknown')}",
        f"confidence={nonempty_metadata_value(metadata, 'confidence', 'low')}",
        f"effective_confidence={confidence_value}",
        f"confidence_basis={confidence_basis}",
        f"freshness={freshness_value}",
        f"scope={nonempty_metadata_value(metadata, 'scope', 'unspecified')}",
        f"effective_scope={scope_value}",
        f"source_count={nonempty_metadata_value(metadata, 'source_count', '0')}",
        f"effective_source_count={source_count_value}",
        f"source_count_basis={source_count_basis}",
        f"surface={nonempty_metadata_value(metadata, 'surface', 'coordination')}",
        f"built_from={nonempty_metadata_value(metadata, 'built_from')}",
        f"evidence={evidence_value}",
        f"evidence_mode={evidence_mode}",
    ]
    for key in ["distilled", "reusable rule", "evidence"]:
        lines.append(f"[{key}]")
        lines.extend(normalize_bullets(sections.get(key, [])))
    return "\n".join(lines)


def lint_note_snapshot_text(path: Path) -> str:
    title, metadata, sections = load_note(path)
    layer = "wiki" if path.is_relative_to(WIKI_ROOT) else "wiki_lite"
    lines = [
        f"title={title.strip()}",
        f"layer={layer}",
    ]
    for key in required_keys_for_layer(layer):
        lines.append(f"{key}_present={'true' if metadata.get(key, '').strip() else 'false'}")

    aliases = build_page_alias_set()
    broken_wikilinks: list[str] = []
    for link in extract_wikilinks(path):
        target = str(link["target"]).strip()
        if target.lower() not in aliases:
            broken_wikilinks.append(f"{int(link['line'])}:{target}")
    if broken_wikilinks:
        lines.append("[broken_wikilinks]")
        lines.extend(sorted(set(broken_wikilinks)))

    evidence_lines = normalize_bullets(sections.get("evidence", []))
    refs = sorted(set(collect_evidence_refs(path, metadata, evidence_lines)))
    checked_refs: list[str] = []
    broken_refs: list[str] = []
    for ref in refs:
        if not looks_like_reference(ref):
            continue
        checked_refs.append(ref)
        if resolve_reference_path(ref) is None:
            broken_refs.append(ref)

    built_from = nonempty_metadata_value(metadata, "built_from")
    if built_from and looks_like_reference(built_from):
        if built_from not in checked_refs and resolve_reference_path(built_from) is None:
            broken_refs.append(built_from)
    if broken_refs:
        lines.append("[broken_evidence_refs]")
        lines.extend(sorted(set(broken_refs)))

    if layer == "wiki_lite":
        distilled = normalize_bullets(sections.get("distilled", []))
        reusable = normalize_bullets(sections.get("reusable rule", []))
        status = normalize_status(nonempty_metadata_value(metadata, "status", "hold"))
        last_reviewed = nonempty_metadata_value(metadata, "last_reviewed", nonempty_metadata_value(metadata, "reviewed_at"))
        review_days = days_since(last_reviewed) if last_reviewed else None
        review_due = status in {"adopt", "hold"} and (review_days is None or review_days > 7)
        lines.extend(
            [
                f"status={status}",
                f"review_due={'true' if review_due else 'false'}",
                f"distilled_present={'true' if distilled else 'false'}",
                f"reusable_rule_present={'true' if reusable else 'false'}",
            ]
        )
        return "\n".join(lines)

    canon_lines = normalize_bullets(sections.get("canon", []))
    freshness_value = nonempty_metadata_value(metadata, "freshness")
    last_reviewed = nonempty_metadata_value(metadata, "last_reviewed")
    stale_flag = nonempty_metadata_value(metadata, "stale_flag", "false").lower()
    supersession = nonempty_metadata_value(metadata, "supersession", "none")
    conflict_with = nonempty_metadata_value(metadata, "conflict_with", "none")
    evidence_mode = nonempty_metadata_value(metadata, "evidence_mode", "unknown")
    confidence_basis = nonempty_metadata_value(metadata, "confidence_basis", "unknown")
    source_count_basis = nonempty_metadata_value(metadata, "source_count_basis", "unknown")
    freshness_days = days_since(freshness_value) if freshness_value else None
    review_days = days_since(last_reviewed) if last_reviewed else None
    stale_candidate = stale_flag == "true" or not is_none_like(supersession) or (freshness_days is not None and freshness_days > 90)
    review_due = review_days is None or review_days > 30
    basis_review = evidence_mode == "trace" or confidence_basis == "conservative_default" or source_count_basis == "trace_only"
    lines.extend(
        [
            f"promoted_from={nonempty_metadata_value(metadata, 'promoted_from')}",
            f"stale_candidate={'true' if stale_candidate else 'false'}",
            f"review_due={'true' if review_due else 'false'}",
            f"supersession={supersession}",
            f"conflict_with={conflict_with}",
            f"basis_review={'true' if basis_review else 'false'}",
            f"canon_present={'true' if canon_lines else 'false'}",
        ]
    )
    lines.append("[canon]")
    lines.extend(canon_lines)
    return "\n".join(lines)


def lint_input_snapshot() -> str:
    rows: list[str] = [LINT_BUNDLE_CACHE_VERSION, current_date()]
    for path in sorted(iter_all_runtime_notes()):
        rows.append(f"{rel_from_root(path)}|{file_content_signature(path)}")
    return hashlib.sha1("\n".join(rows).encode("utf-8")).hexdigest()


def queue_input_snapshot() -> str:
    paths: list[Path] = []
    for path in iter_runtime_notes(LITE_WIKI):
        if is_query_residue_note(path):
            continue
        paths.append(path)
    for folder in CANON_FOLDERS:
        paths.extend(iter_runtime_notes(folder))
    rows: list[str] = [QUEUE_ENTRIES_CACHE_VERSION]
    for path in sorted(paths):
        rows.append(f"{rel_from_root(path)}|{file_content_signature(path)}")
    return hashlib.sha1("\n".join(rows).encode("utf-8")).hexdigest()


def governance_input_snapshot() -> str:
    raw = "\n".join(
        [
            GOVERNANCE_CYCLE_CACHE_VERSION,
            lint_input_snapshot(),
            queue_input_snapshot(),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def hot_compile_input_snapshot() -> str:
    rows: list[str] = [COMPILE_STATE_CACHE_VERSION, "hot"]
    for path in sorted(LITE_WIKI.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        stat = path.stat()
        rows.append(f"{rel_from_root(path)}|{stat.st_size}|{stat.st_mtime_ns}")
    return hashlib.sha1("\n".join(rows).encode("utf-8")).hexdigest()


def cold_compile_input_snapshot() -> str:
    rows: list[str] = [COMPILE_STATE_CACHE_VERSION, "cold"]
    for folder in CANON_FOLDERS:
        for path in sorted(folder.rglob("*.md")):
            if path.name.lower() == "readme.md":
                continue
            stat = path.stat()
            rows.append(f"{rel_from_root(path)}|{stat.st_size}|{stat.st_mtime_ns}")
    return hashlib.sha1("\n".join(rows).encode("utf-8")).hexdigest()


def read_cached_entries(cache_path: Path, snapshot: str) -> list[dict[str, object]] | None:
    cached = read_state(cache_path)
    if cached.get("version") != QUEUE_ENTRIES_CACHE_VERSION:
        return None
    if cached.get("snapshot") != snapshot:
        return None
    entries = cached.get("entries")
    if not isinstance(entries, list):
        return None
    return entries


def write_cached_entries(cache_path: Path, snapshot: str, entries: list[dict[str, object]]) -> None:
    write_state(
        cache_path,
        {
            "version": QUEUE_ENTRIES_CACHE_VERSION,
            "snapshot": snapshot,
            "entries": entries,
            "updated_at": timestamp(),
        },
    )


def read_cached_report(cache_path: Path, cache_key: str) -> dict[str, object] | None:
    cached = read_state(cache_path)
    if cached.get("version") != REPORT_CACHE_VERSION:
        return None
    if cached.get("cache_key") != cache_key:
        return None
    payload = cached.get("payload")
    if not isinstance(payload, dict):
        return None
    report_path = payload.get("report_path")
    if not isinstance(report_path, str) or not Path(report_path).exists():
        return None
    return payload


def write_cached_report(cache_path: Path, cache_key: str, payload: dict[str, object]) -> None:
    write_state(
        cache_path,
        {
            "version": REPORT_CACHE_VERSION,
            "cache_key": cache_key,
            "payload": payload,
            "updated_at": timestamp(),
        },
    )


def report_link_line(path_value: str, label: str) -> str:
    path = Path(path_value)
    return f"- {label}: [{path.name}]({path.name})"


def governance_generated_date(payload: dict[str, object]) -> str:
    generated_at = str(payload.get("generated_at", "")).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", generated_at[:10]):
        return generated_at[:10]
    return current_date()


def governance_daily_path(payload: dict[str, object]) -> Path:
    day = governance_generated_date(payload).replace("-", "")
    return REPORTS_ROOT / f"governance_daily_{day}.md"


def sync_daily_header(path: Path, title: str, day: str) -> str:
    header_lines = [
        f"# {title}-{day}",
        "",
        f"- day: `{day}`",
        "",
    ]
    header_text = "\n".join(header_lines).rstrip() + "\n"
    if not path.exists():
        path.write_text(header_text, encoding="utf-8")
        return header_text

    text = path.read_text(encoding="utf-8").replace("\r", "")
    lines = [line.rstrip() for line in text.splitlines()]
    first_section_index = next((index for index, line in enumerate(lines) if line.startswith("## ")), None)
    tail_lines = lines[first_section_index:] if first_section_index is not None else []
    rebuilt = header_text
    if tail_lines:
        rebuilt += "\n" + "\n".join(tail_lines).strip() + "\n"
    if text != rebuilt:
        path.write_text(rebuilt, encoding="utf-8")
    return rebuilt


def upsert_daily_entry_text(daily_text: str, marker_line: str, entry_lines: list[str]) -> str:
    lines = [line.rstrip() for line in daily_text.replace("\r", "").splitlines()]
    entry_block = "\n".join(entry_lines).rstrip()
    first_section_index = next((index for index, line in enumerate(lines) if line.startswith("## ")), len(lines))
    header_lines = lines[:first_section_index]
    sections: list[list[str]] = []
    current: list[str] = []
    for line in lines[first_section_index:]:
        if line.startswith("## "):
            if current:
                sections.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        sections.append(current)

    replaced = False
    normalized_sections: list[str] = []
    for section in sections:
        if any(line == marker_line for line in section):
            normalized_sections.append(entry_block)
            replaced = True
        else:
            normalized_sections.append("\n".join(section).rstrip())

    body_parts = [part for part in ["\n".join(header_lines).rstrip(), *normalized_sections] if part]
    if not replaced:
        body_parts.append(entry_block)
    return "\n\n".join(body_parts).rstrip() + "\n"


def build_governance_latest_body(payload: dict[str, object], report_paths: dict[str, str]) -> str:
    archive = payload.get("archive_advisory", {})
    last_cycle_at = payload.get("cycle_generated_at", payload.get("generated_at", "unknown"))
    candidate_family_counts = archive.get("candidate_family_counts", {})
    retained_family_counts = archive.get("root_retained_family_counts", {})
    candidate_family_summary = ", ".join(
        f"{key}={value}" for key, value in sorted(candidate_family_counts.items())
    ) if isinstance(candidate_family_counts, dict) and candidate_family_counts else "none"
    retained_family_summary = ", ".join(
        f"{key}={value}" for key, value in sorted(retained_family_counts.items())
    ) if isinstance(retained_family_counts, dict) and retained_family_counts else "none"
    lines = [
        "# governance-latest",
        "",
        f"- refreshed_at: `{timestamp()}`",
        f"- last_cycle_at: `{last_cycle_at}`",
        "- how_to_read: `latest governance-cycle record`",
        f"- daily_summary: [{governance_daily_path(payload).name}]({governance_daily_path(payload).name})",
        "",
        "## latest reports",
        report_link_line(str(payload.get("report_path", "")), "governance"),
        report_link_line(str(report_paths.get("repair", "")), "repair_queue"),
        report_link_line(str(report_paths.get("promotion", "")), "promotion_queue"),
        report_link_line(str(report_paths.get("update", "")), "update_queue"),
        "",
        "## current state",
        f"- maintenance_clean: `{payload.get('maintenance_clean', 'unknown')}`",
        f"- conflict_clean: `{payload.get('conflict_clean', 'unknown')}`",
        f"- staleness_clean: `{payload.get('staleness_clean', 'unknown')}`",
        f"- static_lint_clean: `{payload.get('static_lint_clean', 'unknown')}`",
        "",
        "## queue summary",
        f"- promotion_ready: `{payload.get('ready_count', 0)}`",
        f"- promotion_review: `{payload.get('review_count', 0)}`",
        f"- promotion_blocked: `{payload.get('blocked_count', 0)}`",
        f"- update_refresh_existing: `{payload.get('refresh_existing_count', 0)}`",
        f"- update_review_merge: `{payload.get('review_merge_count', 0)}`",
        f"- broken_wikilinks: `{payload.get('broken_wikilinks', 0)}`",
        f"- broken_evidence_refs: `{payload.get('broken_evidence_refs', 0)}`",
        f"- empty_core_sections: `{payload.get('empty_core_sections', 0)}`",
        "",
        "## archive advisory",
        "- archive_basis: `latest governance-cycle timestamp`",
        f"- candidate_count: `{archive.get('candidate_count', 0)}`",
        f"- candidate_by_type: `{candidate_family_summary}`",
        f"- kept_in_reports: `{retained_family_summary}`",
        f"- threshold: `{archive.get('threshold', 0)}`",
        f"- should_archive: `{archive.get('should_archive', False)}`",
        "",
    ]
    return "\n".join(lines)


def build_governance_daily_entry(payload: dict[str, object], report_paths: dict[str, str]) -> list[str]:
    governance_name = Path(str(payload.get("report_path", ""))).name
    return [
        f"## {payload.get('generated_at', 'unknown')}",
        f"- governance: [{governance_name}]({governance_name})",
        f"- repair_queue: [{Path(str(report_paths.get('repair', ''))).name}]({Path(str(report_paths.get('repair', ''))).name})",
        f"- promotion_queue: [{Path(str(report_paths.get('promotion', ''))).name}]({Path(str(report_paths.get('promotion', ''))).name})",
        f"- update_queue: [{Path(str(report_paths.get('update', ''))).name}]({Path(str(report_paths.get('update', ''))).name})",
        f"- maintenance_clean: `{payload.get('maintenance_clean', 'unknown')}` / static_lint_clean: `{payload.get('static_lint_clean', 'unknown')}`",
        f"- ready/review/blocked: `{payload.get('ready_count', 0)}/{payload.get('review_count', 0)}/{payload.get('blocked_count', 0)}`",
        f"- refresh/merge: `{payload.get('refresh_existing_count', 0)}/{payload.get('review_merge_count', 0)}`",
        f"- lint issues: `wikilink={payload.get('broken_wikilinks', 0)}, evidence={payload.get('broken_evidence_refs', 0)}, core={payload.get('empty_core_sections', 0)}`",
        "",
    ]


def sync_governance_summary_views(payload: dict[str, object], report_paths: dict[str, str]) -> None:
    ensure_dirs()
    GOVERNANCE_LATEST.write_text(build_governance_latest_body(payload, report_paths), encoding="utf-8")

    daily_path = governance_daily_path(payload)
    governance_name = Path(str(payload.get("report_path", ""))).name
    daily_text = sync_daily_header(daily_path, "governance-daily", governance_generated_date(payload))
    marker_line = f"- governance: [{governance_name}]({governance_name})"
    updated = upsert_daily_entry_text(daily_text, marker_line, build_governance_daily_entry(payload, report_paths))
    daily_path.write_text(updated, encoding="utf-8")


def supervisor_generated_date(payload: dict[str, object]) -> str:
    generated_at = str(payload.get("generated_at", "")).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", generated_at[:10]):
        return generated_at[:10]
    return current_date()


def supervisor_daily_path(payload: dict[str, object]) -> Path:
    day = supervisor_generated_date(payload).replace("-", "")
    return REPORTS_ROOT / f"supervisor_daily_{day}.md"


def build_supervisor_latest_body(payload: dict[str, object]) -> str:
    report_path = Path(str(payload.get("report_path", "")))
    governance_report = Path(str(payload.get("governance_report_path", "")))
    archive = payload.get("archive_advisory", {})
    action_plan = payload.get("action_plan", {})
    last_cycle_at = payload.get("cycle_generated_at", payload.get("generated_at", "unknown"))
    candidate_family_counts = archive.get("candidate_family_counts", {})
    retained_family_counts = archive.get("root_retained_family_counts", {})
    candidate_family_summary = ", ".join(
        f"{key}={value}" for key, value in sorted(candidate_family_counts.items())
    ) if isinstance(candidate_family_counts, dict) and candidate_family_counts else "none"
    retained_family_summary = ", ".join(
        f"{key}={value}" for key, value in sorted(retained_family_counts.items())
    ) if isinstance(retained_family_counts, dict) and retained_family_counts else "none"
    lines = [
        "# supervisor-latest",
        "",
        f"- refreshed_at: `{timestamp()}`",
        f"- last_cycle_at: `{last_cycle_at}`",
        "- how_to_read: `latest supervisor-cycle record`",
        f"- cycle_mode: `{payload.get('mode', 'unknown')}`",
        f"- daily_summary: [{supervisor_daily_path(payload).name}]({supervisor_daily_path(payload).name})",
        "",
        "## latest reports",
        f"- supervisor: [{report_path.name}]({report_path.name})",
        f"- governance: [{governance_report.name}]({governance_report.name})",
        "",
        "## summary",
        f"- step_count: `{payload.get('step_count', 0)}`",
        f"- ingest_processed: `{payload.get('ingest_processed', 0)}`",
        f"- lint_clean: `{payload.get('lint_clean', 'unknown')}`",
        f"- promotion_ready: `{payload.get('promotion_ready_count', 0)}`",
        f"- update_refresh: `{payload.get('update_refresh_count', 0)}`",
        "",
        "## operator decision",
        f"- state: `{action_plan.get('state', 'unknown') if isinstance(action_plan, dict) else 'unknown'}`",
        f"- summary: `{action_plan.get('summary', 'unknown') if isinstance(action_plan, dict) else 'unknown'}`",
        "",
        "## archive advisory",
        "- archive_basis: `latest supervisor-cycle timestamp`",
        f"- candidate_count: `{archive.get('candidate_count', 0)}`",
        f"- candidate_by_type: `{candidate_family_summary}`",
        f"- kept_in_reports: `{retained_family_summary}`",
        f"- threshold: `{archive.get('threshold', 0)}`",
        f"- should_archive: `{archive.get('should_archive', False)}`",
        "",
    ]
    return "\n".join(lines)


def build_supervisor_daily_entry(payload: dict[str, object]) -> list[str]:
    supervisor_name = Path(str(payload.get("report_path", ""))).name
    governance_name = Path(str(payload.get("governance_report_path", ""))).name
    action_plan = payload.get("action_plan", {})
    return [
        f"## {payload.get('generated_at', 'unknown')}",
        f"- mode: `{payload.get('mode', 'unknown')}`",
        f"- supervisor: [{supervisor_name}]({supervisor_name})",
        f"- governance: [{governance_name}]({governance_name})",
        f"- step_count: `{payload.get('step_count', 0)}`",
        f"- ingest_processed: `{payload.get('ingest_processed', 0)}`",
        f"- lint_clean: `{payload.get('lint_clean', 'unknown')}`",
        f"- promotion_ready: `{payload.get('promotion_ready_count', 0)}`",
        f"- update_refresh: `{payload.get('update_refresh_count', 0)}`",
        f"- operator_state: `{action_plan.get('state', 'unknown') if isinstance(action_plan, dict) else 'unknown'}`",
        f"- operator_summary: `{action_plan.get('summary', 'unknown') if isinstance(action_plan, dict) else 'unknown'}`",
        "",
    ]


def sync_supervisor_summary_views(payload: dict[str, object]) -> None:
    ensure_dirs()
    SUPERVISOR_LATEST.write_text(build_supervisor_latest_body(payload), encoding="utf-8")

    daily_path = supervisor_daily_path(payload)
    supervisor_name = Path(str(payload.get("report_path", ""))).name
    daily_text = sync_daily_header(daily_path, "supervisor-daily", supervisor_generated_date(payload))
    marker_line = f"- supervisor: [{supervisor_name}]({supervisor_name})"
    updated = upsert_daily_entry_text(daily_text, marker_line, build_supervisor_daily_entry(payload))
    daily_path.write_text(updated, encoding="utf-8")


def read_cycle_payload(cache_path: Path, required_keys: list[str]) -> dict[str, object] | None:
    cached = read_state(cache_path)
    payload = cached.get("payload")
    if not isinstance(payload, dict):
        return None
    for key in required_keys:
        value = payload.get(key)
        if not isinstance(value, str) or not Path(value).exists():
            return None
    return payload


def operator_action_plan(status: dict[str, object], governance: dict[str, object] | None) -> dict[str, object]:
    actions: list[str] = []
    stale_locks = int_or_zero(status.get("lock_stale_count", 0))
    should_archive = bool(status.get("cleanup_recommended_now", status.get("archive_should_run", False)))

    if stale_locks > 0:
        actions.append("run `./scripts/clear_stale_locks.ps1` to remove stale locks first.")
    if should_archive:
        actions.append("run `./scripts/archive_reports.ps1 -Apply` to archive old detailed reports.")
    if governance is None:
        actions.append("run `./scripts/governance_cycle.ps1` to rebuild the current operations state.")
        return {
            "state": "sync_runtime",
            "summary": "the operations board is empty, so rebuild the current runtime state first.",
            "actions": actions,
        }

    needs_repair = not governance.get("maintenance_clean", True) or not governance.get("static_lint_clean", True)
    promotion_ready = int_or_zero(governance.get("ready_count", 0))
    refresh_ready = int_or_zero(governance.get("refresh_existing_count", 0))

    if needs_repair:
        actions.append("open `reports/governance_latest.md` and start with the repair queue.")
        return {
            "state": "repair_runtime",
            "summary": "document quality or maintenance state is degraded, so repair comes first.",
            "actions": actions,
        }

    if promotion_ready > 0 or refresh_ready > 0:
        if promotion_ready > 0:
            actions.append("there are promotion-ready items, so confirm promotion first.")
        if refresh_ready > 0:
            actions.append("there are canon refresh candidates, so review the update queue.")
        return {
            "state": "apply_knowledge_changes",
            "summary": "the system is clean, and there are candidates ready for canon-layer updates.",
            "actions": actions,
        }

    actions.append("no immediate operations work is required. Review again after new raw intake or the next routine check.")
    return {
        "state": "idle_watch",
        "summary": "the current runtime state is stable and can stay idle without extra action.",
        "actions": actions,
    }


def build_operator_latest_body(payload: dict[str, object]) -> str:
    governance = payload.get("governance", {})
    supervisor = payload.get("supervisor", {})
    status = payload.get("status", {})
    action_plan = payload.get("action_plan", {})
    actions = action_plan.get("actions", []) if isinstance(action_plan, dict) else []
    archive_family_counts = status.get("cleanup_candidates_by_type", status.get("archive_candidate_family_counts", {}))
    archive_family_summary = ", ".join(
        f"{key}={value}" for key, value in sorted(archive_family_counts.items())
    ) if isinstance(archive_family_counts, dict) and archive_family_counts else "none"
    governance_latest_name = GOVERNANCE_LATEST.name
    supervisor_latest_name = SUPERVISOR_LATEST.name
    lines = [
        "# operator-latest",
        "",
        f"- refreshed_at: `{payload.get('generated_at', 'unknown')}`",
        "- how_to_read: `current operations board`",
        "",
        "## views",
        f"- governance_latest: [{governance_latest_name}]({governance_latest_name})",
        f"- supervisor_latest: [{supervisor_latest_name}]({supervisor_latest_name})",
    ]

    governance_report_path = governance.get("report_path")
    if isinstance(governance_report_path, str) and governance_report_path:
        governance_report = Path(governance_report_path)
        lines.append(f"- governance_cycle: [{governance_report.name}]({governance_report.name})")

    supervisor_report_path = supervisor.get("report_path")
    if isinstance(supervisor_report_path, str) and supervisor_report_path:
        supervisor_report = Path(supervisor_report_path)
        lines.append(f"- supervisor_cycle: [{supervisor_report.name}]({supervisor_report.name})")

    lines.extend(
        [
            "",
            "## runtime state",
            "- archive_basis: `current timestamp`",
            f"- lock_running_count: `{status.get('lock_running_count', 0)}`",
            f"- lock_stale_count: `{status.get('lock_stale_count', 0)}`",
            f"- cleanup_candidates_now: `{status.get('cleanup_candidates_now', status.get('archive_candidate_count', 0))}`",
            f"- cleanup_candidates_by_type: `{archive_family_summary}`",
            f"- kept_in_reports_now: `{status.get('kept_in_reports_now', status.get('archive_root_retained_count', 0))}`",
            f"- cleanup_recommended_now: `{status.get('cleanup_recommended_now', status.get('archive_should_run', False))}`",
            "",
            "## quality state",
            f"- maintenance_clean: `{governance.get('maintenance_clean', 'unknown')}`",
            f"- static_lint_clean: `{governance.get('static_lint_clean', 'unknown')}`",
            f"- promotion_ready: `{governance.get('ready_count', 0)}`",
            f"- update_refresh_existing: `{governance.get('refresh_existing_count', 0)}`",
            "",
            "## operator decision",
            f"- state: `{action_plan.get('state', 'unknown') if isinstance(action_plan, dict) else 'unknown'}`",
            f"- summary: `{action_plan.get('summary', 'unknown') if isinstance(action_plan, dict) else 'unknown'}`",
            "",
            "## recommended actions",
        ]
    )

    if isinstance(actions, list) and actions:
        for action in actions:
            lines.append(f"- {action}")
    else:
        lines.append("- no immediate action required")

    lines.append("")
    return "\n".join(lines)


def operator_summary_payload() -> dict[str, object]:
    ensure_dirs()
    status = status_payload()
    governance = read_cycle_payload(GOVERNANCE_CYCLE_CACHE, ["report_path"])
    supervisor = read_cycle_payload(SUPERVISOR_CYCLE_CACHE, ["report_path"])
    payload = {
        "generated_at": timestamp(),
        "report_path": str(OPERATOR_LATEST),
        "status": status,
        "governance": governance or {},
        "supervisor": supervisor or {},
    }
    action_plan = operator_action_plan(status, governance)
    payload["action_plan"] = action_plan
    payload["actions"] = action_plan["actions"]
    OPERATOR_LATEST.write_text(build_operator_latest_body(payload), encoding="utf-8")
    return payload


def summary_report_files() -> list[Path]:
    files: list[Path] = []
    for pattern in [
        "governance_latest.md",
        "governance_daily_*.md",
        "supervisor_latest.md",
        "supervisor_daily_*.md",
        "operator_latest.md",
    ]:
        files.extend(sorted(REPORTS_ROOT.glob(pattern)))
    unique: dict[str, Path] = {}
    for path in files:
        unique[str(path)] = path
    return list(unique.values())


def summary_report_link_sources() -> list[Path]:
    files: list[Path] = []
    for pattern in [
        "governance_latest.md",
        "supervisor_latest.md",
        "operator_latest.md",
    ]:
        files.extend(sorted(REPORTS_ROOT.glob(pattern)))
    unique: dict[str, Path] = {}
    for path in files:
        unique[str(path)] = path
    return list(unique.values())


def report_family_key(path: Path) -> str | None:
    name = path.name
    for prefix, family in [
        ("governance_cycle_", "governance_cycle"),
        ("supervisor_cycle_", "supervisor_cycle"),
        ("repair_queue_", "repair_queue"),
        ("promotion_queue_", "promotion_queue"),
        ("canon_update_queue_", "canon_update_queue"),
    ]:
        if name.startswith(prefix):
            return family
    load_test_match = re.match(r"^load_test_([a-z])_\d{8}_\d{6}\.(md|json)$", name)
    if load_test_match:
        return f"load_test_{load_test_match.group(1)}"
    if name.startswith("_") and path.suffix.lower() == ".txt":
        return "runtime_text"
    return None


def count_paths_by_report_family(paths: list[Path]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        family = report_family_key(path) or "other"
        counts[family] = counts.get(family, 0) + 1
    return dict(sorted(counts.items()))


def root_retained_report_names_by_family(protected: set[str]) -> tuple[set[str], dict[str, int]]:
    retained: set[str] = set()
    retained_by_family: dict[str, int] = {}
    family_root_counts: dict[str, int] = {}
    for path in REPORTS_ROOT.iterdir():
        if not path.is_file():
            continue
        family = report_family_key(path)
        if not family:
            continue
        if path.name not in protected:
            continue
        family_root_counts[family] = family_root_counts.get(family, 0) + 1
    for path in sorted(REPORTS_ROOT.iterdir(), key=lambda item: (item.stat().st_mtime, item.name), reverse=True):
        if not path.is_file():
            continue
        if path.name in protected:
            continue
        family = report_family_key(path)
        if not family:
            continue
        budget = REPORT_FAMILY_ROOT_RETENTION.get(family, 0)
        if budget <= 0:
            continue
        total_kept = family_root_counts.get(family, 0) + retained_by_family.get(family, 0)
        if total_kept >= budget:
            continue
        retained.add(path.name)
        retained_by_family[family] = retained_by_family.get(family, 0) + 1
    return retained, dict(sorted(retained_by_family.items()))


def latest_load_test_report_sets() -> set[str]:
    protected: set[str] = set()
    latest_by_scale: dict[str, Path] = {}
    for path in sorted(REPORTS_ROOT.glob("load_test_*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        match = re.match(r"^load_test_([a-z])_\d{8}_\d{6}\.md$", path.name)
        if not match:
            continue
        scale = match.group(1)
        if scale not in latest_by_scale:
            latest_by_scale[scale] = path
    for report_path in latest_by_scale.values():
        protected.add(report_path.name)
        json_pair = report_path.with_suffix(".json")
        if json_pair.exists():
            protected.add(json_pair.name)
    return protected


def extract_report_links(path: Path) -> set[str]:
    names: set[str] = set()
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        target = match.group(1).strip()
        if not target or "/" in target or "\\" in target:
            continue
        candidate = REPORTS_ROOT / target
        if candidate.exists():
            names.add(candidate.name)
    return names


def collect_report_names_from_json(value: object) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            names.update(collect_report_names_from_json(item))
        return names
    if isinstance(value, list):
        for item in value:
            names.update(collect_report_names_from_json(item))
        return names
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return names
        candidate = Path(text)
        if candidate.name:
            rooted = REPORTS_ROOT / candidate.name
            if rooted.exists() and (str(candidate).startswith(str(REPORTS_ROOT)) or rooted.exists()):
                names.add(rooted.name)
        if "reports\\" in text or "reports/" in text:
            parts = re.split(r"[\\/]", text)
            if parts:
                maybe_name = parts[-1]
                if maybe_name and (REPORTS_ROOT / maybe_name).exists():
                    names.add(maybe_name)
    return names


def archive_protection_details() -> dict[str, object]:
    protected: set[str] = set()
    protected.update(latest_load_test_report_sets())
    for path in summary_report_files():
        protected.add(path.name)
    for path in summary_report_link_sources():
        protected.update(extract_report_links(path))
    for state_path in sorted(STATE_ROOT.glob("*.json")):
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        protected.update(collect_report_names_from_json(payload))
    retained, _ = root_retained_report_names_by_family(protected)
    final_protected = set(protected)
    final_protected.update(retained)
    retained_counts = count_paths_by_report_family([REPORTS_ROOT / name for name in retained if (REPORTS_ROOT / name).exists()])
    return {
        "base_protected": protected,
        "retained": retained,
        "retained_counts": retained_counts,
        "protected": final_protected,
    }


def protected_report_names() -> set[str]:
    details = archive_protection_details()
    protected = details.get("protected", set())
    return set(protected) if isinstance(protected, set) else set()


def is_archive_candidate(path: Path, protected: set[str]) -> bool:
    if not path.is_file():
        return False
    name = path.name
    if path.parent != REPORTS_ROOT:
        return False
    if name in protected:
        return False
    prefixes = (
        "governance_cycle_",
        "supervisor_cycle_",
        "repair_queue_",
        "promotion_queue_",
        "canon_update_queue_",
    )
    if name.startswith(prefixes):
        return True
    if name.startswith("load_test_") and path.suffix.lower() in {".md", ".json"}:
        return True
    if name.startswith("_") and path.suffix.lower() == ".txt":
        return True
    return False


def archive_bucket_date(path: Path) -> str:
    match = re.search(r"_(\d{8})(?:_|\.|$)", path.name)
    if match:
        return match.group(1)
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y%m%d")


def archive_candidate_paths() -> tuple[set[str], list[Path]]:
    details = archive_protection_details()
    protected_value = details.get("protected", set())
    protected = set(protected_value) if isinstance(protected_value, set) else set()
    candidates = [path for path in sorted(REPORTS_ROOT.iterdir()) if is_archive_candidate(path, protected)]
    return protected, candidates


def archive_advisory(threshold: int = 10) -> dict[str, object]:
    details = archive_protection_details()
    protected_value = details.get("protected", set())
    retained_value = details.get("retained", set())
    retained_counts_value = details.get("retained_counts", {})
    protected = set(protected_value) if isinstance(protected_value, set) else set()
    retained = set(retained_value) if isinstance(retained_value, set) else set()
    retained_counts = retained_counts_value if isinstance(retained_counts_value, dict) else {}
    candidates = [path for path in sorted(REPORTS_ROOT.iterdir()) if is_archive_candidate(path, protected)]
    return {
        "generated_at": timestamp(),
        "archive_root": str(REPORT_ARCHIVE_ROOT),
        "protected_count": len(protected),
        "candidate_count": len(candidates),
        "candidate_family_counts": count_paths_by_report_family(candidates),
        "root_retained_count": len(retained),
        "root_retained_family_counts": retained_counts,
        "root_retention_budget": dict(sorted(REPORT_FAMILY_ROOT_RETENTION.items())),
        "should_archive": len(candidates) >= threshold,
        "threshold": threshold,
        "sample_candidates": [path.name for path in candidates[:5]],
    }


def archive_reports(apply: bool = False) -> dict[str, object]:
    ensure_dirs()
    REPORT_ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
    details = archive_protection_details()
    protected_value = details.get("protected", set())
    retained_value = details.get("retained", set())
    retained_counts_value = details.get("retained_counts", {})
    protected = set(protected_value) if isinstance(protected_value, set) else set()
    retained = set(retained_value) if isinstance(retained_value, set) else set()
    retained_counts = retained_counts_value if isinstance(retained_counts_value, dict) else {}
    candidates = [path for path in sorted(REPORTS_ROOT.iterdir()) if is_archive_candidate(path, protected)]
    moved: list[dict[str, str]] = []
    for path in candidates:
        bucket = REPORT_ARCHIVE_ROOT / archive_bucket_date(path)
        target = bucket / path.name
        moved.append({"source": str(path), "target": str(target)})
        if apply:
            bucket.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
    if apply:
        if moved:
            rewrite_summary_links_for_archived_reports(moved)
        operator_summary_payload()
    return {
        "generated_at": timestamp(),
        "apply": apply,
        "archive_root": str(REPORT_ARCHIVE_ROOT),
        "protected_count": len(protected),
        "candidate_count": len(candidates),
        "candidate_family_counts": count_paths_by_report_family(candidates),
        "root_retained_count": len(retained),
        "root_retained_family_counts": retained_counts,
        "candidates": moved,
    }


def rewrite_summary_links_for_archived_reports(moved: list[dict[str, str]]) -> None:
    replacements: dict[str, str] = {}
    for item in moved:
        source = Path(str(item.get("source", "")))
        target = Path(str(item.get("target", "")))
        if not source.name or not target.exists():
            continue
        try:
            relative_target = target.relative_to(REPORTS_ROOT).as_posix()
        except ValueError:
            continue
        replacements[source.name] = relative_target
    if not replacements:
        return
    for summary_path in summary_report_files():
        text = summary_path.read_text(encoding="utf-8")
        updated = text
        for source_name, relative_target in replacements.items():
            updated = updated.replace(f"]({source_name})", f"]({relative_target})")
        if updated != text:
            summary_path.write_text(updated, encoding="utf-8")


def loop_lock_paths() -> list[tuple[str, Path]]:
    return [
        ("autopilot", AUTOPILOT_LOCK),
        ("watch", AUTOPILOT_LOCK.with_name("watch.lock")),
        ("intake_scope", intake_scope_lock_path()),
    ]


def process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def lock_status_for_path(lock_name: str, lock_path: Path) -> dict[str, object]:
    if not lock_path.exists():
        return {
            "lock": lock_name,
            "path": str(lock_path),
            "exists": False,
            "state": "absent",
        }
    payload = read_state(lock_path)
    raw_pid = payload.get("pid")
    try:
        pid = int(str(raw_pid))
    except (TypeError, ValueError):
        pid = 0
    is_alive = process_is_alive(pid)
    return {
        "lock": lock_name,
        "path": str(lock_path),
        "exists": True,
        "pid": pid if pid > 0 else None,
        "started_at": payload.get("started_at"),
        "loop": payload.get("loop", lock_name),
        "mode": payload.get("mode"),
        "owner": payload.get("owner"),
        "state": "running" if is_alive else "stale",
    }


def lock_status() -> dict[str, object]:
    statuses = [lock_status_for_path(name, path) for name, path in loop_lock_paths()]
    return {
        "generated_at": timestamp(),
        "locks": statuses,
        "running_count": len([item for item in statuses if item["state"] == "running"]),
        "stale_count": len([item for item in statuses if item["state"] == "stale"]),
    }


def clear_stale_locks() -> dict[str, object]:
    removed: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    for lock_name, lock_path in loop_lock_paths():
        status = lock_status_for_path(lock_name, lock_path)
        if status["state"] == "stale" and lock_path.exists():
            lock_path.unlink()
            removed.append(status)
        else:
            skipped.append(status)
    return {
        "generated_at": timestamp(),
        "removed_count": len(removed),
        "removed": removed,
        "skipped": skipped,
    }


def read_running_lock_payload(lock_path: Path) -> dict[str, object] | None:
    if not lock_path.exists():
        return None
    payload = read_state(lock_path)
    raw_pid = payload.get("pid")
    try:
        pid = int(str(raw_pid))
    except (TypeError, ValueError):
        pid = 0
    if pid <= 0 or not process_is_alive(pid):
        return None
    return payload


def intake_scope_lock_path() -> Path:
    return AUTOPILOT_LOCK.with_name("intake_scope.lock")


def enforce_loop_start_compatibility(loop_name: str, mode: str | None = None) -> None:
    autopilot_payload = read_running_lock_payload(AUTOPILOT_LOCK)
    watch_payload = read_running_lock_payload(AUTOPILOT_LOCK.with_name("watch.lock"))
    intake_scope_payload = read_running_lock_payload(intake_scope_lock_path())

    if loop_name == "watch":
        if intake_scope_payload and str(intake_scope_payload.get("owner", "")).strip().lower() != "watch":
            raise RuntimeError("watch cannot run while raw intake scope is held")
        if autopilot_payload and str(autopilot_payload.get("mode", "")).strip().lower() == "full":
            raise RuntimeError("watch cannot run while autopilot full is running")
        return

    if loop_name == "autopilot" and str(mode or "").strip().lower() == "full":
        if intake_scope_payload and str(intake_scope_payload.get("owner", "")).strip().lower() != "autopilot":
            raise RuntimeError("autopilot full cannot run while raw intake scope is held")
        if watch_payload:
            raise RuntimeError("autopilot full cannot run while watch intake is running")


def acquire_loop_lock(lock_path: Path, loop_name: str, metadata: dict[str, object] | None = None) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "loop": loop_name,
        "pid": os.getpid(),
        "started_at": timestamp(),
    }
    if metadata:
        payload.update(metadata)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)

    for _ in range(3):
        if lock_path.exists():
            existing = read_state(lock_path)
            raw_pid = existing.get("pid")
            try:
                pid = int(str(raw_pid))
            except (TypeError, ValueError):
                pid = 0
            is_alive = process_is_alive(pid)
            if is_alive:
                raise RuntimeError(f"{loop_name} already running or previous lock remains: {lock_path}")
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

        try:
            with lock_path.open("x", encoding="utf-8") as handle:
                handle.write(serialized)
            return
        except FileExistsError:
            existing = read_state(lock_path)
            raw_pid = existing.get("pid")
            try:
                pid = int(str(raw_pid))
            except (TypeError, ValueError):
                pid = 0
            if process_is_alive(pid):
                raise RuntimeError(f"{loop_name} already running or previous lock remains: {lock_path}")
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    raise RuntimeError(f"{loop_name} could not acquire lock after retries: {lock_path}")


def release_loop_lock(lock_path: Path) -> None:
    if lock_path.exists():
        lock_path.unlink()


def collect_watch_snapshot(root: Path) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    if not root.exists():
        return snapshot
    for path in sorted(root.rglob("*.md")):
        snapshot[rel_from_root(path)] = path.stat().st_mtime
    return snapshot


def watch_intake(interval: float, settle_seconds: float) -> None:
    ensure_dirs()
    enforce_loop_start_compatibility("watch", "intake")
    acquire_loop_lock(AUTOPILOT_LOCK.with_name("watch.lock"), "watch", {"mode": "intake"})
    intake_scope_acquired = False
    intake_scope_lock = intake_scope_lock_path()
    try:
        acquire_loop_lock(intake_scope_lock, "intake_scope", {"mode": "raw_intake", "owner": "watch"})
        intake_scope_acquired = True
    except Exception:
        release_loop_lock(AUTOPILOT_LOCK.with_name("watch.lock"))
        raise
    previous = collect_watch_snapshot(LITE_RAW)
    pending_since: float | None = None
    print(json.dumps({
        "watch": "intake",
        "root": str(LITE_RAW),
        "interval_sec": interval,
        "settle_sec": settle_seconds,
        "started_at": timestamp(),
    }, ensure_ascii=False))
    try:
        while True:
            current = collect_watch_snapshot(LITE_RAW)
            changed = current != previous
            now = time.time()
            if changed:
                previous = current
                pending_since = now
            if pending_since is not None and (now - pending_since) >= settle_seconds:
                payload = workflow_intake_autorun()
                print(json.dumps({
                    "watch": "intake",
                    "triggered_at": timestamp(),
                    "raw_file_count": len(current),
                    "autorun": payload,
                }, ensure_ascii=False))
                previous = collect_watch_snapshot(LITE_RAW)
                pending_since = None
            time.sleep(interval)
    except KeyboardInterrupt:
        print(json.dumps({"watch": "intake", "stopped_at": timestamp()}, ensure_ascii=False))
    finally:
        if intake_scope_acquired:
            release_loop_lock(intake_scope_lock)
        release_loop_lock(AUTOPILOT_LOCK.with_name("watch.lock"))


def autopilot_loop(mode: str, interval: float, settle_seconds: float, maintenance_every_minutes: float) -> None:
    ensure_dirs()
    if mode not in {"full", "maintenance"}:
        raise ValueError(f"unsupported autopilot mode: {mode}")
    enforce_loop_start_compatibility("autopilot", mode)
    acquire_loop_lock(AUTOPILOT_LOCK, "autopilot", {"mode": mode})
    intake_scope_acquired = False
    intake_scope_lock = intake_scope_lock_path()
    if mode == "full":
        try:
            acquire_loop_lock(intake_scope_lock, "intake_scope", {"mode": "raw_intake", "owner": "autopilot"})
            intake_scope_acquired = True
        except Exception:
            release_loop_lock(AUTOPILOT_LOCK)
            raise
    previous = collect_watch_snapshot(LITE_RAW) if mode == "full" else {}
    pending_since: float | None = None
    maintenance_period = max(maintenance_every_minutes * 60.0, interval)
    last_maintenance = 0.0
    print(json.dumps({
        "loop": "autopilot",
        "mode": mode,
        "raw_root": str(LITE_RAW),
        "interval_sec": interval,
        "settle_sec": settle_seconds,
        "maintenance_every_minutes": maintenance_every_minutes,
        "started_at": timestamp(),
    }, ensure_ascii=False))
    try:
        while True:
            now = time.time()
            if mode == "full":
                current = collect_watch_snapshot(LITE_RAW)
                changed = current != previous
                if changed:
                    previous = current
                    pending_since = now
                    print(json.dumps({
                        "loop": "autopilot",
                        "mode": mode,
                        "event": "raw_change_detected",
                        "raw_file_count": len(current),
                        "at": timestamp(),
                    }, ensure_ascii=False))

                if pending_since is not None and (now - pending_since) >= settle_seconds:
                    intake_payload = workflow_intake_autorun()
                    print(json.dumps({
                        "loop": "autopilot",
                        "mode": mode,
                        "event": "intake_autorun",
                        "at": timestamp(),
                        "payload": intake_payload,
                    }, ensure_ascii=False))
                    previous = collect_watch_snapshot(LITE_RAW)
                    pending_since = None

            if (now - last_maintenance) >= maintenance_period:
                maintenance_payload = workflow_maintenance_autorun()
                print(json.dumps({
                    "loop": "autopilot",
                    "mode": mode,
                    "event": "maintenance_autorun",
                    "at": timestamp(),
                    "payload": maintenance_payload,
                }, ensure_ascii=False))
                last_maintenance = now

            time.sleep(interval)
    except KeyboardInterrupt:
        print(json.dumps({"loop": "autopilot", "stopped_at": timestamp()}, ensure_ascii=False))
    finally:
        if intake_scope_acquired:
            release_loop_lock(intake_scope_lock)
        release_loop_lock(AUTOPILOT_LOCK)


def workflow_intake_autorun() -> dict:
    ensure_dirs()
    ingest = workflow_ingest()
    should_follow = ingest["processed_count"] > 0
    compile_result = workflow_compile() if should_follow else None
    governance_result = workflow_governance() if should_follow else None
    return {
        "workflow": "intake-autorun",
        "generated_at": timestamp(),
        "triggered_followup": should_follow,
        "reason": "new lite notes created" if should_follow else "no new lite notes; compile and governance skipped",
        "ingest": ingest,
        "compile": compile_result,
        "governance": governance_result,
    }


def workflow_maintenance_autorun() -> dict:
    ensure_dirs()
    lint = workflow_lint()
    clean = lint_payload_is_clean(lint)
    fingerprint = fingerprint_payload(lint)
    previous_state = read_state(MAINTENANCE_AUTORUN_STATE)
    previous_fingerprint = str(previous_state.get("last_lint_fingerprint", ""))
    state_changed = fingerprint != previous_fingerprint
    repair = workflow_repair() if (state_changed and not clean) else None
    governance = workflow_governance() if state_changed else None
    if state_changed:
        write_state(
            MAINTENANCE_AUTORUN_STATE,
            {
                "last_lint_fingerprint": fingerprint,
                "last_clean": clean,
                "updated_at": timestamp(),
            },
        )
    if state_changed and clean:
        reason = "lint state changed; governance refreshed"
    elif state_changed and not clean:
        reason = "issues changed; repair and governance executed"
    elif clean:
        reason = "no lint state change; governance skipped"
    else:
        reason = "issues unchanged; repeated repair/governance skipped"
    return {
        "workflow": "maintenance-autorun",
        "generated_at": timestamp(),
        "lint_clean": clean,
        "state_changed": state_changed,
        "lint_fingerprint": fingerprint,
        "reason": reason,
        "lint": lint,
        "repair": repair,
        "governance": governance,
    }


def workflow_supervisor(mode: str) -> dict:
    ensure_dirs()
    cycle = run_supervisor_cycle(mode)
    return {
        "workflow": "supervisor",
        "generated_at": timestamp(),
        "mode": mode,
        "operator_state": cycle.get("action_plan", {}).get("state"),
        "operator_summary": cycle.get("action_plan", {}).get("summary"),
        "supervisor_cycle": cycle,
    }


def current_operator_snapshot() -> dict[str, object]:
    governance = read_cycle_payload(GOVERNANCE_CYCLE_CACHE, ["report_path"])
    action_plan = operator_action_plan(status_payload(), governance)
    return {
        "state": action_plan.get("state", "unknown"),
        "summary": action_plan.get("summary", "unknown"),
        "first_view": "reports/operator_latest.md",
    }


def mode_brief(mode: str) -> dict[str, object]:
    ensure_dirs()
    current_state = current_operator_snapshot()
    if mode == "starter":
        return {
            "mode": "starter",
            "goal": "manual inspection and low-cost operation",
            "entry_surface": "./scripts/mode.ps1 -Mode starter",
            "execution_model": "manual",
            "current_operator_state": current_state["state"],
            "current_operator_summary": current_state["summary"],
            "first_view": current_state["first_view"],
            "recommended_commands": [
                "./scripts/ingest.ps1",
                "./scripts/compile.ps1",
                "./scripts/query.ps1 -Query \"your question\"",
                "./scripts/lint.ps1",
                "./scripts/repair.ps1",
            ],
            "avoids": [
                "watch",
                "autopilot",
                "long-running loops",
            ],
            "when_to_use": [
                "when attaching a new repository for the first time",
                "when data volume is still small",
                "when you want to inspect document quality directly",
            ],
        }
    if mode == "runtime":
        return {
            "mode": "runtime",
            "goal": "bounded automation and routine maintenance",
            "entry_surface": "./scripts/mode.ps1 -Mode runtime -RuntimeMode full",
            "execution_model": "bounded automation",
            "current_operator_state": current_state["state"],
            "current_operator_summary": current_state["summary"],
            "first_view": current_state["first_view"],
            "recommended_commands": [
                "./scripts/supervisor_cycle.ps1 -Mode intake",
                "./scripts/supervisor_cycle.ps1 -Mode maintenance",
                "./scripts/supervisor_cycle.ps1 -Mode full",
                "./scripts/intake_autorun.ps1",
                "./scripts/maintenance_autorun.ps1",
            ],
            "primary_views": [
                "reports/operator_latest.md",
                "reports/supervisor_latest.md",
                "reports/governance_latest.md",
                f"reports/governance_daily_{current_date().replace('-', '')}.md",
            ],
            "avoids": [
                "always-on loops",
            ],
            "when_to_use": [
                "when raw input exists but full 24-hour automation is unnecessary",
                "when you run inspection loops several times per day",
            ],
        }
    if mode == "autopilot":
        return {
            "mode": "autopilot",
            "goal": "long-running monitoring with automatic intake and maintenance",
            "entry_surface": "./scripts/mode.ps1 -Mode autopilot",
            "execution_model": "long-running loop",
            "current_operator_state": current_state["state"],
            "current_operator_summary": current_state["summary"],
            "first_view": current_state["first_view"],
            "recommended_commands": [
                "./scripts/intake_loop.ps1",
                "./scripts/maintenance_loop.ps1",
                "./scripts/autopilot.ps1 -Mode full",
            ],
            "primary_views": [
                "reports/operator_latest.md",
                "reports/supervisor_latest.md",
                "reports/governance_latest.md",
                f"reports/governance_daily_{current_date().replace('-', '')}.md",
            ],
            "warnings": [
                "do not run intake_loop and autopilot full at the same time",
                "do not run maintenance_loop and autopilot full at the same time",
                "use this only for long-running operation, not for manual starter/runtime checks",
            ],
            "when_to_use": [
                "use intake_loop when you only want continuous raw-intake monitoring",
                "use maintenance_loop when you only want automated maintenance cadence",
                "use autopilot full only when both need to run in one loop",
            ],
        }
    raise ValueError(f"unsupported mode: {mode}")


def print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="wiki_runtime", description="wiki + wiki_lite + retrieval hybrid runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ensure")
    sub.add_parser("status")
    sub.add_parser("operator-summary")
    sub.add_parser("build-hot")
    sub.add_parser("build-cold")
    sub.add_parser("build-all")
    sub.add_parser("lock-status")
    sub.add_parser("clear-stale-locks")
    archive_parser = sub.add_parser("archive-reports")
    archive_parser.add_argument("--apply", action="store_true")
    sub.add_parser("maintenance-report")
    sub.add_parser("conflict-report")
    sub.add_parser("staleness-report")
    sub.add_parser("mark-conflicts")
    sub.add_parser("mark-stale")
    sub.add_parser("repair-queue")
    sub.add_parser("promotion-queue")
    sub.add_parser("update-queue")
    sub.add_parser("governance-cycle")
    supervisor_parser = sub.add_parser("supervisor-cycle")
    supervisor_parser.add_argument("--mode", default="full", choices=["intake", "maintenance", "full"])
    sub.add_parser("workflow-ingest")
    sub.add_parser("workflow-compile")
    sub.add_parser("workflow-lint")
    sub.add_parser("workflow-repair")
    sub.add_parser("workflow-promotion")
    sub.add_parser("workflow-update")
    sub.add_parser("workflow-governance")
    sub.add_parser("workflow-intake-autorun")
    sub.add_parser("workflow-maintenance-autorun")
    mode_parser = sub.add_parser("mode-brief")
    mode_parser.add_argument("--mode", default="starter", choices=["starter", "runtime", "autopilot"])
    watch_parser = sub.add_parser("watch")
    watch_parser.add_argument("--interval", type=float, default=2.0)
    watch_parser.add_argument("--settle-seconds", type=float, default=4.0)
    autopilot_parser = sub.add_parser("autopilot")
    autopilot_parser.add_argument("--mode", default="full", choices=["full", "maintenance"])
    autopilot_parser.add_argument("--interval", type=float, default=2.0)
    autopilot_parser.add_argument("--settle-seconds", type=float, default=4.0)
    autopilot_parser.add_argument("--maintenance-every-minutes", type=float, default=15.0)
    workflow_supervisor_parser = sub.add_parser("workflow-supervisor")
    workflow_supervisor_parser.add_argument("--mode", default="full", choices=["intake", "maintenance", "full"])
    preview_parser = sub.add_parser("promote-preview")
    preview_parser.add_argument("source_name")
    preview_parser.add_argument("--kind", default="topics", choices=["topics", "entities", "concepts", "syntheses"])
    preview_parser.add_argument("--target-name")

    merge_preview_parser = sub.add_parser("merge-preview")
    merge_preview_parser.add_argument("source_name")
    merge_preview_parser.add_argument("--kind", default="topics", choices=["topics", "entities", "concepts", "syntheses"])
    merge_preview_parser.add_argument("--target-name", required=True)

    merge_apply_parser = sub.add_parser("merge-apply")
    merge_apply_parser.add_argument("source_name")
    merge_apply_parser.add_argument("--kind", default="topics", choices=["topics", "entities", "concepts", "syntheses"])
    merge_apply_parser.add_argument("--target-name", required=True)
    merge_apply_parser.add_argument("--decision", required=True, choices=["merge_into_existing", "fork_new_target", "keep_existing"])
    merge_apply_parser.add_argument("--new-target-name")
    merge_apply_parser.add_argument("--force", action="store_true")

    query_parser = sub.add_parser("query")
    query_parser.add_argument("q")
    query_parser.add_argument("-k", type=int, default=10)
    query_parser.add_argument("--domain")
    query_parser.add_argument("--reliability-min", type=float)
    query_parser.add_argument("--hot-weight", type=float, default=0.7)
    query_parser.add_argument("--save-residue", action="store_true")

    promote_parser = sub.add_parser("promote")
    promote_parser.add_argument("source_name")
    promote_parser.add_argument("--kind", default="topics", choices=["topics", "entities", "concepts", "syntheses"])
    promote_parser.add_argument("--target-name")
    promote_parser.add_argument("--force", action="store_true")

    refresh_parser = sub.add_parser("refresh-canon")
    refresh_parser.add_argument("source_name")
    refresh_parser.add_argument("--kind", default="topics", choices=["topics", "entities", "concepts", "syntheses"])
    refresh_parser.add_argument("--target-name")
    refresh_parser.add_argument("--force", action="store_true")

    args = parser.parse_args()

    if args.command == "ensure":
        ensure_dirs()
        print_json({"ok": True, "ensured_root": str(ROOT)})
        return
    if args.command == "status":
        ensure_dirs()
        print_json(status_payload())
        return
    if args.command == "operator-summary":
        print_json(operator_summary_payload())
        return
    if args.command == "build-hot":
        hot_root = prepare_hot_build_root()
        build_index(hot_root, HOT_DB)
        print_json({"ok": True, "built": str(HOT_DB), "root": str(hot_root)})
        return
    if args.command == "build-cold":
        cold_root = prepare_cold_build_root()
        build_index(cold_root, COLD_DB)
        print_json({"ok": True, "built": str(COLD_DB), "root": str(cold_root)})
        return
    if args.command == "build-all":
        hot_root = prepare_hot_build_root()
        build_index(hot_root, HOT_DB)
        cold_root = prepare_cold_build_root()
        build_index(cold_root, COLD_DB)
        print_json({"ok": True, "built": [str(HOT_DB), str(COLD_DB)], "hot_root": str(hot_root), "cold_root": str(cold_root)})
        return
    if args.command == "lock-status":
        print_json(lock_status())
        return
    if args.command == "clear-stale-locks":
        print_json(clear_stale_locks())
        return
    if args.command == "archive-reports":
        print_json(archive_reports(apply=args.apply))
        return
    if args.command == "query":
        payload = query_dual(args.q, args.k, args.domain, args.reliability_min, args.hot_weight)
        if args.save_residue:
            payload["saved_residue"] = save_query_residue(args.q, payload)
        print_json(payload)
        return
    if args.command == "watch":
        watch_intake(args.interval, args.settle_seconds)
        return
    if args.command == "autopilot":
        autopilot_loop(args.mode, args.interval, args.settle_seconds, args.maintenance_every_minutes)
        return
    if args.command == "maintenance-report":
        print_json(maintenance_report())
        return
    if args.command == "conflict-report":
        print_json(conflict_report())
        return
    if args.command == "staleness-report":
        print_json(staleness_report())
        return
    if args.command == "mark-conflicts":
        print_json(mark_conflicts())
        return
    if args.command == "mark-stale":
        print_json(mark_stale())
        return
    if args.command == "repair-queue":
        print_json(generate_repair_queue())
        return
    if args.command == "promotion-queue":
        print_json(generate_promotion_queue())
        return
    if args.command == "update-queue":
        print_json(generate_update_queue())
        return
    if args.command == "governance-cycle":
        print_json(generate_governance_cycle())
        return
    if args.command == "supervisor-cycle":
        print_json(run_supervisor_cycle(args.mode))
        return
    if args.command == "workflow-ingest":
        print_json(workflow_ingest())
        return
    if args.command == "workflow-compile":
        print_json(workflow_compile())
        return
    if args.command == "workflow-lint":
        print_json(workflow_lint())
        return
    if args.command == "workflow-repair":
        print_json(workflow_repair())
        return
    if args.command == "workflow-promotion":
        print_json(workflow_promotion())
        return
    if args.command == "workflow-update":
        print_json(workflow_update())
        return
    if args.command == "workflow-governance":
        print_json(workflow_governance())
        return
    if args.command == "workflow-intake-autorun":
        print_json(workflow_intake_autorun())
        return
    if args.command == "workflow-maintenance-autorun":
        print_json(workflow_maintenance_autorun())
        return
    if args.command == "mode-brief":
        print_json(mode_brief(args.mode))
        return
    if args.command == "workflow-supervisor":
        print_json(workflow_supervisor(args.mode))
        return
    if args.command == "promote-preview":
        source = find_lite_note(args.source_name)
        print_json(promotion_assessment(source, args.kind, args.target_name))
        return
    if args.command == "merge-preview":
        print_json(merge_preview(args.source_name, args.kind, args.target_name))
        return
    if args.command == "merge-apply":
        print_json(
            merge_apply(
                args.source_name,
                args.kind,
                args.target_name,
                args.decision,
                args.new_target_name,
                args.force,
            )
        )
        return
    if args.command == "promote":
        print_json(promote_with_gate(args.source_name, args.kind, args.target_name, args.force))
        return
    if args.command == "refresh-canon":
        print_json(refresh_existing_canon(args.source_name, args.kind, args.target_name, args.force))
        return


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print_json({"ok": False, "error": str(exc)})
        raise SystemExit(1)
