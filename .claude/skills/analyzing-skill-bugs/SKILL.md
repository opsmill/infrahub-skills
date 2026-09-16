---
name: analyzing-skill-bugs
description: >-
  Performs root-cause analysis of a defect in this repository's own skills,
  graders, or scripts, before any test or fix is written, and verifies every
  claim about Infrahub behavior against real source. TRIGGER when: a GitHub
  issue or a description says an Infrahub skill gives wrong guidance, a grader
  cannot fail, a bundled script misbehaves, or a registration surface has
  drifted; you need the root cause before touching anything. DO NOT TRIGGER
  when: the failing test already exists and you are ready to fix it, use
  test-driving-skill-changes or implementing-skill-changes; the input is a raw
  feature idea rather than a defect, use grilling-skill-features; the bug is in
  Infrahub the product rather than in this repository, use
  infrahub-reporting-issues.
argument-hint: <issue number or URL, or a free-text description> [--infrahub <version>] [--sdk <version>] [--fetch]
compatibility: >-
  Requires this repository checked out. `gh` is optional and used only for issue
  numbers and URLs. Ground truth degrades to UNVERIFIED without a local
  opsmill/infrahub checkout or an installed infrahub-sdk.
user-invocable: true
metadata:
  internal: true
  pipeline: skill-change (stage 1 of 3: analyze or grill, then test-drive, then implement)
  version: 0.1.0
  author: OpsMill
---

# Skill bug analyst

## User Input

```text
$ARGUMENTS
```

## Your role

A senior engineer doing root-cause analysis on this repository's own guidance
layer: a skill's prose, a grader check, or a bundled script. This stage writes
no fix and no test. Its entire output is a diagnosis that `test-driving-skill-changes`
turns into a failing test and `implementing-skill-changes` turns into a patch.
Neither of those stages re-investigates, so the diagnosis has to be structured
and precise enough to act on directly.

## Tool usage

- Use the `Read` tool to read files. Do not use `cat`, `head`, or `tail` in Bash.
- Use the `Glob` tool to find files. Do not use `find` or `ls -R` in Bash.
- Use the `Grep` tool to search file contents. Do not use `grep` or `rg` in Bash.
- Reserve Bash for git, `gh`, and commands that need a shell.
- Shell state does not persist across separate Bash calls. Variables and `cd`
  are gone by the next call, so re-derive or restate anything a later snippet
  needs.

## Input

Parse `$ARGUMENTS` for:

- an issue number or URL, fetched with `gh issue view <number>`
- a free-text description, when no issue reference is present
- optional flags: `--infrahub <version>` and `--sdk <version>` pin the ground
  truth check to a version instead of the latest tag; `--fetch` allows the
  GitHub ground-truth rung

Derive the key by the rule in
[`../skill-pipeline-common/handoff-format.md`](../skill-pipeline-common/handoff-format.md):
`<issue_number>-<short-slug>` with an issue, the slug alone without one. This
stage is the pipeline's bug entrance, so it invents the key once; every later
stage reads it back from the handoff file instead of re-deriving a slug that
would drift from the original.

Empty input, or an issue number `gh` cannot fetch: say so and stop. Analyzing
a guess produces a diagnosis nobody asked for.

## Clarity check

| Requirement | What it means |
| --- | --- |
| Clear problem statement | What is wrong, stated once, without hedging |
| Reproduction path | A skill invocation, a command, or steps that show the defect |
| Expected versus actual | What the guidance, grader, or script should have done, and what it did instead |

Rate the report CLEAR or UNCLEAR against the table.

UNCLEAR means say exactly which requirement is missing and stop. Guessing a
root cause for an ambiguous report wastes the ground-truth and classification
work that follows it, and hands the next stage a diagnosis built on a guess.

## Locate the defect

Grep `skills/`, `graders/`, `eval.yaml`, `scripts/`, and `dev/` for the
behavior, command, or claim the report names. Name the file and the line for
every hit that matters: the prose sentence, the check function, the script
line, or the eval task. A root cause with no `file:line` is not a root cause,
it is a hunch with a citation missing.

## Ground truth

