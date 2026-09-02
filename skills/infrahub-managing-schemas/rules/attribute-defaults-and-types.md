---
title: Attribute Defaults, Dropdowns, and Deprecated Fields
impact: HIGH
tags: attribute, optional, dropdown, choices, deprecated, inheritance, allow_override
---

## Attribute Defaults, Dropdowns, and Deprecated Fields

Impact: HIGH

Attributes default to mandatory, dropdown choices are
objects rather than strings, and several legacy field
names still parse but are removed in current Infrahub.

### Why it matters

The optionality default is the opposite of
relationships, so adding a new attribute without
`optional: true` makes every existing object fail
validation on the next load — a five-second oversight
that turns into a data-migration day. Dropdown choices
as bare strings parse only on very old schema
versions; current Infrahub rejects them with a
schema-validation error. The deprecated fields
(`display_labels`, `default_filter`, `String`,
top-level `regex` / `min_length` / `max_length`) are
the highest-cost mistakes because they look correct,
load successfully on older versions, and silently
break when the project upgrades.

### Attributes Are Mandatory by Default

Unlike relationships (which default to optional),
attributes default to `optional: false`. Adding a
new attribute without `optional: true` makes every
existing object fail validation.

**Incorrect -- adding a new required attribute without a default:**

```yaml
- name: serial_number
  kind: Text
  # optional defaults to false -- existing objects will fail validation!
```

**Correct -- add as optional first, or provide a default:**

```yaml
- name: serial_number
  kind: Text
  optional: true              # Safe for existing data

# OR
- name: serial_number
  kind: Text
  default_value: "unknown"    # Provides fallback for existing data
```

### Dropdown Choices Format

Each choice needs at minimum a `name` field. `label`,
`description`, `color` are optional.

**Incorrect:**

```yaml
- name: status
  kind: Dropdown
  choices:
    - active                  # Bare string — needs an object with a name field
    - planned
```

**Correct:**

```yaml
- name: status
  kind: Dropdown
  choices:
    - name: active
      label: Active
      color: "#00FF00"
    - name: planned
      label: Planned
      color: "#0000FF"
```

When referencing dropdown values in object files, use
the `name` value (not `label`): `status: active` not
`status: Active`.

### Overriding an Inherited Dropdown

Giving each concrete kind its own default for a Dropdown
declared on a shared generic is a pattern worth having:
a value fully determined by the kind then disappears
from every object file. But the override has to restate
the **complete** choice list, and the two ways of
getting it wrong behave completely differently.

**The working shape** — restate `kind`, all `choices`,
and add the default:

```yaml
generics:
  - name: Endpoint
    namespace: Net
    attributes:
      - name: media
        kind: Dropdown
        choices:
          - name: fibre
          - name: copper

nodes:
  - name: OpticalEndpoint
    namespace: Net
    inherit_from: [NetEndpoint]
    attributes:
      - name: media
        kind: Dropdown          # required: kind is mandatory on any override
        choices:                # required: Dropdown without choices is rejected
          - name: fibre
          - name: copper
        default_value: fibre    # the point of the override
```

**Omitting `choices`** is rejected at load, before any
data is touched:

```text
The property 'choices' is required for kind=Dropdown
```

**Omitting `kind`** does not produce a clean message at
all. `kind` is a required field on every attribute
declaration, including an override, and leaving it out
raises a bare `KeyError: 'kind'`. If you see that,
you omitted `kind` somewhere.

**Declaring a different `kind`** is a separate failure:

```text
NetOpticalEndpoint.media inherited from NetEndpoint must be the same kind ["Dropdown", "Text"]
```

#### The dangerous half: a wrong list loads silently

Nothing compares a child's restated `choices` against
the generic's. Both of these load successfully:

| Override's list | Loads? | What breaks |
| --------------- | ------ | ----------- |
| Complete and matching | Yes | nothing |
| **Shorter / stale** | **Yes, silently** | writing an object with a newly added choice is rejected at **write** time |
| **Longer, with an invented choice** | **Yes, silently** | that kind accepts a value the generic never declared |

So **adding a choice to a generic looks like a one-line
change and is not.** Every kind that overrides the
attribute keeps its old list, and the gap between adding
the choice and discovering that N kinds never received
it is unbounded, because the failure appears as a data
problem rather than a schema one.

The restated-longer case is the quieter one: a concrete
kind can accept a value that is not in the generic's
list, so a query over the generic can return a value the
generic says is impossible.

#### Guard it, because the server will not

There is no load-time check, so add one of these
deliberately:

1. **A test asserting every restated list still matches
   the generic's.** This is the only guard that permits
   the per-kind-default pattern. Recommended.
2. **`allow_override: none` on the generic's attribute.**
   The server then rejects any override outright:

   ```text
   NetOpticalEndpoint's attribute media inherited from NetEndpoint cannot be overriden
   ```

   This makes drift impossible, at the cost of the
   per-kind default. Use it when the choice list matters
   more than the defaults.

Pick one. Doing neither means the duplication the
generic exists to prevent can drift with no signal.

### Deprecated Fields to Avoid

| Deprecated | Use Instead |
| ---------- | ----------- |
| `display_labels` | `display_label` |
| `default_filter` | `human_friendly_id` |
| `String` (attribute kind) | `Text` |
| `regex` (top-level) | `parameters: { regex: "..." }` |
| `min_length` (top-level) | `parameters: { min_length: N }` |
| `max_length` (top-level) | `parameters: { max_length: N }` |

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
