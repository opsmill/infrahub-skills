# Schema Reference

Complete reference for Infrahub schema properties.

## Node Properties

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | PascalCase, 2-32 chars, pattern: `^[A-Z][a-zA-Z0-9]+$` |
| `namespace` | Yes | PascalCase, 3-32 chars, pattern: `^[A-Z][a-z0-9]+$` |
| `description` | No | Max 128 chars |
| `label` | No | Human-readable name, max 64 chars |
| `icon` | No | Material Design Icons ref (e.g., `mdi:server`) |
| `branch` | No | `aware` (default), `agnostic`, or `local` |
| `inherit_from` | No | List of generic kinds to inherit from |
| `human_friendly_id` | No | List of attribute paths for readable IDs |
| `uniqueness_constraints` | No | Multi-field uniqueness rules |
| `display_label` | No | Jinja2 template for display |
| `order_by` | No | Default sorting fields |
| `default_filter` | No | Default query filter field |
| `include_in_menu` | No | Show in UI sidebar (default: true) |
| `menu_placement` | No | Menu location path |
| `hierarchical` | No | Enable parent-child structures |
| `attributes` | No | List of attribute definitions |
| `relationships` | No | List of relationship definitions |

## Attribute Kinds

| Category | Kinds |
|----------|-------|
| **Text** | `Text`, `TextArea`, `Email`, `URL`, `Password`, `HashedPassword`, `File`, `MacAddress`, `Color` |
| **Numeric** | `Number`, `NumberPool`, `Bandwidth` |
| **Network** | `IPHost`, `IPNetwork` |
| **Boolean** | `Boolean`, `Checkbox` |
| **Temporal** | `DateTime` |
| **Selection** | `Dropdown` (requires `choices`) |
| **Complex** | `List`, `JSON`, `Any` |
| **System** | `ID` |

## Attribute Properties

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | snake_case, 3-32 chars |
| `kind` | Yes | Attribute type from list above |
| `label` | No | Human-readable name |
| `description` | No | Max 128 chars |
| `optional` | No | Allow null values (default: false) |
| `unique` | No | Enforce uniqueness (default: false) |
| `default_value` | No | Default when not specified |
| `choices` | No | For Dropdown: list of `{name, color, description}` |
| `regex` | No | Validation pattern |
| `min_length` / `max_length` | No | Text length constraints |
| `min_value` / `max_value` | No | Numeric constraints |
| `enum` | No | List of allowed values |
| `read_only` | No | Prevent modifications |

## Relationship Kinds

| Kind | Purpose | Use Case |
|------|---------|----------|
| `Generic` | Flexible connection | Default, no special behavior |
| `Attribute` | Inline display | Related entity properties shown inline |
| `Component` | Composition | Parent contains children, cascade delete option |
| `Parent` | Hierarchical | Child belongs to parent (mandatory) |
| `Group` | Membership | System-managed groupings |
| `Profile` | Configuration | Template/profile assignments |

## Relationship Properties

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | snake_case, 3-32 chars |
| `peer` | Yes | Target node/generic kind |
| `kind` | No | Relationship type (default: `Generic`) |
| `cardinality` | No | `one` or `many` (default: `many`) |
| `optional` | No | Allow null (default: false) |
| `identifier` | No | Unique relationship ID for bidirectional |
| `direction` | No | `bidirectional`, `outbound`, `inbound` |
| `on_delete` | No | `no-action` or `cascade` |
| `min_count` / `max_count` | No | Cardinality constraints |

## Generic Properties

Generics share most properties with nodes, plus:

| Property | Description |
|----------|-------------|
| `used_by` | List of node kinds using this generic |

Nodes inherit from generics via `inherit_from`. Properties can be overridden at the node level.

## Naming Conventions

1. **Nodes & Generics**: PascalCase (e.g., `NetworkDevice`, `PhysicalInterface`)
2. **Namespaces**: PascalCase, domain-based (e.g., `Network`, `Organization`, `Infrastructure`)
3. **Attributes**: snake_case (e.g., `hostname`, `ip_address`, `serial_number`)
4. **Relationships**: snake_case, descriptive (e.g., `interfaces`, `primary_site`, `assigned_device`)

## When to Use Generics

Use generics when:
- Multiple nodes share common attributes or relationships
- You need polymorphic relationships (one relationship targeting multiple node types)
- Creating type hierarchies (e.g., `Interface` generic with `PhysicalInterface`, `LogicalInterface` nodes)

## Relationship Modeling Patterns

### Component/Parent Pairs

Use for containment relationships (Device has Interfaces):

```yaml
# Parent side (Device)
relationships:
  - name: interfaces
    peer: NetworkInterface
    kind: Component
    cardinality: many
    identifier: "device__interfaces"

# Child side (Interface)
relationships:
  - name: device
    peer: NetworkDevice
    kind: Parent
    cardinality: one
    optional: false
    identifier: "device__interfaces"
```

### Bidirectional Relationships

Set matching `identifier` on both sides:

```yaml
# On Device
- name: site
  peer: OrganizationSite
  identifier: "site__devices"

# On Site
- name: devices
  peer: NetworkDevice
  identifier: "site__devices"
```

### Hierarchical Structures

Enable `hierarchical: true` on the node for tree structures.

## Human-Friendly IDs (HFID)

Design readable identifiers using attribute paths:

```yaml
human_friendly_id:
  - "hostname__value"           # Single attribute
  - "site__name__value"         # Through relationship
  - "rack__name__value"         # Multiple for compound IDs
```

## Common Pitfalls

### YAML Boolean Quoting

Quote values that look like booleans:

```yaml
# Wrong - YAML interprets as boolean
choices:
  - name: on

# Correct
choices:
  - name: "on"
```

### Missing Relationship Identifiers

Always set `identifier` for bidirectional relationships to ensure consistency.

### Optional on Parent Relationships

Child-side of Component/Parent should have `optional: false` to enforce the containment relationship.

## Best Practices

### General

1. Ensure that every node has an human friendly ID so items can be created idempotently.
2. Ensure that each relationship has an identifier on it that matches it's peer's identifier.
