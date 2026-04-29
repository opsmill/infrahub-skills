# Adding a Rule

A rule is a single-concern best practice that lives
in a skill's `rules/` directory (e.g.,
`skills/infrahub-managing-schemas/rules/parent-rel-optional-false.md`).
Adding a rule without a corresponding test means the
rule lives in the skill's prose only — the AI may
follow it, may not, and there is no automated signal
that the rule still works after future skill edits.

**Every new rule must ship with at least one eval
task that exercises it and one deterministic grader
check that asserts the rule's outcome.** This guide
walks through the full path.

## When This Applies

- Adding a new file under `skills/<skill>/rules/`.
- Tightening an existing rule with a constraint that
  can be assertion-checked (e.g., adding a required
  field that the schema validator now rejects when
  absent).
- Documenting an antipattern in an existing rule that
  the AI tends to produce — the eval should reproduce
  the antipattern conditions and the grader should
  fail on the antipattern shape.

If the rule is purely advisory (taste-based prose
with no observable structural outcome), it does not
need a grader, but should still get an eval task that
inspects the rule's described output via the
`expectations` field for human review.

## Steps

### 1. Write the Rule

Follow the rule structure from
[adding-a-skill.md → Step 3](./adding-a-skill.md#3-add-rules):
title, why it matters, what to check, examples,
common mistakes. Lead with the *why* — the AI
generalizes better from explanations than from
imperatives.

Place the file at:

```text
skills/<skill>/rules/<category>-<concern>.md
```

Use the existing category prefixes from the skill's
`rules/_sections.md`. If the rule introduces a new
concern that doesn't fit any prefix, update
`_sections.md` to add the prefix and document its
scope.

### 2. Add a Grader Check Function

Each skill's grader code lives at
`graders/<skill>/lib.py`. The library exposes a
`CHECKS` registry mapping assertion names to check
functions of the signature:

```python
def check_my_assertion(schema: dict, **_) -> tuple[bool, str]:
    """One-line summary of what this asserts."""
    # ... inspect schema ...
    if not_compliant:
        return False, "Specific failure message"
    return True, "Concise success message"
```

Add the function and register it in `CHECKS`. Keep
the check **deterministic** — no LLM grading, no
network calls. Inspect the parsed YAML structure and
return a hard pass/fail.

If the rule cuts across multiple skills (rare),
duplicate the check function in each affected
`graders/<skill>/lib.py` rather than hoisting to a
shared module — the skills are deliberately
independently owned.

### 3. Add an Eval Task

Add a new task block to the root `eval.yaml`
following the existing schema. The task prompt should
be a realistic user request that *would naturally
exercise the rule* — not a meta-prompt asking the AI
to "follow the rule." Keep prompts at the
abstraction level a real user would type.

```yaml
  - name: my-rule-task
    trials: 3
    instruction: |
      Read the skill at .agents/skills/<skill>/SKILL.md
      and follow its workflow and rules.

      Task: <realistic prompt that naturally requires
      the rule to be applied>

      Save ONLY the final YAML to: output.yml
    graders:
      - type: deterministic
        run: python graders/<skill>/check_my_rule.py
        weight: 1.0
    expected_output: >-
      <one-paragraph description of correct output>
    expectations:
      - <human-readable expectation 1>
      - <human-readable expectation 2>
    assertions:
      - name: <assertion-name-from-CHECKS>
        check: <human-readable description>
```

Set `trials: 3` for new tasks unless the rule is
particularly noisy (in which case 5 may help). The
defaults file uses 3 trials; the smoke preset
overrides to 5 only for tasks that don't set a
per-task `trials` value.

### 4. Add a Task Grader Script

Create `graders/<skill>/check_my_rule.py` that calls
the shared `run_checks` library:

```python
#!/usr/bin/env python3
"""Grader for the my-rule-task eval."""

from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = [
    "schema-version",
    "<assertion-name-from-CHECKS>",
    # ... other related baseline checks
]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.yml"))))
```

Bundle the new assertion with related baseline
assertions (schema version, naming, etc.) so the
grader catches regressions in unrelated rules within
the same task.

### 5. Verify the Grader Locally

Before committing, hand-craft two fixture files —
one compliant and one violating — and confirm the
grader returns 1.0 on the compliant case and < 1.0
on the violating one, with a failure message that
correctly names the violated assertion.

```bash
mkdir -p /tmp/grader-test/{pass,fail}
# write /tmp/grader-test/pass/output.yml (compliant)
# write /tmp/grader-test/fail/output.yml (violating)

cd /tmp/grader-test/pass && python /path/to/graders/<skill>/check_my_rule.py
cd /tmp/grader-test/fail && python /path/to/graders/<skill>/check_my_rule.py
```

A grader that scores 1.0 on a violating fixture is a
silently broken assertion — fix it before committing.

### 6. Sync the JSON Evaluations

`evaluations/<skill>.json` files are auto-generated
from `eval.yaml` for the `/skill-creator` evals
runner. Regenerate them after every `eval.yaml` edit:

```bash
python scripts/sync-evals.py
```

Commit both `eval.yaml` and the regenerated
`evaluations/*.json` files together. CI does not
auto-run sync-evals, so a stale JSON will diverge
from the YAML over time.

### 7. Run a Smoke Pass

```bash
skillgrade --smoke
```

The smoke preset uses 5 trials per task by default,
but tasks that set `trials: 3` (the new
recommendation) use that. A passing smoke run with
your new rule means the AI follows the rule
reliably under the skill's current prose. If smoke
fails:

- Re-read the rule file. If the *why* is buried, the
  AI may not internalize it.
- Add a concrete example to the rule. Models learn
  from examples more reliably than from abstract
  imperatives.
- Check whether the rule conflicts with another
  rule in the same skill — sometimes a new rule
  contradicts an example elsewhere.

## Required Files Checklist

- [ ] `skills/<skill>/rules/<category>-<concern>.md`
- [ ] (if new prefix)
  `skills/<skill>/rules/_sections.md` updated
- [ ] New check function added to
  `graders/<skill>/lib.py` and registered in
  `CHECKS`
- [ ] New task block added to `eval.yaml`
- [ ] `graders/<skill>/check_<task>.py` task grader
  script
- [ ] Grader verified against compliant + violating
  fixtures locally
- [ ] `python scripts/sync-evals.py` run and the
  regenerated `evaluations/*.json` committed
- [ ] `skillgrade --smoke` passes (or smoke failures
  inform a rule rewrite before merging)
