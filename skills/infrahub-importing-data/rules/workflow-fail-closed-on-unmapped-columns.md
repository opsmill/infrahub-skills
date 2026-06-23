---
title: Fail Closed on Unmapped Columns
impact: CRITICAL
description: >-
  If any CSV column has no schema home, stop emission entirely, list the
  offending columns plus the kinds checked, and hand off to
  infrahub-managing-schemas. Never silent-drop, never partial-write.
tags: workflow, fail-closed, schema-gap, escalation
---

## Fail Closed on Unmapped Columns

Impact: CRITICAL

If any CSV column has no schema home — no
attribute, no relationship, no component child —
stop emission entirely. List the offending columns,
list the kinds the skill checked, point the user at
`infrahub-managing-schemas`, and exit. **No partial
writes.**

### Why it matters

Silently dropping an unmapped column "succeeds"
the import while baking a data-quality gap into the
source of truth. A visible failure with a clear
list of what's missing is faster to recover from
than data that's quietly incomplete.

Partial writes (some files emitted, others skipped)
leave the branch in a mixed state. Either the
mapping is complete or no file is written.

Schema changes are a separate manual decision via
[../../infrahub-managing-schemas/SKILL.md](../../infrahub-managing-schemas/SKILL.md).

### What to emit on failure

A structured report the user can act on:

```text
Cannot import: 2 columns have no schema home.

Unmapped columns:
  - inventory.csv: gpu_count          (checked DcimDevice, no matching attribute)
  - inventory.csv: license_tier       (checked DcimDevice, no matching attribute or dropdown)

Schemas checked: DcimDevice, OrganizationManufacturer, LocationSite.

To unblock this import, add the missing attributes
to the DcimDevice schema. See:
  - skills/infrahub-managing-schemas/SKILL.md
  - Then re-run this skill against the same CSV.

No files have been written.
```

### Common mistakes

- **Inventing an attribute name to make the
  mapping work.** That's a schema edit by stealth.
  Stop and report instead.
- **Dropping the column with a comment.** "Skipped
  because no match" silently loses data. The
  failure must surface to the user, not the log.
- **Emitting the files that do map and asking the
  user to fix the rest manually.** That's the
  partial-write state the rule exists to prevent.

### Edge case: the user explicitly says "skip this column"

The interview ([workflow-up-front-interview.md](./workflow-up-front-interview.md))
is the only place a column can be marked skipped.
The skill surfaces every unmapped column there
first; the user picks "skip" deliberately. Only
then does the column not block emission.

### Rationalizations — and why they don't hold

| Rationalization | Reality |
| --------------- | ------- |
| "I'll emit the columns that map and flag the rest for later." | Partial writes leave the branch in a mixed state. Either the mapping is complete or no file is written. |
| "`gpu_count` is obviously a counter — I'll just add the attribute." | That's a schema edit by stealth. Schema decisions route through `infrahub-managing-schemas`, never through the importer. |
| "The column is mostly empty, so dropping it is harmless." | Fill rate is irrelevant. Empties are decided by `optional` / `default_value` (see [mapping-empty-and-null.md](./mapping-empty-and-null.md)); an unmapped column is unmapped no matter how sparse. |
| "Server validate will catch it." | Validate only runs on a branch and only reports schema-resolution errors. A silently dropped column resolves cleanly and ships incomplete. |

### Red flags — stop and emit the report

- About to write some files but not others.
- About to invent an attribute name or dropdown choice to force a mapping.
- About to add a `# skipped: no match` comment instead of reporting the column.
- About to tell the user "I imported most of it."

Any of these means: stop, emit the unmapped-columns report above, and write nothing.

Reference: [Infrahub Docs](https://docs.infrahub.app)
