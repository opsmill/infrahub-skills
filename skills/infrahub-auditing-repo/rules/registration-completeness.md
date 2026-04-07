# Rule: registration-completeness

**Severity**: HIGH
**Category**: Registration

## What It Checks

Ensures all project files are properly registered in
`.infrahub.yml` and no orphan files exist.

## Checks

1. All Python files containing `InfrahubCheck`,
   `InfrahubGenerator`, or `InfrahubTransform`
   subclasses are registered in the appropriate
   `.infrahub.yml` section
2. All `.gql` files are referenced by a `queries` entry
3. All Jinja2 templates (`.j2` files) are referenced by a `jinja2_transforms` entry
4. Schema files are under a path listed in `schemas:`
5. Object files are under a path listed in `objects:`
6. Menu files are listed under `menus:`
7. No orphan Python/query/template files that aren't registered

## Common Issues

- New Python check file created but not added to `check_definitions`
- Query `.gql` file not registered in `queries` section
- Jinja2 template created but not linked via `jinja2_transforms`
- Schema file outside the `schemas:` directory path
