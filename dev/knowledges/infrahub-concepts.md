# Infrahub Concepts for Skill Development

Key Infrahub concepts that inform how the skills are
written. This is not a substitute for the
[Infrahub documentation](https://docs.infrahub.app/)
— it covers what skill authors need to know to write
effective rules and examples.

## Schema

The schema defines the data model. It's a YAML file
starting with `version: "1.0"` and containing `nodes`
and/or `generics`.

### Nodes

A node is a data type — a device, location, VLAN,
circuit, etc. Each node has:

- **Namespace + Name** — Together form the `kind`
  (e.g., `InfraDevice`). The namespace groups related
  nodes; the name identifies the specific type.
- **Attributes** — Data fields on the node (Text,
  Number, Dropdown, Boolean, etc.)
- **Relationships** — Links to other nodes (Component,
  Parent, Attribute, Generic)

### Generics

A generic is an abstract base type. Nodes can
`inherit_from` a generic to share attributes,
relationships, and behavior. Key use case:
`hierarchical: true` generics for location trees.

### Relationships

Relationships are always bidirectional in Infrahub —
both sides must be defined with matching identifiers.
This is the #1 source of errors skill users make,
which is why `relationship-identifiers` is a rule in
multiple skills.

Relationship kinds:

- **Attribute** — A reference between peers
  (most common)
- **Component** — Child belongs to parent; deleted
  when parent is deleted
- **Parent** — The other side of a Component
  relationship
- **Generic** — Relationship to a generic type
  (resolved at query time)

### Key Display Properties

- **`human_friendly_id`** — Fields that uniquely
  identify an object in the UI
  (e.g., `["name__value"]`)
- **`display_label`** — Jinja2 template for how the
  object appears in dropdowns and references
  (e.g., `"{{ name__value }}"`)
- **`order_weight`** — Integer controlling attribute
  display order in the UI (lower = first)

### Common Gotchas

These are the things the skills' rules are
specifically designed to catch:

| Gotcha | Skill Rule |
| ------ | --------- |
| Using `String` instead of `Text` (deprecated) | schema-creator: attribute-defaults-and-types |
| Attribute name < 3 characters | schema-creator: naming-conventions |
| `display_labels` (plural) instead of `display_label` (singular) | schema-creator: display-human-friendly-id |
| Mismatched relationship identifiers | schema-creator: relationship-identifiers |
| Missing `human_friendly_id` | schema-creator: display-human-friendly-id |
| Short kind references (`VlanGroup` vs `IpamVlanGroup`) | schema-creator: relationship-peer-kind |

## .infrahub.yml

The project configuration file. Registers checks,
Generators, Transformations, and other artifacts with
the Infrahub server. Reference:
`skills/common/infrahub-yml-reference.md`.

## GraphQL Queries

Checks, Generators, and Transformations all use
GraphQL to fetch data from Infrahub. The query syntax has
Infrahub-specific conventions. Reference:
`skills/common/graphql-queries.md`.

## Proposed Changes

Infrahub uses a branch-based workflow. A proposed
change is like a pull request — it contains schema
and data modifications that can be reviewed, validated
(via checks), and merged. Checks run automatically in
the proposed change pipeline.
