---
name: implementing-skill-changes
description: >-
  Implements the fix for a skill change whose failing test already exists, runs
  the repository's gates, sweeps the layers the change contradicts, and pushes
  the branch, updating the pull request when one exists.
  Follow the workflow in the body; the description does not summarize it. TRIGGER when: a .skill-change-<key>.md handoff file and
  a failing test both exist and you are ready to make the test pass; you are at
  the final step of the skill-change pipeline. DO NOT TRIGGER when: no failing
  test exists yet, use test-driving-skill-changes; no analysis or design brief
  exists, use analyzing-skill-bugs or grilling-skill-features; you are changing
  Infrahub the product rather than this repository's guidance.
argument-hint: <key>
compatibility: >-
  Requires this repository checked out on the pipeline branch. `gh` and a GitHub
  remote are needed only for the PR path. `skillgrade` is needed for the
  targeted eval run and the discrimination proof on guidance-class changes.
user-invocable: true
metadata:
  internal: true
  pipeline: "skill-change (stage 3 of 3: analyze or grill, then test-drive, then implement)"
  version: 0.1.0
  author: OpsMill
---

# Skill change implementer

## User Input

```text
$ARGUMENTS
```

## Your role

Make the failing test pass by fixing what the analysis or design brief says is
wrong, not by editing the test until it stops complaining. The test is the
validation criterion the prior stage proved fails; the handoff's root cause or
design brief is what drives the fix. Those are not the same thing, and
collapsing them, by weakening a grader check or patching whatever the test
happens to touch, is the failure this stage exists to prevent.

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

Parse `$ARGUMENTS` for `<key>`, then read `.skill-change-<key>.md` and take
`BRANCH` from its `Branch` field. Re-deriving the branch name here drifts from
the name the entrance stage recorded, which is why the handoff carries it.

```bash
BRANCH="<the Branch field from .skill-change-<key>.md>"
gh pr list --head "$BRANCH" --json number,body,headRefName --jq '.[0]'
```

Two guards, both hard stops, checked in this order before anything else runs:

- The body does not contain `AGENT_EVAL_COMPLETE`: the failing-test stage
  never ran. Tell the user to run `test-driving-skill-changes` first, and
  stop.
- The body already contains `AGENT_IMPL_COMPLETE`: this stage already ran
  against this change. Say so, and stop.

No PR found for `$BRANCH`: proceed in local mode instead of failing closed.
Skip the two body guards, since there is no PR body to read; verify instead
that the failing test the prior stage wrote still exists, and run it before
touching anything else. Say plainly that no PR was found.

If that test already passes, stop: say the fix appears to have already been
applied on this branch, and do not proceed. A PR carries `AGENT_IMPL_COMPLETE`
as its idempotency guard against a second run; local mode has no PR body to
check, so a test that is already green is the only equivalent signal
available, and it means the same thing.

Back to the handoff file. Missing file: stop and say so, since this stage has
nothing to implement without it. Pull `Minimum change rung`, `Rule path`,
`Eval task`, `Sweep terms`, `Do NOT`, and `Defect class`; the rest of this
skill acts on exactly those fields. Also read the failing test the prior stage
committed.

## Implement

State the reasoning before editing anything: name the file, the change, and
why it addresses the diagnosis rather than the symptom the test happens to
touch.

Respect the recorded `Minimum change rung`. Rung 3 or lower: refuse to add a
new rule file, and say which rung blocked it. A stage that quietly upgrades
the change defeats the ladder the earlier stages already climbed.

Then branch on `Defect class`:

- `guidance`: write or edit the rule at the handoff's `Rule path`,
  `skills/<skill>/rules/<category>-<concern>.md`. Link it from `SKILL.md` at
  the workflow step that needs it, saying when to read it, because a rule
  reachable only from `_sections.md` gets read after the mistake, which is the
  same as not writing it down. A new category prefix also touches
  `_sections.md`, the `Rule Categories` table, and any ladder or severity
  legend the skill keeps.
- `grader`: fix the check function in `graders/<skill>/lib.py`, or the eval
  task, so it asserts what the handoff's `Test plan` describes.
- `script`: fix the bundled script, or write the `scripts/check-*.py` the test
  demands.

The handoff's `Do NOT` list names artifacts the minimum-change rung already
ruled out. Treat it as binding, not as a suggestion to reconsider.

## Verify

Run every gate, each with its command:

```bash
skillgrade --eval=<task> --trials=1     # guidance class only, must score 1.0
uv run invoke test
uv run invoke lint
if ! uv run python scripts/sync-evals.py; then
  echo "GATE FAILED: sync-evals.py exited non-zero; the diff below means nothing"
elif git diff --quiet -- evaluations/; then
  echo "evals in sync"
else
  echo "STALE: evaluations/ regenerated, commit the result"
  git diff --stat -- evaluations/
fi
```

Then, guidance class only, prove the task measures the skill rather than the
model. The green run above scored 1.0 with the skill read. Comment out the
task's `Read the skill at ...` line and run the same task again:

```bash
skillgrade --eval=<task> --trials=1     # skill unread, must score below 1.0
# then restore the line
```

