---
title: structure-infrahub-yml
impact: CRITICAL
tags: audit, project-structure, infrahub-yml
---

# Rule: structure-infrahub-yml

**Severity**: CRITICAL
**Category**: Project Structure

## What It Checks

Validates the `.infrahub.yml` file exists, parses
as YAML, uses only recognized top-level keys, and
every `file_path` / `template_path` / directory
reference resolves to an existing path on disk.

## Why it matters

`.infrahub.yml` is the entry point Infrahub reads
to discover everything else in the repository —
if it fails to parse or references a missing
file, the sync aborts before any schema, query,
or check is loaded, and the proposed change
pipeline reports a generic "repository sync
failed" with the actual cause buried in server
logs. Typo-level mistakes (one transposed letter
in a file path) produce exactly the same opaque
failure as structural ones. Unknown top-level
keys are ignored silently in older Infrahub
versions and rejected loudly in newer ones, so a
section that "worked yesterday" can break on
upgrade. Validating this at audit time turns a
runtime sync failure into a localizable file-and-
line finding.

## Checks

1. `.infrahub.yml` exists in the project root
2. File is valid YAML (no syntax errors)
3. Only recognized top-level keys are present:
   `schemas`, `menus`, `objects`, `queries`,
   `check_definitions`, `python_transforms`,
   `jinja2_transforms`, `artifact_definitions`,
   `generator_definitions`
4. Every `file_path`, `template_path`, and directory
   path resolves to an existing file or directory
5. Required fields per section type are present (see `.infrahub.yml` reference)
6. No duplicate `name` values within any section
7. Query names are unique across all `queries` entries

## Common Issues

- Typo in file path (e.g., `checks/my_chek.py` instead of `checks/my_check.py`)
- Directory listed under `schemas:` does not exist
- Missing `name` field on a query entry
- Duplicate names causing silent overwrites
