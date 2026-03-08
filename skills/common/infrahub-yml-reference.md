# .infrahub.yml Configuration Reference

The `.infrahub.yml` file is the central manifest that connects your Git repository to Infrahub. It declares all schemas, data, queries, checks, transforms, generators, menus, and artifacts.

## Complete Structure

```yaml
---
# Schema files (loaded first - establishes data models)
schemas:
  - schemas                              # Directory path (loads all .yml files recursively)

# Menu files
menus:
  - menus/menu-full.yml                  # Array of file paths

# Object data files
objects:
  - objects                              # Directory path (loads all .yml files recursively)

# GraphQL queries (used by checks, transforms, generators)
queries:
  - name: my_query                       # Unique query identifier
    file_path: "queries/my_query.gql"    # Path to .gql file

# Check definitions (validation logic)
check_definitions:
  - name: my_check                       # Unique identifier
    file_path: "checks/my_check.py"      # Path to Python file
    class_name: MyCheck                  # Optional: Python class name
    targets: my_group                    # Optional: group name (omit for global)
    parameters:                          # Optional: maps query variables to target attributes
      device: "name__value"

# Python transforms (code-based data transformation)
python_transforms:
  - name: my_transform                   # Unique identifier
    file_path: "transforms/my_transform.py"
    class_name: MyTransform              # Optional: class name
    convert_query_response: true         # Optional: convert to SDK objects

# Jinja2 transforms (template-based text rendering)
jinja2_transforms:
  - name: my_jinja_transform             # Unique identifier
    query: "my_query"                    # GraphQL query name
    template_path: "templates/config.j2" # Path to Jinja2 template
    description: "Optional description"  # Optional

# Artifact definitions (connects transforms to output files)
artifact_definitions:
  - name: my_artifact                    # Unique identifier
    artifact_name: "Human Readable Name" # Optional: display name
    parameters:                          # Maps target attributes to query variables
      device: "name__value"
    content_type: "text/plain"           # MIME type of output
    targets: "my_group"                  # Target group name
    transformation: "my_transform"       # Transform name to use

# Generator definitions (design-driven automation)
generator_definitions:
  - name: my_generator                   # Unique identifier
    file_path: "generators/my_gen.py"    # Path to Python file
    query: my_query                      # GraphQL query name
    targets: my_group                    # Target group name
    class_name: MyGenerator              # Optional: class name
    parameters:                          # Optional: maps target attributes to query variables
      name: "name__value"
    convert_query_response: true         # Optional: convert to SDK objects
    execute_in_proposed_change: true     # Optional (default: true)
    execute_after_merge: true            # Optional (default: true)
```

## Loading Order

Resources are loaded in this order:

1. **Schemas** -- establish data models
2. **GraphQL queries** -- registered for use by other components
3. **Objects** -- initial data population
4. **Python files** -- checks, transforms, generators
5. **Jinja2 transforms** -- template-based transforms
6. **Artifact definitions** -- connect transforms to outputs

## Section Details

### `schemas`

Array of directory paths or file paths. Loads all `.yml`, `.yaml`, and `.json` files recursively.

### `menus`

Array of file paths pointing to menu YAML files. See the menu creator skill.

### `objects`

Array of directory paths. Loads all `.yml`/`.yaml` files recursively, sorted by filename.

### `queries`

Each query needs a `name` (used to reference it from checks/transforms/generators) and a `file_path` to the `.gql` file.

### `check_definitions`

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier |
| `file_path` | Yes | Path to Python file |
| `class_name` | No | Python class name (inferred if omitted) |
| `targets` | No | Group name; omit for global checks |
| `parameters` | No | Maps query variables to target object attributes |

### `python_transforms`

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier |
| `file_path` | Yes | Path to Python file |
| `class_name` | No | Python class name |
| `convert_query_response` | No | Convert GraphQL response to SDK `InfrahubNode` objects |

### `jinja2_transforms`

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier |
| `query` | Yes | GraphQL query name |
| `template_path` | Yes | Path to Jinja2 template |
| `description` | No | Documentation text |

### `artifact_definitions`

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier |
| `artifact_name` | No | Human-readable display name |
| `parameters` | Yes | Maps target object attributes to query variables |
| `content_type` | Yes | MIME type (e.g., `text/plain`, `application/json`, `text/csv`) |
| `targets` | Yes | Group name containing target objects |
| `transformation` | Yes | Name of the transform to use |

### `generator_definitions`

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier |
| `file_path` | Yes | Path to Python file |
| `query` | Yes | GraphQL query name |
| `targets` | Yes | Target group name (`CoreGeneratorGroup`) |
| `class_name` | No | Python class name |
| `parameters` | No | Maps query variables to target object attributes |
| `convert_query_response` | No | Convert to SDK `InfrahubNode` objects |
| `execute_in_proposed_change` | No | Run during proposed changes (default: true) |
| `execute_after_merge` | No | Run after branch merge (default: true) |

## The `parameters` Field

The `parameters` field maps GraphQL query variables to target object attribute paths. The key is the query variable name, the value is the attribute path using `__` notation:

```yaml
parameters:
  device: "name__value"          # Maps $device query variable to the target's name attribute
  name: "name__value"            # Maps $name query variable
```

This enables targeted execution: when a check/transform/generator runs against a specific target object, the target's attribute values are injected as query variables.

## Real-World Example (bundle-dc)

```yaml
---
jinja2_transforms:
  - name: topology_clab
    description: Template to generate a containerlab topology
    query: topology_simulator
    template_path: templates/clab_topology.j2

artifact_definitions:
  - name: spine_config
    artifact_name: spine
    content_type: text/plain
    targets: spines
    transformation: spine
    parameters:
      device: name__value

check_definitions:
  - name: validate_leaf
    class_name: CheckLeaf
    file_path: checks/leaf.py
    targets: leafs
    parameters:
      device: name__value

python_transforms:
  - name: spine
    class_name: Spine
    file_path: transforms/spine.py

generator_definitions:
  - name: create_dc
    file_path: generators/generate_dc.py
    targets: topologies_dc
    query: topology_dc
    class_name: DCTopologyGenerator
    parameters:
      name: name__value

queries:
  - name: topology_dc
    file_path: queries/topology/dc.gql
  - name: spine_config
    file_path: queries/config/spine.gql

schemas:
  - schemas/

menus:
  - menus/menu-full.yml
```
