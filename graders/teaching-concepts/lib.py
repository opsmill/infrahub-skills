#!/usr/bin/env python3
"""Shared grader library for infrahub-teaching-concepts skill evaluations.

Parses the .infrahub-learning/ workspace a lesson session leaves behind and
runs deterministic assertion checks over it. Exposes a CHECKS registry and
run_checks(), which returns skillgrade JSON:

    {"score": 0.5, "details": "...", "checks": [{"name", "passed", "message"}]}

Checks are deterministic: no LLM, no network. The values here mirror the
workspace contract in
skills/infrahub-teaching-concepts/references/lesson-protocol.md.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

LEARNING_DIR = ".infrahub-learning"
SECTION_ORDER = ["Probe", "Explain", "Exercise", "Check"]
VALID_STATUSES = {"not-seen", "introduced", "practiced"}
PROGRESS_HEADER = ["concept", "status", "last-seen", "notes"]
TASK_MARKER = "**Your task:**"

_H2 = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_FENCE = re.compile(r"```[a-zA-Z0-9]*\n(.*?)```", re.DOTALL)
_DOCS_LINK = re.compile(r"https://docs\.infrahub\.app/[\w\-./#?=]+")
_GRADUATION = re.compile(r"infrahub-(?:managing|analyzing)-[a-z-]+")


def _learning(ws: Path) -> Path:
    return ws / LEARNING_DIR


def lessons(ws: Path) -> list[Path]:
    d = _learning(ws) / "lessons"
    return sorted(d.glob("*.md")) if d.is_dir() else []


def solution_for(ws: Path, lesson: Path) -> Path:
    return _learning(ws) / "solutions" / lesson.name


def headings(text: str) -> list[str]:
    return _H2.findall(text)


def sections(text: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            current = match.group(1)
            parts[current] = ""
        elif current is not None:
            parts[current] += line + "\n"
    return parts


def code_blocks(text: str) -> list[str]:
    return [m.strip() for m in _FENCE.findall(text) if m.strip()]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _first_lesson(ws: Path) -> tuple[Path | None, str]:
    found = lessons(ws)
    if not found:
        return None, f"no lesson file under {LEARNING_DIR}/lessons/"
    return found[0], ""


CHECKS: dict[str, Callable[[Path], tuple[bool, str]]] = {}


def run_checks(names: list[str], workspace: Path) -> dict:
    results = []
    for name in names:
        fn = CHECKS[name]
        try:
            passed, message = fn(workspace)
        except Exception as exc:  # noqa: BLE001 - a crash is a failed check
            passed, message = False, f"check crashed: {exc}"
        results.append({"name": name, "passed": passed, "message": message})
    score = sum(r["passed"] for r in results) / len(results) if results else 0.0
    failures = "; ".join(
        f"{r['name']}: {r['message']}" for r in results if not r["passed"]
    )
    return {
        "score": round(score, 2),
        "details": failures or "all checks passed",
        "checks": results,
    }
