from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.check_portability import iter_target_files, scan_repository


def test_skill_files_exist() -> None:
    skill_md = REPO_ROOT / "skills" / "aps-operator" / "SKILL.md"
    ref_md = REPO_ROOT / "skills" / "aps-operator" / "references" / "dsl-and-safety.md"
    assert skill_md.is_file(), "Missing skills/aps-operator/SKILL.md"
    assert ref_md.is_file(), "Missing skills/aps-operator/references/dsl-and-safety.md"
    assert len(iter_target_files()) >= 4


def test_zero_portability_or_denylist_violations() -> None:
    violations = scan_repository()
    assert violations == [], "Found forbidden tokens:\n" + "\n".join(violations)


def test_skill_covers_required_capabilities() -> None:
    skill_text = (REPO_ROOT / "skills" / "aps-operator" / "SKILL.md").read_text(encoding="utf-8")
    ref_text = (REPO_ROOT / "skills" / "aps-operator" / "references" / "dsl-and-safety.md").read_text(encoding="utf-8")
    combined = skill_text + "\n" + ref_text
    required_terms = [
        "describe_machine",
        "describe_hardware",
        "describe_dsl",
        "describe_interlocks",
        "describe_alarms",
        "validate_recipe",
        "compute_deposition_plan",
        "isEmulator",
        "executionTarget",
        "sessionTier",
        "gateValves",
        "isOperational",
        "scriptSummary",
        "inertCommentLinesWithSemicolon",
        "Sputter",
        "ADS",
        "Cluster",
    ]
    for term in required_terms:
        assert term in combined, f"Expected capability term {term!r} in skill docs"
