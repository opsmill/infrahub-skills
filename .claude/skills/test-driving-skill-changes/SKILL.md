---
name: test-driving-skill-changes
description: >-
  Writes the failing test for an analysed or grilled skill change, and proves it
  fails, before any fix is written. Chooses the test surface from the defect
  class: an eval.yaml task plus a grader check for guidance, a pytest for
  grader and script defects. TRIGGER when: a .skill-change-<key>.md handoff
  file exists and the failing test has not been written yet; you are at the
  second step of the skill-change pipeline. DO NOT TRIGGER when: no handoff
  file exists, use analyzing-skill-bugs or grilling-skill-features first; the
  failing test exists and you are implementing the fix, use
  implementing-skill-changes; you are writing tests for a shipped Infrahub
  artifact rather than for this repository.
argument-hint: <key> [pr]
compatibility: >-
  Requires this repository checked out with a clean working tree. `gh` and a
  GitHub remote are needed only for the `pr` path. `skillgrade` is needed for
  the discrimination proof on guidance-class changes.
user-invocable: true
metadata:
  internal: true
  pipeline: skill-change (3 of 4 - analyze or grill, then test-drive, then implement)
  version: 0.1.0
  author: OpsMill
---

# Skill change test-writer

## User Input

```text
$ARGUMENTS
```

## Your role

Write the failing test and nothing else. No fix, no prose edit to the skill
under change. The test is the thing the next stage has to make pass. If you
find yourself editing a rule, a grader's logic beyond the new check, or a
skill's prose, stop: that work belongs to `implementing-skill-changes`.

## Tool usage

- Use the `Read` tool to read files. Do not use `cat`, `head`, or `tail` in Bash.
- Use the `Glob` tool to find files. Do not use `find` or `ls -R` in Bash.
- Use the `Grep` tool to search file contents. Do not use `grep` or `rg` in Bash.
- Reserve Bash for git, `gh`, and commands that need a shell.
- Shell state does not persist across separate Bash calls. Variables and `cd`
  are gone by the next call, so re-derive or restate anything a later snippet
  needs.

## Input and setup

Parse `$ARGUMENTS` for `<key>` and an optional `pr` flag, case-insensitive,
anywhere in the arguments, setting `OPEN_PR`.

Read `.skill-change-<key>.md`. Missing file: tell the user to run
`analyzing-skill-bugs` or `grilling-skill-features` first, and stop. Missing
any field required by
[`../skill-pipeline-common/handoff-format.md`](../skill-pipeline-common/handoff-format.md):
name the field and stop. Guessing a field forward writes a test against a
diagnosis nobody confirmed.

## Step 0: Branch

```bash
git status --porcelain | grep -q . && { echo "Working tree is dirty. Commit or stash first."; exit 1; }
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=$(git remote show origin 2>/dev/null | sed -n 's/.*HEAD branch: //p')
[ "$DEFAULT_BRANCH" = "(unknown)" ] && DEFAULT_BRANCH=""
DEFAULT_BRANCH=${DEFAULT_BRANCH:-main}
BRANCH=ai-skill-pipeline-<key>
git fetch origin "$DEFAULT_BRANCH"
git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" "origin/$DEFAULT_BRANCH"
```

This works from a git worktree, which is how the repository is routinely
checked out. No refspec reconciliation: this repository is small and is not
shallow cloned.

## Route on defect class

