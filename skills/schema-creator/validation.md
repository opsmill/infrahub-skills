# Schema Validation Guide

Commands and practices for validating and loading Infrahub schemas.

## Validation Commands

### Check Schema Before Loading

Always validate schemas before applying them:

```bash
infrahubctl schema check --branch <branch-name> schema.yml
```

This command:
- Validates YAML syntax
- Checks naming conventions
- Verifies relationship references
- Identifies constraint violations

### Load Schema

After validation passes:

```bash
infrahubctl schema load --branch <branch-name> schema.yml
```

## Recommended Workflow

### 1. Create a Branch

Always make schema changes in a branch:

```bash
infrahubctl branch create my-schema-branch
```

### 2. Validate Changes

```bash
infrahubctl schema check --branch my-schema-branch schema.yml
```

### 3. Load to Branch

```bash
infrahubctl schema load --branch my-schema-branch schema.yml
```

### 4. Test in Branch

- Create test data using the new schema
- Verify relationships work correctly
- Test queries and filters

### 5. Merge to Main

```bash
infrahubctl branch merge my-schema-branch
```

## Schema Migrations

### Adding Elements

Simply add new nodes, attributes, or relationships to the schema file and reload.

### Removing Elements

Use `state: absent` to mark elements for removal:

```yaml
attributes:
  - name: deprecated_field
    kind: Text
    state: absent
```

```yaml
relationships:
  - name: old_relationship
    peer: SomeNode
    state: absent
```

```yaml
nodes:
  - name: DeprecatedNode
    namespace: Legacy
    state: absent
```

### Modifying Elements

Most properties can be updated by changing the value and reloading. However, some properties cannot be changed:

**Cannot be modified:**
- `branch` on nodes, attributes, or relationships
- `direction` on relationships
- `hierarchical` on relationships

### Renaming Elements

Renaming requires including the internal UUID temporarily. The safer approach is to:

1. Add the new element
2. Migrate data
3. Remove the old element with `state: absent`

## Validation Checklist

### Node Validation

- [ ] `name` is PascalCase, 2-32 characters
- [ ] `namespace` is PascalCase, 3-32 characters
- [ ] `description` is under 128 characters
- [ ] `label` is under 64 characters
- [ ] `icon` uses valid Material Design Icons format (`mdi:icon-name`)
- [ ] `branch` is one of: `aware`, `agnostic`, `local`
- [ ] `inherit_from` references existing generics with full kind (e.g., `NetworkInterface`)

### Attribute Validation

- [ ] `name` is snake_case, 3-32 characters
- [ ] `kind` is a valid attribute type
- [ ] `description` is under 128 characters
- [ ] `choices` is provided for `Dropdown` kind
- [ ] `default_value` matches the attribute kind
- [ ] `parameters` is only used with supported kinds: `Number`, `NumberPool`, `Text`, `TextArea`
- [ ] For `Number`: `parameters.min_value` < `parameters.max_value` (if both set)
- [ ] For `NumberPool`: `parameters.start_range` < `parameters.end_range`
- [ ] For `Text`/`TextArea`: `parameters.min_length` < `parameters.max_length` (if both set)
- [ ] For `Text`/`TextArea`: `parameters.regex` is valid regular expression syntax

### Relationship Validation

- [ ] `name` is snake_case, 3-32 characters
- [ ] `peer` references an existing node or generic kind
- [ ] `cardinality` is either `one` or `many`
- [ ] `direction` is one of: `bidirectional`, `outbound`, `inbound`
- [ ] `identifier` matches on both sides of bidirectional relationships
- [ ] `on_delete` is either `no-action` or `cascade`
- [ ] Component/Parent pairs are correctly configured

### Generic Validation

- [ ] Same rules as nodes apply
- [ ] `used_by` references valid node kinds (if specified)

## Common Validation Errors

### "Invalid node name"

Node names must be PascalCase and match `^[A-Z][a-zA-Z0-9]+$`.

```yaml
# Wrong
- name: network_device
- name: networkDevice
- name: NETWORKDEVICE

# Correct
- name: NetworkDevice
```

### "Invalid attribute name"

Attribute names must be snake_case and match `^[a-z0-9_]+$`.

```yaml
# Wrong
- name: hostName
- name: HostName
- name: host-name

# Correct
- name: hostname
- name: host_name
```

### "Unknown peer"

The relationship peer must reference an existing node or generic using the full kind (namespace + name).

```yaml
# Wrong (missing namespace)
peer: Device

# Correct
peer: NetworkDevice
```

### "Duplicate identifier"

Each relationship identifier must be unique within the schema, used only by the two sides of a bidirectional relationship.

### "Missing choices for Dropdown"

Dropdown attributes require a `choices` list:

```yaml
- name: status
  kind: Dropdown
  choices:
    - name: active
    - name: inactive
```

## Strict Mode

Infrahub has a strict mode (`INFRAHUB_SCHEMA_STRICT_MODE`) that enforces additional validators by default:

- Relationship parent constraints
- Numeric parameter validation

Disable with environment variable if needed for development:

```bash
export INFRAHUB_SCHEMA_STRICT_MODE=false
```

## Testing Schema Changes

### GraphQL Mutation Test

After loading a schema, test creating data:

```graphql
mutation {
  NetworkDeviceCreate(data: {
    hostname: {value: "test-device-01"}
    model: {value: "Test Model"}
  }) {
    ok
    object { id }
  }
}
```

### Query Test

Verify queries work correctly:

```graphql
query {
  NetworkDevice {
    edges {
      node {
        hostname { value }
        interfaces {
          edges {
            node {
              name { value }
            }
          }
        }
      }
    }
  }
}
```
