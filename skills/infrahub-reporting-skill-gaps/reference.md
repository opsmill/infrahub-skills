# Evidence Reference

Read this in step 1 of the workflow, before gathering
any evidence.

## Evidence sources

Consult sources in this order. Stop as soon as one
gives enough evidence to describe the friction.

| Priority | Source | When to use |
| -------- | ------ | ----------- |
| 1 | Current conversation | Always the first source. Most friction reports come from the session already in progress |
| 2 | A past session log | Optional. Only when the user points at one. See Transcript discovery below |

There is no third source, and no local record of past
reports. The shared record is the issue tracker, read
in step 2; see
[rules/workflow-tracker-first.md](rules/workflow-tracker-first.md).

Two things are **not** evidence sources. An assistant's
own memory or context files (`MEMORY.md`, `CLAUDE.md`,
`AGENTS.md`, and their equivalents) are self-authored
notes, so citing them proves only that the model wrote
something down, not that a rule failed. And a local
draft of an earlier report is not corroboration of
itself. Evidence comes from the ladder in
[rules/evidence-detection-ladder.md](rules/evidence-detection-ladder.md),
and the tracker is what carries a report across
sessions.

## Transcript discovery

Where session logs live is specific to the assistant
running this skill, and no format among them is a public
API. So do not derive a path from an assumed layout.
Instead, in this order:

1. Use the current conversation. It needs no discovery
   and is the source for nearly every report.
2. If the user points at a past session, ask them for
   the file or directory unless you already know where
   your own runtime writes session logs.
3. If you do know, search across all of that
   directory's project folders rather than one derived
   path: a single repo spread over worktrees or clones
   produces many folders, and a term from the friction
   is the cheaper key. On Claude Code, for example, the
   logs are line-delimited JSON under
   `~/.claude/projects/`:

   ```bash
   grep -rl "<term from the friction>" ~/.claude/projects/*/*.jsonl 2>/dev/null | head
   ```

If a log cannot be found or parsed, skip it, fall back
to the current conversation, and say so to the user
plainly. Do not guess at a schema that may no longer
apply. A missing transcript is never a reason to stop:
this step is a convenience for finding a session the
user already remembers.

Friction shows up in a session log as:

- a verifier that failed and later passed on the same
  target: `infrahubctl schema load`, `schema validate`,
  `object load`, `check run`, `transform run`, or a
  `pytest` run of a check's or transform's tests
- `tool_result` blocks carrying `is_error`, two or more
  on the same tool and target
- three or more edits to one artifact inside a single
  task
- repeated user turns restating the same ask in
  different words, or correcting the previous answer
- fetches of `docs.infrahub.app`, `llms.txt`, or
  `schema.infrahub.app` after the relevant skill file
  was already read
- four or more rule files read before the first edit,
  which points at discoverability rather than coverage

The first entry is a verdict; the rest are counters.
Only the verdict, paired with a coverage read of the
skill's `rules/`, establishes that a gap exists. The
counters say where to look. See
[rules/evidence-detection-ladder.md](rules/evidence-detection-ladder.md)
for the full ladder and the thresholds' role in it.

A fetch of `llms.txt` or a `docs.infrahub.app` page is
an escape marker, not just friction: it points away from
a bug, because the fallback rule in
[workflow-information-priority.md](../infrahub-common/rules/workflow-information-priority.md)
only authorizes it once the skill's own files were
checked and found silent. What matters beyond that is
**what happened after the fetch**: an escape that found
the answer points at a feature; an escape that still
failed to answer the question points at a docs gap, and
only once the underlying behavior is settled; and no
escape at all defaults to feature with the docs status
left unverified. The kind is what routes the report, and
the receiver resolves that; this skill names no
destination. See
[rules/workflow-bug-vs-feature.md](rules/workflow-bug-vs-feature.md)
for the full three-way reading and the settled-behavior
gate.

Fetches of `marketplace.infrahub.app` and
`infrahub.opsmill.io` are **not** friction. Several
skills instruct fetching those URLs as part of their
normal workflow (marketplace reuse, live data
analysis). Do not flag them.
