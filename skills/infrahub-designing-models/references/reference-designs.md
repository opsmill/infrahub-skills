# Reference Designs

OpsMill repositories that model a complete use case. Use
the closest one as a worked example: follow its pattern
for the service and its node kinds, and say what differs.
Do not copy schema YAML out of them. Reusable schemas
come from the Marketplace
([../../infrahub-common/marketplace-reference.md](../../infrahub-common/marketplace-reference.md)).

The `Name` column is what the brief's `Closest:` line
names.

| Name | Use it when the request is about | Main node kinds | Service objects |
| ---- | -------------------------------- | --------------- | --------------- |
| `infrahub-demo-dc` | Data center fabrics built from designs, with firewall policy, load balancers and routing | Location (region to rack), Dcim, Ipam, Topology (DataCenter), Security, Loadbalancer, Routing | NetworkSegment, VirtualFabric, VIP, BGPPeering |
| `infrahub-demo-service-catalog` | Connectivity services a customer orders from a catalog, delivered over circuits | Location (country, metro, site, rack), Dcim (Device, Circuit, CircuitContract), Ipam (Prefix, VLAN), Organization (Provider) | DedicatedInternet |
| `infrahub-solution-ai-dc` | AI or GPU fabrics generated from a few inputs, with multi-tenant EVPN/VXLAN overlays | Network (Fabric, Pod, Device, Link), Location (Hall, Rack), Ipam | Tenant, Vrf, Segment, ServerService |
| `infrahub-demo-sp` | Service provider MPLS backbones with L3VPN or SD-WAN services | Location (Region, Site), Dcim, Ipam (VRF, RouteTarget), Topology (MplsBackbone), Mpls, Routing | L3Vpn, L3VpnSite, Sdwan, SdwanSite |
| `infrahub-demo-otn` | Optical transport: fiber spans, ROADMs, wavelengths, diversity | Otn (Site, Roadm, Amplifier, Transponder, FiberSpan, OpticalPath, DiversityGroup) | Otn Service (a wavelength) |
| `infrahub-demo-reachability-check` | Rules about what must or must not reach what, checked on every proposed change | Topology (ReachabilityRule, ReachabilityConstraint) | none |

Each lives at `https://github.com/opsmill/<Name>`.
Checked against each repository's schema files on
2026-10-11.

## Finding newer designs

OpsMill publishes new demos and solutions over time, so
this table can lag. When you have network access, list
the organisation's active ones:

```bash
gh repo list opsmill --limit 300 --no-archived --json name,description \
  --jq '.[] | select(.name | test("^infrahub-(demo|solution)-")) | "\(.name): \(.description)"'
```

Run it once. A repository that is not in the table but
fits the use case better can be the reference design:
read its README and schema files first, and name it in
the brief by its full URL,
`https://github.com/opsmill/<name>`. When the command
fails or does not return promptly, use the table and do
not retry.

The documentation index, `https://docs.infrahub.app/llms.txt`,
also lists OpsMill reference designs and solutions with
their pages. When you read it for this design (SKILL.md
step 6), check it for a design that fits better than the
table, and name that design by its repository's full URL.

## Searching for reuse

SKILL.md step 5 runs these once each, after the scope
check.

1. **The Marketplace.** Read the catalog whole, not by
   keyword: `infrahubctl marketplace list --json` and
   `infrahubctl marketplace list --collections --json`
   (see `../../infrahub-common/marketplace-reference.md`).
   Match it against each node kind the design needs (a
   site, a VLAN, a circuit), not against the project's
   name, and run `infrahubctl marketplace show` on at
   most three candidates to see their generics. Record
   the result in the brief's `Marketplace:` line. A
   command that fails or does not return promptly is not
   retried: write `Marketplace: not searched` with the
   reason, keep it as an open item, and go on.
2. **Newer demos.** List them as "Finding newer designs"
   above describes.

## How to use it

- Pick the row whose use case matches the business and
  service answers, not the one with the most matching
  words.
- Base the draft sketch's guesses on its node kinds and
  its service objects where they fit, and record each
  as a recommendation with this design as the basis.
- When no row fits, say so: `Closest: none`, with the
  reason. A wrong reference design is worse than none.
