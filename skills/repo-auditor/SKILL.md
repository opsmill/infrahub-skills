---
name: infrahub-repo-auditor
description: Audit an Infrahub repository against all best practices and rules. Use when reviewing a project for compliance, onboarding to an existing repo, or before deployment to catch issues early.
---

## Overview

Comprehensive audit of an Infrahub repository against all rules and best practices from the infrahub-skills plugin. Produces a structured report covering schemas, objects, checks, generators, transforms, menus, `.infrahub.yml` configuration, and deployment readiness.

## When to Use

- Before deploying a repository to Infrahub (pre-flight check)
- When onboarding to an existing Infrahub project
- After significant refactoring to catch regressions
- As a periodic quality gate in development workflows
- When troubleshooting issues with schema loading, object sync, or pipeline failures

## How It Works

When invoked, the auditor:

1. **Discovers** the project structure (`.infrahub.yml`, schemas, objects, checks, generators, transforms, menus)
2. **Validates** each component against the rules defined in the infrahub-skills plugin
3. **Cross-references** between components (e.g., query names match between Python files and `.infrahub.yml`)
4. **Generates** a markdown report with findings organized by severity

## Audit Categories

| Priority | Category | What It Checks |
|----------|----------|----------------|
| CRITICAL | Project Structure | `.infrahub.yml` exists, required sections present, file paths valid |
| CRITICAL | Schema Validation | Naming conventions, relationship setup, peer kinds, identifiers, deprecated field migration (`display_labels` → `display_label`) |
| CRITICAL | Object Validation | YAML structure, apiVersion/kind, value types, relationship references |
| CRITICAL | Python Components | Check/generator/transform classes inherit correctly, required methods exist |
| HIGH | Cross-Reference Integrity | Query names match between `.infrahub.yml` and Python `query` attributes, target groups referenced consistently |
| HIGH | Relationship Consistency | Bidirectional identifiers match, Component/Parent cardinality correct |
| HIGH | Registration Completeness | All Python files registered, all queries declared, all transforms linked to artifacts |
| MEDIUM | Best Practices | `human_friendly_id` on nodes, `display_label` set, load order correct, `order_weight` ranges |
| MEDIUM | Deployment Readiness | Git status clean, bootstrap files outside `objects/`, no uncommitted changes |
| LOW | Patterns & Style | Common patterns followed, code organization, file naming conventions |

## Running the Audit

Tell Claude: **"Audit this Infrahub repo"** or **"Run the Infrahub repo auditor"**

The auditor will scan the current working directory and produce a report.

## Report Format

The report is written to `AUDIT_REPORT.md` in the project root with this structure:

```markdown
# Infrahub Repository Audit Report

## Summary
- Total findings: N
- Critical: N | High: N | Medium: N | Low: N | Info: N

## Project Structure
...

## Schema Audit
...

## Object Data Audit
...

## Checks Audit
...

## Generators Audit
...

## Transforms Audit
...

## Menus Audit
...

## Cross-Reference Integrity
...

## Deployment Readiness
...
```

## Audit Rules Reference

The auditor checks rules from all skills:

- **[../schema-creator/](../schema-creator/)** -- Naming, relationships, attributes, hierarchy, display, extensions, uniqueness, migration
- **[../object-creator/](../object-creator/)** -- Format, values, children, ranges, organization
- **[../check-creator/](../check-creator/)** -- Architecture, Python class, API, registration, patterns
- **[../generator-creator/](../generator-creator/)** -- Architecture, Python class, tracking, API, registration
- **[../transform-creator/](../transform-creator/)** -- Types, Python/Jinja2, hybrid, artifacts, API
- **[../menu-creator/](../menu-creator/)** -- Format, item properties, hierarchy, icons, schema integration
- **[../common/](../common/)** -- Git integration, display label caching, `.infrahub.yml` reference, GraphQL queries

## Rules

See [rules/](./rules/) for detailed audit rule definitions.
