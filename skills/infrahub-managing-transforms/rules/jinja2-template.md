---
title: Jinja2 Transform Templates
impact: CRITICAL
tags: jinja2, template, data-variable, netutils
---

## Jinja2 Transform Templates

**Impact:** CRITICAL

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

- Standard Jinja2 filters and syntax
- **Netutils** filters available
  (via `netutils.utils.jinja2_convenience_function()`)
- Can import other templates from the repository
- Both dot notation (`d.name.value`) and bracket
  notation (`d["name"]["value"]`) work

### Key Rules

- The `data` variable is automatically populated with the GraphQL response
- Template path is relative to the repository root
- No Python class needed -- just the `.j2` template and `.infrahub.yml` config

Reference: [Infrahub Transform Docs](https://docs.infrahub.app)
