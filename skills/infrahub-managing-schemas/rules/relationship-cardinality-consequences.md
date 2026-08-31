---
title: Cardinality Is a Data Constraint, Not Only a Shape
impact: HIGH
tags: relationship, cardinality, max_count, migration, write-time
---

## Cardinality Is a Data Constraint, Not Only a Shape

Impact: HIGH

`cardinality: one` declares a shape *and* caps how many
objects may hold that peer through that identifier. The
cap is enforced at **write** time, not at
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

**Keep the singular name.** Renaming the relationship to
a plural at the same time does *not* work. Infrahub reads
the old and new names as two relationships sharing one
identifier and rejects the load:

```text
NetService: Identifier of relationships must be unique for a given direction >
'service__wavelength' : [('wavelength', 'bidirectional'), ('wavelengths', 'bidirectional')]
```

The message lists both names, which is the clue. So a
widened relationship keeps its singular name, and that
looks like an oversight in the schema file forever unless
a comment explains it. Write the comment.

**`max_count` must not be 1 on a `many` relationship:**

```text
NetService: Relationship 'wavelengths' max_count must be 0 or greater than 1 when cardinality is MANY
```

Use `cardinality: one` for a genuine cap of one; `many`
with `max_count: 0` means unbounded.

### It also breaks every existing query

Cardinality selects the GraphQL selection shape, so
widening one is a **query migration as well as a schema
migration**. Grep `queries/` for the relationship name
before loading the change. See
[../../infrahub-common/graphql-queries.md](../../infrahub-common/graphql-queries.md),
which carries the two shapes and the error strings.

### Common mistakes

- Reading `cardinality: one` as purely cosmetic. It is a
  write-time constraint.
- Expecting `schema check` to catch it. The schema is
  valid; the constraint is on the data.
- Widening the wrong side and concluding the cap is not
  cardinality-related.
- Renaming to a plural in the same change as the
  widening.
- Loading the schema change without migrating the queries
  that select the relationship.

Related:
[relationship-defaults.md](relationship-defaults.md),
[validation-common-errors.md](validation-common-errors.md).

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
