# Rule: practices-schema

**Severity**: MEDIUM
**Category**: Best Practices

## What It Checks

Schema best practices that improve usability and maintainability.

## Checks

1. All user-facing nodes have `human_friendly_id` defined
2. `display_label` is set for UI rendering on nodes
3. `order_weight` values fall in recommended ranges:
   - 800-900: key relationships
   - 1000-1999: core attributes
   - 2000-2999: secondary attributes
   - 3000+: tags and metadata
4. Generics are used when 3+ nodes share the same attributes
5. `state: absent` is used to remove attributes (not just deleting them)
6. Cross-file relationships use `extensions` block
7. No usage of deprecated `display_labels` (plural) —
   must be migrated to `display_label` (singular,
   Jinja2 template). See
   [schema-display-labels-deprecated.md](schema-display-labels-deprecated.md)
   for migration patterns

## Common Issues

- Nodes without `human_friendly_id` — makes object references in data files difficult
- All `order_weight` values the same — UI shows attributes in arbitrary order
- Duplicate attribute blocks across many nodes that could be a generic
- Using deprecated `display_labels` (list) instead of
  `display_label` (Jinja2 string) — will break in a
  future release
