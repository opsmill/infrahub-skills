---
title: yagni-python-validator-vs-schema-constraint
impact: MEDIUM
ladder_step: 3
tags: audit, yagni, check, schema
---

# Rule: yagni-python-validator-vs-schema-constraint

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 3 — Can a schema feature express it?

## What It Checks

Python checks that enforce constraints expressible directly in the
schema: uniqueness, optionality, allowed-value sets, and regex format.
A schema constraint runs at load time on every write path; an
equivalent Python check runs only inside the proposed-change pipeline.

## Why it matters

A schema constraint rejects bad data at the source on every write —
proposed changes, API writes, branch merges, ad-hoc SDK calls. The
same constraint as a Python check only fires inside proposed-change
validation, so bad data created via other paths slips in. The check
is also slower to write, slower to run, and silently diverges from the
schema when one is updated without the other. Engineers later have to
guess which one is authoritative.

## Checks

1. Python checks calling `.count()` on a single attribute and raising
   on duplicates → replace with
   `uniqueness_constraints: [["<attr>__value"]]` on the node.
2. Python checks raising on a missing required attribute →
   `optional: false` on the attribute.
3. Python checks validating against a closed set of strings →
   `kind: Dropdown` with `choices`.
4. Python checks running `re.match`/`re.search` on an attribute value →
   `regex: "<pattern>"` on the attribute definition.
5. Python checks asserting that a relationship has exactly one peer
   when the schema already declares `cardinality: one`.

## What NOT to flag

- Cross-node business rules ("device count per location equals
  rack-unit total"). These require relationship traversal and cannot
  be expressed as single-attribute schema constraints.
- Stateful checks that depend on prior-branch data or out-of-band
  state.
- Checks that emit warnings via `level: WARN` rather than errors —
  schema-level rejection has no warning mode.
- Checks whose validation depends on the value of *another* attribute
  on the same node (conditional regex, conditional optional).

## Common Issues

- A node ships with `uniqueness_constraints` *and* a Python check
  doing the same uniqueness assertion. The Python check is dead code;
  delete it and the matching `.gql` query.
- A Python check importing `re` to validate a fixed pattern that
  could live on the attribute as `regex: "..."`.
- A check raising on `value not in {"active", "draft", "retired"}`
  when the schema field could be `kind: Dropdown` with the same
  choices.
