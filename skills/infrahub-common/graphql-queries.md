# GraphQL Queries for Infrahub

GraphQL queries are the data layer for checks, transforms,
and generators. They fetch data from Infrahub's API and pass
it to your Python code.

## Contents

- [File Format](#file-format)
- [Query Structure](#query-structure)
- [Infrahub GraphQL Conventions](#infrahub-graphql-conventions)
- [Response Data Structure](#response-data-structure)
- [File Organization](#file-organization)
- [Best Practices](#best-practices)

## File Format

Queries are stored as `.gql` files and registered in
`.infrahub.yml`:

```yaml
queries:
  - name: my_query
    file_path: queries/my_query.gql
```

## Query Structure

### Global Query (No Variables)

Used by global checks that validate all objects of a type:

```graphql
query RackDevices {
  DcimGenericDevice {
    edges {
      node {
        id
        __typename
        display_label
        name {
          value
        }
        rack {
          node {
            id
            name {
              value
            }
          }
        }
      }
    }
  }
}
```

### Targeted Query (With Variables)

Used by targeted checks, transforms, and generators. The
variable name must match the `parameters` key in
`.infrahub.yml`:

```graphql
query spine_config($device: String!) {
  DcimDevice(name__value: $device) {
    edges {
      node {
        id
        name { value }
        role { value }
        device_type {
          node {
            name { value }
            manufacturer {
              node { name { value } }
            }
          }
        }
        interfaces {
          edges {
            node {
              name { value }
              status { value }
              role { value }
            }
          }
        }
      }
    }
  }
}
```

**How it connects:**

```yaml
# .infrahub.yml
check_definitions:
  - name: validate_spine
    file_path: checks/spine.py
    targets: spines              # Group of target objects
    parameters:
      device: name__value        # $device = target's name
```

When Infrahub runs this check for a device named
`spine-01`, it executes the query with
`$device = "spine-01"`.

### Declared variables must be used

Infrahub uses `graphql-core`, which enforces the
GraphQL spec's `NoUnusedVariables` validation rule
by default. A query that declares `$device: String!`
but never references `$device` in its body is
rejected at validation time (before any field
resolver runs) with an error of the form:

```text
Variable '$device' is never used in operation 'Q'.
```

Because validation runs before execution, the
rejection fires every time the query is rendered —
including for global queries copy-pasted from a
targeted base — so a stray unused `$device` is
enough to block an otherwise correct query.

When converting a targeted query into a global one
(or vice versa), strip the variable declaration as
well as the filter that used it. Empty parens
(`query Q { ... }` with no variables) are valid;
declared-but-unused variables are not.

### Inline fragments populate fields, but `__typename` returns the concrete kind

A query using a generic kind plus inline fragments
selects subtype-specific fields only on matching
nodes:

```graphql
DcimInterface {
  edges {
    node {
      __typename
      name { value }
      ... on InfraInterfaceLayer2 {
        l2_mode { value }
      }
    }
  }
}
```

For each result node, `__typename` resolves to the
**concrete kind** (`InfraInterfacePhysical`,
`InfraInterfaceVirtual`, ...) — not the generic
(`InfraInterfaceLayer2`) named in the fragment.
Branches that compare `__typename` against the
generic name will never fire.

Discriminate on field presence instead: subtype
fields are only populated on nodes the fragment
matched, so `iface.l2_mode is defined and
iface.l2_mode.value` is a reliable signal that this
node is an `InfraInterfaceLayer2`. Field-presence
also survives schema renames cleanly, where a
hardcoded kind name does not. See the worked Jinja2
template in
[../infrahub-managing-transforms/rules/jinja2-template.md](../infrahub-managing-transforms/rules/jinja2-template.md#discriminating-subtypes--dont-trust-__typename-alone).

## Infrahub GraphQL Conventions

### Data Access Pattern

All queries follow the `edges/node` pattern
(Relay-style pagination):

```graphql
MyNodeKind {
  edges {
    node {
      # fields here
    }
  }
}
```

### Attribute Fields

Attributes are nested under a `value` key:

```graphql
name { value }           # Text attribute
status { value }         # Dropdown attribute
rack_u_position { value } # Number attribute
is_full_depth { value }  # Boolean attribute
```

### Relationship Fields (cardinality: one)

Single relationships use `node` nesting:

```graphql
rack {
  node {
    id
    name { value }
  }
}

device_type {
  node {
    model { value }
    manufacturer {
      node {
        name { value }
      }
    }
  }
}
```

### Relationship Fields (cardinality: many)

Many relationships use `edges/node`:

```graphql
interfaces {
  edges {
    node {
      name { value }
      status { value }
    }
  }
}

tags {
  edges {
    node {
      name { value }
    }
  }
}
```

### Cardinality Decides the Shape

**Which of the two shapes above a relationship takes is
decided by its `cardinality`.** Nothing else selects
between them:

| Cardinality | GraphQL type | Selection |
| ----------- | ------------ | --------- |
| `one` | `NestedEdged<Kind>` | `rel { node { … } }` |
| `many` | `NestedPaginated<Kind>` | `rel { edges { node { … } } }`, plus `count` |

`count` exists only on the `many` shape.

On a hierarchical kind the generated fields do not follow
what you declared: `parent` is always node-shaped, while
`children`, `ancestors` and `descendants` are always
edges-shaped.

#### Changing a cardinality is a query migration

Because cardinality selects the shape, **changing a
relationship's cardinality breaks every existing query
that selects it.** A repository may have a dozen across
checks, transforms and generators. The failure is a
server error, not a validation message, and it names an
internal wrapper type rather than the relationship or the
schema change:

```text
Cannot query field 'edges' on type 'NestedEdged<Kind>'
```

The reverse migration gives the mirror:

```text
Cannot query field 'node' on type 'NestedPaginated<Kind>'
```

`NestedEdged<Kind>` and `NestedPaginated<Kind>` appear
nowhere in your schema, your `.gql` files, or the
documentation, so a reader who has just widened a
cardinality has no reason to connect the two. That is the
whole reason this is worth writing down.

A `.gql` file cannot be unit tested, so a query that has
stopped executing is invisible to an offline suite. Dry-run
every migrated query instead: see
[rules/deployment-gql-dry-run.md](rules/deployment-gql-dry-run.md)
for the command per transform type.

The procedure for finding and migrating the affected
queries belongs to the schema change, and lives in
[../infrahub-managing-schemas/rules/relationship-cardinality-consequences.md](../infrahub-managing-schemas/rules/relationship-cardinality-consequences.md).

### Stored Queries Are Part of a Schema Change's Blast Radius

Cardinality is one trigger. The general statement:
**every stored query that selects a field is invalidated
when that field changes or goes away.** Removing an
attribute or a relationship does it too.

Which failure you get depends only on whether the `.gql`
file itself changed:

| The `.gql` file | Where it fails |
| --------------- | -------------- |
| unchanged | the stored query stays in place and fails **at execution**, whenever something next runs it |
| changed, or the repository re-imported from scratch | **at repository import**, because creating the query object validates the text against the live schema: `Query is not valid, …` |

The import-time failure names **the query**, not the
schema change that invalidated it, so a destroy-and-reload
cycle can fail twice before the cause is found. Nothing
fails at the step you made the change in: `schema check`
passes, `schema load` passes, and the break appears one
command later in a subsystem that does not mention
attributes.

So removing or retyping a field has a query-side
precondition. The schema skill owns it:
[../infrahub-managing-schemas/rules/relationship-cardinality-consequences.md](../infrahub-managing-schemas/rules/relationship-cardinality-consequences.md).

### Inline Fragments (Generics/Polymorphism)

When querying a Generic type that has multiple concrete
implementations, use `... on` fragments:

```graphql
location {
  node {
    ... on LocationGeneric {
      name { value }
    }
  }
}

device_services {
  edges {
    node {
      __typename
      name { value }
      status { value }

      ... on ServiceBGP {
        local_as {
          node { asn { value } }
        }
        remote_as {
          node { asn { value } }
        }
      }

      ... on ServiceOSPF {
        process_id { value }
        version { value }
      }
    }
  }
}
```

### Filtering

Filter using `__` notation on query arguments:

```graphql
# Filter by exact value
DcimDevice(name__value: "spine-01") { ... }

# With variable
query my_query($device: String!) {
  DcimDevice(name__value: $device) { ... }
}
```

### Common Fields to Include

Always include these for object identification:

```graphql
node {
  id               # Infrahub internal ID
  __typename       # Concrete node type
  display_label    # Human-readable label
  name { value }   # Primary identifier
}
```

## Response Data Structure

The GraphQL response arrives in your Python code as nested
dictionaries:

```python
# For a query like:
# DcimDevice { edges { node { name { value } } } }
data = {
    "DcimDevice": {
        "edges": [
            {
                "node": {
                    "id": "abc-123",
                    "__typename": "DcimDevice",
                    "name": {"value": "spine-01"},
                    "status": {"value": "active"},
                    "rack": {
                        "node": {
                            "id": "def-456",
                            "name": {
                                "value": "Rack-A"
                            }
                        }
                    },
                    "interfaces": {
                        "edges": [
                            {
                                "node": {
                                    "name": {
                                        "value": "eth0"
                                    },
                                    "status": {
                                        "value": "active"
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        ]
    }
}
```

### Extracting Data

Common patterns for navigating the response:

```python
# Get list of devices
edges = data["DcimDevice"]["edges"]
for edge in edges:
    device = edge["node"]
    name = device["name"]["value"]

# Get a relationship (cardinality: one)
rack_name = (
    device["rack"]["node"]["name"]["value"]
)

# Get a relationship (cardinality: many)
for intf_edge in device["interfaces"]["edges"]:
    intf = intf_edge["node"]
    intf_name = intf["name"]["value"]
```

## File Organization

```text
queries/
  rack_devices.gql              # Global queries
  config/
    spine.gql                   # Device config queries
    leaf.gql
    edge.gql
  topology/
    dc.gql                      # Topology queries
    pop.gql
  validation/
    loadbalancer_validation.gql # Validation queries
  segment/
    segment.gql                 # Service queries
```

## Best Practices

1. **Query only what you need** -- don't fetch entire
   objects if you only need a few fields
2. **Include `id` and `__typename`** -- needed for
   `log_error()` calls in checks and object tracking
   in generators
3. **Use inline fragments** for Generic/polymorphic types
4. **Match variable names** to the `parameters` keys
   in `.infrahub.yml`
5. **Organize by purpose** -- group queries into
   subdirectories (config/, topology/, validation/)
