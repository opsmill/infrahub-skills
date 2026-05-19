---
title: Schema String-Length Limits
impact: HIGH
tags: validation, description, label, identifier, max_length, schema-load, openapi, json-schema
---

## Schema String-Length Limits

Impact: HIGH

Several string fields on schema nodes, attributes, and
relationships have hard `max_length` caps enforced by
Pydantic on the server. Violations are not caught by
YAML editors — they fire at `infrahubctl schema load`
time as

```text
Unable to load the schema:
    Node: <Kind> | <Field>: <name>
    | Input should have at most <N> characters (string_too_long)
```

…which means a schema that "looked fine" all the way
through review and CI rejects on the apply step. Treat
`description:` as a one-line tooltip, not a place to
document picker behavior, validation rules, or change
history.

### Source of truth

The caps drift between Infrahub versions, and a static
table in this rule will go stale. **Resolve them at
validation time from the live spec, never from prose.**

Two equivalent sources expose the same
`minLength` / `maxLength` / `pattern` data — use the
public JSON Schema by default, and fall back to a
running Infrahub instance only if the public source
is unreachable.

### Resolution procedure (2-tier)

#### Tier 1 — Public JSON Schema (preferred)

The same URL referenced in every schema file's
`# yaml-language-server: $schema=...` IDE hint carries
every constraint. It is a public CDN URL, no auth, no
running server required.

```bash
curl -sS -H 'Accept: application/json' \
  -H 'User-Agent: infrahub-skills/1.0' \
  https://schema.infrahub.app/infrahub/schema/latest.json \
| python3 -c '
import json, sys
defs = json.load(sys.stdin)["$defs"]
out = {}
for name in ("NodeSchema", "GenericSchema",
             "AttributeSchema", "RelationshipSchema"):
    fields = {}
    for f, info in defs[name]["properties"].items():
        merged = {}
        for c in [info] + info.get("anyOf", []):
            for k in ("minLength", "maxLength", "pattern"):
                if k in c and k not in merged:
                    merged[k] = c[k]
        if merged:
            fields[f] = merged
    out[name] = fields
print(json.dumps(out))
'
```

The output is ~1 KB. **Read only the filtered JSON
into your context, never the 66 KB raw schema file.**

#### Tier 2 — Running Infrahub `/api/openapi.json` (fallback)

If Tier 1 fails (DNS, non-2xx, timeout), defer
connectivity probing to
[connectivity-server-check.md](../../infrahub-common/rules/connectivity-server-check.md).
That rule handles `infrahubctl info`, the
`INFRAHUB_ADDRESS` environment variable, the Python
environment detection, and the troubleshooting flow —
do not duplicate any of it here.

Once a reachable Infrahub `BASE_URL` has been
established by that rule, fetch the OpenAPI subset
the same way:

```bash
curl -sS -H 'Accept: application/json' \
  -H 'User-Agent: infrahub-skills/1.0' \
  "$BASE_URL/api/openapi.json" \
| python3 -c '
import json, sys
schemas = json.load(sys.stdin)["components"]["schemas"]
out = {}
for openapi_name, key in (("NodeSchema", "NodeSchema"),
                          ("GenericSchema", "GenericSchema"),
                          ("AttributeSchema-Input", "AttributeSchema"),
                          ("RelationshipSchema", "RelationshipSchema")):
    fields = {}
    for f, info in schemas[openapi_name]["properties"].items():
        merged = {}
        for c in [info] + info.get("anyOf", []):
            for k in ("minLength", "maxLength", "pattern"):
                if k in c and k not in merged:
                    merged[k] = c[k]
        if merged:
            fields[f] = merged
    out[key] = fields
print(json.dumps(out))
'
```

Note the path and naming differences vs Tier 1:
- JSON Schema: `$defs.AttributeSchema`
- OpenAPI: `components.schemas.AttributeSchema-Input`

The filter normalizes them so the downstream check
keys against the same names (`NodeSchema`,
`GenericSchema`, `AttributeSchema`,
`RelationshipSchema`) regardless of which tier
produced the data.

#### Tier 3 — Both unreachable

If Tier 1 and the connectivity check in Tier 2 both
fail, stop the length validation and tell the user:

```
Could not reach https://schema.infrahub.app/infrahub/schema/latest.json,
and no running Infrahub instance was found via
connectivity-server-check. String-length validation
cannot be performed for this run.
```

