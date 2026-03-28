---
title: Resources Testing Framework for Transforms
impact: HIGH
tags: testing, transforms, pytest, yaml
---

## Resources Testing Framework for Transforms

**Impact: HIGH**

Transforms should always have accompanying test definitions. The Resources Testing Framework provides test kinds for both Python and Jinja2 transforms, from lightweight syntax validation to full integration testing.

See [Resources Testing Framework](../../common/rules/testing-resource-framework.md) for the general framework overview, YAML structure, and how to run tests.

### Python Transform Test Kinds

| Kind | Purpose | Requires Server | Fixture Files |
|------|---------|-----------------|---------------|
| `python-transform-smoke` | Validates Python syntax and structure | No | None |
| `python-transform-unit-process` | Runs transform() with fixture data | No | `input.json`, output (optional) |
| `python-transform-integration` | Runs transform against live Infrahub | Yes | `variables.json` (optional) |

### Jinja2 Transform Test Kinds

| Kind | Purpose | Requires Server | Fixture Files |
|------|---------|-----------------|---------------|
| `jinja2-transform-smoke` | Validates template syntax | No | None |
| `jinja2-transform-unit-render` | Renders template with fixture data | No | `input.json`, output (optional) |
| `jinja2-transform-integration` | Renders against live Infrahub | Yes | `variables.json` (optional) |

### Smoke Tests

Validate that the transform file (Python or Jinja2) can be parsed without syntax errors. No fixture data needed.

```yaml
- name: smoke_spine
  spec:
    kind: python-transform-smoke

- name: smoke_clab
  spec:
    kind: jinja2-transform-smoke
```

### Unit Tests

Feed fixture data into the transform and optionally compare against expected output.

**Python (`python-transform-unit-process`):**

```yaml
- name: unit_spine_transform
  spec:
    kind: python-transform-unit-process
    directory: fixtures/spine_transform
    input: input.json            # Default, can be omitted
    output: output.txt           # Expected output to compare against
  expect: PASS
```

**Jinja2 (`jinja2-transform-unit-render`):**

```yaml
- name: unit_clab_render
  spec:
    kind: jinja2-transform-unit-render
    directory: fixtures/clab_topology
    input: input.json
    output: output.yml
  expect: PASS
```

The `input.json` fixture contains the GraphQL response that would normally be returned by the transform's query:

```json
{
  "DcimDevice": {
    "edges": [
      {
        "node": {
          "name": { "value": "spine-01" },
          "status": { "value": "active" }
        }
      }
    ]
  }
}
```

### Integration Tests

Run the transform against a live Infrahub instance. Provide variables for targeted transforms.

```yaml
- name: integration_spine
  spec:
    kind: python-transform-integration
    variables:
      device: "spine-01"
  expect: PASS

- name: integration_clab
  spec:
    kind: jinja2-transform-integration
    variables:
      name: "dc-topology-01"
  expect: PASS
```

### Complete Example: `tests/test_transforms.yml`

```yaml
---
version: "1.0"
infrahub_tests:
  - resource: PythonTransform
    resource_name: spine
    tests:
      - name: smoke_spine
        spec:
          kind: python-transform-smoke

      - name: unit_spine
        spec:
          kind: python-transform-unit-process
          directory: fixtures/spine_transform
          output: output.txt
        expect: PASS

  - resource: PythonTransform
    resource_name: simple_transform
    tests:
      - name: smoke_simple
        spec:
          kind: python-transform-smoke

      - name: unit_simple
        spec:
          kind: python-transform-unit-process
          directory: fixtures/simple_transform
        expect: PASS

  - resource: Jinja2Transform
    resource_name: topology_clab
    tests:
      - name: smoke_clab
        spec:
          kind: jinja2-transform-smoke

      - name: unit_clab_render
        spec:
          kind: jinja2-transform-unit-render
          directory: fixtures/clab_topology
          output: output.yml
        expect: PASS

  - resource: PythonTransform
    resource_name: topology_cabling
    tests:
      - name: smoke_cabling
        spec:
          kind: python-transform-smoke

      - name: unit_cabling
        spec:
          kind: python-transform-unit-process
          directory: fixtures/topology_cabling
          output: output.csv
        expect: PASS
```

### Recommended Fixture Directory Structure

```
tests/
  test_transforms.yml
  fixtures/
    spine_transform/
      input.json                 # GraphQL response for spine query
      output.txt                 # Expected rendered config
    simple_transform/
      input.json                 # GraphQL response for simple query
    clab_topology/
      input.json                 # GraphQL response for topology query
      output.yml                 # Expected ContainerLab YAML
    topology_cabling/
      input.json                 # GraphQL response for cabling query
      output.csv                 # Expected CSV output
```

### Incorrect / Correct

**Incorrect** -- transform without tests:

```python
# transforms/simple.py
class SimpleTransform(InfrahubTransform):
    query = "my_query"
    async def transform(self, data): ...
```

```yaml
# .infrahub.yml
python_transforms:
  - name: simple_transform
    class_name: SimpleTransform
    file_path: transforms/simple.py
# No test file created
```

**Correct** -- transform with smoke and unit tests:

```yaml
# tests/test_transforms.yml
---
version: "1.0"
infrahub_tests:
  - resource: PythonTransform
    resource_name: simple_transform
    tests:
      - name: smoke
        spec:
          kind: python-transform-smoke
      - name: unit_valid
        spec:
          kind: python-transform-unit-process
          directory: fixtures/simple_transform
        expect: PASS
```

Reference: [Resources Testing Framework](https://docs.infrahub.app/topics/resources-testing-framework) | [Test Configuration Reference](https://docs.infrahub.app/reference/infrahub-tests)
