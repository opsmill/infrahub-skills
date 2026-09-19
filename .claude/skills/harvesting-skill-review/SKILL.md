---
name: harvesting-skill-review
description: >-
  Turns review feedback on an opsmill/infrahub-skills pull request into durable
  rules, in this repository's own guidance layer. Reports first; edits only
  with approval. Follow the workflow in the body — the description does not
  summarize it. TRIGGER when: the user wants to turn PR review feedback
  on this repository into durable rules; capture recurring reviewer comments as
  contributor documentation; or check whether review lessons are reflected in
  the rules, guides, and graders. DO NOT TRIGGER when: the lesson is about
  Infrahub the product rather than this repository (use
  `infrahub-reporting-issues`); the friction happened live in a session rather
  than in a review thread (use `infrahub-reporting-skill-gaps`); or you only
  need to reply to or resolve review threads (normal `gh` flow).
argument-hint: <PR number, branch name, or empty for the current branch's PR>
compatibility: Requires this repository checked out and the `gh` CLI authenticated for PR/review access.
metadata:
  internal: true
  version: 0.1.0
  author: OpsMill
  variant-of: harvesting-review v0.8.0, opsmill/infrahub `.agents/skills/`
  variant-scope: opsmill/infrahub-skills only
---

# Harvest Review Lessons (infrahub-skills variant)

> **Not the upstream skill.** This started as `harvesting-review` in
> `opsmill/infrahub` and diverged far enough to warrant its own name. Do not
> sync edits between them in either direction; apply a change to whichever
> repository it was reasoned about.
>
> What differs here:
>
> - **Two routing tracks, not one.** A lesson about a shipped skill lands in
>   `skills/<skill>/rules/` and cannot land as prose alone — it pulls in a
>   grader check, an `eval.yaml` task, four fixtures, and `sync-evals.py`. A
>   lesson about contributing lands in `dev/guidelines/` or `dev/` and is cheap.
>   Upstream has only the cheap track.
> - **An extra verdict: covered in prose but nothing can fail.** This
>   repository's characteristic gap, and the fix is a test rather than better
>   wording.
> - **Three GitHub endpoints, not one.** Review feedback here lives in review
>   summaries and PR discussion; inline comment volume is routinely zero.
> - **Different destinations.** `dev/guidelines/`, `dev/guides/`,
>   `dev/knowledges/`, `AGENTS.md`, `skills/*/rules/`, `graders/`, `eval.yaml`.

## What this does

Reviewers repeat themselves. The same missing grader, the same unexecuted
snippet, the same rule that never got linked from `SKILL.md` recur PR after PR
because each lesson lived in a thread and died there. This skill reads a PR's
review comments, keeps the ones that generalize into a rule a future author
should follow, investigates each against the actual code, checks whether it is
already codified, and proposes the smallest edit to the right home.

It also prunes. Every run adds; nothing else stops this repository's guidance
layer from growing forever. §5 sweeps the destinations for rot the repo already
knows how to name, and folds the fix into the same PR.

## Refine, don't accrete — this outranks every other rule here

**A harvest that only adds has made the repo worse, however good each
individual rule is.** `AGENTS.md` is loaded into every session in this
repository, and `dev/guidelines/` loads on every matching file. Both are a tax
every contributor's agent pays. Nothing else in this skill removes a line, so
it has to be you, on every lesson you apply:

1. **Measure before appending.** `wc -l` the target. `SKILL.md` files stay
   under 500 lines (`dev/knowledges/skill-writing-guide.md`). A rule file
   covers one concern; a second concern is a second file, not a longer one.
2. **Cut what the new rule supersedes.** Rewrite the section around the new
   rule instead of bolting it on the end. This is also step 6 of
   `dev/guides/adding-a-rule.md`: sweep `skills/`, `graders/`, and `eval.yaml`
   for the claim the new rule contradicts.
3. **Report added/removed line counts.** Zero deletions means you accreted.
   Say so plainly rather than presenting it as a win.
4. **Raise the bar as the file grows.** "True but rarely needed" loses to
   keeping the doc readable.

Write every edit in the house style: `dev/knowledges/skill-writing-guide.md`.
Rule first, plain words, the *why* before the imperative, compliant and
non-compliant examples in two separate fences.

