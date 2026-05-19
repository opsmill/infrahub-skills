# Rule: xref-query-names

**Severity**: HIGH
**Category**: Cross-References

## What It Checks

Validates that query names are consistent between
Python class attributes, `.infrahub.yml` query entries,
and GraphQL file contents.

## Checks

1. Every `query` class attribute in a
   check/generator/transform Python file matches a
   `name` in the `queries` section of `.infrahub.yml`
2. Every `query` field in `jinja2_transforms` matches
   a query `name`
3. Every query registered in `.infrahub.yml` is
   actually used by at least one component (orphan
   query detection)
4. The `.gql` file content is valid GraphQL syntax

## Common Issues

- Python class has `query = "my_query"` but `.infrahub.yml` has `name: my_query_v2`
- Query registered but never referenced by any check, transform, or generator
- Typo in query name causing runtime "query not found" errors
