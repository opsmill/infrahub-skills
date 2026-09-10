---
title: Two Component Lists Can Share One Relationship
impact: CRITICAL
tags: mapping, components, relationships, silent-loss
---

## Two Component Lists Can Share One Relationship

Impact: CRITICAL

When two NetBox component lists map onto peer kinds
that inherit the same generic, they land on the *same*
Infrahub relationship. The output must carry both — as a
flat list of `{kind, data: <one child>}` items, not one
overwriting the other and not children grouped per kind.

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

Accumulating is necessary but not sufficient — the two
payload shapes the loader accepts are **not**
interchangeable, and picking the wrong one fails the load.

`infrahub_sdk/spec/object.py` classifies the payload
before walking it:

| Payload | Format | How the loader reads `data` |
| ------- | ------ | --------------------------- |
| mapping `{kind, data: [...]}` | `MANY_OBJ_DICT_LIST` | iterates it — one block, many children |
| list of `{kind, data}` | `MANY_OBJ_LIST_DICT` | passes each item's `data` to the **single-object** path |

So a shared relationship emits a **flat** list: one child
per item, `kind` repeated. The loader resolves `kind` per
item, which is what makes two peer kinds in one
relationship work:

```yaml
interfaces:
  - kind: TemplateInterfacePhysical
    data:
      template_name: cisco-c9300-48p__Gi1/0/1
      name: Gi1/0/1
  - kind: TemplateInterfacePhysical
    data:
      template_name: cisco-c9300-48p__Gi1/0/2
      name: Gi1/0/2
  - kind: TemplateDcimConsoleInterface
    data:
      template_name: cisco-c9300-48p__console__con 0
      name: con 0
```

A single mapping keeps the plainer form — the list only
appears where a relationship is genuinely shared:

```yaml
interfaces:
  kind: TemplateInterfacePhysical
  data: [ ... ]
```

Item order follows the order the profile declares the
component lists, and within a list the order of the
NetBox entries.

**Wrong — grouped blocks inside the list form:**

```yaml
interfaces:
  - kind: TemplateInterfacePhysical
    data:                                  # a LIST inside a list item
      - template_name: cisco-c9300-48p__Gi1/0/1
        name: Gi1/0/1
      - template_name: cisco-c9300-48p__Gi1/0/2
        name: Gi1/0/2
```

This reads as the natural pairing of the two forms and is
what the converter emitted until it was run against a
server. `infrahubctl object load` rejects it:

```text
Error: 'list' object has no attribute 'items'
```

— the loader reached `data.items()` on the single-object
path with a list in hand. Nothing catches this before a
real load: the YAML is well-formed, the counts are right,
and every child is present.

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
3. **Did every child survive?** Count children per kind
   in the output, not just the report's per-list counts.
4. **Does each list item carry exactly one child?** Under
   the list form, `data` is a mapping. A list there does
   not load.

**Also wrong — a bare list of children:**

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
- **Nesting the mapping form inside the list form.** The
  two are not composable; see
  [The output shape](#the-output-shape).
- **Treating unit tests as proof the output loads.** The
  grouped shape was self-consistent across the converter,
  this rule, the tests, and the grader — all of them
  agreed, and none of them loaded a file. Only a real
  `infrahubctl object load` closes that gap.
