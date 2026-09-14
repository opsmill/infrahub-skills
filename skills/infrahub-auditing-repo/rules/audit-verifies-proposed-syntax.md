---
title: audit-verifies-proposed-syntax
impact: HIGH
tags: audit, conduct, evidence, findings
---

# Rule: audit-verifies-proposed-syntax

**Severity**: HIGH
**Category**: Conduct

## What It Checks

Every finding that proposes a GraphQL filter, a schema
field, or a config key resolves it against the version
under audit and records how, in a `verified_against`
field. A finding that moves a validation into the
schema also shows that the new constraint accepts
everything the old one accepted.

## Why it matters

A proposed fix reads the same whether it was verified
or inferred, so an implementer has no way to tell them
apart and will not re-derive one that sounds confident.

Three defects have been observed from this, in one
audit. A plural dropdown filter was described as "the
same form the sibling query uses" when the sibling
demonstrated only the singular filter; the plural
happened to exist, so the guess was never punished.
Numeric range filters (`__gte` / `__lte`) were proposed
to push a count to the server, and they do not exist in
that version at all: for every attribute type the
filter generator emits only the singular value, the
plural values, an isnull boolean, node-property ids and
flag booleans. The recommended call would have failed at
runtime.

The third is the dangerous one. A regex constraint was
proposed to move an invariant out of a Python check,
and the pattern was narrower than the check it
replaced: it dropped an optional prefix group the check
deliberately tolerated for imported data. A schema
regex enforces on every write. The repository's own
generator emits values that satisfy the narrowed
pattern, so it would have passed the test dataset and
rejected tens of thousands of nodes of imported
production data. No amount of testing against the test
dataset could have caught it.

## Checks

1. **Resolve the syntax from the audited version's own
   models**, not from the published docs and not from
   recall. The docs describe the current release, which
   is not necessarily the release under audit, so they
   cannot settle the question either way. This is the
   discipline
   [validation-string-limits](../../infrahub-managing-schemas/rules/validation-string-limits.md)
   already applies to cap values.
2. **Record how it was verified** in
   `verified_against`, naming the artifact introspected
   (for example, the filter generator in the pinned
   image) and the version it came from.
3. **"Same form as the sibling" is not verification.**
   A sibling demonstrating the singular form is
   evidence for the singular form and nothing else.
4. **The harness's own SDK is not authoritative.** The
   server parses its repository config with its own
   vendored copy, so the version that decides is the
   one in the image being audited.
5. **A validation moved into the schema is shown, not
   asserted, to be equivalent.** Take the replaced
   pattern verbatim from the code being replaced rather
   than transcribing it, and compare old against new
   across accept and reject cases. State the comparison.
   Passing the test dataset is not evidence: generated
   data satisfies a narrowed pattern that imported data
   does not.
6. **A finding that cannot verify its own proposal says
   so and downgrades**, rather than presenting an
   unverified fix in a verified voice. `verified_against`
   records the failure to verify; it is not a field to
   fill with a guess.
7. **Unverified syntax stays out of the replacement
   entirely, hedged or not.** Saying so in
   `verified_against` and then putting the unconfirmed
   filter in the fix ships the same broken call: the
   replacement is the field an implementer copies, and a
   "this may exist" qualifier does not survive the copy.
   Either the replacement holds syntax that was verified,
   or it holds the recommendation to leave the code
   alone. Name the unconfirmed option in the finding's
   description if it is worth chasing later.

## Example

```json
{
  "rule": "yagni-redundant-check-that-graphql-can-answer",
  "severity": "MEDIUM",
  "ladder_step": 6,
  "file": "checks/check_interface_count.py",
  "line": "18",
  "replacement": "DcimInterface(role__values: [\"uplink\", \"peer\"]) { count }",
  "verified_against": "attribute filter generator, infrahub 1.11.1 pinned image"
}
```

And the honest form when the check could not be run.
Right:

```json
{
  "replacement": "Keep the Python check. No server-side count filter was confirmed for this version.",
  "verified_against": "not verified: the pinned image was unavailable, so no server-side filter is proposed"
}
```

Wrong, and the commoner mistake, because the disclosure
reads as diligence:

```json
{
  "replacement": "DcimInterface(count__gte: 48) { count } (if this version supports range filters)",
  "verified_against": "not verified: the pinned image was unavailable"
}
```

The parenthetical is gone the moment someone pastes the
query.

## Common Issues

- A filter proposed on the strength of a sibling query
  that demonstrates a different filter
- `__gte` / `__lte` and other range filters proposed
  where the version emits none
- A schema regex narrower than the Python check it
  replaces, validated only against generated data
- Syntax confirmed against the published docs when the
  audited version is older
- Config keys confirmed against the local SDK rather
  than the server's vendored copy
- An unverified proposal carrying the same severity and
  the same tone as a verified one
