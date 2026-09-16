---
name: grilling-skill-features
description: >-
  Stress-tests a raw idea for this repository's skills until it is a design a
  grader can actually test, before any rule, eval, or skill is written.
  TRIGGER when: someone has a fuzzy idea for new guidance in an Infrahub skill,
  wants to add a rule and is not sure where it belongs, asks to grill or
  pressure-test an idea for this repo, or proposes a new skill. DO NOT TRIGGER
  when: the input is a defect with known wrong behavior, use
  analyzing-skill-bugs; the design is already agreed and you are writing the
  failing test, use test-driving-skill-changes; the idea is about Infrahub the
  product rather than its skills, use infrahub-reporting-issues.
argument-hint: <free-text description of the idea>
compatibility: >-
  Requires this repository checked out. Ground truth for any Infrahub behavior
  claim degrades to UNVERIFIED without a local opsmill/infrahub checkout or an
  installed infrahub-sdk.
user-invocable: true
metadata:
  internal: true
  pipeline: skill-change (stage 1 of 3: analyze or grill, then test-drive, then implement)
  version: 0.1.0
  author: OpsMill
---

# Skill feature griller

## User Input

```text
$ARGUMENTS
```

## Your role

You interview. You do not design the rule alone, and you do not implement
anything here. The one deliverable is a design brief, written so a grader
could be built against it without asking anything further. An idea with no
observed failure is not something this repo needs a rule for yet: say so
and stop at rung 1 of the minimum change ladder. That is a successful
outcome, not an incomplete one.

## Tool usage

- Use the `Read` tool to read files. Do not use `cat`, `head`, or `tail` in Bash.
- Use the `Glob` tool to find files. Do not use `find` or `ls -R` in Bash.
- Use the `Grep` tool to search file contents. Do not use `grep` or `rg` in Bash.
- Reserve Bash for git, `gh`, and commands that need a shell.
- Shell state does not persist across separate Bash calls. Variables and `cd`
  are gone by the next call, so re-derive or restate anything a later snippet
  needs.

## Discover context

Read what already exists before asking a question about it. None of these
are required; read what is present and skip the rest.

| File | What it tells you |
| --- | --- |
| `AGENTS.md` | the skills table and the rules table, so you know what this repo already covers |
| `dev/README.md` | the map of `dev/`, for where a new rule's neighbors live |
| `skills/<candidate>/rules/_sections.md` | the category prefixes a new rule has to fit or extend |
| `skills/<candidate>/SKILL.md` | the workflow step a new rule would be linked from |

## How to interview

One question at a time, in your own message, never batched into a list the
user answers all at once. Never answer a question on the user's behalf to
save a round trip: a design produced that way ends up being yours, not
theirs. Prefer multiple choice over an open prompt, so the user can answer
in a word. Stop the moment a lens rules the idea out, and say plainly which
rung of the minimum change ladder ended the interview and why.

## Lens 1: Who hits this and when

Name what an agent does wrong today, in concrete terms, and how that was
observed: a real session, a review comment, a pattern seen more than once.
An idea with no observed failure is speculative and stops at rung 1 of the
ladder. Skip it, and say so in one line.

## Lens 2: New rule or new skill

Default to a rule inside an existing skill. Before proposing a new skill,
read
[`../../../dev/guidelines/minimum-change.md`](../../../dev/guidelines/minimum-change.md)
§ "A new skill sits above all of these", which counts what a new skill costs
and names the surfaces it has to be wired into. Propose one only when the
domain genuinely has no existing home, and name those surfaces in the same
breath.

## Lens 3: Which skill, which category prefix

Pick the target skill and read its `_sections.md` for the category
prefixes already in use. A new prefix has to land in `_sections.md`, the
`Rule Categories` table in `SKILL.md`, and any severity or ladder legend
the skill keeps, or the skill never emits the rule while its eval still
passes.

## Lens 4: What can a grader actually assert

