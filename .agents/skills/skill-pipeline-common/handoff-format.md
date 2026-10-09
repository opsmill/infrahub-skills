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
**Duplicate check:** <each matching PR with the user's choice and reason, or: none found>

**Target:** skills/<skill>/ | graders/<skill>/ | scripts/
**Rule path:** `skills/<skill>/rules/<category>-<concern>.md` (or: none, edits <existing file>)
**Grader:** `<check name in CHECKS>` parsing `<artifact>` (or: reuses `<existing check>`)
**Eval task:** `<task name>` (or: rides `<existing task>`)

### Root cause / Design brief

<track specific body>

### Test plan

<what the failing test asserts, which surface it lives on, and the four fixtures:>

- compliant: <sketch>
- compliant variant: <sketch, refactored the way the check's traversal is vulnerable to>
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
`Defect class`, `Minimum change rung`, `Docs impact`, `Duplicate check`,
`Sweep terms`, or a non-empty `Test plan`. Find one missing, name it, and stop
there rather than guessing a value forward.

`Docs impact` and `Sweep terms` are both satisfied by `none`, and `Duplicate
check` by `none found`. An entrance that looked and found nothing has
answered; an entrance that never looked has not, and the two are
indistinguishable once the field is blank.

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

## Searching for existing pull requests

Before an entrance stage writes a root cause or a design brief, it searches
for a pull request that already covers the change. The pipeline's other PR
lookups, `gh pr list --head "$BRANCH"`, only find a PR on the pipeline's own
branch. A PR opened by hand, by someone else, or by a run with a different
slug is invisible to them, and the same change gets built twice.

The search runs in two parts, because the stage learns its inputs at two
different points:

- **Part A**, at key derivation, when the input carries an issue number. Pass
  `--issue` and no `--target`.
- **Part B**, as soon as the stage has named the files it will change. Pass a
  `--target` for each path prefix (`skills/<skill>/`, `graders/<skill>/`,
  `scripts/<file>`, `.agents/skills/<skill>/`), and keep `--issue` if there
  is one.

Run the search script from the repository root:

```bash
uv run python .agents/skills/skill-pipeline-common/scripts/find_existing_prs.py \
  --issue "<issue number>" --target "<path prefix>" --target "<another path prefix>"
```

Leave out `--issue` when there is no issue number, and `--target` when no
files are named yet. It prints one line per open PR, and per merged PR whose
merge commit is not in `HEAD` yet, that closes the issue, names `#<issue>` in
its title or body, or changes a file under a target. Closed, unmerged PRs are
left out. The search reads every PR, not the newest page, and the full file
list of large PRs; the script's docstring states exactly what it checks.

No output and exit status 0: record `Duplicate check: none found` and
continue.

`SEARCH FAILED` and exit status 1: nothing was searched. Report the
error and stop. Never record `none found` for a search that did not run,
because the next stage cannot tell the two apart.

Any output: list each PR with its number, title, branch, state, and whether
the issue or a file matched, then stop and ask the user to choose one of:

- stop the pipeline here;
- continue on that PR's branch instead of `ai-skill-pipeline-<key>`;
- continue on a new branch, with a one-line reason the PR does not duplicate
  this change.

Do not choose for them. A file match is often a PR doing different work in
the same files, and only the user can tell overlap from duplication. Record
each PR and the choice in `Duplicate check`.
