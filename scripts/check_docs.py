"""Consistency, link-integrity, and canonical inventory checker for PULSE docs."""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

CANONICAL_DOCS = {
    "README.md",
    "CHANGELOG.md",
    "docs/DOCUMENTATION_INDEX.md",
    "docs/METHODOLOGY.md",
    "docs/architecture/CURRENT_ARCHITECTURE.md",
    "docs/architecture/ARCHITECTURE_HISTORY.md",
    "docs/architecture/KAFKA_ARCHITECTURE.md",
    "docs/architecture/AGENT_ARCHITECTURE.md",
    "docs/research/SCIENTIFIC_FOUNDATIONS.md",
    "docs/research/RESEARCH_AND_PRIOR_ART.md",
    "docs/validation/VALIDATION_AND_BENCHMARKS.md",
    "docs/decisions/DECISION_LOG.md",
}

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def check_docs() -> int:
    errors: list[str] = []

    # 1. Verify exact Markdown file inventory under root and docs/
    actual_root_mds = {p.name for p in ROOT.glob("*.md") if p.name not in {"phase4_report.md"}}
    actual_docs_mds = {p.relative_to(ROOT).as_posix() for p in (ROOT / "docs").rglob("*.md")}
    actual_canonical = actual_root_mds | actual_docs_mds

    missing = sorted(CANONICAL_DOCS - actual_canonical)
    extra = sorted(actual_canonical - CANONICAL_DOCS)
    if missing:
        errors.append(f"Missing canonical docs: {missing}")
    if extra:
        errors.append(f"Stray or unarchived .md files in root/docs/: {extra}")

    # 2. Validate titles, size, links, and active-claim hygiene across canonical docs
    h1_seen: dict[str, str] = {}
    index_text = (ROOT / "docs/DOCUMENTATION_INDEX.md").read_text(encoding="utf-8") if (ROOT / "docs/DOCUMENTATION_INDEX.md").exists() else ""

    for rel in sorted(CANONICAL_DOCS & actual_canonical):
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if len(lines) < 20:
            errors.append(f"Doc too short / stub (<20 lines): {rel} ({len(lines)} lines)")

        # First H1 check
        h1_lines = [ln for ln in lines if ln.startswith("# ")]
        if not h1_lines:
            errors.append(f"Missing H1 header: {rel}")
        else:
            title = h1_lines[0][2:].strip()
            if title in h1_seen:
                errors.append(f"Duplicate H1 title '{title}' in {rel} and {h1_seen[title]}")
            h1_seen[title] = rel

        # Must be referenced in docs/DOCUMENTATION_INDEX.md
        if rel != "docs/DOCUMENTATION_INDEX.md":
            short_name = pathlib.Path(rel).name
            if short_name not in index_text and rel not in index_text:
                errors.append(f"Canonical doc missing from docs/DOCUMENTATION_INDEX.md: {rel}")

        # Relative Markdown links check
        for match in LINK_RE.finditer(text):
            raw_target = match.group(1).strip()
            if not raw_target or raw_target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_no_anchor = raw_target.split("#", 1)[0].split("?", 1)[0].strip()
            if not target_no_anchor:
                continue
            resolved = (path.parent / target_no_anchor).resolve()
            if not resolved.exists():
                errors.append(f"Broken relative link in {rel}: '{raw_target}' -> '{resolved}'")

        # Stale operational claim guards (skip lines explicitly contrasting legacy/old state)
        for idx, line in enumerate(lines, start=1):
            lower = line.lower()
            is_legacy_contrast = any(
                kw in lower
                for kw in (
                    "legacy",
                    "replaced",
                    "previously",
                    "superseded",
                    "old ",
                    "before ",
                    "prior ",
                    "instead of",
                    "not `",
                    "never `",
                    "never use",
                    "deprecated",
                    "historical",
                    "eliminat",
                )
            )
            if is_legacy_contrast:
                continue
            if "pulse.f1." in line:
                errors.append(f"Stale topic prefix 'pulse.f1.' presented as active in {rel}:{idx}")
            if "normalizer-v2" in line:
                errors.append(f"Stale Flink job 'normalizer-v2' presented as active in {rel}:{idx}")

        # Ensure Stage 9 placeholder marker does not linger in canonical docs
        if "pending stage 9" in text.lower() or "stage 9 final execution pending" in text.lower():
            errors.append(f"Unresolved Stage 9 placeholder marker present in {rel}")

    if errors:
        print("[FAIL] Documentation check failed:")
        for err in errors:
            print("  -", err)
        return 1

    print(f"[OK] All {len(CANONICAL_DOCS)} canonical docs verified: valid links, unique titles, cleanly indexed.")
    return 0


if __name__ == "__main__":
    sys.exit(check_docs())
