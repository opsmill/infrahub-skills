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

- **Part A**, at key derivation, when the input carries an issue number. Set
  `ISSUE` and leave `TARGETS` empty.
- **Part B**, as soon as the stage has named the files it will change. Set
  `TARGETS` to their path prefixes (`skills/<skill>/`, `graders/<skill>/`,
  `scripts/<file>`, `.agents/skills/<skill>/`), and keep `ISSUE` if there is
  one.

It prints open PRs, and merged PRs whose merge commit is not in `HEAD` yet,
that close `ISSUE`, name `#ISSUE` in their title or body, or change a file
under `TARGETS`. Closed, unmerged PRs are left out.

The search is complete, not a sample. It keeps doubling `--limit` until `gh`
returns fewer PRs than it asked for, so an old PR is not dropped for being
past the first page. Merged PRs are narrowed on the server to those merged
since the date of this branch's base commit on the default branch, because
anything merged earlier is already in `HEAD`. Without a local
`origin/<default branch>` it reads every merged PR instead. It needs no
fetch: a merge commit missing from the local repository is not in `HEAD`
either.

```bash
ISSUE="<issue number, or empty>"
TARGETS="<space-separated path prefixes, or empty>"
TARGETS_JSON=$(printf '%s\n' $TARGETS | jq -R 'select(length > 0)' | jq -cs .)
MATCH="(\"$ISSUE\" != \"\" and (any(.closingIssuesReferences[]; .number == ${ISSUE:-0}) or (((.title // \"\") + \" \" + (.body // \"\")) | test(\"(^|[^0-9A-Za-z])#${ISSUE:-0}([^0-9A-Za-z_]|\$)\")))) or ([.files[].path] | any(. as \$p | $TARGETS_JSON | any(. as \$t | \$p | startswith(\$t))))"
FIELDS=number,title,body,headRefName,closingIssuesReferences,files,mergeCommit
# Every PR in a state: double --limit until gh returns fewer than it was asked for.
all_prs() {
  local state=$1 limit=100 json
  shift
  while :; do
    json=$(gh pr list --state "$state" --limit "$limit" "$@" --json "$FIELDS") || return 1
    [ "$(printf '%s' "$json" | jq length)" -lt "$limit" ] && { printf '%s' "$json"; return 0; }
    limit=$((limit * 2))
  done
}
# A PR merged before this branch's base commit is already in HEAD.
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
BASE=$(git merge-base HEAD "origin/${DEFAULT_BRANCH:-main}" 2>/dev/null)
SINCE=${BASE:+--search merged:>=$(TZ=UTC git log -1 --date=format-local:%Y-%m-%d --format=%cd "$BASE")}
OPEN=$(all_prs open) && MERGED=$(all_prs merged $SINCE) \
  || { echo "SEARCH FAILED: gh pr list did not complete, so nothing was searched"; exit 1; }
printf '%s' "$OPEN" | jq -r ".[] | select($MATCH) | \"#\(.number)\topen\t\(.headRefName)\t\(.title)\""
printf '%s' "$MERGED" | jq -r ".[] | select($MATCH) | \"\(.number)\t\(.mergeCommit.oid)\t\(.headRefName)\t\(.title)\"" |
  while IFS=$'\t' read -r n sha ref t; do
    git merge-base --is-ancestor "$sha" HEAD 2>/dev/null || printf '#%s\tmerged, not in HEAD\t%s\t%s\n' "$n" "$ref" "$t"
  done
```

No output and exit status 0: record `Duplicate check: none found` and
continue.

`SEARCH FAILED`, or any other non-zero exit: nothing was searched. Report the
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
