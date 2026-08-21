# .infrahub.yml Configuration Reference

The `.infrahub.yml` file is the central manifest that
connects your Git repository to Infrahub. It declares all
schemas, data, queries, checks, Transformations, Generators,
menus, and artifacts.

## Complete Structure

```yaml
---
# Schema files (loaded first - establishes data models)
schemas:
  - schemas                     # Directory path

# Menu files
menus:
  - menus/menu-full.yml         # Array of file paths

# Object data files
objects:
  - objects                     # Directory path

# GraphQL queries (used by checks, transforms, generators)
queries:
  - name: my_query              # Unique query identifier
    file_path: "queries/my_query.gql"

# Check definitions (validation logic)
check_definitions:
  - name: my_check              # Unique identifier
    file_path: "checks/my_check.py"
    class_name: MyCheck         # Optional: class name
    targets: my_group           # Optional: group name
    parameters:                 # Optional: maps variables
      device: "name__value"

# Python transforms (code-based data transformation)
python_transforms:
  - name: my_transform          # Unique identifier
    file_path: "transforms/my_transform.py"
    class_name: MyTransform     # Optional: class name
    convert_query_response: true
    watch:                      # Always declare — see `watch` below
      files:
        - shared/helpers.py     # [] if nothing outside the dir

# Jinja2 transforms (template-based text rendering)
jinja2_transforms:
  - name: my_jinja_transform    # Unique identifier
    query: "my_query"           # GraphQL query name
    template_path: "templates/config.j2"
    description: "Optional description"
    watch:                      # Only for undetected deps — see below
      files:
        - templates/partials/

# artifact definitions (connects Transformations to outputs)
artifact_definitions:
  - name: my_artifact           # Unique identifier
    artifact_name: "Human Readable Name"
    parameters:                 # Maps target attrs
      device: "name__value"
    content_type: "text/plain"  # MIME type of output
    targets: "my_group"         # Target group name
    transformation: "my_transform"

# Generator definitions (design-driven automation)
generator_definitions:
  - name: my_generator          # Unique identifier
    file_path: "generators/my_gen.py"
    query: my_query             # GraphQL query name
    targets: my_group           # Target group name
    class_name: MyGenerator     # Optional: class name
    parameters:                 # Optional: maps variables
      name: "name__value"
    convert_query_response: true
    execute_in_proposed_change: true
    execute_after_merge: true
    watch:                      # Always declare — see `watch` below
      files:
        - src/my_package/       # [] if nothing outside the dir
```

## Loading Order

Resources are loaded in this order:

1. **Schemas** -- establish data models
2. **GraphQL queries** -- registered for use by others
3. **Objects** -- initial data population
4. **Python files** -- checks, transforms, generators
5. **Jinja2 transforms** -- template-based transforms
6. **Artifact definitions** -- connect transforms to outputs

## Section Details

### `schemas`

Array of directory paths or file paths. Loads all `.yml`,
`.yaml`, and `.json` files recursively.

### `menus`

Array of file paths pointing to menu YAML files. See the
menu creator skill.

### `objects`

Array of directory paths. Loads all `.yml`/`.yaml` files
recursively, sorted by filename.

### `queries`

Each query needs a `name` (used to reference it from
checks/transforms/generators) and a `file_path` to the
`.gql` file.

### `check_definitions`

| Field | Required | Description |
| ----- | -------- | ----------- |
| `name` | Yes | Unique identifier |
| `file_path` | Yes | Path to Python file |
| `class_name` | No | Python class name (inferred if omitted) |
| `targets` | No | Group name; omit for global checks |
| `parameters` | No | Maps query variables to target attrs |

> **No `query` field.** Unlike `generator_definitions`
> and `jinja2_transforms`, `check_definitions` does
> **not** accept a `query:` key. The associated query
> is declared on the Python class (`query = "..."`)
> and must reference a `name` from the top-level
> `queries:` section. The Pydantic model uses
> `extra="forbid"`, so adding `query:` here makes the
> repository config fail to load.

### `python_transforms`

