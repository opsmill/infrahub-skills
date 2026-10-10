Both files in one block.

```yaml
---
queries:
  - name: topology_dc
    file_path: queries/topology/dc.gql
generator_definitions:
  - name: create_dc
    file_path: generators/generate_dc.py
    query: topology_dc
    targets: topologies_dc
    class_name: DCTopologyGenerator
    parameters:
      name: name__value
    watch:
      files: []
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: CoreStandardGroup
  data:
    - name:
        value: topologies_dc
      description: Data center designs, any CoreGroup kind works and CoreGeneratorGroup is not needed
```

```yaml
# WRONG: do not convert the group
- kind: CoreGeneratorGroup
  data:
    - name: topologies_dc
```
