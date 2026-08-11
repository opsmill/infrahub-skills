---
title: Deterministic, Unique Template Names
impact: HIGH
tags: naming, template_name, slug, uniqueness
---

## Deterministic, Unique Template Names

Impact: HIGH

Derive the parent template name from the NetBox
`slug`, and namespace every component template name
with its parent's name.

### Why it matters

`template_name` carries a uniqueness constraint on
every generated template kind, and it is the
template's `human_friendly_id`. Two templates that
compute the same name do not merge — the second one
fails the constraint and the load aborts partway
through, leaving a half-populated branch.

Component templates are where this actually bites.
Every switch in the library has an interface called
`GigabitEthernet1/0/1`. Naming component templates
after the interface alone means the second device type
you convert collides with the first. Because the
constraint is per kind and not per parent, "it is
scoped to its device" is not true here.

The NetBox `slug` is the right basis for the parent
name: it is unique across the whole device-type
library by construction, and it is stable across
releases, so re-running the conversion updates the
same templates instead of creating near-duplicates.

### How to apply it

```yaml
template:
  template_name: "{slug}"                    # cisco-c9300-48p

components:
  interfaces:
    template_name: "{template_name}__{name}" # cisco-c9300-48p__GigabitEthernet1/0/1
```

**Wrong — collides across device types:**

```yaml
components:
  interfaces:
    template_name: "{name}"   # every switch claims GigabitEthernet1/0/1
```

**Wrong — non-deterministic, so re-running duplicates
everything:**

```yaml
template:
  template_name: "{model}-imported-2026"
```

### Common mistakes

- **Using `model` instead of `slug`.** Models collide
  across manufacturers and contain spaces and slashes.
- **Assuming component template names are scoped to
  their parent.** The uniqueness constraint is per
  kind.
- **Adding a timestamp or run counter.** The next run
  then creates a second set of templates rather than
  updating the first.
