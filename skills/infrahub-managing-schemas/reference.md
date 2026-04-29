# Infrahub Schema Property Reference

Complete reference for all schema properties. JSON
Schema validation available at:
`https://schema.infrahub.app/infrahub/schema/latest.json`

## Top-Level Schema File

| Property | Type | Required | Default | Description |
| -------- | ---- | -------- | ------- | ----------- |
| `version` | string | **Yes** | - | Always `"1.0"` |
| `generics` | list | No | `[]` | GenericSchema defs |
| `nodes` | list | No | `[]` | NodeSchema defs |
| `extensions` | object | No | `{}` | SchemaExtension |

---

## Node Properties

Properties for entries in the `nodes:` list.
**Required: `name`, `namespace`.**

### Identity & Display

| Property | Type | Default | Constraints | Description |
| -------- | ---- | ------- | ----------- | ----------- |
| `name` | string | *required* | 2-32, PascalCase | Node name |
| `namespace` | string | *required* | 3-32, First upper | Namespace |
| `description` | string | null | Max 128 chars | Short desc |
| `label` | string | null | Max 64 chars | Display name |
| `icon` | string | null | Iconify value | e.g., `mdi:server` |
| `display_label` | string | null | - | Jinja2 template |
| `human_friendly_id` | list | null | - | Human-readable ID paths |
| `order_by` | list | null | - | Default sort order |

### Menu & Visibility

| Property | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `include_in_menu` | boolean | null | Show in nav menu |
| `menu_placement` | string | null | Parent generic kind |
| `documentation` | string | null | URL to docs |

### Inheritance & Hierarchy

| Property | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `inherit_from` | list | `[]` | Generic kinds to inherit |
| `parent` | string | null | Parent kind in hierarchy |
| `children` | string | null | Child kind in hierarchy |
| `hierarchy` | string | null | Internal (auto-set) |

### Constraints

| Property | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `uniqueness_constraints` | list | null | `__value` for attrs, bare for rels |
| `branch` | enum | `"aware"` | `aware`, `agnostic`, `local` |

### Advanced

| Property | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `state` | enum | `"present"` | `present` or `absent` |
| `generate_profile` | boolean | `true` | Auto-generate Profile |
| `generate_template` | boolean | `false` | Auto-generate Template |

---

## Generic Properties

Generics use **all the same properties as nodes**,
plus:

| Property | Type | Default | Description |
| -------- | ---- | ------- | ----------- |
| `hierarchical` | boolean | `false` | Enable hierarchical mode |
| `used_by` | list | `[]` | Internal — nodes using this |

**Generics do NOT have**: `inherit_from`, `parent`,
`children`.

---

## Attribute Types

| Kind | Description | Special Properties |
| ---- | ----------- | ------------------ |
| `Text` | Standard text | `regex`, `min_length`, `max_length` (via `parameters` block; top-level deprecated) |
| `TextArea` | Multi-line text | Same as Text (via `parameters` block; top-level deprecated) |
| `Number` | Integer | `min_value`, `max_value` |
| `Boolean` | True/false | - |
| `Checkbox` | Boolean variant | - |
| `DateTime` | Date and time | - |
| `Dropdown` | Selection list | Requires `choices` |
| `IPHost` | IP host (e.g., 192.168.1.1/24) | - |
| `IPNetwork` | IP network (e.g., 192.168.0.0/24) | - |
| `MacAddress` | MAC address | - |
| `Email` | Email address | - |
| `URL` | URL | - |
| `Password` | Encrypted password | - |
| `HashedPassword` | Pre-hashed password | - |
| `JSON` | JSON data | - |
| `Any` | Any type | - |
| `List` | List of values | - |
| `File` | File reference | - |
| `Bandwidth` | Bandwidth value | - |
| `Color` | Hex color | - |

**Deprecated**: `String` (use `Text`),
`NumberPool` (special internal use)

## Attribute Properties

| Property | Type | Default | Constraints | Description |
| -------- | ---- | ------- | ----------- | ----------- |
| `name` | string | *required* | 3-64, snake_case | Attr name |
| `kind` | string | *required* | AttributeKind | Attr type |
| `label` | string | null | Max 64 chars | Display label |
| `description` | string | null | Max 128 chars | Help text |
| `default_value` | any | null | - | Default value |
| `unique` | boolean | `false` | - | Globally unique |
| `optional` | boolean | **`false`** | - | **Mandatory by default** |
| `read_only` | boolean | `false` | - | Cannot modify |
| `order_weight` | integer | null | - | Display order |
| `enum` | list | null | - | Valid values |
| `choices` | list | null | - | Dropdown choices |
| `allow_override` | enum | `"any"` | `"none"`/`"any"` | Profile override |
| `state` | enum | `"present"` | - | `absent` to remove |
| `deprecation` | string | null | Max 128 chars | Deprecation msg |

### Attribute Parameters (kind-specific)

**Text/TextArea parameters:**

```yaml
- name: hostname
  kind: Text
  parameters:
    regex: "^[a-zA-Z0-9-]+$"
    min_length: 3
    max_length: 64
```

**Number parameters:**

```yaml
- name: vlan_id
  kind: Number
  parameters:
    min_value: 1
    max_value: 4094
    excluded_values: "1,4094"    # Comma-separated or ranges
```

### Computed Attributes

```yaml
- name: computed_field
  kind: Text
  read_only: true
  computed_attribute:
    kind: Jinja2
    jinja2_template: >-
      {% if asset_tag__value %}
      {{ asset_tag__value }}
      {% else %}N/A{% endif %}
```

