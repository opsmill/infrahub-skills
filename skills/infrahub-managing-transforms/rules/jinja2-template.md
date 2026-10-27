---
title: Jinja2 Transform Templates
impact: CRITICAL
tags: jinja2, template, data-variable, netutils
---

## Jinja2 Transform Templates

Impact: CRITICAL

A Jinja2 transform is a `.j2` file plus a
`jinja2_transforms` entry in `.infrahub.yml` that
binds it to a named query via a top-level `query:`
field.

### Why it matters

Unlike Python transforms — where the query name lives
on the class — Jinja2 transforms have no Python file
to bind a query to, so the binding lives in
`.infrahub.yml` itself. Omitting `query:` (a frequent
copy-paste mistake from the Python form) means the
template renders against an empty `data` variable;
every loop produces zero output and the artifact ends
up empty rather than failing loudly. Inside the
template, `data` is the raw GraphQL response, so
nested values are reached as `node.<attr>.value` (e.g.
`d.name.value`) — not `node.<attr>` — because the
response wraps every attribute in a `{value, ...}`
object.

Jinja2 transforms render a template using GraphQL
query data. No Python code needed.

### Template Structure

```jinja2
{# templates/device_config.j2 #}
{% for device in data["DcimDevice"]["edges"] %}
{% set d = device.node %}
hostname {{ d.name.value }}
!
{% for intf in d.interfaces.edges %}
interface {{ intf.node.name.value }}
  description {{ intf.node.description.value | default("") }}
  {% if intf.node.ip_addresses is defined %}
  {% for ip in intf.node.ip_addresses.edges %}
  ip address {{ ip.node.address.value }}
  {% endfor %}
  {% endif %}
{% endfor %}
{% endfor %}
```

The `data` variable contains the full GraphQL query response.

### Registration in .infrahub.yml

```yaml
queries:
  - name: device_config_query
    file_path: queries/config/device.gql

jinja2_transforms:
  - name: device_config
    query: device_config_query
    template_path: templates/device_config.j2
    description: "Generate device startup config"
```

### Jinja2 Features

- A **whitelisted** subset of standard Jinja2
  filters (the SDK only enables filters in its
  `AVAILABLE_FILTERS` list — many builtins are
  excluded; see below)
- **Netutils** filters loaded on top
  (via `netutils.utils.jinja2_convenience_function()`)
- Can import other templates from the repository
- Both dot notation (`d.name.value`) and bracket
  notation (`d["name"]["value"]`) work

### Discriminating Subtypes — Don't Trust `__typename` Alone

When the query uses a generic kind and inline
fragments to pull in subtype-specific fields:

```graphql
DcimInterface {
  edges {
    node {
      name { value }
      ... on InfraInterfaceLayer2 {
        l2_mode { value }
      }
      ... on InfraInterfaceLayer3 {
        ip_addresses { edges { node { address { value } } } }
      }
    }
  }
}
```

`__typename` on each `node` resolves to the
**concrete kind** (`InfraInterfacePhysical`,
`InfraInterfaceVirtual`, ...), never to the generic
(`InfraInterfaceLayer2`) the fragment matched on.
A template that branches on
`__typename == "InfraInterfaceLayer2"` will never
hit that branch.

Discriminate on **field presence** instead, since
the fragment populates the subtype's fields only on
matching nodes:

```jinja2
{% for edge in data["DcimInterface"]["edges"] %}
  {% set iface = edge.node %}
  {% if iface.l2_mode is defined and iface.l2_mode.value %}
  switchport mode {{ iface.l2_mode.value }}
  {% endif %}
  {% if iface.ip_addresses is defined %}
  {% for ip in iface.ip_addresses.edges %}
  ip address {{ ip.node.address.value }}
  {% endfor %}
  {% endif %}
{% endfor %}
```

Field-presence discrimination also survives schema
renames cleanly, where a hardcoded kind name does
not.

### Filter Environment — Allowlist Sandbox

The SDK builds the Jinja2 `Environment` from an
explicit `AVAILABLE_FILTERS` allowlist
(`infrahub_sdk/template/__init__.py`) plus netutils.
**Anything else — Ansible filters and several
stdlib Jinja2 filters — is not registered** and
fails at render time with `No filter named 'X'`.

| Filter you might reach for | Replacement |
| -------------------------- | ----------- |
| `regex_replace` (Ansible) | `replace` for literal, or a Python transform for real regex |
| `to_nice_yaml` / `to_yaml` (Ansible) | `yaml.dump` in a Python transform (hybrid pattern) |
| `ansible.utils.ipmath`, `ipaddr` math | netutils `ip_addition`, `ip_subtraction` |
| `ansible.utils.ipv4`, `ipv4`, `ipv6` | netutils `ipaddress_network`, `is_valid_ip`, `is_ip_within` |
| `combine`, `dict2items` (Ansible) | Python preprocessing in a hybrid transform |
| `dictsort`, `groupby`, `map`, `pprint`, `select`, `sort` (stdlib Jinja2) | Pre-shape data in a Python transform |

For anything not covered, the hybrid pattern — a
Python transform prepares the data, a Jinja2
template renders it — has the full Python stdlib
plus any package available. See
[hybrid-python-jinja2.md](./hybrid-python-jinja2.md).

### Key Rules

- The `data` variable is automatically populated with the GraphQL response
- Template path is relative to the repository root
- No Python class needed -- just the `.j2` template and `.infrahub.yml` config

Reference: [Infrahub Transform Docs](https://docs.infrahub.app)
