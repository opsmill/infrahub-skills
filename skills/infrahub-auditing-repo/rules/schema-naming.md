# Rule: schema-naming

**Severity**: CRITICAL
**Category**: Schema

## What It Checks

Validates that all schema naming conventions are
followed: namespace, node/generic names,
attribute/relationship names, and kind derivation.

## Checks

1. **Namespace**: matches `^[A-Z][a-z0-9]+$`, 3-32 characters
2. **Node/Generic name**: matches `^[A-Z][a-zA-Z0-9]+$`, 2-32 characters
3. **Attribute names**: match `^[a-z0-9_]+$`, 3-32 characters
4. **Relationship names**: match `^[a-z0-9_]+$`, 3-32 characters
5. **Kind**: equals Namespace + Name concatenation
   (e.g., namespace `Infra` + name `Device` = kind
   `InfraDevice`)

## Common Issues

- Namespace starting with lowercase
- Node names with underscores (should be PascalCase)
- Attribute names with uppercase letters (should be snake_case)
- Kind not matching namespace + name
