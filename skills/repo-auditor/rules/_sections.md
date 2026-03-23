# Repo Auditor Rule Sections

Rules are organized by audit phase. Each rule file
contains the checks to perform and the expected outcomes.

| Priority | Category | Prefix | Description |
| -------- | -------- | ------ | ----------- |
| CRITICAL | Structure | `structure-` | .infrahub.yml, file paths |
| CRITICAL | Schema | `schema-` | Naming, relationships, deprecated fields |
| CRITICAL | Objects | `objects-` | YAML format, values, refs |
| CRITICAL | Python | `python-` | Class inheritance, methods |
| HIGH | Cross-Refs | `xref-` | Query name consistency |
| HIGH | Registration | `registration-` | All components declared |
| MEDIUM | Practices | `practices-` | human_friendly_id, display |
| MEDIUM | Deployment | `deployment-` | Git status, bootstrap |
| LOW | Patterns | `patterns-` | Code org, file naming |
