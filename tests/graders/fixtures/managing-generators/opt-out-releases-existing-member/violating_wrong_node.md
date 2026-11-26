Removes a segment the run still tracks, not the trunk it opted out.

```python
from infrahub_sdk.generator import InfrahubGenerator


class ServiceLegs(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        service = data["NetService"]["edges"][0]["node"]
        trunk = await self.client.create(kind="NetContainer", data={"name": "shared-trunk"})
        await trunk.save(allow_upsert=True, update_group_context=False)

        group = await self.client.group_context.get_group()
        if group:
            await group.remove_relationships(relation_to_update="members", related_nodes=[segment.id])

        for leg in service["legs"]["edges"]:
            segment = await self.client.create(
                kind="NetSegment",
                data={"name": leg["node"]["name"]["value"], "parent": trunk.id},
            )
            await segment.save(allow_upsert=True)
```
