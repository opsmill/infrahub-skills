# Concept Map

Dependency-ordered curriculum. Enter wherever probing says the learner
is; prerequisites say what to backfill first. Probe questions are
starting points; adapt wording, keep intent. Doc anchors verified
against docs.infrahub.app on 2026-09-09.

| # | Concept | Prerequisites | Probe intent | Exercise spec | Verify via | Tier | Doc anchor | Graduation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | foundations | none | prior source-of-truth tools; git familiarity | predict what happens to data on two branches | conceptual | 1 | <https://docs.infrahub.app/overview> | none |
| 2 | schema | foundations | data modeling background; has read a schema file? | extend the learner's schema with one node or relationship | schema YAML | 2 | <https://docs.infrahub.app/schema/overview> | infrahub-managing-schemas |
| 3 | objects | schema | YAML fluency; created data by API before? | write one object file for an existing kind | object YAML | 2 | <https://docs.infrahub.app/objects/overview> | infrahub-managing-objects |
| 4 | graphql | schema | queried an API before? REST vs GraphQL? | write a query answering a question about their data | GraphQL query | 1 | <https://docs.infrahub.app/development-resources/graphql/overview> | infrahub-analyzing-data |
| 5 | branches | foundations | git branching model? | diff two branches of their data | GraphQL query | 1 | <https://docs.infrahub.app/branches/overview> | none |
| 6 | repo-integration | objects | used CI? knows what a repo connector is? | write a minimal .infrahub.yml for their repo | object YAML | 2 | <https://docs.infrahub.app/git-integration/overview> | none |
| 7 | proposed-changes | branches | code review experience? | open and read a proposed change end to end | conceptual | 3 | <https://docs.infrahub.app/proposed-changes/overview> | none |
| 8 | checks | proposed-changes | written a test before? | design one check for their data quality risk | check code | 2 | <https://docs.infrahub.app/checks/overview> | infrahub-managing-checks |
| 9 | transforms | repo-integration | Jinja2 or templating? | render one config artifact from their data | transform code | 2 | <https://docs.infrahub.app/transformations/overview> | infrahub-managing-transforms |
| 10 | generators | transforms, checks | infrastructure-as-code background? | trace one generator run: input to created objects | conceptual | 1 | <https://docs.infrahub.app/generators/overview> | infrahub-managing-generators |
| 11 | menus | schema | none | sketch a sidebar grouping for their kinds | object YAML | 2 | <https://docs.infrahub.app/menu/overview> | infrahub-managing-menus |

Generic fallback examples (used only when the learner has no artifacts):
a two-node schema, `GardenSensor` and `GardenBed`, with one
relationship. Keep the fallback this small; anything richer belongs to
the learner's own files.

A concept missing from this table is not out of scope: teach it as an
off-map lesson through the shared docs fallback (see
`lesson-protocol.md`, "Off-map concepts"). Recurring off-map topics are
candidates for new rows here.
