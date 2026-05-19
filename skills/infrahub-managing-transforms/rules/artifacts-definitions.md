---
title: Artifact Definitions
impact: HIGH
tags: artifacts, content-type, targets, CoreArtifactTarget
---

## Artifact Definitions

**Impact:** HIGH

Artifacts connect transforms to output files attached to target objects.

### Configuration

```yaml
artifact_definitions:
  - name: spine_config                   # Unique identifier
    artifact_name: spine                 # Display name
    content_type: text/plain             # MIME type
    targets: spines                      # Target group
    transformation: spine                # Transform name (must match)
    parameters:
      device: name__value               # Maps target attribute to query variable
```

### Content Types

| Content Type       | Use Case                          |
| ------------------ | --------------------------------- |
| `text/plain`       | Device configs, scripts           |
| `application/json` | Structured data, API payloads     |
| `text/csv`         | Cable matrices, inventory reports |
| `text/yaml`        | YAML config files                 |

### Target Requirements

Target nodes must inherit from `CoreArtifactTarget` in their schema:

```yaml
# In schema file
generics:
  - name: GenericDevice
    namespace: Dcim
    inherit_from:
      - CoreArtifactTarget            # Required for artifact generation
```

### Key Rules

- **`transformation` must match** the Transformation `name`
  in `python_transforms` or `jinja2_transforms`
- **`targets`** references a group whose members get artifacts generated
- **`parameters`** maps target object attributes to query variables
- **`content_type`** must match what the transform actually outputs

Reference:
[infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md)
