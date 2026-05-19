---
title: MDI Icon Reference
impact: HIGH
tags: icons, mdi, material-design
---

## MDI Icon Reference

Impact: HIGH

Icons use the Material Design Icons (MDI) library
with `mdi:` prefix.

### Common Infrastructure Icons

| Icon                   | Use For                  |
| ---------------------- | ------------------------ |
| `mdi:server`           | Servers, generic devices |
| `mdi:switch`           | Network switches         |
| `mdi:router-network`   | Routers                  |
| `mdi:power-socket`     | PDUs                     |
| `mdi:battery-charging` | UPS                      |
| `mdi:factory`          | Manufacturers, buildings |
| `mdi:earth`            | Regions                  |
| `mdi:office-building`  | Sites                    |
| `mdi:door`             | Rooms                    |
| `mdi:map-marker`       | Locations (generic)      |
| `mdi:cog`              | Settings, types, config  |
| `mdi:package-variant`  | Device types             |
| `mdi:chip`             | Platforms                |
| `mdi:expansion-card`   | Modules, cards           |
| `mdi:ethernet`         | Interfaces               |
| `mdi:camera`           | Cameras                  |
| `mdi:snowflake`        | Chillers, cooling        |
| `mdi:laser-pointer`    | Lasers                   |
| `mdi:tray`             | Shelves                  |
| `mdi:serial-port`      | Serial servers           |
| `mdi:shield-lock`      | Security                 |
| `mdi:ip-network`       | IP/Network               |

### Browse All Icons

Full library: <https://pictogrammers.com/library/mdi/>

### Usage

```yaml
- namespace: Dcim
  name: Servers
  label: Servers
  kind: DcimServer
  icon: mdi:server          # No quotes needed
  # icon: "mdi:server"     # Quotes also work
```

Reference:
[Material Design Icons](https://pictogrammers.com/library/mdi/)