Do not fall back to numbers baked into this rule.
Continue with the rest of the schema review — patterns
can still be checked offline against the regex in
[naming-conventions.md](./naming-conventions.md) — but
flag explicitly that length checks were skipped.

### Validation

Use the filtered dict (from whichever tier succeeded)
to validate every node, generic, attribute, and
relationship in the user's YAML. Keys map directly:

| Schema field | Filtered-dict path |
| ------------ | ------------------ |
| Node / Generic `name`, `namespace`, `label`, `description` | `NodeSchema.<field>` / `GenericSchema.<field>` |
| Attribute `name`, `label`, `description`, `deprecation` | `AttributeSchema.<field>` |
| Relationship `name`, `label`, `description`, `identifier`, `deprecation` | `RelationshipSchema.<field>` |

For each over-cap field, emit an error of the form
`{kind}.{field}: <len> chars (max <cap>, from <source-url>)` so the source of the cap is
auditable. Always cite the actual URL — never the
version of Infrahub baked into prose.

### Why this rule does not list the numbers

The reference here is the *contract* (live sources,
fetch procedure, fallback behavior), not the
*values*. Listing numbers in markdown puts the
constraints in two places — they drift, and the
silent failure mode is a wrong number in this file
that the AI propagates into a generated schema.
Always read the live spec.

For the same reason, the property tables in
[reference.md](../reference.md), the patterns in
[naming-conventions.md](./naming-conventions.md),
and the validation guide in
[validation.md](../validation.md) all carry the
regex patterns (which are stable) but do not list
length numbers. They point back to this rule.

### Incorrect

A long, helpful-looking description that paste
straight from a design doc:

```yaml
relationships:
  - name: cpe_handover_interface
    peer: DcimInterface
    kind: Attribute
    description: >-
      Port on a CSW (customer switch) where the provider's
      backbone hands traffic off to the customer's CPE. The
      picker walks SbsDevice → SbsPhysicalInterface via the
      peer's HFID; pick a CSW device (e.g. csw01.sjc2) and then
      its handover port. Non-CSW devices are rejected at submit
      by the generator's `_validate()` step.
```

At schema-load time, against any current Infrahub
(check the live cap with the procedure above):

```text
$ infrahubctl schema load schemas/
Unable to load the schema:
    Node: SbsL3VPNIntent | Relationship: cpe_handover_interface
    Port on a CSW (customer switch) where the provider's backbone hands traffic off to the customer's CPE. ...
    | Input should have at most <N> characters (string_too_long)
```

### Correct

Short, tooltip-sized `description:`. Put the
operator-facing detail in a YAML comment so it lives
in the file but doesn't fight the limit:

```yaml
relationships:
  # Picker walks SbsDevice → SbsPhysicalInterface via the
  # peer's HFID. The generator's _validate() step rejects
  # non-CSW devices at submit, so this relationship only
  # constrains the picker's *shape*, not its acceptance.
  - name: cpe_handover_interface
    peer: DcimInterface
    kind: Attribute
    description: CSW port where provider hands off to the customer CPE.
```

`description` is what shows up in the UI tooltip and
the GraphQL introspection — it should be one sentence
a user can read at a glance. Anything longer belongs
in surrounding YAML/Python comments, in
`documentation:` (a free-text URL field, currently
uncapped — confirm against the live spec), or in the
project's design docs.

### Pre-flight check

`infrahubctl schema load` is too late — by then
you've already pushed the branch. Drop this into
project CI or a pre-commit hook to catch the
violation locally. The script below uses the same
2-tier source so it stays correct across Infrahub
upgrades and runs without a server when the public
schema is reachable:

