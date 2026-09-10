# Adding a Rule

A rule is a single-concern best practice that lives
in a skill's `rules/` directory (e.g.,
`skills/infrahub-managing-schemas/rules/relationship-component-parent.md`).
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
  the AI tends to produce.

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
`rules/_sections.md`. A new prefix has to be
registered everywhere the skill enumerates its
categories, not only in `_sections.md`:

- `rules/_sections.md` — the prefix and its scope
- the `Rule Categories` table in `SKILL.md`
- any severity or ladder legend the skill keeps
  (`infrahub-auditing-repo` has one in both
  `audit-procedure.md` and `SKILL.md`)

A prefix registered in only one of those is a rule
the skill never emits, while its eval still passes.

#### Make the rule reachable

`_sections.md` is a table of contents, not a load
trigger — an agent reads it once it already knows
which category it wants. Link the new rule from
`SKILL.md` at the workflow step where an agent needs
it, and say *when* to read it, not just what it
covers:

```markdown
Before adding a relationship, read
[rules/relationship-identifiers.md](./rules/relationship-identifiers.md)
— both sides must share one identifier.
```

A rule reachable only from `_sections.md` gets read
after the mistake, which is the same as not writing
it down.

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
independently owned. Rules that belong to
`infrahub-common` itself grade from
`graders/common/`.

#### Parse the answer; never substring-match it

`"x" in text` is the reflexive first draft, and it is
the commonest way a check goes wrong: it passes an
answer that merely mentions the trap and fails a
correct answer that words it differently. Parse the
artifact instead:

| Artifact | Parse with |
| -------- | ---------- |
| Schema / object / menu YAML | `yaml.safe_load`, then walk the structure |
| Python (checks, generators, transforms) | `ast` — see `graders/managing-generators/lib.py` |
| Shell commands | `shlex.split`; never split on `[;\|&]`, which fabricates segments inside quotes |
| Prose reports | locate the section, then match inside it |

Three failure modes follow from matching raw text:

- **Comments and docstrings count as code.** Strip
  them before asserting, or a `# WRONG:` contrast
  block in the answer satisfies the check meant to
  fail it.
- **Only the first fence gets graded.** Extract every
  fenced block, and accept an answer whose entire
  output is fenced.
- **Adjacency is not structure.** A verb next to a
  path does not mean the command ran against that
  path.

### 3. Add an Eval Task

Add a task block to the root `eval.yaml`. The block
schema is documented once, in
[running-evals.md](./running-evals.md#evalyaml-format).

The prompt is where new tasks go wrong. It has to be
a realistic user request that *would naturally
exercise the rule*, and it must not carry the answer:

- **No meta-prompts.** Don't ask the AI to "follow
  the rule", and don't dictate the output schema — a
  prompt that names the fields it wants back is
  answerable without the skill.
- **Prove it discriminates.** Comment out the
  instruction's `Read the skill at ...` line and run
  `skillgrade --eval=<task-name> --trials=1`
  ([procedure](./running-evals.md#writing-good-eval-prompts)).
  If the grader still scores 1.0, the task measures
  the model, not the skill; make the prompt harder,
  or grade something only the rule produces.
- **Reproduce the antipattern conditions.** Where the
  rule has a tempting wrong shape, put the temptation
  in the prompt instead of hoping the AI stumbles
  into it.

Set `trials: 3` for new tasks unless the rule is
particularly noisy (in which case 5 may help). The
`defaults` block in `eval.yaml` already sets 3, so a
new task only needs the key to differ from it.

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

For `infrahub-auditing-repo` yagni-* rules, don't add a
new bespoke script — wire the shared parameterized
grader straight from `eval.yaml`:
`python graders/auditing-repo/check_yagni_rule.py
<rule> <severity> <ladder-step>`. Write a dedicated
script only when the task needs file-attribution or
carve-out checks the parameterized grader can't express
(see `graders/auditing-repo/check_yagni_reuse_marketplace.py`).

### 5. Verify the Grader Both Ways

A check is wrong in two directions, and the obvious
compliant/violating pair catches neither. Hand-craft
**four** fixtures and run the grader on each:

| Fixture | Expected |
| ------- | -------- |
| Compliant, written the way the rule shows | 1.0 |
| Compliant, written differently — other field order, a helper, a synonym | 1.0 |
| Violating, obviously | < 1.0 |
| Violating **near-miss** — satisfies the check's keyword while breaking the rule | < 1.0 |

The last of each pair is the one that finds bugs:

- **False fail.** A correct answer phrased differently
  scores < 1.0. Write out the answer the rule's own
  example shows and watch whether it passes.
- **Laundering.** A violating answer scores 1.0
  because it mentions the right word, imports the
  right module, or names the right helper somewhere
  in the file. Ask what the smallest edit is that
  makes the violating fixture pass — if a comment or
  a bare string is enough, the check grades
  vocabulary, not substance.

```bash
mkdir -p /tmp/grader-test/{pass,pass-variant,fail,fail-nearmiss}
# write output.yml in each

for d in pass pass-variant fail fail-nearmiss; do
  echo "--- $d"
  (cd /tmp/grader-test/$d &&
    python /path/to/graders/<skill>/check_my_rule.py)
done
```

Check the failure message too: it has to name the
assertion that actually broke. A check that cannot
fail is worse than no check — it reports the rule as
covered forever.

### 6. Sweep the Layers the Rule Contradicts

If the rule corrects something the repo said before,
the prose layer is not the only place the old claim
lives. Grep the whole tree and fix every hit in the
same change — except `evaluations/`, which step 7
regenerates from `eval.yaml` rather than taking
hand edits:

```bash
grep -rn "<old claim, command, or field>" \
  skills/ graders/ eval.yaml evaluations/ dev/
```

The hits that get missed are the ones outside
`skills/`: a grader still asserting a command the
rule deletes, an `eval.yaml` expectation restating
the old causality, an `expectations` rubric that
rewards it. An impact or severity label bumped in
the rule has to move in the skill's index too.

### 7. Sync the JSON Evaluations

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

### 8. Run a Smoke Pass

```bash
skillgrade --smoke
```

A passing smoke run with your new rule means the AI
follows the rule reliably under the skill's current
prose. If smoke fails:

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
- [ ] Rule linked from `SKILL.md` at the workflow
  step that needs it
- [ ] (if new prefix) `rules/_sections.md`, the
  `SKILL.md` `Rule Categories` table, and any ladder
  legend all updated
- [ ] New check function added to
  `graders/<skill>/lib.py` and registered in
  `CHECKS`, parsing rather than substring-matching
- [ ] New task block added to `eval.yaml`, verified
  to fail with the skill's `Read the skill at ...`
  line commented out
- [ ] `graders/<skill>/check_<task>.py` task grader
  script
- [ ] Grader run against all four fixtures, including
  the compliant variant and the violating
  near-miss
- [ ] Old claims the rule contradicts swept from
  `skills/`, `graders/`, and `eval.yaml`
- [ ] `python scripts/sync-evals.py` run and the
  regenerated `evaluations/*.json` committed
- [ ] `skillgrade --smoke` passes (or smoke failures
  inform a rule rewrite before merging)
