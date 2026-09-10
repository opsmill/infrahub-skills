---
title: Report Everything the Conversion Dropped
impact: HIGH
tags: coverage, report, data-loss, unmapped
---

## Report Everything the Conversion Dropped

Impact: HIGH

Every conversion emits a coverage report naming each
skipped component list, each dropped field, and each
value coercion. Hand it over with the YAML.

### Why it matters

A NetBox device type carries more than most Infrahub
schemas model. Against the stock schema-library, a
48-port switch converts its interfaces and silently
discards its console ports, module bays, media types,
and PoE settings — roughly a third of the file. The
YAML that comes out looks complete, loads cleanly, and
is wrong in a way nobody notices until someone asks
where the console ports went, six months later, with
400 device types already loaded.

Reporting the loss costs nothing and turns an
invisible gap into a decision: extend the schema, or
accept the omission knowingly.

### What the report must name

| Category | Example |
| -------- | ------- |
| Skipped component lists | `console-ports (2 entries)` |
| Dropped top-level fields | `airflow`, `front_image` |
| Dropped component fields | `interfaces`: `type`, `poe_mode` |
| Value coercions | `16.1 lb converted to 7.303 kg` |

Fields that were *consumed* rather than lost do not
belong in the report — `slug` drives the template name
and `weight_unit` drives the kilogram conversion, so
reporting them as dropped trains readers to ignore the
report.

**Wrong — no report:**

> Converted 40 device types to `generated/`.

**Right — the loss is stated up front, with the way
out:**

> Converted 40 device types to `generated/`. All 40
> lost their `console-ports` and `module-bays`, and
> every interface lost its `type` — the schema models
> no console-port node, and `InterfacePhysical` has no
> media-type attribute. Full detail in
> `coverage-report.md`.
>
> If you want those, both are additive schema changes:
> `type` needs one attribute on `InterfacePhysical`,
> console ports need a node plus a Component
> relationship. `extending-your-schema.md` has the YAML
> for each. Say the word and I'll draft them.

### Say it in the response, not only the file

The report is the evidence; the response is where the
user actually learns what happened. Name the top one
or two losses in prose, explain *why* the schema could
not hold them, and offer the fix. A user who does not
know Infrahub generates component templates only from
`Component` relationships cannot act on a line that
says `Skipped console-ports` — teach the reason, then
point at
[../extending-your-schema.md](../extending-your-schema.md).

Offer; do not unilaterally rewrite their schema. A
schema change is a migration against their source of
truth.

### Common mistakes

- **Filing the report and not mentioning it.** The
  point is the reader knowing; a file they never open
  is silent loss with extra steps.
- **Reporting only skipped lists.** Dropped *fields*
  (interface `type`) are the easier loss to miss,
  because the component itself did convert.
- **Failing the run instead of reporting.** Against a
  typical schema almost every real NetBox file has
  something unmappable; a converter that refuses them
  converts nothing.