## Where lessons go

This repository has two destination classes, and they cost very different
amounts. Decide which track a lesson is on before choosing a file.

### Track A — the skills we ship

The lesson is something an *Infrahub user's* agent should do differently. It
belongs in `skills/<skill>/rules/`, and prose alone is not a landing:

> A new rule ships with its eval coverage in the same change.
> — `dev/guidelines/rule-equals-test.md`

That means a check function in `graders/<skill>/lib.py` registered in `CHECKS`,
an `eval.yaml` task run with the instruction's `Read the skill at ...` line
deleted, scoring below 1.0 or recording which reading explains the 1.0, a
task grader run against four fixtures, and
`python scripts/sync-evals.py`. Budget for it before proposing the rule, and
say in the report that this is the expensive track. Full procedure:
`dev/guides/adding-a-rule.md`.

### Track B — how we contribute

The lesson is about working *on* this repository. Cheap by comparison.

| Destination | What lives there | Bar |
| ----------- | ---------------- | --- |
| `dev/guidelines/*.md` | Terse constraints, loaded automatically when a matching file is touched | Highest. Edit an existing rule before adding a file; a new file means a new `paths:` glob that fires for every future edit under it. |
| `dev/guides/**` | How to do X — task procedures and their checklists | When the lesson belongs in a step of a recurring task. |
| `dev/knowledges/**` | How the repo works and why — reference, not do/don't | When the lesson is an explanation a future contributor needs. |
| `AGENTS.md` | Repo-wide facts, navigation, boundaries | For *what to do / where things live*, not craft detail. It loads every session, so the bar is high and the entry is short. |
| `dev/README.md` | The index for `dev/` | Only when a new destination file needs a route. |

`AGENTS.md` and `dev/README.md` are routers. Put the rule in its topical home
and the *trigger* in the router; never move a rule into `AGENTS.md` because
`AGENTS.md` is read more often.

## Workflow

### 1. Gather scope

Resolve the argument to a PR: a number, a branch name
(`gh pr view <branch>`), or nothing, in which case use the current branch's
PR. If none exists, ask.

Three endpoints, not one. `/comments` returns only
diff-anchored comments, so a reviewer who writes the lesson
in a "Request changes" summary — or in plain PR discussion —
is invisible to a run that reads that endpoint alone.

```bash
gh pr view <n> --json title,body,headRefName,commits

# inline, diff-anchored
gh api repos/opsmill/infrahub-skills/pulls/<n>/comments --paginate \
  -q '.[] | "--- \(.user.login) on \(.path):\(.line // .original_line)\n\(.body)\n"'

# review summaries (approve / request-changes bodies)
gh api repos/opsmill/infrahub-skills/pulls/<n>/reviews --paginate \
  -q '.[] | select(.body != "") | "--- \(.user.login) [\(.state)]\n\(.body)\n"'

# general PR discussion
gh api repos/opsmill/infrahub-skills/issues/<n>/comments --paginate \
  -q '.[] | "--- \(.user.login)\n\(.body)\n"'
```

Read **resolved and unresolved** threads. A resolved thread whose lesson never
reached a rule or a grader is exactly the gap this skill exists to catch.
Prioritise human reviewers but do not filter by author: a bot comment goes
through the same step-3 investigation and is kept when the code confirms it.
When a bot-sourced lesson survives, flag its origin. Skim the addressing commit
messages too; they often state the lesson more crisply than the thread.

### 2. Extract and abstract

Abstract each comment to the underlying rule. Promote the rule, not the
reviewer's wording. Keep a candidate only if it passes all three:

1. **Generalizes** beyond these lines.
2. **Actionable as an imperative** a future author follows.
3. **Would prevent a repeat comment.**

A fourth check bounds the other end: the rule must be specific to this
repository or a non-obvious gotcha. Universal hygiene every competent author
already applies is not worth the load cost.

Set aside anything obviously PR-local now. Borderline cases are not judged yet;
the investigation is what tells you whether they generalize.

### 3. Investigate each candidate — before any verdict

No verdict, no home, no edit until a candidate clears this step. It is the one
most easily skipped.

