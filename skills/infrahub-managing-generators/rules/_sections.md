# Infrahub Generator Creator - Rule Sections

1. **Architecture (architecture-)** -- CRITICAL.
   Three-component structure (target group + query + Python),
   what triggers generators, execution on proposed changes
   and after merge.

2. **Python Class (python-)** -- CRITICAL.
   InfrahubGenerator base class, async generate() method,
   object creation via self.client.create(), save with
   allow_upsert=True, relationship references by ID,
   stable iteration in create-loops, string-literal
   ``kind=`` arguments, no broad except, no early return
   after creates, no self-read of just-created kinds, and
   ``parallel=True`` on ``.filters(...)`` calls.

3. **Validation (validation-)** -- CRITICAL.
   Upstream count checks before creating anything. Guards
   against partial GraphQL responses silently corrupting
   downstream state via the tracking system.

4. **Cascade (cascade-)** -- CRITICAL *when building a
   cascade*. One generator per layer, GeneratorTarget
   inheritance on downstream nodes, checksum-based guard,
   GENERATOR_VERSION constant. Does NOT apply to
   single-generator solutions; see SKILL.md Step 2 for the
   topology choice.

5. **Tracking (tracking-)** -- CRITICAL. Automatic cleanup
   of stale objects via delete_unused_nodes=True,
   idempotent behavior, why allow_upsert is essential, and
   why nodes fetched (not created) by the generator must
   save with ``update_group_context=False`` to avoid being
   deleted on the next run.

6. **API Reference (api-)** -- HIGH. Constructor parameters,
   instance properties (client, nodes, store, branch), key
   methods, convert_query_response option.

7. **Registration (registration-)** -- HIGH.
   .infrahub.yml generator_definitions config, query name
   matching, targets (CoreGeneratorGroup), parameters
   mapping.

8. **Patterns (patterns-)** -- MEDIUM. Data cleaning helper,
   batch object creation, using the local store for
   inter-object references.

9. **Testing (testing-)** -- LOW. infrahubctl generator
   commands, listing and running Generators locally.

Reactive guidance for diagnosing misbehaving cascades and
verifying changes lives outside `rules/` at
[`../troubleshooting.md`](../troubleshooting.md) — it's
reference material, not assertions about model output.