Many reports here are claims about how Infrahub behaves, not claims about this
repository's prose. Before writing the root cause, verify each such claim
against real Infrahub source at a specific version, and check whether the
behavior was already fixed upstream: guidance that was correct for an older
release is a version-scoped rule, not a bug. Run the ladder in
[`../skill-pipeline-common/ground-truth.md`](../skill-pipeline-common/ground-truth.md)
before the root cause paragraph, not after it. The rung used, the tag or
version, and the SHA (or `UNVERIFIED`) go in the handoff header's
`Ground truth` field.

## Classify the defect

| Defect class | What is wrong | Failing test surface |
| --- | --- | --- |
| `guidance` | A skill's prose, rule, or example gives wrong or version-stale instruction | An eval task plus a grader check that fails against the current prose |
| `grader` | A check function exists but cannot fail, or asserts the wrong thing | A pytest against the check function, run over four fixtures |
| `script` | A bundled script, or a registration/category-prefix surface, has drifted | A pytest against the script |

Registration drift (a skill missing from one of its five surfaces) and
category-prefix drift (a rule file named outside its registered prefixes) are
`script`, not a fourth class: both are detectable by comparing the tree
against the five registration surfaces, and `check-cli-invocations.py`,
`check-plugin-freshness.py`, and `check-symlinks.py` already do exactly
this kind of comparison. There is no defect class with no test surface.

## Coverage check

Check whether an eval task, a grader check, or a pytest already covers this
behavior. If one exists and passes despite the defect, the test is wrong too,
not just the guidance, the grader, or the script: say so, and make fixing the
test part of the fix strategy rather than leaving it for the next stage to
discover on its own.

## Minimum change rung

Run the ladder in
[`../../../dev/guidelines/minimum-change.md`](../../../dev/guidelines/minimum-change.md)
before proposing a fix shape. Read it now, at the point of decision, not
after a strategy is already written around the wrong rung. Record which rung
the fix stops at and one line of why it does not need to go further, in the
handoff's `Minimum change rung` field.

## Fix strategy

State the approach and its scope: which file or files change, what stays
untouched, and a `Do NOT` list of the artifacts the minimum-change rung rules
out. This is the strategy the next stages execute, not the patch itself: no
diff, no fix code, no test code belongs here.

Then work out what the fix leaves stale. A skill whose behavior changes keeps
every documentation surface it already had, and those surfaces go on
describing behavior it no longer has. Read
[`../../../dev/guidelines/skill-registration.md`](../../../dev/guidelines/skill-registration.md)
§ "When behavior changes" now, while the scope is in front of you, and run the
grep it gives. Record the answer in the handoff's `Docs impact` field. `none`
is a complete answer; a blank field is not, because it cannot be told apart
from never having looked.

## Output

1. Derive the default branch and fetch it, using the snippet in
   [`../skill-pipeline-common/handoff-format.md`](../skill-pipeline-common/handoff-format.md).
   Record the SHA. If the fetch fails, stop and report the failure rather than
   writing a handoff with a guessed baseline.
2. Write `.skill-change-<key>.md` at the repo root, following the template in
   the same file, with `Track: bug` and the `Defect class` set to exactly one
   of `guidance`, `grader`, `script`.
3. Confirm `.skill-change-*.md` is covered by `.gitignore`. It is a working
   file for this pipeline, not a repository artifact.
4. Display the analysis in full so the user can review it before the next
   stage reads it.

## Escalation

Stop and report rather than guessing forward, when:

- the input cannot be resolved to an issue or a description
- the clarity check rates the report UNCLEAR
- exploration finds no root cause after checking `skills/`, `graders/`,
  `eval.yaml`, `scripts/`, and `dev/`
- ground truth contradicts the report: the current guidance is already right
- the default-branch fetch fails

## Common mistakes

| Mistake | Why it breaks the pipeline |
| --- | --- |
| Writing fix code or a test into the analysis | This stage produces a diagnosis, not a patch; the next stage owns the code |
| Analyzing an UNCLEAR bug | A root cause built on a guess sends the wrong fix downstream |
| Re-deriving the slug later in the pipeline | The key drifts from the one recorded in the handoff, and later stages lose the thread |
| Writing the analysis with no baseline SHA | Later stages cannot tell what the fix diverged from |
| Encoding an Infrahub behavior claim that ground truth never checked | A stale or version-specific claim ships as a correction |
| `git add`-ing the handoff file | `.skill-change-*.md` is a local working file, never a commit |

## Boundaries

Follow the repository-wide boundaries in
[`../../../AGENTS.md`](../../../AGENTS.md) § Boundaries.
