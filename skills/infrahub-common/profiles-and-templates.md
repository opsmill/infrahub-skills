# Profiles and Object Templates

Two Infrahub features that look similar and are constantly
confused. They solve different problems:

- **Profiles** supply shared default **values**.
- **Object Templates** supply a cloneable **structure**
  (a node *and its `Component` children*).

Reach for the wrong one and you either duplicate values that
never stay in sync, or hand-rebuild the same structure every
time. This reference is the single source of truth; skill
rules point here instead of re-explaining.

## Profiles

`generate_profile: true` on a concrete node makes Infrahub
generate a companion `Profile<Kind>` node. A Profile instance
holds default values for that node's **attributes and
relationships**. Objects that reference the Profile inherit
those values unless they set them explicitly.

- Assign via the object's `profiles:` relationship — an array
  of Profile HFIDs. An object may reference several Profiles.
- When Profiles disagree on an attribute or relationship,
  `profile_priority` decides (lower number wins — 500 beats
  1000). Array order does not matter.
- An explicit value on the object overrides every Profile.
  Overriding a **relationship** replaces it as a whole —
  modifying it clears the Profile-source of every peer in that
  relationship.
- Provenance is queryable: an inherited value carries
  `is_from_profile: true` and a `source` pointing at the
  winning Profile.

Profiles supply default **values** — for attributes and for
relationship *peers* (e.g. a default site/location, an
untagged VLAN for end-user interfaces). They never clone
structure or create a node's child components.

Use a Profile when the same values recur across many objects
and should change in one place — MTU per site tier, default
status, default location. Do **not** use a Profile for a
single value that never varies: that is what an attribute
`default_value` is for (see
[managing-schemas: attribute defaults](../infrahub-managing-schemas/rules/attribute-defaults-and-types.md)).

**Constraints** (do not model around them):

- Attributes/relationships that are part of a **uniqueness
  constraint or the HFID** cannot be profiled.
- Only **`Attribute`- and `Generic`-kind relationships** are
  supported (not `Component`/`Parent`).
- Assignment is **static** — no conditional rules, and a
  Profile **cannot extend another Profile** (no composition).
- Profiles are **node-type-specific**: a `Profile<Kind>` applies
  only to that kind. There are no global or cross-schema
  Profiles.

## Object Templates

`generate_template: true` on a concrete node (never a generic
— generics are not instantiable) makes Infrahub generate a
`Template<Kind>` node. A template captures the node **and its
`Component` children**: `Component` relationships are covered
automatically when template generation is enabled.

- Create an object from a template by setting its
  `object_template` relationship to the template. Infrahub
  copies the template's attribute values and **recreates its
  component children and relationships** on the new object.
- `member_of_groups_for_instances` and
  `subscriber_of_groups_for_instances` on a template propagate
  group membership to *every* object created from it (the
  plain `member_of_groups` / `subscriber_of_groups` apply to
  the template object itself only).

Object Templates move **structure**. They are a starting
point you clone, not a live link — editing the template later
does not retroactively change objects already created from it.

Use a template when users repeatedly create objects of the
same shape — a device model with a fixed set of interfaces, a
topology blueprint, a service definition with many child
parts.

## Choosing between them

| Need | Use |
| ---- | --- |
| The same attribute *or relationship* values across many objects, kept in sync | **Profile** |
| A single value that never varies | attribute `default_value` (not a Profile) |
| A reusable *structure* (node + child components) to clone | **Object Template** |
| Objects *computed* from a design definition or topology | **Generator** — see [managing-generators](../infrahub-managing-generators/SKILL.md) |

Profiles and Object Templates are independent and can coexist
on the same node: a Device may be cloneable from a template
*and* inherit shared values from a Profile. Enable each on its
own merits, never because the other is present.
