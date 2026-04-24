---
title: Produce Only What Was Requested
impact: HIGH
tags: execution, discipline, scope, simplicity, schema, objects, generators
---

## Produce Only What Was Requested

Impact: HIGH

Speculative additions -- attributes "you'll probably
want," extra relationships "for completeness," helper
nodes that weren't asked for -- have a real cost in
Infrahub. They inflate the schema, drive generator and
protocol regeneration, force data-file updates, and
become load-bearing once committed even though nobody
designed them on purpose.

The rule: generate the minimum set of nodes, generics,
attributes, relationships, data entries, checks, or
transforms that satisfies the request. Nothing more.

### Typical Overreach, and What It Costs

| Overreach | Cost |
| --------- | ---- |
| Adding `description`, `notes`, `tags` attributes "just in case" | Noise in UI, in protocols, in every data file |
| Adding a `status` Dropdown when only `name` was asked for | Requires choice definitions the user didn't specify |
| Inventing a `Location` hierarchy around a requested `Device` node | Commits the schema to a containment model the user didn't ask for |
| Adding both sides of a relationship the user only mentioned once | Doubles the surface area; may conflict with existing nodes |
| Pre-populating data files with "example" objects | Data becomes real once loaded; someone has to clean it up |
| Writing a generator "because we have a schema" | Generators are infrastructure, not freebies |

### When Addition Is Justified

- Bidirectional relationships: Infrahub requires both
  sides, so defining a relationship on one node forces a
  matching definition on the peer. This is not
  speculation -- it is the rule.
- `human_friendly_id` and `display_label` on every new
  node: these are required for a usable UI, not
  speculative features.
- `order_weight` when multiple attributes are added: the
  display order must come from somewhere.

Anything else, ask or skip.

### Verification Before Submitting

Before declaring a schema/object/artifact complete, walk
each node, attribute, and relationship and ask: "Did the
user request this, is it required by Infrahub, or did I
invent it?" Delete anything in the third category.

### Prevention

When tempted to add "obvious" extras, write them down as
a follow-up suggestion instead of adding them to the
artifact. The user can pull them in on the next request.
