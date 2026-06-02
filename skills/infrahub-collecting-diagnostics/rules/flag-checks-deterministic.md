---
title: Flag checks are deterministic pattern matches, not diagnoses
impact: HIGH
tags: flag-checks, deterministic, hints
---

## Flag checks are deterministic pattern matches, not diagnoses

Impact: HIGH

Flag checks emit hints to `flags.yml`. They are pure
pattern matches over collected files — `grep`, `jq`,
`yq` — never LLM-judged narratives. Each entry
points the expert at concrete evidence and stops
there.

### Why it matters

The collector is not the debugger. An LLM-summarized
"I think the problem might be a multi-worker git
race because the symptoms look like #9036" reads
plausibly but routinely points at the wrong root
cause: the expert then wastes time disproving a
confident-sounding guess. Deterministic checks
either fire on observable evidence or they do not.
The expert chooses what to make of a hit.

### What to do

Run the catalog from `flag-checks.md` against the
collected files. For each match, write one entry to
`flags.yml` with this shape:

```yaml
- id: <check-id>             # from the catalog
  severity: info | warning   # only these two values
  evidence:
    file: baseline/logs/task-worker-1.log
    line: 4521
    excerpt: "CommitNotFoundError: ..."
  related_issues: [9036, 8930]
  hint: "Multi-worker git race; expert should check ..."
```

Every entry must include `id`, `severity`,
`evidence` (with `file`, `line`, `excerpt`),
`related_issues` (list, may be empty), and `hint`
(one short sentence — never a claim of diagnosis).

Hits are reported once per pattern per file. If a
pattern catches no evidence, do not write an entry —
silence is a valid result. `flags.yml` must always
exist; if nothing fired, the file content is `[]`.

The catalog is run inline by the AI using shell
tools: `grep -nE`, `jq`, `yq`, `awk`. No
LLM-judgement step is allowed in between the match
and the emitted entry.

### Compliant

```yaml
# bundle/flags.yml
- id: commit-not-found
  severity: warning
  evidence:
    file: baseline/logs/infrahub-task-worker-1.log
    line: 4521
    excerpt: "CommitNotFoundError: Commit abc123 not found with GitRepository"
  related_issues: [9036, 8930]
  hint: "May indicate multi-worker git race; check whether the other workers logged the same commit succeeding."
```

### Non-compliant

```yaml
# bundle/flags.yml
- id: probable-root-cause
  severity: critical                 # not an allowed severity
  hint: |
    I think the problem is a race condition between
    task-worker-1 and task-worker-2 because the
    timing of the CommitNotFoundError suggests they
    both tried to clone at the same time. The fix
    is probably to set worker concurrency to 1.
  # no evidence pointer, no related_issues
```

### Common mistakes

- Letting the AI summarize across multiple log
  lines into a narrative. The evidence pointer
  must reference a single file and line; multi-line
  context goes in the `excerpt`, not in a
  paraphrased hint.
- Using severities other than `info` and
  `warning`. There is no `critical`, no `error`,
  no `debug` — the expert assigns severity
  themselves.
- Adding a check inline without registering it in
  `flag-checks.md`. New flags belong in the
  catalog so the next bundle reviewer knows the
  set.
- Skipping `flags.yml` when nothing fired. The
  file must exist (`[]`) so the expert knows the
  catalog ran.
