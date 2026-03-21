---
title: Resources Testing Framework
impact: HIGH
tags: testing, resources, pytest, yaml, ci, checks, transforms, queries
---

## Resources Testing Framework

**Impact: HIGH**

Infrahub provides a YAML-driven, pytest-based testing framework for validating checks, transforms, and GraphQL queries without writing Python test code. Tests are defined in YAML files and executed automatically by the Infrahub SDK's pytest plugin.

**Always create tests when creating a new check, transform, or query.** Tests catch regressions early and run automatically in the proposed change pipeline.

### YAML Structure

Test files must start with the `test_` prefix (e.g., `test_checks.yml`, `test_transforms.yml`) and follow this structure:

```yaml
---
version: "1.0"
infrahub_tests:
  - resource: Check              # Check | PythonTransform | Jinja2Transform | GraphQLQuery
    resource_name: my_check      # Must match the name in .infrahub.yml
    tests:
      - name: descriptive_test_name
        spec:
          kind: check-smoke      # Test kind (see below)
        expect: PASS             # PASS (default) or FAIL
```

### Test Tiers

| Tier | Purpose | Requires Server | Fixture Files |
|------|---------|-----------------|---------------|
| **Smoke** | Validates syntax and structure | No | None |
| **Unit** | Verifies processing with fixture data | No | `input.json`, output file |
| **Integration** | Validates against a live Infrahub instance | Yes | `variables.json` (optional) |

### Supported Resource Types and Test Kinds

| Resource | Smoke | Unit | Integration |
|----------|-------|------|-------------|
| `Check` | `check-smoke` | `check-unit-process` | `check-integration` |
| `PythonTransform` | `python-transform-smoke` | `python-transform-unit-process` | `python-transform-integration` |
| `Jinja2Transform` | `jinja2-transform-smoke` | `jinja2-transform-unit-render` | `jinja2-transform-integration` |
| `GraphQLQuery` | `graphql-query-smoke` | — | `graphql-query-integration` |

### Spec Fields

- **`kind`** (required): The test kind string from the table above
- **`directory`** (optional): Path to fixture directory containing input/output files
- **`input`** (optional): Input fixture filename (default: `input.json`)
- **`output`** (optional): Expected output fixture filename
- **`variables`** (optional, integration only): Variables filename (default: `variables.json`)

### Expect Field

- **`PASS`** (default): Test succeeds when the resource processes without errors
- **`FAIL`**: Test succeeds when the resource produces errors (useful for testing error detection)

### How to Run

```bash
# Run all tests in the tests/ directory
pytest tests/

# Run a specific test file
pytest tests/test_checks.yml

# Verbose output
pytest tests/ -v
```

The Infrahub SDK includes a pytest plugin that automatically discovers and parses `test_*.yml` files.

### CI Integration

Tests run automatically in the proposed change pipeline. When a proposed change is created or updated, the Task worker executes `pytest` against all test files in the repository. Each test generates a check result recording the outcome and any failure messages.

### Fixture Directory Layout

```
tests/
  test_checks.yml
  test_transforms.yml
  fixtures/
    check_tag_naming/
      input.json               # GraphQL response data for unit tests
    spine_transform/
      input.json               # GraphQL response data
      output.txt               # Expected rendered output
```

### Incorrect / Correct

**Incorrect** -- creating a check without tests:

```
checks/
  tag_naming.py
queries/
  tags.gql
```

**Correct** -- always include test definitions:

```
checks/
  tag_naming.py
queries/
  tags.gql
tests/
  test_checks.yml
  fixtures/
    check_tag_naming/
      input.json
```

Reference: [Resources Testing Framework](https://docs.infrahub.app/topics/resources-testing-framework) | [Test Configuration Reference](https://docs.infrahub.app/reference/infrahub-tests)
