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

- **Identity.** What makes two of these the same object?
  What would a duplicate look like?
- **Kind or variant.** Are the variants different kinds
  that share attributes (a generic), or one kind with a
  dropdown?
- **Peers and cardinality.** Can a peer exist without
  this node? One or many on each side?
- **Value class.** Does the requester give this value,
  is it allocated from a resource pool, computed from
  other values, or imported?
- **Source of truth.** Which system is authoritative for
  this node kind? Does Infrahub write to it or read from
  it?
- **Mechanism.** Does this behavior create new nodes?
  Only then is it a generator; otherwise a computed
  attribute, a check or a transform.
- **Hierarchy.** Is there a parent and child tree
  (region, site, rack) that queries walk?

## Recommendations that rest on Infrahub defaults

Use these as the basis of a recommendation when the
user's own material gives none:

- A built-in node kind, or one from the Marketplace,
  before a custom one.
- A resource pool before code that allocates values.
- A computed attribute, a check or a transform before a
  generator, unless the behavior creates nodes.
- One generic before copies of the same attributes on
  several kinds.
