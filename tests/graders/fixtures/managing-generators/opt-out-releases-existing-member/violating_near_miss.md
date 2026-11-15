```python
from infrahub_sdk.generator import InfrahubGenerator


class ServiceLegs(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        service = data["NetService"]["edges"][0]["node"]
        trunk = await self.client.create(kind="NetContainer", data={"name": "shared-trunk"})
        await trunk.save(allow_upsert=True, update_group_context=False)
        # Drops stale legs from the trunk; does not touch the generator group.
        stale = [c for c in trunk.children.peer_ids if c not in service["leg_ids"]]
        await trunk.remove_relationships(relation_to_update="children", related_nodes=stale)
        for leg in service["legs"]["edges"]:
            segment = await self.client.create(
                kind="NetSegment",
                data={"name": leg["node"]["name"]["value"], "parent": trunk.id},
            )
            await segment.save(allow_upsert=True)
```
