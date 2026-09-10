---
title: Object Template File Structure
impact: CRITICAL
tags: format, envelope, template, components
---

## Object Template File Structure

Impact: CRITICAL

A template is an ordinary Infrahub object authored
under its generated `Template<Kind>`. Its component
children nest inline under the component relationship
name, wrapped in `kind` + `data`.

### Why it matters

The object loader has no special path for templates —
they go through the same envelope validation as any
object file, so a missing `apiVersion` or a `spec.kind`
naming the base node instead of the template kind is
rejected outright. And because component relationships
in DCIM schemas usually target a *generic* peer
(`DcimInterface`, not `InterfacePhysical`), the loader
cannot infer which concrete kind to instantiate; the
`kind` wrapper is what tells it.

Nesting also does the parent wiring for you. A
component template's `device` relationship points at
the *parent template*, not a real device — writing
that reference by hand is easy to get backwards, and
nesting removes the opportunity.

### The structure

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: TemplateDcimDevice         # the generated template kind
  data:
    - template_name: cisco-c9300-48p   # identifies the template
      device_type: Catalyst 9300-48P   # hfid reference to the real device type
      interfaces:                       # component relationship name
        kind: TemplateInterfacePhysical # concrete child template kind
        data:
          - template_name: cisco-c9300-48p__GigabitEthernet1/0/1
            name: GigabitEthernet1/0/1
            status: active
```

`template_name` is required on every template and
every component template — it is the template's
`human_friendly_id`.

**Wrong — base kind, and children not wrapped:**

```yaml
spec:
  kind: DcimDevice             # creates real devices, not a template
  data:
    - template_name: cisco-c9300-48p
      interfaces:
        - name: GigabitEthernet1/0/1   # no kind, no data wrapper
```

**Wrong — component template pointing back by hand:**

```yaml
spec:
  kind: TemplateInterfacePhysical
  data:
    - template_name: cisco-c9300-48p__Gi1/0/1
      device: cisco-c9300-48p    # brittle; nest under the parent instead
```

### Common mistakes

- **`spec.kind: DcimDevice`** when the intent was a
  template. That silently creates real device objects.
- **Omitting the `kind` wrapper** on a component list
  whose relationship peer is a generic — the document
  is rejected before any child is written.
- **Putting model data on the template** (`height`,
  `part_number`). Templates carry structure; the device
  type object carries the model.
- **Omitting `template_name`** on a component child.
  Every template node needs one.
