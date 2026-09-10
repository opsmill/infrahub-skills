# Concepts behind the conversion

Read this if the Infrahub side is unfamiliar. It
explains *why* one NetBox file becomes three Infrahub
artifacts, and why some NetBox data has nowhere to go
until the schema changes.

## What an object template is

An object template is a reusable blueprint for
creating objects. Define one for a switch model, and
every device created from it arrives with all its
ports already in place — you fill in only what differs
(name, serial, rack position).

That is exactly the problem NetBox device types solve
on their side, which is why the two map onto each
other so cleanly.

> Docs:
> [Object Templates overview](https://docs.infrahub.app/object-templates/overview)
> · [Use object templates](https://docs.infrahub.app/object-templates/use)

Templates are **generated kinds**. You do not write
`TemplateDcimDevice` into your schema — Infrahub
creates it because `DcimDevice` declares
`generate_template: true`. Before that flag is set and
the schema loaded, the kind does not exist and nothing
referencing it can load.

Two consequences worth internalising:

- `generate_template` is a **node** property. Setting
  it on a generic does nothing.
- Templates are **not retroactive**. Editing a
  template does not change devices already created
  from it.

## Why the model data is not on the template

This surprises most people. A NetBox device type
carries both *structure* (which ports exist) and
*model facts* (how many rack units, what it weighs,
the part number). Infrahub splits those:

| Lives on | What | Why |
| -------- | ---- | --- |
| `DcimDeviceType` object | `height`, `part_number`, `weight`, `full_depth` | Facts about the model, shared by every unit |
| `TemplateDcimDevice` | Structure and the link to the device type | The blueprint for making devices |
| The device itself | `name`, `serial`, position | Per-instance detail |

The template holds a *relationship* to the device
type, so creating a device from the template also
wires up its model. That is why the converter emits
manufacturers, device types, **and** templates rather
than templates alone — and why
`02_device_types.yml` has to load before
`03_device_templates.yml`.

## Unique attributes do not exist on a template

A `unique` attribute is **not copied onto the generated
template at all**. Not optional — absent. Infrahub
decides per attribute:

```python
@property
def support_templates(self) -> bool:
    return self.read_only is False and self.unique is False
```

and skips any attribute that fails it. The template is
then re-keyed on its own identity:
`human_friendly_id: ["template_name__value"]`,
`uniqueness_constraints: [["template_name__value"]]`.

Everything else is copied with `unique` stripped and
`optional: true`, so nothing the template omits blocks
creating one.

This is why `TemplateDcimDevice` has no `name`:
`DcimGenericDevice.name` is `unique: true`, so the
template never had one. The name is supplied on the
device you create *from* the template.

### What follows from it

**A node whose identity is a unique attribute is still
templatable.** This is the single most common wrong
conclusion, and it is worth stating plainly because it
looks so much like a blocker:

> `DcimGenericModule.computed_name` is `unique: true`
> and is how a module is identified, so a module cannot
> be templated.

That is **false**. `TemplateDcimModule` simply has no
`computed_name` attribute, is keyed on `template_name`,
and is created without one. The identity is supplied on
each module instantiated from it — exactly as a
device's `name` is.

The same holds for **mandatory relationships**:
`DcimGenericModule.module_bay` is `optional: false`, yet
a module template is created without being installed in
a bay. Infrahub relaxes those on generated templates the
way it omits unique attributes.

The real question is never "is this attribute unique?"
but "does this node have a `Component` relationship
holding the children I want the template to recreate?"

> Docs:
> [Attribute reference](https://docs.infrahub.app/reference/schema/attribute)
> · [Object Templates overview](https://docs.infrahub.app/object-templates/overview)

## Why only some relationships become templates

Infrahub generates a component template only for
relationships whose `kind` is `Component`. That is the
single most useful thing to understand when a
conversion produces an empty template.

| Relationship kind | Meaning | Template generated? |
| ----------------- | ------- | ------------------- |
| `Component` | Child belongs to the parent and is deleted with it (a device's interfaces) | **Yes** |
| `Parent` | The other side of a Component pair | Yes, as the link back |
| `Attribute` | A reference to an independent object (a device's location) | No — points at real objects |
| `Generic` | Reference to a generic kind, resolved at query time | No |

An interface is a *component* of a device: it has no
meaning without it, and deleting the device should
delete it. A location is not — it exists on its own
and many devices point at it. So `interfaces` becomes
`TemplateDcimInterface`, and `location` keeps
referring to a real site.

If you need NetBox console ports or module bays to
convert, this is the shape you have to add: a node,
plus a `Component`/`Parent` relationship pair joining
it to the device.

> Docs:
> [Relationships](https://docs.infrahub.app/schema/relationships)
> · [Relationship reference](https://docs.infrahub.app/reference/schema/relationship)

## Why component children need a `kind` wrapper

Most DCIM schemas point a device's `interfaces`
relationship at a **generic** (`DcimInterface`) rather
than a concrete node, so that physical and virtual
interfaces can share it. When the loader reads a
nested component list it cannot tell which concrete
kind to instantiate, so the file names it:

```yaml
interfaces:
  kind: TemplateInterfacePhysical   # the concrete kind
  data:
    - template_name: cisco-c9300-48p__Gi1/0/1
      name: Gi1/0/1
```

> Docs:
> [Generics and inheritance](https://docs.infrahub.app/schema/generics-and-inheritance)

## Templates vs Profiles

Both push shared values onto objects, and picking the
wrong one is a common mistake.

|         | Object template                      | Profile                                    |
| ------- | ------------------------------------ | ------------------------------------------ |
| Copies  | Structure — components are recreated | Values only                                |
| Applied | Once, at creation                    | Live; changing the Profile changes objects |
| Use for | "This model has 48 ports"            | "All branch switches use MTU 9000"         |

They compose: a template can carry Profiles, so the
template defines which ports exist while a Profile
supplies their settings — and changing the Profile
updates them in bulk.

> Docs:
> [Profiles](https://docs.infrahub.app/profiles/overview)
> · [Assign Profiles to a template](https://docs.infrahub.app/object-templates/with-profiles)

## Where unique per-object values come from

A template sets static values, so anything that must
be unique per device (a management IP, a circuit ID)
cannot live on it. Infrahub closes that with resource
pools: a template field like
`primary_address_from_resource_pool` allocates a fresh
value from a pool each time an object is created.

NetBox device types carry no such data, so the
converter never emits it — but it is the right answer
when someone asks "how do I template the management
IP too?"

> Docs:
> [Allocate resources from pools](https://docs.infrahub.app/object-templates/allocate-resources-from-pools)

## Where to go next

- Gaps between NetBox and your schema, and how to
  close them: [extending-your-schema.md](./extending-your-schema.md)
- The mechanics of the conversion itself:
  [reference.md](./reference.md)
- Building a schema from scratch:
  [Build your first schema](https://docs.infrahub.app/academy/tutorials/build-your-first-schema)
