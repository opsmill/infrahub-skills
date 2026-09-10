# Running Evaluations

## Overview

Evaluations test that skills produce correct output.
All skills share a single `eval.yaml` at the project
root, with grader scripts organized under `graders/<skill>/`.
Evals are run with [skillgrade](https://github.com/mgechev/skillgrade),
which replaces the previous custom eval runner.

A second consumer of `eval.yaml` exists: the
`/skill-creator` evals workflow reads
`evaluations/*.json`, which is a per-skill JSON
projection of the same task definitions. Those JSON
files are generated, never hand-edited.

## Installation

```bash
npm i -g skillgrade
```

## Syncing eval.yaml → evaluations/*.json

After every edit to `eval.yaml` (adding a task,
changing a prompt, tuning trials), regenerate the
JSON projection:

```bash
python scripts/sync-evals.py
```

Commit the regenerated `evaluations/*.json` files
together with the `eval.yaml` change. CI does not
run sync-evals automatically, so missing this step
silently desynchronizes the two formats.

## Running Evals Locally

Run evals from the project root:

```bash
# Quick smoke test (5 trials) — fastest feedback loop
skillgrade --smoke

# Reliable run (15 trials) — for iterating on a skill
skillgrade --reliable

# Regression run (30 trials) — for pre-release validation
skillgrade --regression
```

### Presets

| Flag | Trials | Use When |
| ---- | ------ | -------- |
| `--smoke` | 5 | Quick check during active development |
| `--reliable` | 15 | Confirming a fix or improvement |
| `--regression` | 30 | Pre-release or PR gate |

### CI Mode

CI runs each skill with:

```bash
skillgrade --ci --provider=local --threshold=0.8
```

This runs from the project root against the single
`eval.yaml`. It exits non-zero if the pass rate falls
below 0.8, which is what the CI quality gate checks.

## Viewing Results

```bash
# Show results in the terminal
skillgrade preview

# Open results in the browser
skillgrade preview browser
```

## eval.yaml Format

A `defaults` block sets the agent, provider, trials,
timeout, and threshold; `tasks` is a flat list of
task blocks that override those per task. Each task
names the skill to load in its own `instruction`,
which is how tasks for different skills coexist in
one file:

```yaml
tasks:
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
    assertions:
      - name: <assertion-name-from-CHECKS>
        check: <human-readable description>
```

`graders` is what skillgrade scores, by weight.
Under skillgrade, `expected_output`, `expectations`,
and `assertions` document the task for whoever reads
the results and do not fail a run on their own.

They are not inert, though: `scripts/sync-evals.py`
copies all three into `evaluations/<skill>.json`, and
whether the `/skill-creator` runner scores them is
outside this repo. Write them as if they were
graded: objectively verifiable and specific ("Status
uses `kind: Dropdown`", not "the schema is well
designed"), and about what the skill uniquely
provides.

## Writing Grader Scripts

Graders live in `graders/<skill>/` and are
deterministic Python scripts. A task grader reads the
artifact the instruction told the AI to save (usually
`output.yml` in the working directory), calls
`run_checks` from its skill's `lib.py`, and prints
the skillgrade JSON result to stdout:

```python
#!/usr/bin/env python3
"""Grader for the my-rule-task eval."""

from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import run_checks  # noqa: E402

CHECKS = ["schema-version", "<assertion-name>"]

if __name__ == "__main__":
    print(json.dumps(run_checks(CHECKS, Path("output.yml"))))
```

The individual assertions live in
`graders/<skill>/lib.py` under a `CHECKS` registry.
Writing one — including how to parse rather than
substring-match the answer, and the four fixtures
that prove it works — is covered in
[adding-a-rule.md](./adding-a-rule.md#2-add-a-grader-check-function).

**Keep graders deterministic.** No LLM grading, no
network calls, no dependence on timing.

**Name the script after what it asserts.** The
filename appears in results, so
`check_dropdown_for_status.py` beats `check1.py`.

## Writing Good Eval Prompts

**Be realistic.** Write the kind of thing an actual
user would type — with specific names, namespaces,
field types, and context. Not "create a schema" but
"Create an Infrahub schema for a VLAN management
system with an id attribute, a name, a status
dropdown, and a role field."

**Cover different complexity levels.** Include:

- A basic scenario that exercises core functionality
- A moderate scenario with relationships and
  cross-references
- An advanced scenario with generics, hierarchies,
  or edge cases

**Include known trouble spots.** If the skill has
rules for common mistakes (e.g., using deprecated
field names, missing bidirectional identifiers), write
eval prompts that would expose these mistakes without
the skill's guidance.

**Don't put the answer in the question.** A prompt
that dictates the output schema, names the fields it
wants back, or tells the AI to "follow the rule" is
answerable without the skill. Keep the prompt at the
abstraction level a real user would type and let the
skill supply the shape.

**Prove the task discriminates.** Every task's
`instruction` opens with a `Read the skill at
.agents/skills/<skill>/SKILL.md` line, and that line
is the only thing that loads the skill. To run the
task without it, comment the line out and run that
task alone:

```bash
skillgrade --eval=<task-name> --trials=1
# then restore the line
```

Leave the rest of the instruction untouched, since
the task body is what you are testing. If the grader
still scores 1.0, the task measures the model rather
than the skill; that is a broken task, not a passing
one. Make the prompt harder, or grade something only
the skill's rules produce.

## Iteration Loop

1. Run evals, review output with `skillgrade preview`
2. Improve the skill (rules, examples, descriptions)
3. Re-run evals and compare pass rates
4. Repeat until satisfied

## Existing Evals

All tasks live in the single root `eval.yaml`; graders
live under `graders/<skill>/`. Rather than restating
the per-skill counts here, where they go stale
silently, read them off the file:

```bash
grep -oE '\.agents/skills/infrahub-[a-z-]+' eval.yaml |
  sort | uniq -c | sort -rn
```

A skill absent from that output has rules but no
eval coverage, which makes it the highest-value place
to add a task.
