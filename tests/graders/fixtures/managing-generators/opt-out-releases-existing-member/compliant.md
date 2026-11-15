The trunk is shared by every service, so no run may own it. Earlier runs
already saved it normally, so it is a member of each service's group:
remove it from this run's group before cleanup reads the group.

```python
from infrahub_sdk.generator import InfrahubGenerator


class ServiceLegs(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        service = data["NetService"]["edges"][0]["node"]
        trunk = await self.client.create(kind="NetContainer", data={"name": "shared-trunk"})
        await trunk.save(allow_upsert=True, update_group_context=False)

        group = await self.client.group_context.get_group()
        if group and trunk.id in group.members.peer_ids:
            await group.remove_relationships(relation_to_update="members", related_nodes=[trunk.id])

        for leg in service["legs"]["edges"]:
            segment = await self.client.create(
                kind="NetSegment",
                data={"name": leg["node"]["name"]["value"], "parent": trunk.id},
            )
            await segment.save(allow_upsert=True)
```
