---
title: Emit Three Files in Load Order
impact: MEDIUM
tags: output, load-order, branch, references
---

## Emit Three Files in Load Order

Impact: MEDIUM

Split the output into manufacturers, device types, and
templates, numbered in dependency order, and load them
onto a dedicated branch.

### Why it matters

Each stage references the one before it by
`human_friendly_id`. A device type names its
manufacturer; a template names its device type. The
loader resolves references against what already
exists, so a template loaded before its device type
fails with "reference not found" — and it fails after
the earlier files have already written, leaving a
branch in a partial state.

Numbering the filenames makes the order visible in a
directory listing and lets a glob load them correctly:

```text
generated/
├── 01_manufacturers.yml     # OrganizationManufacturer
├── 02_device_types.yml      # DcimDeviceType  → manufacturer
├── 03_device_templates.yml  # TemplateDcimDevice → device_type
└── coverage-report.md
```

### Loading

Load onto a branch, never the default branch. A bulk
import of hundreds of device types written straight to
`main` is undone object by object; a bad branch is
discarded in one command.

```bash
infrahubctl branch create netbox-import
for file in generated/0*.yml; do
  infrahubctl object load "$file" --branch netbox-import
done
```

Review the branch, then merge it through a proposed
change.

**Wrong — one file, everything interleaved:**

```yaml
# templates.yml — device types and templates in one document
# order within a single spec.data is not a dependency guarantee
```

**Wrong — straight to the default branch:**

```bash
infrahubctl object load generated/03_device_templates.yml
```

### Common mistakes

- **Loading templates before device types.** The
  `device_type` reference cannot resolve.
- **Assuming manufacturers already exist.** They may,
  and re-loading them is idempotent — but assuming
  wrongly breaks the whole batch.
- **Skipping the branch.** See
  [../../infrahub-managing-objects/rules/workflow-branch-first.md](../../infrahub-managing-objects/rules/workflow-branch-first.md).
