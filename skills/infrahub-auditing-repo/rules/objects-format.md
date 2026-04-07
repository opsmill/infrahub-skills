# Rule: objects-format

**Severity**: CRITICAL
**Category**: Objects

## What It Checks

Validates that object YAML files follow the required structure and value conventions.

## Checks

1. Each YAML document has `apiVersion: infrahub.app/v1`
2. Each document has `kind: Object`
3. `spec.kind` is present and uses full kind (Namespace + Name)
4. `spec.data` is present and is a list
5. One kind per YAML document (use `---` separator for multiple)
6. `expand_range: true` is in `parameters` block, not on individual items
7. Hierarchical children include `kind` field at each level
8. Component children include `kind` field under relationship name

## Common Issues

- Missing `apiVersion` field
- `spec.data` as an object instead of a list
- Multiple kinds in a single YAML document without `---` separator
- `expand_range` placed on data items instead of `parameters`
