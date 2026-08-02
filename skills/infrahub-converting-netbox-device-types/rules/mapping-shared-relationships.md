---
title: Two Component Lists Can Share One Relationship
impact: CRITICAL
tags: mapping, components, relationships, silent-loss
---

## Two Component Lists Can Share One Relationship

Impact: CRITICAL

When two NetBox component lists map onto peer kinds
that inherit the same generic, they land on the *same*
Infrahub relationship. The output must carry both as a
list of `{kind, data}` blocks — not one overwriting the
other.

### Why it matters

This is the highest-consequence trap in the whole
conversion, because it fails **silently and the
coverage report says it succeeded**.

Many DCIM schemas model a console port as a node that
inherits the interface generic — `DcimConsoleInterface`
inheriting `DcimInterface` is exactly what
infrahub-demo-dc ships. A console port is then just a
kind of interface, so it belongs on the device's
`interfaces` Component relationship, and the natural
profile says so:

```yaml
components:
  interfaces:
    kind: TemplateInterfacePhysical
    relationship: interfaces
  console-ports:
    kind: TemplateDcimConsoleInterface
    relationship: interfaces      # the same relationship
```

Written naively, the second mapping replaces the first.
On a real 48-port switch that discards every physical
interface and keeps two console ports — and because the
coverage report counts what each *mapping produced*
rather than what survived, it still reports
`interfaces (51), console-ports (2)`. Measured on three
real device types: **108 component templates expected,
4 emitted, zero warnings.**

### The output shape

Infrahub's object loader resolves `kind` per item for a
many-cardinality relationship, so a list of blocks is
valid and is what the converter emits:

```yaml
interfaces:
  - kind: TemplateInterfacePhysical
    data:
      - template_name: cisco-c9300-48p__Gi1/0/1
        name: Gi1/0/1
  - kind: TemplateDcimConsoleInterface
    data:
      - template_name: cisco-c9300-48p__console__con 0
        name: con 0
```

A single mapping keeps the plainer form — the list only
appears where a relationship is genuinely shared:

```yaml
interfaces:
  kind: TemplateInterfacePhysical
  data: [ ... ]
```

Block order follows the order the profile declares the
component lists.

### What to check

1. **Does the peer kind inherit the interface generic?**
   If so it shares the relationship — that is the whole
   reason console ports need no schema change on such a
   schema.
2. **Do the component template names stay unique?**
   Name-spacing must distinguish them, since both land
   in one relationship and `template_name` is
   uniqueness-constrained per kind. Give each list its
   own infix: `{template_name}__{name}` and
   `{template_name}__console__{name}`.
3. **Did every block survive?** Count children per kind
   in the output, not just the report's per-list counts.

**Wrong — a bare list of children:**

```yaml
interfaces:
  - template_name: cisco-c9300-48p__Gi1/0/1   # no kind, no data wrapper
    name: Gi1/0/1
```

### Common mistakes

- **Assuming one relationship means one component
  list.** Inheritance makes sharing normal, not
  exceptional.
- **Trusting the per-list counts in the report** as
  proof nothing was lost. They report what each mapping
  produced, not what reached the file.
- **Reusing one `template_name` pattern** across both
  lists, so a device with `Gi1/0/1` and a console port
  of the same name collides.
