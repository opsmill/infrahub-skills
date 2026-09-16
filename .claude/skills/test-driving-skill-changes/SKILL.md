---
name: test-driving-skill-changes
description: >-
  Writes the failing test for an analysed or grilled skill change, and proves it
  fails, before any fix is written. Chooses the test surface from the defect
  class: an eval.yaml task plus a grader check for guidance, a pytest for
  grader and script defects.
  Follow the workflow in the body; the description does not summarize it. TRIGGER when: a .skill-change-<key>.md handoff
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
  the red run on guidance-class changes.
user-invocable: true
metadata:
  internal: true
  pipeline: "skill-change (stage 2 of 3: analyze or grill, then test-drive, then implement)"
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

- Use the `Read` tool to read files and the `Glob` tool to find them, rather
  than `cat`, `find`, or `ls -R`.
- Use the `Grep` tool when you are searching the tree yourself. That covers
  exploration, not the commands this pipeline prints: where this skill or a
  file it links gives a literal `grep`, `head`, or `tail`, run it as given.
  The sweep and the ground-truth reads are those commands.
- Reserve Bash for git, `gh`, the snippets this skill gives you, and anything
  else that needs a shell.
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

Take `BRANCH` from the handoff's `Branch` field. Re-deriving a slug here
drifts from the name the entrance stage recorded, and the later stages would
then be working on a different branch.

```bash
git status --porcelain | grep -q . && { echo "Working tree is dirty. Commit or stash first."; exit 1; }
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=$(git remote show origin 2>/dev/null | sed -n 's/.*HEAD branch: //p')
[ "$DEFAULT_BRANCH" = "(unknown)" ] && DEFAULT_BRANCH=""
DEFAULT_BRANCH=${DEFAULT_BRANCH:-main}
BRANCH="<the Branch field from .skill-change-<key>.md>"
git fetch origin "$DEFAULT_BRANCH"
git fetch origin "$BRANCH" 2>/dev/null || true
git checkout "$BRANCH" || git checkout -b "$BRANCH" "origin/$DEFAULT_BRANCH"
```

Fetching `$BRANCH` first is what lets a re-run pick up work pushed from
another machine or another worktree, instead of quietly branching off the
default branch and losing the failing test already committed there.

The first `git checkout` keeps its error visible on purpose. This repository
is routinely checked out as a git worktree, and a branch already checked out
elsewhere fails with "already used by worktree at ...", which is the message
you need rather than the misleading "already exists" from the fallback.

No refspec reconciliation: this repository is small and is not shallow cloned.

## Route on defect class

