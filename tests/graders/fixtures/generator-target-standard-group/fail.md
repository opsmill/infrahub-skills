objects/generator_groups.yml

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: CoreGeneratorGroup
  data:
    - name: topologies_dc_gen
```

objects/designs.yml

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: TopologyDataCenter
  data:
    - name: dc-ams1
      member_of_groups: [topologies_dc, topologies_dc_gen]
    - name: dc-fra1
      member_of_groups: [topologies_dc, topologies_dc_gen]
```

.infrahub.yml

```yaml
generator_definitions:
  - name: create_dc
    file_path: generators/generate_dc.py
    query: topology_dc
    targets: topologies_dc_gen
    class_name: DCTopologyGenerator
    parameters:
      name: name__value
    watch:
      files: []
```
