# Infrahub Generator Creator - Rule Sections

1. **Architecture (architecture-)** -- CRITICAL.
   Three-component structure (target group + query + Python),
   what triggers generators, execution on proposed changes
   and after merge.

2. **Python Class (python-)** -- CRITICAL.
   InfrahubGenerator base class, async generate() method,
   object creation via self.client.create(), save with
   allow_upsert=True, relationship references via HFID dict /
   ID dict / SDK object (never bare string), and multi-peer
   add iteration on RelationshipManager.

3. **Tracking (tracking-)** -- HIGH. Automatic cleanup of
   stale objects via delete_unused_nodes=True, idempotent
   behavior, why allow_upsert is essential, and object
   ownership: the tracking group is per *target*, every
   `save()` (including an upsert) claims the node, so a
   shared object needs `update_group_context=False` or it
   gets deleted when one target stops writing it.

4. **API Reference (api-)** -- HIGH. Constructor parameters,
   instance properties (client, nodes, store, branch), key
   methods, convert_query_response option.

5. **Registration (registration-)** -- HIGH.
   .infrahub.yml generator_definitions config, query name
   matching, targets (CoreGeneratorGroup), parameters
   mapping, and populating the target group: membership is
   assigned from the *member* side, because
   `CoreGroup.members` peers `CoreNode` which has nothing
   to resolve a name against. An existing but empty group
   dispatches nothing and reports no error.

6. **Patterns (patterns-)** -- MEDIUM. Data cleaning helper,
   batch object creation, using the local store for
   inter-object references, and natural-key preflight for
   form-driven mutations. **HIGH** for hydration —
   `InfrahubNode.from_graphql` for peer iteration to collapse
   `O(N + 1)` round trips — and for path traversal: prefer
   the SDK's `traverse_paths` to a hand-written walk, and
   constrain it by relationship identifier plus a depth
   bound, since kind filtering restricts which nodes appear
   rather than which edges are followed.

7. **Testing (testing-)** -- LOW. infrahubctl generator
   commands, listing and running Generators locally, and the
   integration-test workflow (run end-to-end against a live
   instance before declaring done).