### Dropdown Choices

```yaml
- name: status
  kind: Dropdown
  default_value: active
  choices:
    - name: active               # Internal value (required)
      label: Active              # Display text (optional)
      description: "Operational" # Help text (optional)
      color: "#00FF00"           # Hex color (optional)
    - name: planned
      label: Planned
      color: "#0000FF"
```

---

## Relationship Properties

| Property | Type | Default | Constraints | Description |
| -------- | ---- | ------- | ----------- | ----------- |
| `name` | string | *required* | 3-64, snake_case | Rel name |
| `peer` | string | *required* | PascalCase | Target kind |
| `kind` | enum | `"Generic"` | See table | Rel type |
| `label` | string | null | Max 64 chars | Display label |
| `description` | string | null | Max 128 chars | Help text |
| `identifier` | string | null | Max 128, snake_case | Match both sides |
| `cardinality` | enum | **`"many"`** | `"one"`/`"many"` | Count |
| `optional` | boolean | **`true`** | - | **Optional by default** |
| `direction` | enum | `"bidirectional"` | bi/out/in | Direction |
| `on_delete` | enum | null | no-action/cascade | Delete behavior |
| `order_weight` | integer | null | - | Display order |
| `min_count` | integer | 0 | - | Min related objects |
| `max_count` | integer | 0 | - | Max (0=unlimited) |
| `read_only` | boolean | `false` | - | Cannot modify |
| `allow_override` | enum | `"any"` | `"none"`/`"any"` | Profile override |
| `state` | enum | `"present"` | - | `absent` to remove |
| `common_parent` | string | null | - | Must share parent |
| `common_relatives` | list | null | - | Must share relatives |
| `deprecation` | string | null | Max 128 chars | Deprecation msg |

### Relationship Kinds

| Kind | Use Case | Typical Pattern |
| ---- | -------- | --------------- |
| `Generic` | Standard relationship | Default, no special semantics |
| `Attribute` | "Belongs to" style | `Device -> DeviceType` |
| `Component` | Parent owns children | `Device -> Interfaces` (many) |
| `Parent` | Child points to parent | `Interface -> Device` (one) |
| `Group` | Group membership | Special group relationships |
| `Hierarchy` | Hierarchical locations | Auto-managed |

### Component/Parent Pattern

Always define both sides with matching `identifier`:

```yaml
# On the parent (Device):
- name: interfaces
  peer: DcimInterface
  kind: Component
  cardinality: many
  identifier: "device__interface"

# On the child (Interface):
- name: device
  peer: DcimGenericDevice
  kind: Parent
  cardinality: one
  optional: false              # Required on every kind: Parent
  identifier: "device__interface"
```

---

## Extensions

Add attributes/relationships to nodes defined in other
schema files:

```yaml
extensions:
  nodes:
    - kind: OrganizationProvider
      attributes:
        - name: website
          kind: URL
          optional: true
      relationships:
        - name: sites
          peer: LocationSite
          cardinality: many
          optional: true
```

### NodeExtensionSchema Properties

| Property | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `kind` | string | **Yes** | Node kind to extend |
| `attributes` | list | No | New attributes to add |
| `relationships` | list | No | New relationships to add |
| `inherit_from` | list | No | Additional generics |

---

## Menu Configuration

Menus are defined in separate YAML files:

```yaml
---
apiVersion: infrahub.app/v1
kind: Menu
spec:
  data:
    - namespace: Dcim
      name: DeviceManagement
      label: Device Management
      icon: "mdi:server"
      children:
        data:
          - namespace: Dcim
            name: Devices
            label: Devices
            kind: DcimGenericDevice
            icon: "mdi:server"
```

### Menu Item Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `namespace` | string | Namespace for the menu item |
| `name` | string | Unique name |
| `label` | string | Display text |
| `icon` | string | MDI/Iconify icon |
| `kind` | string | Optional - node kind for leaves |
| `children.data` | list | Nested sub-menu items |

---

## Built-in Types

These types are built into Infrahub and can be
referenced without defining them:

| Type | Description |
| ---- | ----------- |
| `BuiltinTag` | Tag system (use in `tags` rels) |
| `BuiltinIPAddress` | Base IP address (for IPAM) |
| `BuiltinIPPrefix` | Base IP prefix (for IPAM) |
| `CoreArtifactTarget` | Artifact generation target |

---

## order_weight Convention

| Range | Purpose |
| ----- | ------- |
| 900-999 | Primary relationships |
| 1000-1099 | Primary identifying attributes |
| 1100-1499 | Secondary attributes |
| 1500-1999 | Tertiary/optional attributes |
| 2000-2999 | Advanced/computed/metadata |
| 3000+ | Tags and generic relationships |

---

## Naming Constraints Summary

| Element | Convention | Pattern | Length |
| ------- | ---------- | ------- | ------ |
| Node name | PascalCase | `^[A-Z][a-zA-Z0-9]+$` | 2-32 |
| Namespace | First upper | `^[A-Z][a-z0-9]+$` | 3-32 |
| Attr name | snake_case | `^[a-z0-9\_]+$` | 3-64 |
| Rel name | snake_case | `^[a-z0-9\_]+$` | 3-64 |
| Identifier | snake_case | `^[a-z0-9\_]+$` | max 128 |
| Kind (auto) | NS + Name | - | - |
| Description | Free text | - | max 128 |
| Label (attr) | Free text | - | max 64 |
| Label (node) | Free text | - | max 64 |
