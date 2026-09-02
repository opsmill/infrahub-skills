---
title: order_by Resolves Against the Declaring Schema Only
impact: MEDIUM
tags: display, order_by, generics, inheritance
---

## order_by Resolves Against the Declaring Schema Only

Impact: MEDIUM

`order_by` on a generic resolves only against fields
that generic itself declares. Naming an attribute the
inheriting kinds all have, but the generic does not
declare, is rejected at schema load.

### Why it matters

A generic that exists as a cross-kind query surface is
exactly the case where you want listings ordered by
something the concrete kinds share, and that is the case
that fails. Nothing in the property's name or
description hints at the scope, so it costs a load cycle
to discover, and the obvious workaround (add the
attribute to the generic purely to satisfy the
constraint) changes the data model to satisfy a display
concern.

The generic is the *source* of inheritance, not a
recipient, so it has no inherited fields to resolve
against. The value is copied down to each implementer
that does not declare its own, which is why the same
entry can be valid on the node and invalid on the
generic.

### The failure

```yaml
generics:
  - name: Endpoint
    namespace: Net
    order_by: ["name__value"]   # rejected: Endpoint has no `name`
    attributes:
      - name: label
        kind: Text

nodes:
  - name: Optical
    namespace: Net
    inherit_from: [NetEndpoint]
    attributes:
      - name: name              # this implementer declares it
        kind: Text

  - name: Console
    namespace: Net
    inherit_from: [NetEndpoint]
    attributes:
      - name: port_id           # this one has no `name`
        kind: Text
```

```text
NetEndpoint.order_by: attribute 'name' not defined on this schema (entry: 'name__value').
```

**The message may name an implementer instead of the
generic.** The generic's `order_by` is copied down to
every implementer that declares none of its own, and each
copy is validated against the schema it landed on.
`NetOptical` declares `name`, so its copy resolves.
`NetConsole` does not, so its copy fails too, and
whichever failing schema is validated first is the one
named:

```text
NetConsole.order_by: attribute 'name' not defined on this schema (entry: 'name__value').
```

on a kind whose file does not mention `order_by` at all.
When the named kind has no `order_by`, look at the
generics it inherits from.

### Three ways forward

| Option | When to use it |
| ------ | -------------- |
| Declare the attribute on the generic | It genuinely belongs to every implementer. Now the ordering and the model agree |
| Set `order_by` on each concrete kind | The attribute is per-kind. Costs repetition, changes no data model |
| Order by node metadata | You want *a* stable order, not a semantic one |

The metadata form needs no declared attribute at all
and is valid on a generic that declares nothing:

```yaml
generics:
  - name: Endpoint
    namespace: Net
    order_by: ["node_metadata__updated_at"]
```

Only two metadata fields exist. Anything else is
rejected:

```text
NetEndpoint.order_by: unknown metadata field (entry: 'node_metadata__nope').
Supported metadata fields: created_at, updated_at.
```

### What else `order_by` accepts

- A direction suffix: `name__value__asc`,
  `name__value__desc`. Ascending is the default.
- An attribute reached through a **cardinality-one
  relationship the same schema declares**:
  `device__name__value`. The relationship may be
  optional here, unlike in `uniqueness_constraints`.
- Each target at most once. Listing one target twice,
  even with opposite directions, is rejected:

  ```text
  NetThing.order_by: target 'name.value' appears in order_by more than once
  (entries: 'name__value__asc', 'name__value__desc'). Each target may appear
  at most once.
  ```

### Common mistakes

- Putting `order_by` on a generic to order a cross-kind
  listing by an attribute the generic does not declare.
  This is the reported case and the one worth
  remembering.
- Adding an attribute to a generic purely to make
  `order_by` load. If the attribute has no meaning for
  every implementer, order by metadata or move
  `order_by` down to the concrete kinds instead.
- Assuming a generic's `order_by` overrides an
  implementer's. It is copied down **only** to
  implementers that declare none of their own.
- Reading the error as a typo. The attribute name is
  usually spelled correctly; it is on the wrong schema.

Related: [display-order-weight.md](display-order-weight.md)
governs display order *within* an object;
`order_by` governs the order of objects in a listing.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
