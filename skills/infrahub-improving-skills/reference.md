# Evidence and Notes Reference

Read this in step 1 of the workflow, before gathering
any evidence.

## Evidence sources

Consult sources in this order. Stop as soon as one
gives enough evidence to corroborate the friction.

| Priority | Source | When to use |
| -------- | ------ | ----------- |
| 1 | Current conversation | Always the first source. Most friction reports come from the session already in progress |
| 2 | `~/.claude/projects/<slug>/*.jsonl` | When the user points at a past session. See Transcript discovery below |
| 3 | Notes file (`~/.infrahub-skills/improving/notes.jsonl`) | To check for a prior `observed` note on the same signature, not as primary evidence |

The transcript format under `~/.claude/projects/` is
not a public API. It can change without notice between
Claude Code releases. If a transcript file cannot be
parsed, fall back to the current conversation and say
so to the user plainly. Do not guess at a schema that
may no longer apply.

## Transcript discovery

The project slug is the working directory path with
every `/` replaced by `-`. To list the most recent
sessions for the current project:

```bash
ls -t ~/.claude/projects/"$(pwd | tr '/' '-')"/*.jsonl 2>/dev/null | head -10
```

Friction shows up in a transcript as:

- `tool_result` blocks carrying `is_error`
- repeated user turns restating the same ask in
  different words
- fetches of `docs.infrahub.app` or
  `schema.infrahub.app` after the relevant skill file
  was already read

Fetches of `marketplace.infrahub.app` and
`infrahub.opsmill.io` are **not** friction. Several
skills instruct fetching those URLs as part of their
normal workflow (marketplace reuse, live data
analysis). Do not flag them.

## Notes file

Location: `~/.infrahub-skills/improving/notes.jsonl`.

Append-only. One JSON object per line. Fields:

| Field | Meaning |
| ----- | ------- |
| `ts` | ISO 8601 timestamp of the note |
| `skill` | The Infrahub skill directory implicated, e.g. `infrahub-managing-schemas` |
| `signature` | A short fingerprint of the friction, for matching against future occurrences |
| `transcript_path` | Path to the session transcript this note was drawn from, if any |
| `status` | One of `observed`, `filed`, `skipped`, `deferred` |

`signature` exists only to help a later session
recognize a recurring pattern quickly. It is not a
substitute for evidence. When drafting an issue,
always re-read `transcript_path` rather than trusting
the signature alone. A matching signature does not
guarantee the underlying cause is the same.
