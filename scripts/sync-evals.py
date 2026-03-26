#!/usr/bin/env python3
"""Generate evaluations/*.json from skills/*/eval.yaml.

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
SKILLS_DIR = REPO_ROOT / "skills"
EVALS_DIR = REPO_ROOT / "evaluations"


def extract_prompt(instruction: str) -> str:
    """Extract the user prompt from a skillgrade instruction.

    Strips the skill-reading preamble and the output-save suffix,
    returning just the task description.
    """
    # Extract text between "Task: " and "Save ONLY"
    match = re.search(
        r"Task:\s*(.+?)(?:\n\s*\n\s*Save ONLY|\Z)",
        instruction,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    # Fallback: return the full instruction stripped of preamble
    return instruction.strip()


def convert_eval_yaml(eval_path: Path, skill_name: str) -> dict:
    """Convert a single eval.yaml to skill-creator JSON format."""
    with open(eval_path) as f:
        data = yaml.safe_load(f)

    evals = []
    for idx, task in enumerate(data.get("tasks", []), start=1):
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

    return {"skill_name": skill_name, "evals": evals}


def main() -> None:
    EVALS_DIR.mkdir(exist_ok=True)

    converted = 0
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        eval_yaml = skill_dir / "eval.yaml"
        if not eval_yaml.exists():
            continue

        # Derive skill name from SKILL.md frontmatter
        skill_md = skill_dir / "SKILL.md"
        skill_name = f"infrahub-{skill_dir.name}"
        if skill_md.exists():
            text = skill_md.read_text()
            match = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
            if match:
                skill_name = match.group(1).strip()

        result = convert_eval_yaml(eval_yaml, skill_name)
        out_path = EVALS_DIR / f"{skill_dir.name}.json"

        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)
            f.write("\n")

        n = len(result["evals"])
        print(f"  {skill_name} -> {out_path.name} ({n} evals)")
        converted += 1

    if converted:
        print(f"\nSynced {converted} eval file(s) to {EVALS_DIR}/")
    else:
        print("No eval.yaml files found under skills/")


if __name__ == "__main__":
    main()
