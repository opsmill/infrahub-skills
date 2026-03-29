---
title: GraphQL Query Patterns for Compliance
impact: CRITICAL
tags: graphql, query, filters, pagination
---

## GraphQL Query Patterns for Compliance

Impact: CRITICAL

Compliance queries have different requirements from
generator or transform queries: they often need all
objects of a type (no filtering), must traverse
multiple relationship levels, and sometimes need to
combine data that doesn't naturally live together.
These patterns cover the most common compliance
query shapes.

---

### Pattern 1: Fetch All Objects of a Kind

The baseline compliance query — get every object
with the attributes needed to evaluate the policy.

**Correct:**

```graphql
query AllDevices {
  DcimDevice {
    edges {
      node {
        id
        display_label
        name { value }
        role { value }
        platform {
          node {
            name { value }
          }
        }
        site {
          node {
            name { value }
          }
        }
      }
    }
  }
}
```

Do not add filters unless you intentionally want
to scope the compliance check to a subset.

---

### Pattern 2: Filter by Attribute Value

Scope a compliance check to objects matching a
criterion.

**Correct:**

```graphql
query ActiveLeafDevices {
  DcimDevice(
    role__value: "leaf",
    status__value: "active"
  ) {
    edges {
      node {
        id
        display_label
        name { value }
        interfaces {
          edges {
            node {
              name { value }
              description { value }
            }
          }
        }
      }
    }
  }
}
```

Infrahub GraphQL filter format:
`<attribute>__value: "<value>"` for scalar
attributes,
`<relationship>__<attribute>__value: "<value>"`
for relationship traversal.

---

### Pattern 3: Multi-Level Relationship Traversal

Fetch data across multiple hops for correlation
(e.g., device -> interface -> IP -> prefix).

**Correct:**

```graphql
query DeviceIpCompliance {
  DcimDevice {
    edges {
      node {
        id
        name { value }
        site {
          node {
            name { value }
          }
        }
        interfaces {
          edges {
            node {
              name { value }
              role { value }
              ip_addresses {
                edges {
                  node {
                    id
                    address { value }
                    ip_prefix {
                      node {
                        prefix { value }
                        role { value }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

Each relationship level adds one
`edges { node { ... } }` wrapper.

---

### Pattern 4: Inline Fragments for Generic Types

When querying a generic node kind that has concrete
subtypes, use inline fragments to fetch
subtype-specific fields.

**Correct:**

```graphql
query GenericDeviceCompliance {
  DcimGenericDevice {
    edges {
      node {
        id
        __typename
        display_label
        name { value }
        ... on DcimDevice {
          role { value }
          platform {
            node { name { value } }
          }
        }
        ... on DcimVirtualMachine {
          vcpus { value }
          memory { value }
        }
      }
    }
  }
}
```

Always include `__typename` when using inline
fragments so you can identify the concrete type
in your correlation logic.

---

### Pattern 5: Counting Relationships for Threshold Checks

Fetch relationship lists to count them (e.g.,
"device must have >=2 BGP peers").

**Correct:**

```graphql
query BgpPeerCounts {
  DcimDevice(role__value: "spine") {
    edges {
      node {
        id
        name { value }
        bgp_sessions {
          edges {
            node {
              id
              status { value }
              remote_as {
                node {
                  asn { value }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

Then in correlation:
`len(device["bgp_sessions"]["edges"]) >= 2`.

---

### Pattern 6: Fetching Policy Source Objects

When the policy itself is stored in Infrahub
(e.g., approved VLANs, authorized prefixes),
fetch it as a separate query before the compliance
query.

**Policy source query:**

```graphql
query ApprovedVlans {
  IpamVlan(
    status__value: "active",
    role__value: "approved"
  ) {
    edges {
      node {
        vlan_id { value }
        site {
          node {
            name { value }
          }
        }
      }
    }
  }
}
```

**Current state query:**

```graphql
query InterfaceVlanAssignments {
  DcimInterface(mode__value: "access") {
    edges {
      node {
        id
        name { value }
        untagged_vlan {
          node {
            vlan_id { value }
          }
        }
        device {
          node {
            name { value }
            site {
              node { name { value } }
            }
          }
        }
      }
    }
  }
}
```

Run both queries, build a lookup from the first,
check each item in the second.

---

### Pagination Note

Infrahub returns all objects in a single response
by default (no cursor pagination needed for typical
dataset sizes). If a query returns an unexpectedly
empty `edges` list:

1. Verify the kind name is correct using
   `mcp__infrahub__infrahub_list_schema`
2. Check that the filter values match exactly
   (case-sensitive for `value` fields)
3. Try without filters to confirm data exists

Reference:
[Infrahub GraphQL Query Reference](../../infrahub-common/graphql-queries.md)