Read `Defect class` from the handoff file: `guidance` follows
[## Guidance class](#guidance-class) below; `grader` and `script` follow
[## Grader and script classes](#grader-and-script-classes).

## Guidance class

1. Read [`../../../dev/guides/adding-a-rule.md`](../../../dev/guides/adding-a-rule.md)
   §§2 to 5 and [`../../../dev/guidelines/graders.md`](../../../dev/guidelines/graders.md).
   Both describe the shape a guidance-class test has to take.
2. Read [`../../../dev/guidelines/minimum-change.md`](../../../dev/guidelines/minimum-change.md)
   for the ladder, then answer two coverage questions before writing anything
   new:
   - **Can an existing grader check assert it?** Reuse the function in
     `graders/<skill>/lib.py` and add its name to an existing task's `CHECKS`
     list. A new check function is only warranted when no existing one parses
     the right artifact.
   - **Can it ride an existing eval task?** Add the assertion to a task whose
     prompt already produces the scenario. A new task costs trials times model
     runs on every regression sweep, forever.
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
7. Run the red run: `skillgrade --eval=<task> --trials=1` against the branch
   with the skill read normally and the new rule still absent. This is the
   failing test, and nothing before it is one. The fixtures prove the grader
   discriminates across four files you wrote by hand, which is not the
   repository as it stands scoring below 1.0. Require a score below 1.0 here.
   A score of 1.0 means the model already produces the wanted behavior
   without the rule, so the rule may be redundant: escalate, do not record it
   as a pass. The discrimination proof, the same task run with the skill
   unread, belongs to `implementing-skill-changes`: while the rule is absent
   the task scores below 1.0 whether the skill is read or not, so running it
   here proves nothing.
8. Run `uv run python scripts/sync-evals.py` and commit `eval.yaml`, the
   regenerated `evaluations/*.json`, and the grader files together. The
   `evals-sync` job in CI regenerates them and fails the pull request on any
   diff, so skipping this turns into a red build rather than silent drift.
9. Lint and run `uv run invoke test`.

## Four fixtures

Hand-craft four fixtures and run the grader on each. What each fixture is, and
why the second and fourth are the ones that find bugs, is written once in
[`../../../dev/guides/adding-a-rule.md`](../../../dev/guides/adding-a-rule.md)
§ "Verify the Grader Both Ways". Read it there rather than working from memory.

The scores this stage requires, in fixture order: `1.0 / 1.0 / <1.0 / <1.0`.

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

## Grader and script classes

Write a failing pytest under `tests/graders/` or `tests/scripts/`. For drift
defects, the test asserts the behavior of the `scripts/check-*.py` that does
not exist yet, or exists but does not catch the drift. Run it with:

```bash
uv run --group test pytest tests/<path> -k <name> -v
```

It must fail, and fail for the reason the handoff's `Test plan` states,
rather than on an import error or a typo in the test itself. Commit the test.

On the `grader` class the four fixtures in
[## Four fixtures](#four-fixtures) are the pytest's parameter cases: the same
compliant, compliant variant, violating, and near-miss artifacts, asserted
directly against the check function instead of through a `skillgrade` run.
The separate four-fixture run and the red run do not apply here; the pytest is
the whole test.

## Close out

Close out only once the red run, the fixture run, or the pytest, whichever the
defect class produced, has actually confirmed the failure. See `## Hard gate`
below before pushing anything.

With `OPEN_PR`, push and open a draft PR whose body carries
`AGENT_EVAL_COMPLETE`, reusing an existing PR for the branch rather than
opening a duplicate:

```bash
BRANCH="<the Branch field from .skill-change-<key>.md>"
git push -u origin "$BRANCH"
PR=$(gh pr list --head "$BRANCH" --json number --jq '.[0].number')
if [ -z "$PR" ]; then
  gh pr create --draft --title "<type>(<scope>): <title>" \
    --body "$(printf '%s\n\n%s\n' '<one paragraph on the defect or design, linking the issue>' 'AGENT_EVAL_COMPLETE')"
else
  BODY=$(gh pr view "$PR" --json body --jq .body)
  printf '%s' "$BODY" | grep -q 'AGENT_EVAL_COMPLETE' \
    || gh pr edit "$PR" --body "$(printf '%s\n\n%s\n' "$BODY" 'AGENT_EVAL_COMPLETE')"
fi
```

Both halves stamp the marker. An earlier version only stamped it on the create
path, so a branch that already had a pull request, from a re-run or one opened
by hand, reached `implementing-skill-changes` with no marker and hit its hard
stop with no way out: re-running this stage took the same reuse path and still
did not stamp it. The `grep -q` guard keeps a second run from appending it
twice.

Without `OPEN_PR`, push the branch and report its name.

## Hard gate

Never hand off if the test does not fail. A test that passes on broken code
is not a test. State plainly what you ran and what it printed, for the
fixture run or the pytest, whichever the defect class produced.

The required evidence differs by class. Guidance: the red run of step 7,
scoring below 1.0 with the skill read and the rule absent, quoted with its
score, alongside the fixture run. Grader and script: the failing pytest,
quoted with its failure message.

## Escalation

Stop and report rather than guessing forward, when:

- the handoff file is missing or is missing a required field
- the working tree is dirty and cannot be cleaned safely
- the test cannot be made to fail against the current code
- the red run scores 1.0, meaning the model already produces the wanted
  behavior without the rule and the rule may be redundant

## Common mistakes

| Mistake | Why it breaks the pipeline |
| --- | --- |
| Writing the fix in this stage | The next stage has nothing left to implement, and no failing test proves it needed to |
| Substring matching in the check | Passes an answer that mentions the trap and fails one worded differently |
| Skipping the near-miss fixture | The check ships grading vocabulary instead of substance, and nobody notices |
| Treating the fixture run as the failing test | Four files you wrote by hand are not the repository scoring below 1.0 |
| Committing `eval.yaml` without the regenerated `evaluations/*.json` | The `evals-sync` job regenerates them and fails the pull request on any diff |
| Adding a new task where an existing one would carry the assertion | Every task costs trials times model runs on every regression sweep, forever |

## Boundaries

Follow the repository-wide boundaries in
[`../../../AGENTS.md`](../../../AGENTS.md) § Boundaries.
