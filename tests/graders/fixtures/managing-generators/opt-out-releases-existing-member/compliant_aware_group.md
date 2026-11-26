The definition sets `execute_after_merge: false`, so the run's group is a `CoreGeneratorAwareGroup`.

```python
from infrahub_sdk.generator import InfrahubGenerator


class ServiceLegs(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        service = data["NetService"]["edges"][0]["node"]
        trunk = await self.client.create(kind="NetContainer", data={"name": "shared-trunk"})
        await trunk.save(allow_upsert=True, update_group_context=False)

        group = await self.client.get(kind="CoreGeneratorAwareGroup", name__value=self.group_name)
        await group.remove_relationships(relation_to_update="members", related_nodes=[trunk.id])

        for leg in service["legs"]["edges"]:
            segment = await self.client.create(
                kind="NetSegment",
                data={"name": leg["node"]["name"]["value"], "parent": trunk.id},
            )
            await segment.save(allow_upsert=True)
```
