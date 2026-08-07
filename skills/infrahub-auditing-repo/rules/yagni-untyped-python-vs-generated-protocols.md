---
title: yagni-untyped-python-vs-generated-protocols
impact: LOW
ladder_step: 7
tags: audit, yagni, protocols, generators, transforms, checks, type-safety
---

# Rule: yagni-untyped-python-vs-generated-protocols

**Severity**: LOW
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 7 — Can a generated protocol class type it at author time?

## What It Checks

Non-trivial, schema-coupled Python (generators, transforms, checks) that
passes a bare string `kind` to the SDK — `client.create/get/all/filters/count`
with `kind="DcimDevice"` (or the kind as a positional string) — or hand-builds
node payloads as untyped dicts, when a generated protocol class for that kind
is available. Importing the class and passing it instead gives dev-time type
checking and autocomplete, so a later schema change surfaces as a type error
on the exact line rather than a runtime failure in the pipeline.

## Why it matters

The official SDK guidance is explicit: whenever you specify the kind of object
as a string, you can use the corresponding protocol instead. A bare-string
`kind` returns an untyped node — every `.attribute.value` access is unchecked,
and a renamed or retyped attribute compiles fine and fails only at runtime,
deep in a proposed-change pipeline or a failed artifact generation. With the
generated class, the type checker turns that same schema drift into a list of
errors pointing at the exact lines to fix. The cost of *not* adopting
protocols is paid later, and in a worse place.

## Checks

1. `client.create/get/all/filters/count` called with a string-literal kind
   (`kind="Foo"` or a positional `"Foo"`) for a kind that has a generated
   protocol class available — a repo module (`protocols.py`,
   `schema_protocols.py`, a `*_sync.py` / `*_async.py` protocols file) or
   `infrahub_sdk.protocols`.
2. Node payloads hand-built as untyped `dict`s and passed to `create` /
   `update` instead of constructed against a protocol class.
3. Multiple such call sites, or one file reading/writing many attributes or
   several kinds — i.e. non-trivial schema-coupled Python, not a one-off.

## What NOT to flag

- Relationship-only access — generated protocols type attributes, not
  relationship peers (`RelatedNode` / `RelationshipManager` carry no peer
  type). Do not claim protocols would type `.interfaces`.
- Trivial one-offs: a script touching a single kind and one or two attributes.
  Adopting protocols there is itself over-engineering.
- Code already importing and passing protocol classes — including SDK-provided
  core protocols (`from infrahub_sdk.protocols import CoreIPPrefixPool`); that
  is the target pattern, not a violation.
- A second, trimmed protocol module kept deliberately (e.g. a generator that
  runs inside Infrahub and cannot import the repo package).
- Repos with no managed schema, or no Python artifacts.

## Common Issues

- `await client.create(kind="IpamIPAddress", address=...)` in a generator that
  already imports and uses other protocol classes — drop the quotes:
  `from ...protocols import IpamIPAddress` then
  `await client.create(IpamIPAddress, address=...)`.
- A transform fetching `client.filters(kind="NetworkLink", ...)` and reading
  many untyped `["value"]` fields, when `NetworkLink` is already generated.
- Untyped `dict` payloads assembled field-by-field for `create`, losing every
  attribute-name and optionality check the protocol class would enforce.

## Related

- [protocols-adopt-typed-kinds](../../infrahub-common/rules/protocols-adopt-typed-kinds.md)
  — how to generate and adopt protocols (the authoring half).
- [protocols-generated](../../infrahub-common/rules/protocols-generated.md)
  — generated files are build artifacts; regenerate, don't hand-edit (the
  maintenance half).
