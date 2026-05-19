# Schema Validation & Migration Guide

> **Server Required**: `infrahubctl schema check` and
> `infrahubctl schema load` both require a running
> Infrahub server. Run `infrahubctl info` first to
> verify connectivity. See
> [Server Connectivity Check](../infrahub-common/rules/connectivity-server-check.md).

## Validation Commands

### Check Schema (Dry Run)

Validate schema files without loading them:

```bash
# Check a directory of schemas
infrahubctl schema check schemas/

# Check specific files
infrahubctl schema check schemas/base/dcim.yml schemas/base/location.yml

# Check against a specific branch
infrahubctl schema check schemas/ --branch develop
```

This will:

1. Parse YAML files
2. Validate against the Infrahub schema spec (Pydantic models)
3. Show validation errors if any
4. Show a diff of what would change vs current schema in Infrahub

### Load Schema

Load schemas into a running Infrahub instance:

```bash
# Load all schemas from directory
infrahubctl schema load schemas/

# Load to a specific branch
infrahubctl schema load schemas/ --branch feature-branch

# Load and wait for convergence
infrahubctl schema load schemas/ --wait 30
```

### Using invoke tasks (project-specific)

If the project has `tasks.py`:

```bash
uv run invoke load-schema
```

## Project Configuration

The `.infrahub.yml` file defines what gets loaded:

```yaml
---
schemas:
  - schemas              # Loads all .yml/.yaml/.json files recursively

menus:
  - menus/menu-full.yml

objects:
  - objects              # Data files to populate

queries:
  - name: query_name
    file_path: queries/query.gql

check_definitions:
  - name: check_name
    class_name: CheckClassName
    file_path: checks/check.py
```

## Common Validation Errors

### "Unknown field"

The JSON schema has `additionalProperties: false`. Any typo causes this:

```text
# BAD - typo in property name
- name: MyNode
  namspace: Dcim         # Should be "namespace"
```

### "Name must match pattern"

Names have strict regex patterns:

```text
# Node name: ^[A-Z][a-zA-Z0-9]+$
- name: my_node          # BAD - must start with uppercase, no underscores
- name: MyNode           # GOOD

# Namespace: ^[A-Z][a-z0-9]+$
- namespace: DCIM        # BAD - only first letter uppercase
- namespace: Dcim        # GOOD

# Attribute name: ^[a-z0-9\_]+$
- name: MyAttribute      # BAD - must be lowercase
- name: my_attribute     # GOOD
```

### "Name too short/long"

```text
# Node name: 2-32 chars
- name: X                # BAD - too short

# Namespace: 3-32 chars
- namespace: DC          # BAD - too short

# Attribute/Relationship name: 3-64 chars
- name: id               # BAD - too short, use "obj_id" or similar
```

### "Peer not found"

Relationship peer must reference the full kind (namespace + name):

```text
# BAD
- peer: DeviceType       # Missing namespace

# GOOD
- peer: DcimDeviceType
```

### "Identifier mismatch"

Bidirectional relationships need matching identifiers:

```yaml
# On Device:
- name: interfaces
  peer: DcimInterface
  identifier: "device__interface"    # Must match

# On Interface:
- name: device
  peer: DcimGenericDevice
  identifier: "device__interface"    # Must match
```

### "Uniqueness constraint references unknown field"

Use `__value` suffix for attributes in constraints:

```yaml
# BAD
uniqueness_constraints:
  - ["name", "rack"]

# GOOD
uniqueness_constraints:
  - ["name__value", "rack"]    # __value for attributes, bare name for relationships
```

## Schema Migration Strategies

### Adding a New Attribute

Just add it to the schema. If `optional: false`, existing data will need a value:

```yaml
# Safe: add as optional first
- name: new_field
  kind: Text
  optional: true

# Later: make mandatory after data is populated
- name: new_field
  kind: Text
  optional: false
  default_value: "unknown"
```

### Removing an Attribute

Use `state: absent`:

```yaml
- name: old_field
  kind: Text
  state: absent
```

### Renaming an Attribute

Two-step migration:

1. Add new attribute (optional), keep old one
2. Migrate data from old to new
3. Remove old attribute with `state: absent`

### Adding a New Node

Just add the node definition. No migration needed.

### Adding a Relationship

Add the relationship to the schema. For bidirectional
relationships, add both sides with matching `identifier`.

### Changing Attribute Type

Some type changes require `validate_constraint` checks. The safest approach:

1. Add new attribute with new type
2. Migrate data
3. Remove old attribute

### Making an Optional Field Mandatory

```yaml
# Step 1: Ensure all data has values (via data migration or default)
# Step 2: Update schema
- name: field
  kind: Text
  optional: false
  default_value: "default"    # Provides fallback for existing data
```

## Branch-Based Schema Changes

Infrahub supports schema changes on branches:

```bash
# Create a branch for schema work
# (via Infrahub UI or API)

# Check schema against the branch
infrahubctl schema check schemas/ --branch schema-updates

# Load schema to the branch
infrahubctl schema load schemas/ --branch schema-updates

# Test and validate on branch, then merge via Infrahub UI
```

### Branch Support Types

| Type | Behavior |
| ---- | -------- |
| `aware` | Branch-aware (default). Changes isolated. |
| `agnostic` | Same data across all branches. Changes are global. |
| `local` | Data is local to the branch where created. |

## Pre-Validation Checklist

Before running `infrahubctl schema check`, verify:

- [ ] Server is reachable (`infrahubctl info` succeeds)
- [ ] Every schema file starts with `version: "1.0"`
- [ ] All node/generic names are PascalCase
- [ ] All namespaces start with uppercase, rest lowercase
- [ ] All attribute/relationship names are snake_case, 3+ chars
- [ ] All relationship `peer` values use full kind (namespace + name)
- [ ] All bidirectional relationships have matching `identifier` on both sides
- [ ] All Component relationships have a matching Parent on the other node
- [ ] All hierarchical nodes inherit from a generic with `hierarchical: true`
- [ ] Root hierarchical nodes have `parent: null`
- [ ] All `Dropdown` attributes have `choices` defined
- [ ] `human_friendly_id` is set on nodes that will be user-facing
- [ ] `uniqueness_constraints` use `__value` suffix for attributes
- [ ] No deprecated fields used (`display_labels`, `default_filter`, `String` kind)
- [ ] The `$schema` comment is present for IDE validation

## IDE Integration

Add this comment to the top of every schema file for IDE autocompletion:

```yaml
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
```

This enables:

- Property name autocompletion
- Type validation
- Inline error highlighting
- Documentation tooltips
