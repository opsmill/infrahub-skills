# Repo Auditor Rule Sections

Rules are organized by audit phase. Each rule file contains the checks to perform and the expected outcomes.

| Priority | Category | Prefix | Description |
|----------|----------|--------|-------------|
| CRITICAL | Project Structure | `structure-` | .infrahub.yml validation, file path resolution, required sections |
| CRITICAL | Schema | `schema-` | Naming, relationships, attributes, hierarchy, display settings |
| CRITICAL | Objects | `objects-` | YAML format, value types, relationship references, children |
| CRITICAL | Python Components | `python-` | Class inheritance, method signatures, query attribute matching |
| HIGH | Cross-References | `xref-` | Query name consistency, target group references, parameter mapping |
| HIGH | Registration | `registration-` | All components declared in .infrahub.yml, no orphan files |
| MEDIUM | Best Practices | `practices-` | human_friendly_id, display_label, order_weight, load order |
| MEDIUM | Deployment | `deployment-` | Git status, bootstrap file placement, repo type selection |
| LOW | Patterns | `patterns-` | Code organization, file naming, common pattern adherence |
