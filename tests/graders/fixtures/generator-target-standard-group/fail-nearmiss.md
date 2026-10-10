.infrahub.yml

```yaml
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
```

objects/groups.yml

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: CoreGeneratorGroup
  data:
    - name: topologies_dc
      description: Data center designs
```
