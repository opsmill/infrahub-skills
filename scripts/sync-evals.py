#!/usr/bin/env python3
"""Generate evaluations/*.json from the root eval.yaml.

eval.yaml is the single source of truth. This script exports the
skill-creator-compatible JSON format used by /skill-creator evals.

Usage:
    python scripts/sync-evals.py
"""

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is required: pip install pyyaml")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_YAML = REPO_ROOT / "eval.yaml"
EVALS_DIR = REPO_ROOT / "evaluations"
SKILLS_DIR = REPO_ROOT / "skills"


def extract_prompt(instruction: str) -> str:
    """Extract the user prompt from a skillgrade instruction.

    Strips the skill-reading preamble and the output-save suffix,
    returning just the task description.
    """
    match = re.search(
        r"Task:\s*(.+?)(?:\n\s*\n\s*Save ONLY|\Z)",
        instruction,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return instruction.strip()


def _skill_name_from_instruction(instruction: str) -> str | None:
    """Extract the skill directory name from the instruction preamble."""
    match = re.search(r"skills/([^/]+)/SKILL\.md", instruction)
    return match.group(1) if match else None


def main() -> None:
    EVALS_DIR.mkdir(exist_ok=True)

    if not EVAL_YAML.exists():
        print(f"No eval.yaml found at {EVAL_YAML}")
        sys.exit(1)

    with open(EVAL_YAML) as f:
        data = yaml.safe_load(f)

    # Group tasks by skill
    skills: dict[str, list[dict]] = {}
    for task in data.get("tasks", []):
        instruction = task.get("instruction", "")
        skill_dir = _skill_name_from_instruction(instruction)
        if not skill_dir:
            continue
        skills.setdefault(skill_dir, []).append(task)

    converted = 0
    for skill_dir, tasks in sorted(skills.items()):
        # Derive skill name from SKILL.md frontmatter
        skill_md = SKILLS_DIR / skill_dir / "SKILL.md"
        skill_name = f"infrahub-{skill_dir}"
        if skill_md.exists():
            text = skill_md.read_text()
            match = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
            if match:
                skill_name = match.group(1).strip()

        evals = []
        for idx, task in enumerate(tasks, start=1):
            prompt = extract_prompt(task.get("instruction", ""))
            entry = {
                "id": idx,
                "prompt": prompt,
                "expected_output": task.get("expected_output", ""),
                "files": [],
                "expectations": task.get("expectations", []),
                "assertions": task.get("assertions", []),
            }
            evals.append(entry)

        result = {"skill_name": skill_name, "evals": evals}
        out_path = EVALS_DIR / f"{skill_dir}.json"

        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)
            f.write("\n")

        print(f"  {skill_name} -> {out_path.name} ({len(evals)} evals)")
        converted += 1

    if converted:
        print(f"\nSynced {converted} skill(s) to {EVALS_DIR}/")
    else:
        print("No tasks found in eval.yaml")


if __name__ == "__main__":
    main()
