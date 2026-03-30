# GraphQL Queries for Infrahub

GraphQL queries are the data layer for checks, transforms,
and generators. They fetch data from Infrahub's API and pass
it to your Python code.

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