Read `Defect class` from the handoff file: `guidance` follows
[## Guidance class](#guidance-class) below; `grader` and `script` follow
[## Grader and script classes](#grader-and-script-classes).

## Guidance class

1. Read [`../../../dev/guides/adding-a-rule.md`](../../../dev/guides/adding-a-rule.md)
   §§2 to 5 and [`../../../dev/guidelines/graders.md`](../../../dev/guidelines/graders.md).
   Both describe the shape a guidance-class test has to take.
2. Read [`../../../dev/guidelines/minimum-change.md`](../../../dev/guidelines/minimum-change.md)
   and check rungs 5 and 6 before writing anything new: an existing check
   function in `graders/<skill>/lib.py` or an existing `eval.yaml` task may
   already carry the assertion.
3. Write the check in `graders/<skill>/lib.py` and register it in `CHECKS`.
   Parse the artifact, never substring-match it. Strip comments and
   docstrings before asserting, or a contrast block in the answer satisfies a
   check meant to fail it. Extract every fenced block rather than the first,
   or an answer whose real output sits in the second fence passes on an
   empty check.
4. Write `graders/<skill>/check_<task>.py`, bundling the new assertion with
   related baseline checks so the task also catches regressions in
   neighbouring rules.
5. Add the `eval.yaml` task. Keep `trials: 3` in the file: that is the value
   the weekly regression suite runs against. Every local run in this skill
   still passes `--trials=1` on the command line, because a local check only
   needs one failing trial to prove the point, not a statistically reliable
   rate. The file value and the local flag are different on purpose.
6. Build and run the four fixtures. See
   [## Four fixtures](#four-fixtures) below.
7. Run the discrimination proof. See
   [## Discrimination proof](#discrimination-proof) below.
8. Run `uv run python scripts/sync-evals.py` and commit `eval.yaml`, the
   regenerated `evaluations/*.json`, and the grader files together. A stale
   JSON silently diverges from the YAML.
9. Lint and run `uv run invoke test`.

## Four fixtures

| Fixture | Expected score |
| --- | --- |
| Compliant, written the way the rule shows | 1.0 |
| Compliant, written differently (other field order, a helper, a synonym) | 1.0 |
| Violating, obviously | < 1.0 |
| Violating near miss (satisfies the check's keyword while breaking the rule) | < 1.0 |

```bash
REPO=$(git rev-parse --show-toplevel)
mkdir -p /tmp/skill-fixtures/{pass,pass-variant,fail,fail-nearmiss}
# write the artifact under test (output.yml, or the file the grader reads) in each
for d in pass pass-variant fail fail-nearmiss; do
  echo "--- $d"
  (cd /tmp/skill-fixtures/$d && uv run --project "$REPO" python "$REPO/graders/<skill>/check_<task>.py")
done
```

If the near miss scores 1.0, the check grades vocabulary, not substance:
rewrite it before continuing. Check the failure message too, and confirm it
names the assertion that actually broke. A check that cannot fail is worse
than no check, because it reports the rule as covered forever.

## Discrimination proof

Comment out the task's `Read the skill at ...` line, then run:

```bash
skillgrade --eval=<task> --trials=1
# then restore the line
```

Require a score below 1.0. A task that still scores 1.0 measures the model
rather than the skill: harden the prompt, or grade something only the rule
produces, then re-run to confirm the score drops once the line is restored.

## Grader and script classes

Write a failing pytest under `tests/graders/` or `tests/scripts/`. For drift
defects, the test asserts the behavior of the `scripts/check-*.py` that does
not exist yet, or exists but does not catch the drift. Run it with:

```bash
uv run --group test pytest tests/<path> -k <name> -v
```

It must fail, and fail for the reason the handoff's `Test plan` states,
rather than on an import error or a typo in the test itself. Commit the test.

## Close out

Close out only once the fixture run or the discrimination proof has actually
confirmed the failure. See `## Hard gate` below before pushing anything.

With `OPEN_PR`, push and open a draft PR whose body carries
`AGENT_EVAL_COMPLETE`, reusing an existing PR for the branch rather than
opening a duplicate:

```bash
git push -u origin "$BRANCH"
gh pr list --head "$BRANCH" --json number --jq '.[0].number' | grep -q . \
  || gh pr create --draft --title "<type>(<scope>): <title>" --body "$(cat <<'EOF'
<one paragraph on the defect or design, linking the issue>

AGENT_EVAL_COMPLETE
EOF
)"
```

Without `OPEN_PR`, push the branch and report its name.

## Hard gate

Never hand off if the test does not fail. A test that passes on broken code
is not a test. State plainly what you ran and what it printed, for both the
fixture run and, for guidance-class changes, the discrimination proof.

## Escalation

Stop and report rather than guessing forward, when:

- the handoff file is missing or is missing a required field
- the working tree is dirty and cannot be cleaned safely
- the test cannot be made to fail against the current code
- the discrimination run scores 1.0 and the prompt cannot be hardened further

## Common mistakes

| Mistake | Why it breaks the pipeline |
| --- | --- |
| Writing the fix in this stage | The next stage has nothing left to implement, and no failing test proves it needed to |
| Substring matching in the check | Passes an answer that mentions the trap and fails one worded differently |
| Skipping the near-miss fixture | The check ships grading vocabulary instead of substance, and nobody notices |
| Skipping the discrimination proof | A task that scores 1.0 with the skill unread measures the model, not the rule |
| Committing `eval.yaml` without the regenerated `evaluations/*.json` | The two projections diverge silently, since CI does not run sync-evals |
| Adding a new task where an existing one would carry the assertion | Every task costs trials times model runs on every regression sweep, forever |

## Boundaries

Follow the repository-wide boundaries in
[`../../../AGENTS.md`](../../../AGENTS.md) § Boundaries.
