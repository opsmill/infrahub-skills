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

The root `eval.yaml` defines all tasks to run:

```yaml
skill_name: infrahub-my-skill  # matches SKILL.md frontmatter name

tasks:
  - id: basic-scenario
    prompt: >-
      A realistic user request with specific names,
      namespaces, and field types.
    expected_output: >-
      Human-readable description of what correct
      output looks like.
    grader: graders/my-skill/basic-scenario.sh  # path to deterministic grader

  - id: advanced-scenario
    prompt: >-
      A more complex request with relationships
      and cross-references.
    expected_output: >-
      Expected output description.
    grader: graders/my-skill/advanced-scenario.sh
```

## Writing Grader Scripts

Graders live in `graders/<skill-name>/` and
are deterministic shell scripts that inspect the
model's output and emit a JSON result.

A grader receives the model output on stdin and must
print a JSON object to stdout:

```bash
#!/usr/bin/env bash
# graders/my-skill/basic-scenario.sh
output=$(cat)

# Check for required patterns
if echo "$output" | grep -q 'kind: Dropdown'; then
  echo '{"pass": true, "reason": "Status uses Dropdown kind"}'
else
  echo '{"pass": false, "reason": "Status does not use Dropdown kind"}'
fi
```

**Keep graders deterministic.** They should not call
external services or depend on timing. Parse the
output text and check for the presence or absence of
specific patterns.

**Use descriptive file names.** The grader filename
appears in results (`dropdown-for-status.sh` is more
readable than `check1.sh`).

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

## Writing Good Assertions

**Make them objectively verifiable.** "Output looks
nice" is not an assertion. "Status uses kind: Dropdown
with choice objects" is.

**Use descriptive names.** The grader filename appears
in results. Someone scanning results should understand
what `dropdown-for-status.sh` checks without reading
the full script.

**Focus on what the skill uniquely provides.** If a
model would get something right even without the
skill, testing it isn't very informative. Test the
things the skill's rules specifically address.

## Iteration Loop

1. Run evals, review output with `skillgrade preview`
2. Improve the skill (rules, examples, descriptions)
3. Re-run evals and compare pass rates
4. Repeat until satisfied

## Existing Evals

| Skill | Eval File | Tasks |
| ----- | --------- | ----- |
| infrahub-managing-schemas | `eval.yaml` (tasks: vlan-management, circuit-management, location-hierarchy) | 3 |
| infrahub-managing-menus | `eval.yaml` (tasks: flat-menu, hierarchical-menu, generic-kind-menu) | 3 |

Other skills don't have evals yet — adding them is a
good contribution. Focus on skills with the most
complex rules first (managing-objects, managing-checks,
managing-generators).
