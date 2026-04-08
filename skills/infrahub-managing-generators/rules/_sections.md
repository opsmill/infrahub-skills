# Infrahub Generator Creator - Rule Sections

1. **Architecture (architecture-)** -- CRITICAL.
   Three-component structure (target group + query + Python),
   what triggers generators, execution on proposed changes
   and after merge.

2. **Python Class (python-)** -- CRITICAL.
   InfrahubGenerator base class, async generate() method,
   object creation via self.client.create(), save with
   allow_upsert=True, relationship references by ID.

3. **Tracking (tracking-)** -- HIGH. Automatic cleanup of
   stale objects via delete_unused_nodes=True, idempotent
   behavior, why allow_upsert is essential.

4. **API Reference (api-)** -- HIGH. Constructor parameters,
   instance properties (client, nodes, store, branch), key
   methods, convert_query_response option.

5. **Registration (registration-)** -- HIGH.
   .infrahub.yml generator_definitions config, query name
   matching, targets (CoreGeneratorGroup), parameters
   mapping.

6. **Patterns (patterns-)** -- MEDIUM. Data cleaning helper,
   batch object creation, using the local store for
   inter-object references.

7. **Testing (testing-)** -- LOW. infrahubctl generator
   commands, listing and running Generators locally.
