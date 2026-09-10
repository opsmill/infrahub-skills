---
title: Drive the Conversion From a Mapping Profile
impact: CRITICAL
tags: mapping, profile, schema, attributes
---

## Drive the Conversion From a Mapping Profile

Impact: CRITICAL

Every Infrahub kind, attribute, and relationship name
used in the conversion comes from a mapping profile
that was read out of the target schema. None of them
are guessed.

### Why it matters

NetBox and Infrahub disagree on names for the same
concept, and no two Infrahub schemas agree with each
other. NetBox calls it `u_height`; schema-library
calls it `height`; a custom schema might call it
`rack_units`. A converter that hardcodes one set of
names produces YAML that loads cleanly against one
schema and fails against every other — and the failure
mode when a guessed attribute name is *almost* right
is worse than an error: Infrahub rejects the unknown
attribute, so a whole batch dies on a typo nobody
reviewed.

Putting the names in a profile makes the mapping a
reviewable artifact. Someone reading
`u_height -> height` can check it against the schema
file; nobody can check a name buried in Python.

### How to apply it

Read the target schema YAML (or query the live
instance) and fill in the profile from it. Start from
`scripts/mappings/_template.yml`, or from
`scripts/mappings/schema-library.yml` if the project
uses the OpsMill schema-library.

```yaml
device_type:
  kind: DcimDeviceType            # from the schema's namespace + name
  manufacturer_relationship: manufacturer
  fields:
    model: name                   # netbox field: infrahub attribute
    u_height:
      target: height
      transform: number
```

Confirm three things per line before writing it:

1. The Infrahub kind exists (namespace + name, full
   kind reference — `DcimDeviceType`, not `DeviceType`).
2. The attribute exists on that kind and its Infrahub
   `kind` accepts the NetBox value (a `Number`
   attribute will not take `"1U"`).
3. Dropdown targets accept the value being written.
   NetBox `airflow: front-to-rear` only lands if the
   schema declares a choice named `front-to-rear`.

**Wrong — inventing a plausible attribute:**

```yaml
fields:
  u_height: rack_units    # no such attribute; the load fails
  airflow: airflow        # attribute exists but is a Dropdown
                          # with no 'front-to-rear' choice
```

**Right — names taken from the schema, unmappable
fields left out and reported:**

```yaml
fields:
  u_height:
    target: height
    transform: number
  # airflow has no home in this schema — omitted, and the
  # coverage report records it as dropped
```

### Common mistakes

- **Short kind references.** Infrahub resolves by full
  namespace + name; `DeviceType` does not match
  `DcimDeviceType`.
- **Mapping a NetBox field onto a Dropdown whose
  choices do not include the value.** Add the choice to
  the schema first, or leave the field unmapped.
- **Editing the script instead of the profile** when a
  schema differs. The script is schema-agnostic on
  purpose; a fork per schema is a fork per bug fix.
