The existing `topologies_dc` group already holds both designs, so no object file changes.

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
