# Rule: schema-file-object-misuse

**Severity**: MEDIUM
**Category**: Schema integrity

## What It Checks

`CoreFileObject` is a built-in Infrahub generic that
turns a node into a file-bearing entity — Infrahub
stores the uploaded file in object storage and
exposes a `file:` argument on the node's `Create`,
`Update`, and `Upsert` GraphQL mutations. The
inheriting node automatically receives five
**read-only** system-managed attributes:
`file_name`, `file_size`, `file_type`, `checksum`,
and `storage_id`.

This rule flags three drift conditions in the
repository's schema files:

1. A node that inherits `CoreFileObject` and
   **redeclares** any of the five reserved attribute
   names. Redeclaration collides with system-managed
   metadata — at best a schema-load error, at worst
   silent overwrites on every upload.
2. `CoreFileObject` declared on a `generics:` entry.
   Generics aren't instantiable; the upload mutation
   has nothing to attach to.
3. A node that *looks like* a file-bearing entity —
   for example, a `Text` attribute named `file_url`,
   `file_path`, `filename`, `url`, `path`, or
   `location` — but does **not** inherit
   `CoreFileObject`. This is the bypass antipattern:
   storing a string pointer to a file living
   elsewhere instead of using Infrahub's first-class
   file capability (loses branch isolation,
   permissions, and checksum integrity).

## Checks

For each schema YAML file in the repository:

1. Parse `nodes:` and `generics:`.
2. **Reserved-attribute collision** — for every node
   whose `inherit_from` contains `CoreFileObject`,
   assert no entry in `attributes:` has a `name` in
   `{file_name, file_size, file_type, checksum,
   storage_id}`.
3. **Inheritance on a generic** — assert that no
   entry in `generics:` lists `CoreFileObject` in its
   `inherit_from`.
4. **Bypass antipattern** — for every node that has
   a `kind: Text` attribute named `file_url`,
   `file_path`, `filename`, `url`, `path`, or
   `location`, raise a warning unless either
   `CoreFileObject` is in the node's `inherit_from`
   *or* the attribute is renamed to make its
   "external pointer" intent obvious (e.g.
   `external_reference`, `vendor_portal_url`).
   This third check is advisory — there are
   legitimate cases (a URL to a vendor portal,
   documentation link) where an external reference
   is correct.

## Common Issues

- A schema author manually defines `file_name` /
  `checksum` / etc. as a "convenience" before
  learning about `CoreFileObject`. The node loads but
  uploads silently overwrite the user-managed value.
- A domain generic gets `CoreFileObject` added "to
  let all heirs accept files" — but generics aren't
  instantiable, so no upload mutation appears on the
  heirs unless they also inherit `CoreFileObject`
  directly. The generic-level inheritance is dead
  weight at best.
- A legacy schema (often imported from another
  system) stores files as `Text` URLs pointing to S3,
  SharePoint, or a network share. The file is
  outside Infrahub's branch isolation and permission
  model; deleting or moving the external file leaves
  a dangling reference.
- Multi-inheritance refactor drops `CoreFileObject`
  while keeping the domain generic
  (`inherit_from: [DcimGenericAttachment]` instead
  of `[DcimGenericAttachment, CoreFileObject]`).
  Upload mutation disappears from the GraphQL schema
  without any other observable change.

## How to Fix

**Reserved-attribute collision** — remove the
redeclared attribute. If the domain genuinely needs
a separate display name distinct from the original
filename, add a *new* attribute (e.g. `title`,
`document_label`) rather than shadowing the inherited
one.

**`CoreFileObject` on a generic** — move the
inheritance from the generic onto each concrete heir
that should be file-bearing. Apply only to nodes
that *are* a stored file, not to every heir
indiscriminately.

```yaml
generics:
  - name: GenericAttachment
    namespace: Dcim
    # Remove CoreFileObject from here

nodes:
  - name: NetworkDiagram
    namespace: Dcim
    inherit_from:
      - CoreFileObject              # Move it here
      - DcimGenericAttachment
```

**Bypass antipattern** — if the file genuinely
belongs to Infrahub, refactor to
`inherit_from: [..., CoreFileObject]` and drop the
manual `Text` attribute; migrate any existing rows
via an object-load script that uploads the file and
sets the back-relationship. If the file genuinely
lives in an external system outside the Infrahub
boundary, rename the attribute to make intent clear
(e.g. `external_reference`, `vendor_portal_url`) so
future auditors can tell at a glance whether it's a
bypass or a legitimate external pointer.

## Related

- Schema-side rule:
  [../../infrahub-managing-schemas/rules/extension-file-object.md](../../infrahub-managing-schemas/rules/extension-file-object.md)
- Parallel capability-target rule:
  [./artifact-target-inheritance.md](./artifact-target-inheritance.md)
