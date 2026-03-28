---
title: Resources Testing Framework for Checks
impact: HIGH
tags: testing, checks, pytest, yaml
---

## Resources Testing Framework for Checks

**Impact: HIGH**

Checks should always have accompanying test definitions. The Resources Testing Framework provides three test kinds for checks, from lightweight syntax validation to full integration testing.

See [Resources Testing Framework](../../common/rules/testing-resource-framework.md) for the general framework overview, YAML structure, and how to run tests.

### Check Test Kinds

| Kind | Purpose | Requires Server | Fixture Files |
|------|---------|-----------------|---------------|
| `check-smoke` | Validates check syntax and structure | No | None |
| `check-unit-process` | Runs validate() with fixture data | No | `input.json`, output (optional) |
| `check-integration` | Runs check against live Infrahub | Yes | `variables.json` (optional) |

### Smoke Test

Validates that the check Python file and its associated query can be parsed without errors. No fixture data needed.

```yaml
- name: smoke_tag_naming
  spec:
    kind: check-smoke
```

### Unit Test (`check-unit-process`)

Feeds fixture data (a saved GraphQL response) into the check's `validate()` method and verifies the outcome. Use `expect: PASS` for valid data and `expect: FAIL` for data that should trigger errors.

```yaml
- name: unit_tag_naming_valid
  spec:
    kind: check-unit-process
    directory: fixtures/check_tag_naming
    input: input.json          # Default, can be omitted
  expect: PASS

- name: unit_tag_naming_invalid
  spec:
    kind: check-unit-process
    directory: fixtures/check_tag_naming_invalid
    input: input.json
  expect: FAIL                 # Expects log_error() to be called
```

The `input.json` fixture contains the GraphQL response that would normally be returned by the check's query:

```json
{
  "BuiltinTag": {
    "edges": [
      {
        "node": {
          "id": "abc123",
          "name": { "value": "valid-tag" }
        }
      }
    ]
  }
}
```

### Integration Test (`check-integration`)

Runs the check against a live Infrahub instance. Optionally provide variables for targeted checks.

```yaml
- name: integration_tag_naming
  spec:
    kind: check-integration
    variables:
      device: "spine-01"       # For targeted checks with parameters
  expect: PASS
```

### Complete Example: `tests/test_checks.yml`

```yaml
---
version: "1.0"
infrahub_tests:
  - resource: Check
    resource_name: check_tag_naming
    tests:
      - name: smoke_tag_naming
        spec:
          kind: check-smoke

      - name: unit_tag_naming_valid
        spec:
          kind: check-unit-process
          directory: fixtures/check_tag_naming
        expect: PASS

      - name: unit_tag_naming_invalid
        spec:
          kind: check-unit-process
          directory: fixtures/check_tag_naming_invalid
        expect: FAIL

  - resource: Check
    resource_name: check_rack_unit_collision
    tests:
      - name: smoke_rack_collision
        spec:
          kind: check-smoke

      - name: unit_rack_collision_no_overlap
        spec:
          kind: check-unit-process
          directory: fixtures/rack_collision_pass
        expect: PASS

      - name: unit_rack_collision_overlap
        spec:
          kind: check-unit-process
          directory: fixtures/rack_collision_fail
        expect: FAIL
```

### Recommended Fixture Directory Structure

```
tests/
  test_checks.yml
  fixtures/
    check_tag_naming/
      input.json                 # Valid tags - expect PASS
    check_tag_naming_invalid/
      input.json                 # Invalid tags - expect FAIL
    rack_collision_pass/
      input.json                 # No overlapping RU positions
    rack_collision_fail/
      input.json                 # Overlapping RU positions
```

### Incorrect / Correct

**Incorrect** -- check without tests:

```python
# checks/tag_naming.py
class TagNamingCheck(InfrahubCheck):
    query = "tags"
    def validate(self, data): ...
```

```yaml
# .infrahub.yml
check_definitions:
  - name: check_tag_naming
    class_name: TagNamingCheck
    file_path: checks/tag_naming.py
# No test file created
```

**Correct** -- check with smoke and unit tests:

```yaml
# tests/test_checks.yml
---
version: "1.0"
infrahub_tests:
  - resource: Check
    resource_name: check_tag_naming
    tests:
      - name: smoke
        spec:
          kind: check-smoke
      - name: unit_valid
        spec:
          kind: check-unit-process
          directory: fixtures/check_tag_naming
        expect: PASS
```

Reference: [Resources Testing Framework](https://docs.infrahub.app/topics/resources-testing-framework) | [Test Configuration Reference](https://docs.infrahub.app/reference/infrahub-tests)