**a. Reconstruct before → after, then verify.** Read the code the reviewer saw
and the correction that actually landed. The correction is the ground truth;
the comment only prompted it. A thread with no landed change is unresolved or a
no-op: flag it, do not invent a fix. Then check the reviewer is technically
right, and grep for the suggested alternative elsewhere in the repo to confirm
it is an established drop-in.

**b. Interpret the intent.** Separate a preference for new work from a
repo-wide migration; directional guidance from an actionable request; and the
precise boundary of what the rule covers.

**c. Size the naive reading.** If acting on the literal comment implies
rewriting every skill or regrading every task, you have probably mis-read it.
Name the over-scoped reading you are ruling out; that record stops the next
person over-scoping too.

**d. Derive the rule and its root cause.** Write the one-sentence imperative,
scoped exactly as the investigation showed. Then name why an agent would have
produced the rejected shape: a missing convention, a reflexive idiom, a copied
template, a guide that still says the old thing. In this repository the root
cause is very often **a stale claim somewhere else in the tree** — check before
concluding, because the fix is then a sweep, not a new rule.

The investigation can also demote a candidate. Record the reason. Judge
"generalizes" by whether the underlying idiom recurs, not by the size of the
local fix.

**Never demote on the assumption a linter already enforces it.** A reviewer
having to raise it is evidence the tooling did not catch it.

### 4. Check existing coverage, then route

Grep both layers. In this repository a rule can be codified in prose, in a
test, or in neither, and the three need different fixes:

```bash
grep -rin "<keyword>" dev/guidelines/ dev/ AGENTS.md skills/*/rules/
grep -rin "<keyword>" graders/ eval.yaml
```

**A grep hit is not coverage until you read it.** Open the match, confirm it
states *this* rule and not an adjacent one, and cite the exact `file:line`.

Verdicts:

- **Missing** — written nowhere. Propose the smallest addition in the
  most-specific home, on the track §"Where lessons go" assigns. If the only
  reason to write it down is a defect in the code today, it is not
  documentation: phrase it as a forward-looking convention or file an issue
  instead.
- **Covered in prose but nothing can fail** — the rule is written in a
  `SKILL.md` or a rule file, and no grader asserts it. **This is the
  characteristic failure of this repository**, and it is a finding, not a
  relief: the constraint survives only until the next refactor of the prose.
  The fix is a test, not better wording. Route to
  `dev/guides/adding-a-rule.md` §2 and §5, and verify the new check against
  four fixtures including the violating near-miss.
