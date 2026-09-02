---
title: Cardinality Is a Data Constraint, Not Only a Shape
impact: HIGH
tags: relationship, cardinality, max_count, migration, write-time
---

## Cardinality Is a Data Constraint, Not Only a Shape

Impact: HIGH

`cardinality: one` declares a shape *and* caps how many
peers **you** may hold through that identifier. The cap
that stops several objects pointing at one peer is the
same declaration read from the other side, so it lives on
the *peer's* relationship, not yours. Either way it is
enforced at **write** time, not at
`infrahubctl schema check`, so it only fires when the
second writer arrives.

### Why it matters

[relationship-defaults.md](relationship-defaults.md) is
thorough on the other direction: you wrote a singular
field name, forgot `cardinality:`, got `many`, and the UI
shows a multi-select. Correct advice, with an unstated
consequence. Setting `one` on anything singular also
declares a data constraint, and being wrong about it
fails in production on the second object rather than in
the UI on the first.

For a relationship like `rack` on a device the cap is
obviously intended. For a relationship that reads
singularly *today* because the workflow happens to be
one-to-one today, `one` quietly encodes an assumption a
later feature has to migrate out of.

### Which side actually caps

This is the part that is easy to get backwards.

**Your `cardinality: one` limits how many peers *you*
hold.** What limits how many objects may point *at* a
peer is that **peer's own** relationship on the same
identifier being `cardinality: one`.

```yaml
# Service holds at most one Wavelength...
- name: Service
  namespace: Net
  relationships:
    - name: wavelength
      peer: NetWavelength
      cardinality: one          # caps what Service holds
      identifier: service__wavelength

# ...and THIS is what stops two Services sharing one Wavelength.
- name: Wavelength
  namespace: Net
  relationships:
    - name: service
      peer: NetService
      cardinality: one          # caps what points AT a Wavelength
      identifier: service__wavelength
```

If the peer declares nothing on that identifier, there is
**no inbound cap at all**.

The failure names the identifier and the count:

```text
Node <id> has 2 peers for service__wavelength, maximum of 1 allowed
```

`min_count` gives the mirror on delete:

```text
Node <id> has 0 peers for service__wavelength, no fewer than 1 allowed
```

### Widening your own side is not enough

The direct consequence of the above, and the trap:
changing `Service.wavelength` to `cardinality: many`
while `Wavelength.service` stays `one` **loads cleanly
and does not remove the cap.** The second service still
fails at write time, because the cap was never on the
Service side.

To let several services share one wavelength you must
widen the **Wavelength** side.

### Before you set `one`, ask which kind of singular it is

> Is this relationship singular **by nature**, or singular
> **by current workflow**?

A wavelength that carries one circuit today may carry
several tomorrow. Being wrong in the `many` direction
shows up in the UI on the first object; being wrong in
the `one` direction shows up in production on the second.

### Migrating `one` to `many`

Widening migrates cleanly: `schema check` reports the
diff, the load is accepted, existing data survives. Two
things to know:

**Keep the singular name in the widening change.**
Renaming to a plural in the same edit does *not* work when
the old declaration is still loaded, which is the ordinary
in-place `infrahubctl schema load`. Infrahub then sees the
old and new names as two relationships sharing one
identifier in one direction and rejects the load:

```text
NetService: Identifier of relationships must be unique for a given direction >
'service__wavelength' : [('wavelength', 'bidirectional'), ('wavelengths', 'bidirectional')]
```

The message lists both names, which is the clue.

Renaming is still possible, just not in the same step:
drop the old declaration with `state: absent`, load, then
re-add it under the new name with the same identifier. See
[relationship-identifiers.md](relationship-identifiers.md).
That is a second load and a second query migration, so
most widenings simply keep the singular name. A singular
name on a `many` relationship looks like an oversight
forever unless a comment explains it. Write the comment.

**`max_count` must not be 1 on a `many` relationship:**

```text
NetService: Relationship 'wavelengths' max_count must be 0 or greater than 1 when cardinality is MANY
```

Use `cardinality: one` for a genuine cap of one; `many`
with `max_count: 0` means unbounded.

### Any stored query that selects the field is part of the change

This section owns three cases, not one: **widening a
cardinality, removing a field, and retyping a field.**
Every stored query that selects the field is invalidated
by all three, and nothing in the schema tooling says so.

Cardinality is the least obvious of the three, because
cardinality selects the GraphQL selection shape, so
widening one is a **query migration as well as a schema
migration**.

#### Nothing fails at the step you made the change in

`schema check` passes. `schema load` passes. The break
appears one command later, in a subsystem that does not
mention the field. Which failure you get depends only on
whether the `.gql` file itself changed:

| The `.gql` file | Where it fails |
| --------------- | -------------- |
| unchanged | the stored query stays in place and fails **at execution**, whenever something next runs it |
| changed, or the repository re-imported from scratch | **at repository import**, because creating the query object validates the text against the live schema: `Query is not valid, …` |

The import-time failure names **the query**, not the
schema change that invalidated it, so a
destroy-and-reload cycle can fail twice before the cause
is found.

#### Find every affected query first

Run this before loading the change, not after:

1. Resolve the query files from `.infrahub.yml`. Every
   `file_path` under `queries:` is a stored query; there
   is no guarantee they all sit under `queries/`.
2. Search those files for the relationship name, then
   search `checks/`, `transforms/` and `generators/` for
   it as well. GraphQL written inline in Python is never
   imported as a stored query, so it never fails at
   import; it just returns nothing at runtime.
3. Migrate each hit between `{ node { … } }` and
   `{ edges { node { … } } }`.
4. Dry-run each hit. See
   [../../infrahub-common/rules/deployment-gql-dry-run.md](../../infrahub-common/rules/deployment-gql-dry-run.md)
   for the command per transform type.

[../../infrahub-common/graphql-queries.md](../../infrahub-common/graphql-queries.md)
carries the two selection shapes and the
`NestedEdged<Kind>` / `NestedPaginated<Kind>` error
strings the server prints.

### Common mistakes

- Reading `cardinality: one` as purely cosmetic. It is a
  write-time constraint.
- Expecting `schema check` to catch it. The schema is
  valid; the constraint is on the data.
- Widening the wrong side and concluding the cap is not
  cardinality-related.
- Renaming to a plural in the same change as the
  widening. Rename in a separate step instead: `state:
  absent` on the old declaration, load, then re-add.
- Loading the schema change without migrating the queries
  that select the relationship.

Related:
[relationship-defaults.md](relationship-defaults.md),
[validation-common-errors.md](validation-common-errors.md).

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
