---
name: infrahub-schema-creator
description: Create, validate, and modify Infrahub schemas for infrastructure data management. Use when designing infrastructure data models, creating schema nodes with attributes and relationships, validating schema definitions, or planning schema migrations.
---

# Infrahub Schema Creator

Create, validate, and modify Infrahub schemas for infrastructure data management.

## Description

This skill assists with designing and implementing Infrahub schemas. Infrahub is an infrastructure data management platform where schemas define data structure using YAML format. This skill covers the full schema lifecycle: creation, validation, and modification.

## Capabilities

- Create new Infrahub schemas from natural language requirements
- Design nodes with appropriate attributes and relationships
- Create generics for shared properties and inheritance
- Validate schemas against Infrahub conventions
- Migrate and update existing schemas
- Generate human-friendly IDs and uniqueness constraints

## When to Use

This skill is invoked when:

- Creating new Infrahub schema definitions
- Modeling infrastructure data (devices, sites, networks, etc.)
- Adding or modifying nodes, attributes, or relationships
- Designing schema inheritance with generics
- Validating existing schemas
- Planning schema migrations

## Quick Start

### Basic Schema Structure

```yaml
---
version: "1.0"
generics:
  - name: GenericName
    namespace: Namespace
    # ... definition
nodes:
  - name: NodeName
    namespace: Namespace
    # ... definition
extensions:
    nodes:
    # ... definition
```

### Simple Node Example

```yaml
---
version: "1.0"
nodes:
  - name: Device
    namespace: Network
    label: Network Device
    icon: mdi:server
    human_friendly_id:
      - "hostname__value"
    attributes:
      - name: hostname
        kind: Text
        unique: true
      - name: model
        kind: Text
        optional: true
```

## Documentation

- [Schema Reference](reference.md) - Complete node, attribute, and relationship properties
- [Validation Guide](validation.md) - Schema validation and migration commands
- [Example Templates](examples.md) - Ready-to-use schema patterns

## Best Practices Summary

1. **Naming**: PascalCase for nodes/generics/namespaces, snake_case for attributes/relationships
2. **Generics**: Use when multiple nodes share attributes or need polymorphic relationships
3. **Relationships**: Always set `identifier` for bidirectional relationships
4. **Human-friendly IDs**: Design readable identifiers using attribute paths
5. **Migrations**: Use `state: absent` to remove elements, always validate before loading

## Resources

- [Infrahub Schema Documentation](https://docs.infrahub.app/topics/schema)
- [Creating a Schema Guide](https://docs.infrahub.app/guides/create-schema)
- [Schema Library](https://github.com/opsmill/schema-library)
