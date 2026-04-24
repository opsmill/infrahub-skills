---
title: Edit Existing Artifacts Surgically
impact: HIGH
tags: execution, discipline, edits, schema, refactor, relationship-identifiers
---

## Edit Existing Artifacts Surgically

Impact: HIGH

Editing an existing Infrahub schema or data repository is
more dangerous than editing ordinary code. Renaming a
node changes every peer reference. Reordering attributes
changes UI display. Rewriting a relationship identifier
breaks the other side. "Cleaning up" adjacent YAML can
silently flip `optional` or `branch` semantics.

When the user asks for a change, touch only the lines
required by that change. Leave the rest of the file in
the state you found it -- including style, ordering,
quoting, and comments you don't like.

### What Not to Touch

- **Node and attribute names** elsewhere in the file, even
  if they don't match the repo's convention
- **Relationship identifiers** on unrelated relationships
  -- changing one side without the other breaks the link
- **`order_weight` values** on attributes you aren't
  changing, even if they look "off"
- **`inherit_from`** lists, unless the request is about
  inheritance
- **YAML formatting** (quote style, indentation width,
  blank lines) -- reformatting produces huge diffs that
  hide the real change
- **Unrelated nodes in the same file**, even to fix a bug
  you happen to notice; mention it instead

### What to Clean Up

When a change you make leaves something orphaned,
removing it is part of the change, not out of scope:

- A relationship whose peer node you removed -- delete
  both sides
- A `display_label` template referring to an attribute
  you removed -- update the template
- A `human_friendly_id` entry pointing to a removed
  attribute -- remove the entry

### Renames Are Not Surgical

Renaming a node's `name` or `namespace`, or changing a
relationship's `identifier`, is never a surgical edit in
Infrahub -- it ripples into peer relationships, data
files, protocols, and any generator or check that
references the old `kind`. Treat renames as their own
task and confirm the scope before starting.

### Surfacing Issues You Notice

If, while making the requested change, you see an
unrelated problem (a typo in another node, a wrong
identifier elsewhere, a deprecated `String` kind) --
mention it in the response, do not fix it in the same
diff. The user can ask for the follow-up fix.

### Prevention

Before saving, run a mental diff: "Does every changed
line trace to the user's request, or to a consequence of
it?" Any line that doesn't should revert.
