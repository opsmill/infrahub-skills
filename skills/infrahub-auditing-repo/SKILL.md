---
name: infrahub-auditing-repo
description: >-
  Audits an Infrahub repository against best practices and rules, producing a structured compliance report.
  TRIGGER when: reviewing repo for compliance, onboarding to existing project, pre-deployment validation, catching issues.
  DO NOT TRIGGER when: creating schemas, writing checks/generators, querying live data, populating objects.
context: fork
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
argument-hint: "[focus-area]"
metadata:
  version: 1.2.4
  author: OpsMill
---

# Infrahub Repo Auditor

## Overview

Comprehensive audit of an Infrahub repository against
all rules and best practices from the infrahub-skills
plugin. Produces a structured report covering schemas,
objects, checks, generators, transforms, menus,
`.infrahub.yml` configuration, and deployment readiness.

## Project Context

Project structure:
!`find . -maxdepth 2 -type f \( -name "*.yml" -o -name "*.yaml" -o -name "*.py" -o -name "*.gql" -o -name "*.j2" \) 2>/dev/null | head -40`

Infrahub config:
!`cat .infrahub.yml 2>/dev/null || echo "No .infrahub.yml found"`

## When to Use

- Before deploying a repository to Infrahub
- When onboarding to an existing Infrahub project
- After significant refactoring to catch regressions
- As a periodic quality gate in development workflows
- When troubleshooting schema loading, object sync,
  or pipeline failures

## How It Works

When invoked, the auditor:

1. **Discovers** the project structure
   (`.infrahub.yml`, schemas, objects, checks,
   generators, transforms, menus)
2. **Validates** each component against the rules
   defined in the infrahub-skills plugin
3. **Cross-references** between components (e.g.,
   query names match between Python files and
   `.infrahub.yml`)
4. **Generates** a markdown report with findings organized by severity

## Audit Categories

| Priority | Category | What It Checks |
| -------- | -------- | -------------- |
| CRITICAL | Project Structure | `.infrahub.yml` exists, paths valid |
| CRITICAL | Schema Validation | Naming, relationships, deprecated fields |
| CRITICAL | Object Validation | YAML structure, value types, refs |
| CRITICAL | Python Components | Class inheritance, required methods |
| HIGH | Cross-References | Query names match, target groups |
| HIGH | Relationships | Bidirectional IDs, cardinality |
| HIGH | Registration | All files registered, no orphans |
| MEDIUM | Best Practices | human_friendly_id, display_label |
| MEDIUM | Deployment | Git status, bootstrap placement |
| LOW | Patterns & Style | Code organization, naming |

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

- **[../infrahub-managing-schemas/](../infrahub-managing-schemas/)** -- Naming,
  relationships, attributes, hierarchy, display,
  extensions, uniqueness, migration
- **[../infrahub-managing-objects/](../infrahub-managing-objects/)** -- Format,
  values, children, ranges, organization
- **[../infrahub-managing-checks/](../infrahub-managing-checks/)** --
  Architecture, Python class, API, registration
- **[../infrahub-managing-generators/](../infrahub-managing-generators/)** --
  Architecture, Python class, tracking, API
- **[../infrahub-managing-transforms/](../infrahub-managing-transforms/)** --
  Types, Python/Jinja2, hybrid, artifacts, API
- **[../infrahub-managing-menus/](../infrahub-managing-menus/)** -- Format,
  item properties, hierarchy, icons
- **[../infrahub-common/](../infrahub-common/)** -- Git integration,
  caching, `.infrahub.yml` reference, GraphQL

## Rules

See [rules/](./rules/) for detailed audit rule definitions.
