# Question Bank

Questions to draw from, by layer, in the order the
interview asks them. Pick the one whose answer changes
the design most; skip any the user's files or earlier
answers already settle. Each question is asked in the
block layout from
[../rules/interview-one-question-recommended.md](../rules/interview-one-question-recommended.md).

## Inputs (asked once, first)

- Do you have anything that shows the design or today's
  data: diagrams, spreadsheets or inventory exports, a
  service catalog, a requirements or PoV document, or
  another tool's schema?

## Business: why the data exists

- Which decision, automation or report fails today
  because this data is wrong or missing? Name one
  incident.
- Who uses this data: a person, a pipeline that renders
  configurations, monitoring, billing?
- What is out of scope for the first version?

## Service: what is delivered

- What does a customer or internal team order? The thing
  on the order, not the devices behind it.
- What does the requester decide, and what does the
  network team derive from it?
- Which lifecycle states does a service go through, and
  who moves it from one state to the next?
- What happens to the service when a device or site is
  replaced?

## Data: the model (F1 only after a split)

Each question names the rule that decides what the
answer turns into. Read that rule before recommending an
answer, and name it in the question's basis. These links
are starting points, not the full set: the schema and
`yagni-*` rules grow over time, so list the current rule
files (SKILL.md step 6) and ask about any other decision
a rule needs from the user.

- **Identity.** What makes two of these the same object?
  What would a duplicate look like? Is it unique
  everywhere, or only within a parent (a VLAN ID within
  its group)? Rules:
  [uniqueness-constraints](../../infrahub-managing-schemas/rules/uniqueness-constraints.md),
  [display-human-friendly-id](../../infrahub-managing-schemas/rules/display-human-friendly-id.md).
- **Kind or variant.** Are the variants different kinds
  that share attributes (a generic), or one kind with a
  dropdown? Will other teams query by the shared type?
  Rules:
  [generic-membership-is-a-published-interface](../../infrahub-managing-schemas/rules/generic-membership-is-a-published-interface.md),
  [yagni-duplicate-shape-not-extracted-to-generic](../../infrahub-auditing-repo/rules/yagni-duplicate-shape-not-extracted-to-generic.md).
- **Peers and cardinality.** Can a peer exist without
  this node? One or many on each side? Rules:
  [relationship-component-parent](../../infrahub-managing-schemas/rules/relationship-component-parent.md),
  [relationship-cardinality-consequences](../../infrahub-managing-schemas/rules/relationship-cardinality-consequences.md).
- **Deletion.** When this node is deleted, what happens
  to the nodes that hang off it: deleted with it, or
  kept? Rule:
  [relationship-on-delete](../../infrahub-managing-schemas/rules/relationship-on-delete.md).
- **Navigation.** Will queries, checks or reports walk
  this relationship from both ends (from a site to its
  devices, and from a device to its site)? Rule:
  [yagni-missing-inverse-forces-python-filter](../../infrahub-auditing-repo/rules/yagni-missing-inverse-forces-python-filter.md).
- **Store or reach.** Is a value stored on this node, or
  reached through a peer (the site of an interface
  through its device)? Rule:
  [yagni-denormalized-vs-indirect-relationship](../../infrahub-auditing-repo/rules/yagni-denormalized-vs-indirect-relationship.md).
- **Value class.** Does the requester give this value,
  is it allocated from a resource pool, computed from
  other values, or imported? Rules:
  [attribute-computed-jinja2](../../infrahub-managing-schemas/rules/attribute-computed-jinja2.md),
  [yagni-imperative-allocation-vs-resource-pool](../../infrahub-auditing-repo/rules/yagni-imperative-allocation-vs-resource-pool.md).
- **Same on every branch.** Must this value be the same
  on every branch, like a serial number or an asset tag?
  Rule:
  [attribute-branch-agnostic](../../infrahub-managing-schemas/rules/attribute-branch-agnostic.md).
- **Shared defaults.** Do many objects start from the
  same settings, like every device of one model? Is that
  a starting shape copied once, or values kept in step
  later? Rules:
  [extension-object-template](../../infrahub-managing-schemas/rules/extension-object-template.md),
  [extension-object-profile](../../infrahub-managing-schemas/rules/extension-object-profile.md),
  [yagni-template-profile-confusion](../../infrahub-auditing-repo/rules/yagni-template-profile-confusion.md).
- **Source of truth.** Which system is authoritative for
  this node kind? Does Infrahub write to it or read from
  it?
- **Mechanism.** Does this behavior create or maintain
  other nodes from a design: create them, update their
  attributes or peers, or remove them? Then it is a
  generator. A value derived on the same node is a
  computed attribute, a pass or fail rule is a check,
  and a rendered output is a transform. A rule the
  schema can enforce, such as uniqueness, is a schema
  constraint, not a check
  ([yagni-python-validator-vs-schema-constraint](../../infrahub-auditing-repo/rules/yagni-python-validator-vs-schema-constraint.md)).
  Then ask what the mechanism needs: which node kind
  drives it, what it produces, and when it runs. For a
  generator, what happens to what it created when the
  driving object is deleted; for a transform, who
  consumes the output. The building skill's own rules
  hold the rest (SKILL.md step 6).
- **Hierarchy.** Is there a parent and child tree
  (region, site, rack) that queries walk? Rule:
  [hierarchy-setup](../../infrahub-managing-schemas/rules/hierarchy-setup.md).

## Recommendations that rest on Infrahub defaults

Use these as the basis of a recommendation when the
user's own material gives none:

- A built-in node kind, or one from the Marketplace,
  before a custom one
  ([yagni-reuse-existing-marketplace-schema](../../infrahub-auditing-repo/rules/yagni-reuse-existing-marketplace-schema.md)).
- The closest reference design's pattern before a new
  one ([reference-designs.md](reference-designs.md)).
- A resource pool before code that allocates values.
- A computed attribute, a check or a transform before a
  generator, unless the behavior creates or maintains
  other nodes.
- One generic before copies of the same attributes on
  several kinds.