```python
# scripts/check_schema_string_limits.py
"""Validate schema YAML string lengths against the live
Infrahub schema constraints. Tier 1: public JSON Schema
at schema.infrahub.app. Tier 2: /api/openapi.json on the
INFRAHUB_ADDRESS server (when set). Skip with a clear
warning if neither is reachable — do not fall back to
hardcoded numbers."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

PUBLIC_SCHEMA_URL = "https://schema.infrahub.app/infrahub/schema/latest.json"

# (openapi_schema_name, normalized_key)
OPENAPI_SCHEMAS = (
    ("NodeSchema", "NodeSchema"),
    ("GenericSchema", "GenericSchema"),
    ("AttributeSchema-Input", "AttributeSchema"),
    ("RelationshipSchema", "RelationshipSchema"),
)

JSON_SCHEMA_NAMES = ("NodeSchema", "GenericSchema",
                     "AttributeSchema", "RelationshipSchema")


def _fetch(url: str) -> dict | None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "infrahub-skills/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        print(f"WARNING: {url} unreachable ({exc}).", file=sys.stderr)
        return None


def _merge(info: dict) -> dict:
    """Merge minLength/maxLength/pattern across anyOf branches."""
    merged: dict[str, int | str] = {}
    for c in [info] + info.get("anyOf", []):
        for k in ("minLength", "maxLength", "pattern"):
            if k in c and k not in merged:
                merged[k] = c[k]
    return merged


def load_caps() -> tuple[dict[str, dict[str, dict]] | None, str | None]:
    """Return ({SchemaName: {field: {min/max/pattern}}}, source_url) or (None, None)."""
    spec = _fetch(PUBLIC_SCHEMA_URL)
    if spec is not None:
        defs = spec.get("$defs", {})
        out = {
            name: {f: _merge(info) for f, info in defs.get(name, {}).get("properties", {}).items() if _merge(info)}
            for name in JSON_SCHEMA_NAMES
        }
        return out, PUBLIC_SCHEMA_URL

    # Tier 2: fall back to a running server per
    # connectivity-server-check.md. INFRAHUB_ADDRESS is the
    # one variable that rule exposes for the address — do not
    # invent a localhost fallback here.
    base = (os.environ.get("INFRAHUB_ADDRESS") or "").rstrip("/")
    if not base:
        return None, None
    url = f"{base}/api/openapi.json"
    spec = _fetch(url)
    if spec is None:
        return None, None
    schemas = spec.get("components", {}).get("schemas", {})
    out = {}
    for openapi_name, key in OPENAPI_SCHEMAS:
        props = schemas.get(openapi_name, {}).get("properties", {})
        out[key] = {f: _merge(info) for f, info in props.items() if _merge(info)}
    return out, url


def walk(doc: dict, file_path: str, caps: dict) -> list[str]:
    issues: list[str] = []

    def check(ref: str, obj: dict, table: dict[str, dict]) -> None:
        for field, info in table.items():
            cap = info.get("maxLength")
            if cap is None:
                continue
            value = obj.get(field)
            if isinstance(value, str) and len(value) > cap:
                issues.append(f"{ref}.{field}: {len(value)} chars (max {cap})")

    kind_to_schema = {"nodes": "NodeSchema", "generics": "GenericSchema"}
    for kind, schema_key in kind_to_schema.items():
        for node in doc.get(kind, []) or []:
            ref = f"{file_path}:{node.get('namespace', '?')}{node.get('name', '?')}"
            check(ref, node, caps[schema_key])
            for attr in node.get("attributes", []) or []:
                check(f"{ref}.{attr.get('name', '?')}", attr, caps["AttributeSchema"])
            for rel in node.get("relationships", []) or []:
                check(f"{ref}.{rel.get('name', '?')}", rel, caps["RelationshipSchema"])
    return issues


def main() -> int:
    caps, source = load_caps()
    if caps is None:
        print(
            "WARNING: Could not reach the public schema or a configured "
            "Infrahub instance. String-length validation cannot be "
            "performed for this run.",
            file=sys.stderr,
        )
        return 0
    print(f"# string-length caps resolved from {source}", file=sys.stderr)
    all_issues: list[str] = []
    for path in sys.argv[1:]:
        doc = yaml.safe_load(Path(path).read_text()) or {}
        all_issues.extend(walk(doc, path, caps))
    for line in all_issues:
        print(line)
    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.exit(main())
```

Run as
`python scripts/check_schema_string_limits.py schemas/*.yml`.

### Why this isn't enforced earlier

The schema-load validator is the Pydantic models
generated under
`backend/infrahub/core/schema/generated/`. The
public JSON Schema at
`https://schema.infrahub.app/infrahub/schema/latest.json`
mirrors the same `maxLength` / `minLength` /
`pattern` constraints — which is why this rule
prefers it as the primary source. The
`# yaml-language-server: $schema=...` comment in
every schema file points editors at the same URL,
so a properly configured IDE will warn on over-cap
strings inline. CI that runs `infrahubctl schema
check` against only naming patterns (and skips
length validation) still misses the failure mode
this rule guards against — which is why the
pre-flight script above explicitly validates
lengths.
