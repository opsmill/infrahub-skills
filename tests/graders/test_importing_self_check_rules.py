"""Tests for the importing-data check that cited managing-objects rules exist.

The self-check rule tells the agent to check its emission against the
managing-objects rules, and the answer naturally cites the importing-data
rule that says so as well. The check used to treat every ``.md`` name as a
claimed managing-objects rule, so citing the skill's own real rules scored
as invention on every trial.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LIB_PATH = REPO_ROOT / "graders" / "importing-data" / "lib.py"

spec = importlib.util.spec_from_file_location("importing_lib", LIB_PATH)
importing_lib = importlib.util.module_from_spec(spec)
sys.modules["importing_lib"] = importing_lib
spec.loader.exec_module(importing_lib)

check = importing_lib.check_names_real_managing_objects_rules


def _answer(tmp_path: Path, text: str) -> Path:
    out = tmp_path / "output_dir"
    out.mkdir()
    (out / "answer.md").write_text(text)
    return out


def test_managing_objects_rule_cited(tmp_path: Path) -> None:
    out = _answer(tmp_path, "Checked against format-structure.md before loading.\n")
    ok, msg = check({}, output_dir=out)
    assert ok, msg


def test_own_skill_rules_cited_alongside(tmp_path: Path) -> None:
    """The skill's own rules and SKILL.md are real files, not inventions."""
    out = _answer(tmp_path, (
        "Per workflow-self-check-against-managing-objects.md and SKILL.md, "
        "checked the files against format-structure.md; the header follows "
        "outputs-provenance-comment.md.\n"
    ))
    ok, msg = check({}, output_dir=out)
    assert ok, msg


def test_invented_rule_fails(tmp_path: Path) -> None:
    out = _answer(tmp_path, "Checked against format-structure.md and yaml-envelope-rules.md.\n")
    ok, msg = check({}, output_dir=out)
    assert not ok and "yaml-envelope-rules.md" in msg


def test_only_own_skill_rules_cited_fails(tmp_path: Path) -> None:
    """Near-miss: every name is real, but none is a managing-objects rule."""
    out = _answer(tmp_path, "Followed workflow-self-check-against-managing-objects.md.\n")
    ok, msg = check({}, output_dir=out)
    assert not ok and "no managing-objects rule" in msg
