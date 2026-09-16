# Skill change handoff file

The pipeline hands work between stages with one file per change, at
`<repo root>/.skill-change-<key>.md`. It is never committed. Every stage after
the one that wrote it reads it before doing anything else.

## Deriving the key

With an issue number, the key is `<issue_number>-<short-slug>`. Without one,
it is the slug alone. The slug is a lowercase hyphenated summary, two to five
words. Whichever entrance stage runs first invents the key once, and it is
canonical from then on: later stages read it from this file instead of
re-deriving a slug that would drift from the original.

## Template

````markdown
## Skill change <key>

**Key:** `<key>`
**Branch:** `ai-skill-pipeline-<key>`
**Track:** bug | feature
**Title:** <one line>
**Based on:** `<SHA of origin/<default branch>>`

**Ground truth:** <rung used> | infrahub `<tag>` `<sha>` | sdk `<version>` | UNVERIFIED | n/a
**Defect class:** guidance | grader | script
**Minimum change rung:** <1-6, and one line saying why it stopped there>
**Docs impact:** <surfaces this change leaves stale, or: none>

**Target:** skills/<skill>/ | graders/<skill>/ | scripts/
**Rule path:** `skills/<skill>/rules/<category>-<concern>.md` (or: none, edits <existing file>)
**Grader:** `<check name in CHECKS>` parsing `<artifact>` (or: reuses `<existing check>`)
**Eval task:** `<task name>` (or: rides `<existing task>`)

### Root cause / Design brief

<track specific body>

### Test plan

<what the failing test asserts, which surface it lives on, and the four fixtures:>

- compliant: <sketch>
- compliant variant: <sketch, different field order or synonym>
- violating: <sketch>
- violating near miss: <sketch that satisfies the check keyword and breaks the rule>

### Sweep terms

- `<old claim, command, or field to grep for>`

### Do NOT

- <common wrong approach>
- <unnecessary artifact the minimum change ladder rules out>

### Notes for downstream

<edge cases, risks, registration surfaces if a new skill>
````

## Required fields

A stage may not proceed past a handoff file missing any of: `Key`, `Branch`,
`Defect class`, `Minimum change rung`, `Docs impact`, `Sweep terms`, or a
non-empty `Test plan`. Find one missing, name it, and stop there rather than guessing a
value forward.

`Docs impact` and `Sweep terms` are both satisfied by `none`. An entrance that
looked and found nothing has answered; an entrance that never looked has not,
and the two are indistinguishable once the field is blank.

`Ground truth` is satisfied by `n/a` when the defect lives entirely inside this
repository and makes no claim about how Infrahub behaves. That is not the same
as `UNVERIFIED`, which means there was a claim and no rung could check it.

## Deriving the default branch

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
[ -z "$DEFAULT_BRANCH" ] && DEFAULT_BRANCH=$(git remote show origin 2>/dev/null | sed -n 's/.*HEAD branch: //p')
[ "$DEFAULT_BRANCH" = "(unknown)" ] && DEFAULT_BRANCH=""
DEFAULT_BRANCH=${DEFAULT_BRANCH:-main}
git fetch origin "$DEFAULT_BRANCH" || { echo "Cannot fetch origin/$DEFAULT_BRANCH"; exit 1; }
git rev-parse "origin/$DEFAULT_BRANCH"
```

Shell state does not persist between separate Bash calls, so re-derive this in
any snippet that needs it.