A task that still scores 1.0 with the skill unread is graded by the model, not
by the rule you just wrote: harden the prompt, or grade something only the rule
produces, then re-run with the line commented out to confirm the score drops.
This proof only carries signal now that the rule exists, which is why
`test-driving-skill-changes` leaves it to this stage: with the rule absent the
task scores below 1.0 either way.

Escalate to `--trials=3` only when a single run is ambiguous, and say why in
the report. Never report an interrupted or timed-out `skillgrade` run as a
pass; an interruption is not evidence of anything.

## Sweep

For every term in the handoff's `Sweep terms`:

```bash
grep -rn "<sweep term>" skills/ graders/ eval.yaml dev/ README.md AGENTS.md docs/ .agents/skills/
```

Skip `evaluations/`, which `sync-evals.py` regenerates from `eval.yaml`. Fix
every hit, and delete what the change makes wrong. An impact or severity label
bumped in a rule has to move in the skill's index too, or the index now
disagrees with the rule it indexes.

Then update every surface the handoff's `Docs impact` field names. Those pages
describe behavior this change just altered, so leaving them is worse than
having written nothing: a reader trusts a stale page and search finds it.
[`../../dev/guidelines/skill-registration.md`](../../../dev/guidelines/skill-registration.md)
§ "When behavior changes" lists what goes stale and when. A `Docs impact` of
`none` needs no edit, and the report says so rather than passing over it in
silence.

## Registration

Only when the change adds a new skill: wire the five surfaces listed in
[`../../dev/guidelines/skill-registration.md`](../../../dev/guidelines/skill-registration.md).
Its five rows already include the per-skill docs page and the manifest entry,
so there is nothing to add beyond them. Link the table rather than restating
it here; a second copy is the exact drift the guideline warns about.

## Changelog

```bash
uv run towncrier create -c "<one sentence describing the change>" <issue>.housekeeping.md
# With no issue number, use a descriptive slug prefixed with +:
uv run towncrier create -c "<one sentence>" +<slug>.housekeeping.md
```

Apply the matching `changes/*` label to the PR; it drives the version bump.
Never edit `CHANGELOG.md` by hand and never run `towncrier build`. This
repository assembles its changelog from fragments, and skill or tooling work
goes under `housekeeping`.

## Scope check

Read `git diff` against the base branch. Nothing unrelated widened, and no
file changed that the handoff did not name. A fix that grew past the
handoff's `Target` needs a fresh diagnosis, not a bigger commit.

## Close out

Close out only once Verify, Sweep, and Scope check have all passed.

In local mode there is no PR body to update, so push the branch, report its
name, and say plainly that the change still needs a pull request opened. Do
not run `gh pr edit`: `PR_NUMBER` is empty by construction on this path, and
this skill never opens the PR itself.

With a PR, push, then update the PR body by appending `AGENT_IMPL_COMPLETE`:

```bash
BRANCH="<the Branch field from .skill-change-<key>.md>"
PR_NUMBER=$(gh pr list --head "$BRANCH" --json number --jq '.[0].number')
git push -u origin "$BRANCH"
gh pr view "$PR_NUMBER" --json body --jq .body > /tmp/pr-body-"$PR_NUMBER".md
printf '\n\nAGENT_IMPL_COMPLETE\n' >> /tmp/pr-body-"$PR_NUMBER".md
gh pr edit "$PR_NUMBER" --body-file /tmp/pr-body-"$PR_NUMBER".md
```

`--body` replaces the whole body, so the marker has to be appended to the
body that is already there. Reading it back first is what keeps the stage's
own `AGENT_EVAL_COMPLETE` gate — and the description — from being
overwritten.

Report what ran and what it printed for every gate in Verify. Then offer a
full `skillgrade --smoke` run as an opt-in the user can decline; never run it
automatically.

## Escalation

Stop and report rather than guessing forward, when:

- the handoff file is missing or missing a required field
- the PR body is missing `AGENT_EVAL_COMPLETE`
- the PR body already contains `AGENT_IMPL_COMPLETE`
- local mode, and the failing test already passes before any fix is applied
- the fix the diagnosis calls for needs an artifact the recorded rung forbids
- the targeted eval will not reach 1.0 after reasonable rewording
- the discrimination run scores 1.0 with the skill unread and the prompt
  cannot be hardened further
- a gate fails for a reason outside the handoff's scope

## Common mistakes

| Mistake | Why it breaks the pipeline |
| --- | --- |
| Weakening the grader instead of fixing the cause | The test passes, but the defect the handoff diagnosed is still there |
| Adding a rule file when the rung said edit an existing one | Splits one concern across two files and pays a second grader and eval forever |
| Linking the rule only from `_sections.md` | The rule is read after the mistake, which is the same as not writing it down |
| Skipping the discrimination proof | A task that scores 1.0 with the skill unread measures the model, not the rule |
| Skipping the sweep | An old claim the change makes wrong survives next to the new one |
| Committing `eval.yaml` without the regenerated JSON | `evaluations/*.json` silently diverges from the source it was built from |
| Editing `CHANGELOG.md` by hand | Bypasses the fragment system that assembles the release notes |
| Claiming a timed-out eval run passed | An interruption is not a score; the next reader trusts a result that never happened |

## Boundaries

Follow the repository-wide boundaries in [`../../AGENTS.md`](../../../AGENTS.md) § Boundaries.
