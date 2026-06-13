---
title: File Objects (CoreFileObject)
impact: MEDIUM
tags: extension, file, attachment, CoreFileObject, inheritance
---

## File Objects (CoreFileObject)

Impact: MEDIUM

`CoreFileObject` is a built-in Infrahub generic that
turns a node into a **file-bearing entity**. The node
becomes the schema-side handle for a stored file —
the file itself (PDF, Visio `.vsdx`, KMZ, image,
spreadsheet, certificate, runbook, contract, config
backup, anything) lives in Infrahub's object storage,
and the node carries the domain metadata that
explains *what the file is for*.

Inheriting it has two automatic effects:

1. Infrahub adds a `file:` argument to the node's
   `Create`, `Update`, and `Upsert` GraphQL mutations,
   so files can be uploaded against the node.
2. The node receives five **read-only** system-managed
   attributes populated on upload — see the table
   below.

Use it whenever the answer to *"what is this node?"*
is "a stored file plus its context."

### The Pattern

```yaml
nodes:
  - name: NetworkDiagram
    namespace: Dcim
    label: Network Diagram
    icon: mdi:file-image
    inherit_from:
      - CoreFileObject              # File capability
    human_friendly_id:
      - title__value
    display_label: "{{ title__value }}"
    attributes:
      - name: title
        kind: Text
        optional: false
      - name: author
        kind: Text
        optional: true
      - name: last_reviewed
        kind: DateTime
        optional: true
    relationships:
      - name: site
        peer: LocationSite
        kind: Attribute
        cardinality: one
        optional: false
        order_weight: 900
```

That single `inherit_from` entry is the whole
contract. Do **not** also declare attributes for the
filename, size, MIME type, checksum, or storage path
— `CoreFileObject` already provides them and the
system manages them on upload.

### Reserved Attributes (Do Not Redeclare)

`CoreFileObject` provides these read-only attributes
automatically. Redeclaring any of them on the
inheriting node collides with system-managed
metadata and breaks the upload pipeline:

| Attribute | Populated by | Purpose |
| --------- | ------------ | ------- |
| `file_name` | Upload | Original filename as submitted |
| `file_size` | Upload | Size in bytes |
| `file_type` | Upload | MIME type derived from content |
| `checksum` | Upload | SHA-1 of the uploaded bytes |
| `storage_id` | Upload | Internal reference into object storage |

If the domain needs a *display name* distinct from
the original filename, add a separate `title` (or
similar) attribute — do not shadow `file_name`.

### When to Reach For It

Whenever the *primary identity* of the node is a
stored file. Cross-domain examples:

| Use case | Example node kind | Attaches to |
| -------- | ----------------- | ----------- |
| Diagrams (Visio, draw.io, PNG) | `DcimNetworkDiagram` | Site, Region, Device |
| Legal / commercial docs | `DcimCircuitContract`, `OrgServiceAgreement` | Circuit, Customer |
| Geo overlays | `LocationKmzOverlay` | Region, Site |
| Imagery | `DcimRackPhoto`, `DcimCablingPhoto` | Rack, Device, Cable |
| Compliance / security | `SecurityCertificate`, `ComplianceAuditReport` | Device, Service |
| Operational artifacts | `OpsRunbook`, `OpsConfigBackup` | Service, Device |
| Engineering deliverables | `DesignTopologyBlueprint`, `DesignBomSheet` | Project, Customer |

The list isn't exhaustive — the trigger is the same
in every case: a file *is* the record, not a side
attribute of one.

### Apply It to the Concrete, Not the Generic

Generics aren't instantiable, so a file has nothing
to attach to. If several concrete nodes are
file-bearing variants of the same domain, add
`CoreFileObject` to each concrete node, not to the
shared generic:

```yaml
generics:
  - name: GenericAttachment
    namespace: Dcim
    # Do NOT add CoreFileObject here

nodes:
  - name: NetworkDiagram
    namespace: Dcim
    inherit_from:
      - CoreFileObject              # File-bearing concrete
      - DcimGenericAttachment

  - name: RackPhoto
    namespace: Dcim
    inherit_from:
      - CoreFileObject              # File-bearing concrete
      - DcimGenericAttachment
```

### Pair With a Back-Relationship

A file without context is an orphan in the graph. A
diagram is a diagram *of* something; a contract is a
contract *for* something. Every file-bearing node
should carry a `cardinality: one` (or, less commonly,
`many`) relationship back to the parent entity it
describes:

```yaml
relationships:
  - name: site
    peer: LocationSite
    kind: Attribute
    cardinality: one
    optional: false
```

If the file is conceptually *owned by* the parent
(deleting the site should delete its diagrams), use
a `Component` relationship with a matching `Parent`
on the other side — see
[relationship-component-parent.md](./relationship-component-parent.md).

### Decision Rule (Design Time)

Before finalizing any node, ask: *"Is this node a
stored file at its core, or does it merely reference
one?"*

- "It *is* a stored file" → `inherit_from:
  CoreFileObject`. Add domain attributes (title,
  dates, author) and a back-relationship.
- "It *references* one externally" → a regular node
  with a `kind: Text` URL attribute. But verify this
  is genuinely external storage and not an attempt
  to bypass `CoreFileObject` for files that should
  live in Infrahub. See the bypass antipattern below.

Adding `CoreFileObject` to an already-loaded node
forces a schema migration. Declaring it upfront when
the use case fits costs nothing.

### Antipatterns

**Redeclaring reserved attributes:** writing
`name: file_name`, `name: checksum`, etc. on the
inheriting node collides with the inherited
read-only versions. Symptom: schema validation
errors or, worse, schema loads but uploads silently
overwrite the user-defined values.

**`CoreFileObject` on a generic:** generics aren't
instantiable, so no file can be uploaded. Symptom:
the upload mutation never appears in the GraphQL
schema for the generic's heirs unless the heirs also
inherit `CoreFileObject` directly.

**Missing back-relationship:** the file-bearing node
exists in the graph with no link to whatever it
describes. Symptom: orphan files that can be queried
but not navigated to from the parent entity.

**Storing the file as a `Text` URL or path:**
declaring a `Text` attribute named `url`, `path`,
`file_url`, `filename`, or `location` to hold a
string pointer to a file is the bypass antipattern —
the file lives outside Infrahub, no checksum, no
permissions, no branch isolation. If the file
genuinely belongs to Infrahub, use `CoreFileObject`.
If it genuinely lives in an external system you do
not own, keep the URL but name the attribute
descriptively (e.g., `external_reference`) so
auditors can tell intent from a glance.

Reference:
[Infrahub File Objects](https://docs.infrahub.app/schema/file-object)