- **Covered but ineffective** — the rule is written, a grader may even exist,
  yet a reviewer still had to flag it. Diagnose why it did not land:
  - **too abstract** — states the principle, not the concrete case. The signal:
    the reviewer had to write the correct shape themselves. Add the
    compliant/non-compliant pair, in two separate fences.
  - **not discoverable** — the rule is in the right file, but nothing pulled
    that file into context. Two coordinated edits, not a move: fix the
    load-trigger (the `SKILL.md` link at the workflow step that needs it, or
    the rule's `paths:` glob, or the `AGENTS.md`/`dev/README.md` entry) *and*
    strengthen the rule in place. A rule reachable only from `_sections.md` is
    read after the mistake.
  - **mis-homed** — genuinely in the wrong file. Move it, then fix the
    load-trigger so the new home is reachable.
  - **stale or contradicted** — another layer still says the old thing, so
    authors discount it. Sweep per `dev/guides/adding-a-rule.md` §6.
- **Not applicable** — coincidental match, or the comment was a question.
  Demote with the reason.

**Scope is not an alibi.** "Out of scope for this PR" is a reason not to change
*code* now. It never exempts the guidance from being made concrete.

Routing rule of thumb: most-specific existing home wins; edit before create;
strengthen before duplicate; fix the load-trigger before relocating;
`dev/guidelines/` only for a constraint worth loading on every matching file.
Confirm the target file exists before routing a lesson to it.

### 5. Sweep for rot

Cheap, and it is what keeps "harvested" from meaning "bloated". Run it every
time.

**a. Staleness grep.** Scope it to the prose that states rules, and match the
shape a citation actually takes — a bare `#\d+` also matches hex colours and
legitimate upstream issue references, and this repository's own PR numbers are
three digits, not five:

```bash
SCOPE=(dev/guidelines dev/guides dev/knowledges AGENTS.md
       skills/*/*.md skills/*/rules/ .claude/skills/)
EXCL=(--exclude=examples.md --exclude='*reference.md'
      --exclude-dir=harvesting-skill-review)

grep -rnoE "${EXCL[@]}" '\(#[0-9]{2,4}\)|PR #[0-9]+' "${SCOPE[@]}"
grep -rniE "${EXCL[@]}" \
  '(currently (broken|unfixed)|not yet fixed|known gap|for now)' "${SCOPE[@]}"
```

The exclusions are part of the command, not an instruction to remember:
`examples.md` and `*reference.md` carry literals — colours, IDs, sample
payloads — that look like citations and are not, and this skill's own
directory is skipped because the patterns above appear in it verbatim. Everything else that states a
rule is in scope, including each skill's `SKILL.md` and its prose files.

**A hit is a candidate, not a defect.** Read it before touching it. A reference
to an `opsmill/infrahub` issue is documenting upstream behaviour and stays; a
reference to a merged PR in *this* repository, made to justify a rule that now
stands on its own, is the rot. If the grep returns only the first kind, the
sweep is clean — say so and move on. Drop a stale citation and keep the
behaviour description it was attached to. Check a defect note against the
current code: delete it if fixed, reframe it as a convention if not.

**b. Broken-route check.** This repository routes by file path, so a moved file
silently breaks every pointer to it:

```bash
uv run invoke lint
python scripts/check-cli-invocations.py
```

**c. Supersession.** When this run's lesson generalizes something an earlier run
wrote narrowly, broaden the earlier entry in place rather than leaving both.

**d. Fix every confirmed defect now.** A punch list is not pruning. A hit you
read and kept — an upstream reference doing real work — is resolved, not
outstanding; say so and move on. The only entries that may stay genuinely
unresolved are calls for the user.

### 6. Report

Present the findings and **stop**. Do not edit yet. These files shape every
contributor's agent.

### 7. Apply (opt-in)

Ask: all, cherry-pick, or none. Then edit, following §4 routing and §5 pruning,
and apply *Refine, don't accrete* — measure, cut what is superseded, report the
line counts.

Reviewer quotes, PR numbers, and the investigation trail belong in the report
and the commit message, never in the file text.

A Track A lesson is not done when the rule file is written. Finish the
checklist in `dev/guides/adding-a-rule.md`, then:

```bash
uv run invoke lint
uv run invoke test
python scripts/sync-evals.py     # if eval.yaml changed; commit the JSON too
skillgrade --smoke               # optional, slow, needs an API key
```

**Never resolve review threads.** Reply if useful; resolution is the reviewer's
call.

## Report format

```markdown
## Review-Lessons Report — PR #<n>

### Scope
<!-- PR, branch, threads read (resolved + unresolved). After applying: lines
     added/removed per file, and what was cut. Zero deletions is a finding. -->

### Covered in prose, nothing can fail
<!-- The repository's characteristic gap, so it leads the report. For each:
     lesson, source, the exact file:line that states it, and the check +
     eval task that would make it enforceable. Omit the section when empty. -->

### Existing coverage to strengthen
<!-- Written, yet a reviewer still had to raise it. Lesson, source, the exact
     file:line confirmed to be the same rule, why it didn't land (too abstract
     / not discoverable / mis-homed / stale), and how to make the existing
     coverage land. Not a duplicate rule. -->

### New rules to add
<!-- For each: the one-sentence imperative; source (reviewer + quote, and the
     addressing commit); the investigation trail (before → after, the claim
     verified in code, intent, the over-scoped reading ruled out); the root
     cause; Track A or B and the exact file; and the text to add, already in
     house style. For Track A, list the grader and eval work it pulls in. -->

### Not lessons
<!-- PR-local fixes, and candidates the investigation demoted. Say why,
     briefly. Promoting every comment to a rule is as useless as missing the
     real ones. -->

### Pruned or consolidated
<!-- Debt from earlier runs, already fixed in this PR's diff. For each:
     file:line, what was there, why it changed. Label a genuine user call
     "Needs a decision". Say "none found" when the sweep is clean. -->
```
