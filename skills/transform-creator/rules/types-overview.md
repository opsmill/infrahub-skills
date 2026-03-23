---
title: Transform Types Overview
impact: CRITICAL
tags: types, python, jinja2, choosing
---

## Transform Types Overview

**Impact:** CRITICAL

Choose the right transform type based on your output needs.

### Comparison

| Type       | Output       | Entry Point   |
| ---------- | ------------ | ------------- |
| **Python** | JSON or text | `transform()` |
| **Jinja2** | Text         | `.j2` file    |

Register Python Transformations under `python_transforms`
and Jinja2 Transformations under `jinja2_transforms` in
`.infrahub.yml`.

### When to Use Python

- Complex data transformations or computations
- Multiple output formats from one query
- Conditional logic that's hard in Jinja2
- CSV output, JSON restructuring
- When you need to combine data from multiple sources

### When to Use Jinja2

- Device configuration rendering
- Text-based output with clear template structure
- When the template closely mirrors the output format
- Simple data-to-text mappings

### When to Use Both (Hybrid)

- Python prepares/cleans the data, Jinja2 renders it
- Platform-specific template selection
  (e.g., `arista_eos.j2` vs `cisco_nxos.j2`)
- Complex data extraction with template-based output

### File Organization

```text
transforms/
  __init__.py
  common.py                      # Shared utilities
  spine.py                       # Python transforms
  topology_cabling.py

templates/
  configs/
    spines/
      arista_eos.j2             # Platform-specific templates
      cisco_nxos.j2
  clab_topology.j2

queries/
  config/
    spine.gql
    leaf.gql
```

Reference: [Infrahub Transform Docs](https://docs.infrahub.app)