| Field | Required | Description |
| ----- | -------- | ----------- |
| `name` | Yes | Unique identifier |
| `file_path` | Yes | Path to Python file |
| `class_name` | No | Python class name |
| `convert_query_response` | No | Convert to SDK objects |
| `watch` | Strongly recommended | Extra dependencies; see [`watch`](#the-watch-field) |

### `jinja2_transforms`

| Field | Required | Description |
| ----- | -------- | ----------- |
| `name` | Yes | Unique identifier |
| `query` | Yes | GraphQL query name |
| `template_path` | Yes | Path to Jinja2 template |
| `description` | No | Documentation text |
| `watch` | Only if deps go undetected | See [`watch`](#the-watch-field) |

### `artifact_definitions`

| Field | Required | Description |
| ----- | -------- | ----------- |
| `name` | Yes | Unique identifier |
| `artifact_name` | No | Human-readable display name |
| `parameters` | Yes | Maps target attrs to query variables |
| `content_type` | Yes | MIME type (e.g., `text/plain`) |
| `targets` | Yes | Group name for target objects |
| `transformation` | Yes | Name of the transform to use |

### `generator_definitions`

| Field | Required | Description |
| ----- | -------- | ----------- |
| `name` | Yes | Unique identifier |
| `file_path` | Yes | Path to Python file |
| `query` | Yes | GraphQL query name |
| `targets` | Yes | Target group name |
| `class_name` | No | Python class name |
| `parameters` | No | Maps query vars to target attrs |
| `convert_query_response` | No | Convert to SDK objects |
| `execute_in_proposed_change` | No | Run during proposed changes |
| `execute_after_merge` | No | Run after branch merge |
| `watch` | Strongly recommended | Extra dependencies; see [`watch`](#the-watch-field) |

## The `parameters` Field

The `parameters` field maps GraphQL query variables to
target object attribute paths. The key is the query variable
name, the value is the attribute path using `__` notation:

```yaml
parameters:
  device: "name__value"  # Maps $device to target's name
  name: "name__value"    # Maps $name query variable
```

This enables targeted execution: when a
check/transform/generator runs against a specific target
object, the target's attribute values are injected as query
variables.

## The `watch` Field

`watch` declares the files a Transformation or Generator
depends on that Infrahub's automatic detection cannot see.
It is a strict object with one key, `files`, holding paths
relative to the repository root:

```yaml
watch:
  files:
    - src/my_package/       # directory: every tracked file beneath it
    - shared/constants.py   # single file
```

Valid **only** on `python_transforms`, `jinja2_transforms`,
and `generator_definitions` (1.10+ for Transformations,
1.11+ for Generators). The models use `extra="forbid"`, so
`watch` on `check_definitions` or `artifact_definitions`
fails the repository import, as does the bare-list form
`watch: [a, b]` or any key other than `files`.

### What detection supplies

On import, Infrahub computes a **dependency closure** per
definition. In a proposed change, a changed file re-renders
that definition's artifacts (or re-runs the Generator's
instances) only if the file is in that closure.

| Kind | Rely on being detected |
| ---- | ---------------------- |
| `python_transforms`, `generator_definitions` | **Only the entry file at `file_path`.** Imports are never followed. Some versions also add every tracked file in the entry point's directory, but that listing is being withdrawn ([opsmill/infrahub#9644](https://github.com/opsmill/infrahub/issues/9644)) — never build a `watch` list that leans on it. |
| `jinja2_transforms` | The template, plus every template reachable through a **literal** `{% include %}` / `{% import %}` / `{% extends %}`, transitively. |

So for a Python transform or a Generator, treat **every
first-party module the entry point imports as undeclared
until you list it** — a relative import of a sibling module
included. Runtime file reads
(`Path("data/vendors.yml").read_text()`, `FileSystemLoader`)
and a Jinja2 reference resolved from a variable
(`{% include partial_name %}`) are invisible too.
Third-party packages are not tracked repository files and
never belong in `watch`; a **generated** `protocols.py`
committed in the repo does.

### Why Python entries should always declare it

Infrahub does not trust detection to have found a Python
definition's dependencies — it never scanned the imports.
With no `watch` key it folds the commit id into the
fingerprint, so the definition re-renders or re-runs on
**every commit**. A present key switches that off: it is the
author's assertion that the list is complete. An explicitly
empty `files: []` makes that assertion too, and is correct
only for an entry point with no first-party import and no
runtime file read.

`jinja2_transforms` are the exception. Their closure comes
from parsing the template and following every reference it
declares, and an unfollowable reference already marks the
closure incomplete, so a complete Jinja2 closure is trusted
on its own — declare `watch` there only to cover an
undetected dependency. An empty `files: []` does nothing for
a Jinja2 transform whose closure is already incomplete.

Declaring `watch` trades a safe default for a precise one,
so an inaccurate list is worse than none: an **incomplete**
list silently under-regenerates with no error anywhere, and
an entry matching **no Git-tracked file** (typo, gitignored
path, symlink) cannot extend the closure yet still counts as
a declaration, surfacing only as a warning in the import
log. Derive the list from the code rather than guessing —
the procedure is in
[../infrahub-managing-transforms/rules/artifacts-watch-dependencies.md](../infrahub-managing-transforms/rules/artifacts-watch-dependencies.md)
and
[../infrahub-managing-generators/rules/registration-watch-dependencies.md](../infrahub-managing-generators/rules/registration-watch-dependencies.md).

### Path semantics

- Paths are relative to the repository root; a leading `./`
  and a trailing `/` are both accepted and normalized.
- A directory matches **recursively** over Git-tracked files.
- Gitignored files, `.pyc` files, `__pycache__/`, and
  symlinks are never included, whatever the entry says.
- Watched files are **added** to whatever was detected, never
  a replacement, so an entry that turns out to be covered
  already is harmless. Listing a dependency explicitly is
  always safe; omitting one because detection might cover it
  is not.

## Real-World Example (bundle-dc)

```yaml
---
jinja2_transforms:
  - name: topology_clab
    description: >-
      Template to generate a containerlab topology
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
