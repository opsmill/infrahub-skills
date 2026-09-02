---
title: Uniqueness Constraint Format and Scope
impact: HIGH
tags: uniqueness, constraints, validation, generics, inheritance, migration
---

## Uniqueness Constraint Format and Scope

Impact: HIGH

Uniqueness constraints reference attributes with the
`__value` suffix and relationships by bare name. A
constraint declared on a generic is enforced across
**every** kind that inherits it.

### Why it matters

The format half is a load-time cost: get it wrong and
the schema is rejected with a message that names the
wrong field but not the right one. The scope half is a
migration cost, and it is the expensive one. Whether a
constraint on a generic applies per inheriting kind or
across all of them decides whether a migration can run
both kinds side by side while it is verified, or has to
delete the old instances first. That is the difference
between a reversible migration and one that has to be
right the first time.

### Format

| Field Type | Format | Example |
| ---------- | ------ | ------- |
| Attribute | `attribute_name__value` | `name__value` |
| Relationship | bare name | `rack`, `device_type` |

**Incorrect:**

```yaml
uniqueness_constraints:
  - ["name", "rack"]                # missing __value on attribute
  - ["name__value", "rack__value"]  # __value on relationship
```

**Correct:**

```yaml
uniqueness_constraints:
  - ["name__value", "rack"]  # __value for attributes, bare name for relationships
```

### What a relationship in a constraint must be

A relationship is only usable in a constraint if it is
**cardinality one**, **mandatory**, and referenced
**bare**. All three are checked, each with its own
message, and all four failures below are load-time:

| What you wrote | Error |
| -------------- | ----- |
| `optional: true` | ``cannot use <rel> relationship, relationship must be mandatory. (`<rel>`)`` |
| `cardinality: many` | ``cannot use <rel> relationship, relationship must be of cardinality one (`<rel>`)`` |
| `rel__attr__value` | ``cannot use attributes of related node, only the relationship. (`rel__attr__value`)`` |
| `name` instead of `name__value` | ``invalid attribute, it must end with one of the following properties: value. (`name`)`` |

Every message is prefixed `<Kind>.uniqueness_constraints:`
and every one is raised at schema load, before any data
is touched.

The mandatory requirement is the one that costs a full
design cycle, because a constraint designed against an
optional relationship looks reasonable and only fails
at schema load, after the surrounding model is
committed to. If the relationship genuinely has to be
optional, the constraint cannot express the rule and it
belongs in a check.

WRONG. `rack` is optional, so this is rejected at
load:

```yaml
- name: Pdu
  namespace: Dcim
  uniqueness_constraints:
    - ["rack", "name__value"]
  relationships:
    - name: rack
      peer: DcimRack
      cardinality: one
      optional: true          # <- makes the constraint invalid
```

RIGHT. Mandatory, cardinality one, referenced bare:

```yaml
- name: Pdu
  namespace: Dcim
  uniqueness_constraints:
    - ["rack", "name__value"]
  relationships:
    - name: rack
      peer: DcimRack
      cardinality: one
      optional: false
```

### Optional attributes collide on null

An attribute with no value is compared as the literal
sentinel `"NULL"`, not skipped. So two rows that both
leave an optional constrained attribute empty carry the
same value for it and collide. A constraint spanning an
optional attribute therefore permits at most one row
with that attribute unset, which is rarely the intent.
Either make the attribute mandatory or leave it out of
the constraint.

### Scope: a constraint on a generic spans every implementer

An **implementer** is a concrete node kind that lists a
generic in its `inherit_from`. The word is used
throughout this rule for that, and nothing else.

**A constraint declared on a generic is enforced across
every implementer, not per kind.** Two objects of
different implementing kinds cannot share the
constrained values.

```yaml
generics:
  - name: Endpoint
    namespace: Net
    uniqueness_constraints:
      - ["parent", "name__value"]   # spans ALL implementers

nodes:
  - name: OpticalEndpoint
    namespace: Net
    inherit_from: [NetEndpoint]
  - name: EthernetEndpoint
    namespace: Net
    inherit_from: [NetEndpoint]
```

Loading a `NetOpticalEndpoint` with `parent: rack-a`,
`name: e1` succeeds. Loading a `NetEthernetEndpoint`
with the same pair is rejected:

```text
Violates uniqueness constraint 'parent-name'
```

The two objects differ in kind. They collide only on
the constrained pair, and the constraint is declared in
exactly one place.

The mechanism is that every implementer carries the
generic's label, and the constraint query is issued
against the **generic's** kind, so it matches instances
of every implementer.

### A concrete kind cannot narrow what it inherits

Declaring `uniqueness_constraints` on a concrete kind
does **not** replace the generic's. It **adds** a
kind-scoped check on top; the generic-scoped check
still runs, because the inherited constraint is
evaluated from `inherit_from` regardless of what the
kind declares.

So the effect of declaring your own is:

| You want | You get |
| -------- | ------- |
| To loosen the generic's constraint | Not possible. The generic's still applies |
| To tighten it further for one kind | Works. Both checks run |
| To replace it with a different pair | Both apply, not just yours |

If one implementer genuinely needs a looser rule, the
constraint is on the wrong layer: move it down onto
each concrete kind that wants it. Check the generic for
the two keys below before concluding it declares none.

### What this means for a migration

Splitting one kind into several more specific kinds that
share a generic:

- If the constraint lives on the **generic**, the old
  and new instances **collide**, so the old rows must be
  deleted before the new ones load. Deletion is an
  ordering precondition, and a migration that stops half
  way leaves neither set complete.
- If it lives on each **concrete kind**, both sets can
  coexist while the change is verified, and the old rows
  can be removed last.

Decide this before writing the migration, because it
determines the load order. When both can work, putting
the constraint on the concrete kinds buys a reversible
migration.

### Two other keys compile into `uniqueness_constraints`

`uniqueness_constraints` is not the only way to declare
one. Both of these are folded into the entity's
`uniqueness_constraints` at schema load, **on the layer
they are declared on**:

| Key | Becomes |
| --- | ------- |
| `human_friendly_id: [parent__name__value, name__value]` | the group `["parent", "name__value"]` (relationship paths collapse to the bare relationship) |
| an attribute with `unique: true` | the single-field group `["<attr>__value"]` |

So a generic that carries either one has generic-scoped
uniqueness even with no `uniqueness_constraints:` key in
the file, and the resulting load error is reported
against a constraint nobody wrote:

```text
<Kind>.uniqueness_constraints: cannot use <rel> relationship, relationship must be mandatory.
```

**Moving a constraint down onto the concrete kinds means
moving the `human_friendly_id` and any `unique: true`
down with it.** Leaving either on the generic reinstates
the cross-kind check you just moved.

`human_friendly_id` on a generic fails with a different
message than a plain constraint does, and the message is
misleading. See
[display-human-friendly-id.md](display-human-friendly-id.md).

### Example: unique name per rack

```yaml
nodes:
  - name: Pdu
    namespace: Dcim
    uniqueness_constraints:
      - ["rack", "name__value"]   # name is unique within each rack
    human_friendly_id:
      - name__value
      - rack__name__value
```

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
