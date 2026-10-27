---
title: yagni-duplicate-shape-not-extracted-to-generic
impact: MEDIUM
ladder_step: 2
tags: audit, yagni, schema, generic
---

# Rule: yagni-duplicate-shape-not-extracted-to-generic

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 2 — Already in this codebase?

## What It Checks

Three or more nodes that share the same attribute set (and often the
same relationships) without extracting the shared shape into a
generic with `inherit_from`. The duplication is data the schema is
forcing reviewers to keep in sync by hand.

## Why it matters

When `name`, `status`, `description`, `owner` appear identically on
six nodes, a change to one (rename, type tightening, new default)
silently diverges the others. Schema reviews stop catching the drift
once it spans more than two files. A generic centralises the shape
in one place; nodes pick it up via `inherit_from`, which is the
mechanism the platform expects. Indexing, GraphQL fragment reuse, and
SDK type generation also collapse to one definition instead of N.

## Checks

1. Three or more nodes whose attribute lists are >70% identical by
   name and kind. Likely candidates for a shared generic.
2. Repeated attribute blocks across nodes for `name`, `description`,
   `status`, `owner`, `notes` — the canonical "common metadata"
   bundle. Move to a `Generic` base.
3. Two or more nodes already inheriting from the same generic that
   duplicate *additional* attributes between themselves. Promote the
   shared additional attributes into the generic or a second generic.
4. Pairs of nodes with identical relationship blocks (peer kinds,
   identifiers, cardinality) — the relationship belongs on a shared
   generic.

## What the finding must disclose

Extracting a generic is cheap and usually right, but it
is not free, and two of the costs are invisible until
after the hierarchy is written. A finding that only says
"extract a generic" hands the reader a surprise. Name
these alongside the recommendation:

1. **A relationship moved onto a generic has its peer
   frozen there.** No inheriting kind can narrow or widen
   it, from either side. So if the sibling nodes have
   relationships that ought to pair up precisely
   (`OpticalPort` only ever attaches to `OpticalDevice`),
   extracting the relationship to the generic makes that
   pairing **inexpressible in the schema** — it has to
   move to a Python check or go unenforced. Hierarchy
   relationships are exempt. See
   [../../infrahub-managing-schemas/rules/relationship-peer-kind.md](../../infrahub-managing-schemas/rules/relationship-peer-kind.md).
2. **The generic's implementer set becomes a published
   interface.** Every query rooted on the generic, every
   uniqueness constraint declared on it, and every
   consumer that sums or filters over it now answers
   differently, and adding the next implementer changes
   those answers again with no migration and no
   validation to flag it.
3. **A Dropdown moved onto a generic can drift.** A
   concrete kind that overrides it to add a default must
   restate the whole choice list, and a stale or invented
   list loads silently.

None of this makes the finding wrong. It means the
suggested replacement should say *which* attributes and
relationships to hoist, and should leave a precisely
paired relationship on the concrete kinds rather than
sweeping it up with the rest.

## Feasibility gate

`feasibility` is the finding's verdict on whether the
extraction it proposes can actually be performed. It
defaults to `clear (unverified)`. A finding may only
label itself `clear` once it has checked, and reported,
all three of:

1. **Every member's `identifier`** for each relationship
   proposed for hoisting.
2. **Every member's `peer` kind** for those same
   relationships.
3. **Whether any node-level setting being hoisted**
   (`human_friendly_id`, `uniqueness_constraints`,
   `display_label`, `order_by`) **traverses a
   relationship that is staying put.** If it does, it
   cannot move either.

**Differing identifiers or differing peers make the
relationship non-hoistable.** One generic edge means one
identifier, so hoisting collapses several distinct
parent edges into one and collides the reverse
relationships on the other side. It does this silently,
per
[relationship-identifiers](../../infrahub-managing-schemas/rules/relationship-identifiers.md),
which is CRITICAL for exactly this reason. Identifiers
are also immutable once loaded, so the mistake is
expensive to retrofit on a live instance.

When the relationship is blocked, **reduce the finding
to the attributes rather than dropping it.** The
duplication the rule exists to remove is still there,
and the attributes still share a definition.

**Enumerate every member that declares a field before
proposing to hoist it**, including members whose
declaration differs. A third kind carrying a narrower
choice list is a blocker, not a detail: hoisting the
wider list silently widens what that kind accepts. List
each declaring kind's file in `sites`, per
[audit-cites-all-reference-sites](./audit-cites-all-reference-sites.md).

Verdicts:

| `feasibility` | Meaning |
| ------------- | ------- |
| `clear (unverified)` | Default. The three checks above were not run, so the reader must re-derive the finding before acting on it |
| `clear` | All three ran and the extraction is performable as described |
| `blocked-differing-identifiers` | Members declare the relationship under different identifiers |
| `blocked-differing-peers` | Members point the relationship at different peer kinds |
| `blocked-setting-traverses-unhoisted-rel` | A hoisted node-level setting traverses a relationship that is staying on the concrete kinds |

**More than one blocker can apply at once, and any of
them is a correct verdict.** A member set that declares
three identifiers often also peers two different kinds,
because both follow from the same modelling choice. The
blockers carry no precedence: report the one you would
have to undo first, and name the others in the finding
rather than picking silently. A reader needs to know the
extraction is blocked and why; which blocker was written
in the field does not change what they do next.

**The verdict names the blocker, not the outcome.** When
the relationship is blocked and the finding is reduced
to attributes, the verdict is still the `blocked-` reason
that caused the reduction, and the reduction itself is
described in the replacement. An implementer reading
"reduced to attributes" learns what to do; only the
blocker tells them why, and whether it also applies to
the next extraction they attempt.

The distinction is what lets an implementer know which
findings to re-derive. Two extraction findings in one
audit, one respecting identifiers and one not, had
completely different outcomes: the first was
implementable nearly in full, the second had to be cut
to a fraction.

## What NOT to flag

- Two nodes sharing one or two trivial attributes (`name`,
  `description`). The cost of a generic exceeds the duplication.
- A relationship whose peer differs meaningfully per sibling, where
  the pairing is the point. Hoisting it to a generic would erase a
  constraint the schema is currently enforcing.
- Nodes that share attribute *names* but differ in kind or
  constraints (one's `id` is `Text`, another's is `Number`). They
  aren't the same shape.
- Nodes already inheriting from `opsmill/schema-library` generics
  where the shared attributes come from the library — that's reuse,
  not duplication.
- Domain-specific generics that exist for documentation purposes
  even when only one node currently inherits them (the second
  consumer is planned).

## Common Issues

- Six device-type nodes (`DeviceSpine`, `DeviceLeaf`, `DeviceEdge`,
  ...) each repeating the same 10 attributes. One `DeviceCommon`
  generic + six minimal nodes.
- A new node copy-pasted from an existing one without converting the
  shared block to inheritance.
- `Site`, `Region`, `Country` repeating the same metadata fields
  instead of inheriting from a `LocationBase` generic.
