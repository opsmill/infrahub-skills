# Rule: schema-relationships

**Severity**: CRITICAL
**Category**: Schema

## What It Checks

Validates relationship definitions: peer kinds use full
namespace, bidirectional identifiers match, and
Component/Parent cardinality is correct.

## Checks

1. **Peer kind**: every `peer` field uses full kind
   (Namespace + Name), not just name
2. **Bidirectional identifiers**: both sides of a relationship share the same `identifier`
3. **Identifier convention**: uses `__` separator (e.g., `parent__children`)
4. **Component relationships**: have `kind: Component` and `cardinality: many`
5. **Parent relationships**: have `kind: Parent` and `cardinality: one`
6. **Component/Parent pairs**: share the same `identifier`
7. **Default awareness**: cardinality defaults to `many`,
   optional defaults to `true` — flag when these
   defaults may cause confusion

## Common Issues

- `peer: Device` instead of `peer: InfraDevice`
- Mismatched identifiers between two sides of a bidirectional relationship
- Component side with `cardinality: one` (should be `many`)
- Parent side with `cardinality: many` (should be `one`)
