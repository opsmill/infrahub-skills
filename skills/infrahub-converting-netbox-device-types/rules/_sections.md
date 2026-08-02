## Rule Categories

| Prefix | Category | Description |
| ------ | -------- | ----------- |
| `workflow` | Workflow | Schema prerequisites and the order operations must happen in |
| `mapping` | Mapping | How NetBox fields are bound to Infrahub kinds and attributes |
| `format` | Format | Structure of the emitted object and template YAML |
| `naming` | Naming | Template name derivation and uniqueness |
| `coverage` | Coverage | Reporting data that did not survive the conversion |
| `output` | Output | File layout, load order, and how the result reaches Infrahub |

## Rules

| Rule | Impact |
| ---- | ------ |
| [workflow-schema-prerequisites.md](./workflow-schema-prerequisites.md) | CRITICAL |
| [mapping-profile-driven.md](./mapping-profile-driven.md) | CRITICAL |
| [mapping-fallback-sources.md](./mapping-fallback-sources.md) | HIGH |
| [format-template-objects.md](./format-template-objects.md) | CRITICAL |
| [naming-template-names.md](./naming-template-names.md) | HIGH |
| [coverage-report-unmapped.md](./coverage-report-unmapped.md) | HIGH |
| [output-load-order.md](./output-load-order.md) | MEDIUM |
