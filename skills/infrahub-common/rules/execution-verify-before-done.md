---
title: Verify Before Declaring a Task Complete
impact: HIGH
tags: execution, discipline, verification, infrahubctl, schema-check, protocols
---

## Verify Before Declaring a Task Complete

Impact: HIGH

Infrahub artifacts fail in quiet ways: a schema parses as
YAML but fails `infrahubctl schema check`; a check file
imports a protocol that was never regenerated; a
generator references a relationship identifier that
exists only on one side. "The code looks right" is not a
finish line. Every artifact type has a concrete command
that exercises it -- use it before reporting done.

### Verification by Artifact Type

| Artifact | Minimum check |
| -------- | ------------- |
| Schema (YAML in `schemas/`) | `infrahubctl schema check schemas/` -- parses, validates, reports missing peers and bad identifiers |
| Objects (YAML data) | `infrahubctl object load --dry-run <file>` against a branch, or load into a scratch branch |
| Checks / Generators / Transforms | Protocols regenerated (`infrahubctl protocols generate --schema-dir schemas/`), Python imports resolve, unit test or `infrahubctl` dry-run succeeds |
| `.infrahub.yml` changes | `infrahubctl` picks up the registered artifact without error |
| Menu YAML | Loads via `infrahubctl menu load` (or equivalent) without validation errors |

### When Tooling Is Unavailable

If the environment does not expose `infrahubctl`, a
running Infrahub instance, or network access:

- Say so explicitly in the response -- do not claim the
  artifact is verified
- Do the checks you *can* do offline: YAML parses,
  relationship identifiers match on both sides, peer
  `kind` references resolve within the file, protocols
  referenced in Python exist in `generated/`
- List what the user should run before committing

### Goal-Driven Shape

Where a workflow has multiple steps, attach a verify line
to each:

```text
1. Update schema node  -> verify: infrahubctl schema check
2. Regenerate protocols -> verify: generated/ diff reviewed
3. Update the check     -> verify: import resolves, unit test passes
```

This makes it easy for the user (and the next AI run) to
see where the work actually stopped.

### Anti-Patterns

- "Schema looks correct" with no command run
- Regenerating protocols and committing without reading
  the diff -- silent field removals slip through
- Claiming a check "should work" without importing it
- Marking a task done after writing the code but before
  loading or validating it

### Prevention

Before writing the final "done" message, list the
verification commands you actually ran and their results.
If the list is empty, run something first. If you
couldn't run anything, state that and hand the commands
to the user.
