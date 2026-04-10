# Rule: structure-infrahub-yml

**Severity**: CRITICAL
**Category**: Project Structure

## What It Checks

Validates the `.infrahub.yml` file exists, is valid
YAML, contains recognized sections, and all
file/directory references resolve to existing paths.

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