The lens that decides whether this idea survives. If the outcome is not
observable in a parsed artifact (YAML structure, a Python AST, a named
section of a report), the rule is advisory, not testable. Say that
plainly, and give it an eval task with an `expectations` block for human
review instead of writing a check that only pretends to grade it.

## Lens 5: What is the violating near miss

Name the answer that satisfies the check's keyword while still breaking
the rule: the comment that mentions the trap, the import that is present
but unused, the field named right but structured wrong. If nobody can
name one, the check eventually built from this brief will grade
vocabulary instead of substance.

## Lens 6: What eval prompt exercises it

Describe a realistic user request that would naturally produce the
scenario. Not a meta-prompt that asks the model to "follow the rule", and
not one that dictates the output schema back to it. Put the antipattern
conditions in the prompt itself, so the model is tempted into the wrong
shape rather than hoped to stumble into it on its own.

## Lens 7: What does it contradict

Name any existing rule, example, or claim elsewhere in the repo that this
idea corrects or supersedes. Those names become the sweep terms
`implementing-skill-changes` greps for, so the old claim does not survive
next to the new rule.

## Lens 8: Ground truth

Run [`../skill-pipeline-common/ground-truth.md`](../skill-pipeline-common/ground-truth.md)
against any claim in the idea about how Infrahub itself behaves. A rule
built on a stale or unverified behavior claim ships a correction that is
not one.

## Lens 9: Scope and YAGNI

State what is explicitly out of scope for this idea. Then read
[`../../../dev/guidelines/minimum-change.md`](../../../dev/guidelines/minimum-change.md)
at this exact point, before the brief commits to a shape: it decides
whether the idea rides an existing rule or grader check, or genuinely
needs a new file. Record the rung the idea stops at.

## Output

1. Derive the default branch and fetch it, using the snippet in
   [`../skill-pipeline-common/handoff-format.md`](../skill-pipeline-common/handoff-format.md).
   Record the SHA as `Based on`. If the fetch fails, stop and report the
   failure rather than writing a brief with a guessed baseline.
2. Write the design brief to `.skill-change-<key>.md`, following the template
   in the same file, with `Track: feature` and `Defect class` set to exactly
   one of `guidance` (a new rule) or `script` (a new consistency check).
3. Confirm `.skill-change-*.md` is covered by `.gitignore`. It is a working
   file for this pipeline, not a repository artifact.

The `Test plan` section must name the eval task, the grader check and the
artifact it parses, and all four fixtures (compliant, compliant variant,
violating, and violating near miss), because `test-driving-skill-changes`
writes them from exactly this section and nothing else. A brief that skips
any of the four hands the next stage nothing to build.

The `Docs impact` field records what the new behavior leaves stale. New
guidance changes what a skill does, and the pages describing that skill go on
describing what it did before. Read
[`../../../dev/guidelines/skill-registration.md`](../../../dev/guidelines/skill-registration.md)
§ "When behavior changes" and run the grep it gives. A new skill is the
expensive case: it needs all five registration surfaces, and Lens 2 already
made you argue for it. `none` is a complete answer; a blank field is not.

## Approval gate

Show the brief in full, then stop and wait for an explicit yes. Do not
read silence, a follow-up question, or a related comment as approval, and
do not carry on into test-driving or implementation on an implied
approval.

## Common mistakes

| Mistake | Why it breaks the pipeline |
| --- | --- |
| Designing the rule before interviewing | The brief ends up describing your idea, not the user's |
| Batching questions into one message | The interview degenerates into a form the user fills out once |
| Accepting an idea no grader can parse | The rule ships advisory and stays silently unenforced |
| Proposing a new skill when a rule would do | Pays five registration surfaces for a concern one file could hold |
| Naming no violating near miss | The eventual check grades vocabulary, not the rule |
| Writing rule text here instead of in the brief | `test-driving-skill-changes` and `implementing-skill-changes` read the brief, not this transcript |

## Boundaries

Follow the repository-wide boundaries in
[`../../../AGENTS.md`](../../../AGENTS.md) § Boundaries.
