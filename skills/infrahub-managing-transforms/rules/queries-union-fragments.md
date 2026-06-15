---
title: Querying Union-Typed Relationships with Inline Fragments
impact: CRITICAL
tags: gql, query, union, generic, inline-fragment, location
---

## Querying Union-Typed Relationships with Inline Fragments

**Impact:** CRITICAL

When a relationship's ``peer:`` in the schema is a **generic**
(or any type with multiple concrete inheritors that diverge in
fields), the GraphQL query must use inline fragments
(``... on TypeName { fields }``) to select fields that exist on
some inheritors but not others. Selecting such fields directly
on the union fails for any concrete instance whose type doesn't
define the field — the server returns
``Cannot query field 'X' on type 'Y'`` and the entire query
errors out.

### Common union-typed relationships in Infrahub's base schema

| Node.relationship | Peer (union) | Concrete inheritors |
| ----------------- | ------------ | ------------------- |
| ``DcimDevice.location`` | ``LocationGeneric`` | ``LocationSite``, ``LocationBuilding``, ``LocationHosting`` |
| ``OrganizationGeneric`` peers | ``OrganizationGeneric`` | ``OrganizationManufacturer``, ``OrganizationProvider``, ``OrganizationTenant`` |

The exact fields that diverge depend on your deployment's schema
— in some base-schema versions ``name``/``shortname`` live on the
generic itself and are queryable directly. The durable point is
the *pattern*, not these specific fields: when a union's
inheritors diverge, wrap the diverging fields in inline
fragments. Always check ``peer:`` and each inheritor's attributes
before writing the query.

### Anti-pattern

```graphql
query {
  DcimDevice {
    edges {
      node {
        location {
          node {
            name { value }       # fails on any inheritor lacking this field
            shortname { value }
          }
        }
      }
    }
  }
}
```

Server response when the dataset contains a ``LocationHosting``
instance:

```text
Cannot query field 'name' on type 'LocationHosting'.
```

In a ``CoreRepository`` import, this stops the schema-sync; the
repo never finishes loading and downstream pipelines fail with
no obvious root cause.

### Correct pattern

```graphql
query {
  DcimDevice {
    edges {
      node {
        location {
          node {
            ... on LocationSite { name { value } shortname { value } }
            ... on LocationBuilding { name { value } }
            # A subtype that defines neither — skip it, or
            # include only the fields it actually defines.
          }
        }
      }
    }
  }
}
```

### How to know if a relationship needs fragments

1. Find the relationship in the schema. Inspect ``peer:``.
2. If ``peer:`` is a generic type (or matches a ``generics:``
   entry by namespace+name), the relationship is a union.
3. Find every node with ``inherit_from:`` containing that
   generic. Check whether each declares the same attribute
   set. If they diverge, you need fragments.
4. When in doubt, use fragments. They never hurt; their
   absence does.

### Verify before merge

This failure is invisible to ``infrahubctl schema check`` and
YAML validation — it only surfaces when ``CoreRepository``
executes the query during schema-sync. So before opening a PR
that changes a ``.gql`` file, dry-run the query against a live
schema (``infrahubctl render <transform> --branch <branch>``,
or run the check/generator that owns the query). See the shared
rule
[../../infrahub-common/rules/deployment-gql-dry-run.md](../../infrahub-common/rules/deployment-gql-dry-run.md).

Reference:
[Infrahub schema docs](https://docs.infrahub.app)
